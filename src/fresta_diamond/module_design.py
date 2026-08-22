"""Non-executable autonomous module suggestions below the controller boundary."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4

from fresta_diamond.anti_entropy import (
    ModuleAdmissionPolicy,
    ModuleDiscoveryEvidence,
    ModuleSource,
)
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
    Remainder,
    RemainderKind,
)
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.prompt_boundary import DATA_BOUNDARY_INSTRUCTION, render_inert_data


MODULE_SUGGESTION_REQUEST_SCHEMA = "artifact://module-suggestion-request@1"
MODULE_SUGGESTION_SCHEMA = "artifact://module-suggestion@1"
MODULE_SUGGESTION_CAPABILITY = "module.suggest-design@1"
MODULE_SUGGESTION_AUTHORITY = "UNVALIDATED_MODULE_DESIGN"
MODULE_LAYER = "BELOW_CONTROLLER"


class ModuleSuggestionDecision(str, Enum):
    PROPOSE_MODULE = "PROPOSE_MODULE"
    NO_NEW_MODULE = "NO_NEW_MODULE"
    REJECTED_PROPOSAL = "REJECTED_PROPOSAL"


@dataclass(frozen=True)
class ModuleOperationDesign:
    module_id: str
    operation_id: str
    capability: str
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    determinism: str = "DETERMINISTIC"

    def __post_init__(self) -> None:
        if not all((
            self.module_id.strip(),
            self.operation_id.strip(),
            self.capability.strip(),
        )):
            raise ValueError("Module operation design identifiers are required")
        if not self.outputs:
            raise ValueError("Module operation design requires an output")
        object.__setattr__(self, "inputs", dict(self.inputs))
        object.__setattr__(self, "outputs", dict(self.outputs))


@dataclass(frozen=True)
class ModuleSuggestion:
    suggestion_id: str
    decision: ModuleSuggestionDecision
    objective: str
    required_capability: str
    layer: str
    rationale: str
    exact_provider_refs: tuple[str, ...]
    reuse_candidate_refs: tuple[str, ...]
    remainder_refs: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    allowed_permissions: tuple[str, ...]
    o1_required_outcomes: tuple[str, ...]
    o2_composition_analysis: tuple[str, ...]
    o2_dependencies: tuple[str, ...]
    o3_constraints: tuple[str, ...]
    o3_completion_conditions: tuple[str, ...]
    operation: ModuleOperationDesign | None = None
    admission_precheck_passed: bool | None = None
    policy_remainders: tuple[Remainder, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    authority: str = MODULE_SUGGESTION_AUTHORITY

    def __post_init__(self) -> None:
        if not all((
            self.suggestion_id.strip(),
            self.objective.strip(),
            self.required_capability.strip(),
            self.rationale.strip(),
            self.created_at.strip(),
        )):
            raise ValueError("Module suggestion fields are required")
        if self.layer != MODULE_LAYER:
            raise PermissionError("Module suggestions must remain below controller")
        if self.authority != MODULE_SUGGESTION_AUTHORITY:
            raise PermissionError("Module suggestion cannot grant executable authority")
        if self.decision is ModuleSuggestionDecision.PROPOSE_MODULE:
            if self.operation is None or self.admission_precheck_passed is False:
                raise ValueError("Proposed module requires an operation design")
            if not all((
                self.o1_required_outcomes,
                self.o2_composition_analysis,
                self.o3_constraints,
                self.o3_completion_conditions,
            )):
                raise ValueError("Proposed module lacks an O1/O2/O3 design boundary")
        elif self.operation is not None and self.decision is ModuleSuggestionDecision.NO_NEW_MODULE:
            raise ValueError("NO_NEW_MODULE cannot contain an operation design")
        if self.decision is ModuleSuggestionDecision.REJECTED_PROPOSAL:
            if not self.policy_remainders or self.admission_precheck_passed is not False:
                raise ValueError("Rejected proposal requires policy remainders")


@dataclass(frozen=True)
class StoredModuleSuggestion:
    suggestion: ModuleSuggestion
    content_hash: str
    path: Path


class ModuleSuggestionArchiveError(RuntimeError):
    """A module suggestion could not be persisted or verified."""


class AtomicModuleSuggestionArchive:
    """File-per-suggestion immutable archive; stores no executable code."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def save(self, suggestion: ModuleSuggestion) -> StoredModuleSuggestion:
        body = encode_module_suggestion(suggestion)
        content_hash = _hash_body(body)
        record = {**body, "content_hash": content_hash}
        filename = sha256(suggestion.suggestion_id.encode("utf-8")).hexdigest() + ".json"
        path = self._root / filename
        pending = self._root / f"{filename}.pending"
        if path.exists() or pending.exists():
            raise ModuleSuggestionArchiveError("Module suggestion already exists")
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(_canonical_json(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, path)
        except OSError as exc:
            raise ModuleSuggestionArchiveError(
                f"Could not persist module suggestion: {type(exc).__name__}"
            ) from exc
        return StoredModuleSuggestion(suggestion, content_hash, path)

    def load(self, suggestion_id: str) -> StoredModuleSuggestion:
        filename = sha256(suggestion_id.encode("utf-8")).hexdigest() + ".json"
        path = self._root / filename
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise TypeError("suggestion record is not an object")
            content_hash = record.pop("content_hash")
            if not isinstance(content_hash, str) or content_hash != _hash_body(record):
                raise ModuleSuggestionArchiveError("Module suggestion hash mismatch")
            suggestion = decode_module_suggestion(record)
            if suggestion.suggestion_id != suggestion_id:
                raise ModuleSuggestionArchiveError("Module suggestion identity mismatch")
            return StoredModuleSuggestion(suggestion, content_hash, path)
        except ModuleSuggestionArchiveError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ModuleSuggestionArchiveError(
                f"Malformed module suggestion: {type(exc).__name__}"
            ) from exc

    def suggestions(self) -> tuple[StoredModuleSuggestion, ...]:
        if not self._root.exists():
            return ()
        values = []
        for path in sorted(self._root.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                suggestion_id = record["suggestion_id"]
                if not isinstance(suggestion_id, str):
                    raise TypeError("suggestion_id is invalid")
                values.append(self.load(suggestion_id))
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ModuleSuggestionArchiveError(
                    f"Could not enumerate module suggestions: {type(exc).__name__}"
                ) from exc
        return tuple(sorted(values, key=lambda item: item.suggestion.created_at))


@dataclass(frozen=True)
class LlmModuleSuggestionOperation:
    temperature: float = 0.1
    max_tokens: int = 2_000

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Module suggestion request is required")
        _validate_request(request)
        response = context.invoke(
            "llm.generate",
            messages=build_module_suggestion_messages(request),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("llm.generate returned no module suggestion")
        proposed = _extract_json_object(content)
        return {"suggestion": _anchor_suggestion(request, proposed, response)}


def build_module_suggestion_request(
    manifests: tuple[ModuleManifest, ...],
    *,
    objective: str,
    required_capability: str,
    input_schemas: Mapping[str, str],
    output_schema: str,
    remainders: tuple[Remainder, ...],
    occurrence_count: int = 1,
    allowed_effects: tuple[str, ...] = (),
    allowed_permissions: tuple[str, ...] = (),
) -> Artifact:
    if not objective.strip() or not required_capability.strip() or not output_schema.strip():
        raise ValueError("Module gap objective, capability, and output schema are required")
    if occurrence_count < 1:
        raise ValueError("Module gap occurrence count must be positive")
    if not remainders or not any(
        item.kind is RemainderKind.MISSING_CAPABILITY for item in remainders
    ):
        raise ValueError("Module suggestion requires observed missing-capability evidence")
    operations = tuple(
        (manifest, operation)
        for manifest in manifests
        for operation in manifest.operations
    )
    exact = tuple(
        f"{manifest.module_id}:{operation.operation_id}"
        for manifest, operation in operations
        if required_capability in operation.capabilities
    )
    reuse = tuple(
        f"{manifest.module_id}:{operation.operation_id}"
        for manifest, operation in operations
        if output_schema in operation.outputs.values()
        and required_capability not in operation.capabilities
    )
    return Artifact(
        MODULE_SUGGESTION_REQUEST_SCHEMA,
        {
            "objective": objective,
            "required_capability": required_capability,
            "input_schemas": dict(input_schemas),
            "output_schema": output_schema,
            "occurrence_count": occurrence_count,
            "allowed_effects": tuple(allowed_effects),
            "allowed_permissions": tuple(allowed_permissions),
            "exact_provider_refs": exact,
            "reuse_candidate_refs": reuse,
            "remainders": tuple({
                "remainder_id": item.remainder_id,
                "kind": item.kind.value,
                "description": item.description,
                "required_for": item.required_for,
                "suggested_capability": item.suggested_capability,
            } for item in remainders),
            "inventory": tuple({
                "module_id": manifest.module_id,
                "operation_id": operation.operation_id,
                "capabilities": operation.capabilities,
                "inputs": dict(operation.inputs),
                "outputs": dict(operation.outputs),
                "effects": operation.effects,
            } for manifest, operation in operations),
            "layer": MODULE_LAYER,
            "authority": "MODULE_GAP_REQUEST_ONLY",
        },
        provenance=tuple(item.remainder_id for item in remainders),
    )


def deterministic_existing_provider_suggestion(
    request: Artifact,
    *,
    suggestion_id: str | None = None,
) -> ModuleSuggestion | None:
    exact = _text_tuple(request.payload, "exact_provider_refs")
    if not exact:
        return None
    return ModuleSuggestion(
        suggestion_id=suggestion_id or f"module-suggestion:{uuid4()}",
        decision=ModuleSuggestionDecision.NO_NEW_MODULE,
        objective=_text(request.payload, "objective"),
        required_capability=_text(request.payload, "required_capability"),
        layer=MODULE_LAYER,
        rationale=(
            "An exact provider already exists; reuse must be attempted before "
            "creating another module."
        ),
        exact_provider_refs=exact,
        reuse_candidate_refs=_text_tuple(request.payload, "reuse_candidate_refs"),
        remainder_refs=tuple(request.provenance),
        allowed_effects=_text_tuple(request.payload, "allowed_effects"),
        allowed_permissions=_text_tuple(request.payload, "allowed_permissions"),
        o1_required_outcomes=(),
        o2_composition_analysis=("Exact capability provider found.",),
        o2_dependencies=exact,
        o3_constraints=("Do not create a duplicate provider.",),
        o3_completion_conditions=("Existing provider is selected or rejected with evidence.",),
        admission_precheck_passed=None,
    )


def validate_module_suggestion(
    suggestion: ModuleSuggestion,
    *,
    policy: ModuleAdmissionPolicy | None = None,
) -> ModuleSuggestion:
    if suggestion.decision is not ModuleSuggestionDecision.PROPOSE_MODULE:
        return suggestion
    operation = suggestion.operation
    if operation is None:
        raise ValueError("Proposed module operation is missing")
    manifest = ModuleManifest(
        module_id=operation.module_id,
        version="0.0.1-proposal",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id=operation.operation_id,
            version="0.0.1-proposal",
            capabilities=(operation.capability,),
            inputs=operation.inputs,
            outputs=operation.outputs,
            effects=operation.effects,
            permissions=operation.permissions,
            failure_modes=operation.failure_modes,
            determinism=operation.determinism,
        ),),
    )
    report = (policy or ModuleAdmissionPolicy()).evaluate(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=(f"module-suggestion:{suggestion.suggestion_id}",),
        ),
    )
    boundary_remainders = list(report.remainders)
    for label, requested, allowed in (
        ("effect", operation.effects, suggestion.allowed_effects),
        ("permission", operation.permissions, suggestion.allowed_permissions),
    ):
        for value in sorted(set(requested) - set(allowed)):
            boundary_remainders.append(Remainder(
                kind=RemainderKind.PERMISSION_DENIED,
                description=(
                    f"Proposed {label} {value!r} exceeds the host-supplied "
                    "module-design boundary."
                ),
                required_for=f"module-suggestion:{suggestion.suggestion_id}",
                resolvable=True,
            ))
    if report.admitted and not boundary_remainders:
        return replace(suggestion, admission_precheck_passed=True)
    return replace(
        suggestion,
        decision=ModuleSuggestionDecision.REJECTED_PROPOSAL,
        admission_precheck_passed=False,
        policy_remainders=tuple(boundary_remainders),
        rationale=(
            suggestion.rationale
            + " Host anti-entropy precheck rejected the proposed boundary."
        ),
    )


def decode_module_suggestion_artifact(artifact: Artifact) -> ModuleSuggestion:
    if artifact.schema != MODULE_SUGGESTION_SCHEMA:
        raise ValueError("Unknown module suggestion schema")
    suggestion = decode_module_suggestion(artifact.payload)
    return validate_module_suggestion(suggestion)


def module_suggestion_blueprint(permissions: tuple[str, ...]) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="module.suggest-design",
        version=1,
        intent=(
            "Refuse or propose one non-executable module design below the "
            "controller after checking existing capability reuse."
        ),
        requirement=CapabilityRequirement(
            capability=MODULE_SUGGESTION_CAPABILITY,
            input_name="request",
            input_schema=MODULE_SUGGESTION_REQUEST_SCHEMA,
            output_name="suggestion",
            output_schema=MODULE_SUGGESTION_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=permissions,
    )


def module_suggestion_manifest(permissions: tuple[str, ...]) -> ModuleManifest:
    return ModuleManifest(
        module_id="local-llm.module-suggestion",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="module.suggest-design",
            version="1.0.0",
            capabilities=(MODULE_SUGGESTION_CAPABILITY,),
            inputs={"request": MODULE_SUGGESTION_REQUEST_SCHEMA},
            outputs={"suggestion": MODULE_SUGGESTION_SCHEMA},
            effects=("llm.generate",),
            permissions=permissions,
            failure_modes=(
                "MODEL_UNAVAILABLE",
                "MALFORMED_DESIGN",
                "POLICY_BOUNDARY_REJECTED",
            ),
            idempotency="NOT_SAFE_RETRY",
            determinism="STOCHASTIC",
        ),),
    )


def register_module_suggestion_provider(
    registry: ModuleRegistry,
    *,
    permissions: tuple[str, ...],
    operation: LlmModuleSuggestionOperation | None = None,
) -> None:
    manifest = module_suggestion_manifest(permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:bounded-module-suggestion",),
        ),
    )
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Module suggestion provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: (
            operation or LlmModuleSuggestionOperation()
        )},
    )


def build_module_suggestion_messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
    bounded = {
        key: _plain(request[key])
        for key in (
            "objective",
            "required_capability",
            "input_schemas",
            "output_schema",
            "occurrence_count",
            "allowed_effects",
            "allowed_permissions",
            "exact_provider_refs",
            "reuse_candidate_refs",
            "remainders",
            "inventory",
            "layer",
        )
    }
    return [
        {
            "role": "system",
            "content": (
                "You may only suggest a non-executable module below the controller. "
                "Prefer reuse or composition. Return JSON only. Decision must be "
                "NO_NEW_MODULE or PROPOSE_MODULE. Never propose changes to kernel, "
                "controller, validators, Gatekeepers, EffectBroker, journal history, "
                "or direct/promoted memory. For either decision return rationale, "
                "o1_required_outcomes, o2_composition_analysis, o2_dependencies, "
                "o3_constraints, and o3_completion_conditions. For PROPOSE_MODULE "
                "also return module_id, operation_id, effects, permissions, "
                "failure_modes, and determinism. The host fixes capability and schemas."
                " Effects and permissions must be subsets of the trusted allowed_effects "
                "and allowed_permissions arrays; if they are empty, return empty arrays."
                " Narrative O1/O2/O3 fields must be arrays of non-empty strings. "
                "Use empty arrays only when decision is NO_NEW_MODULE and the field "
                "does not apply. " + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data("module_gap", bounded),
        },
    ]


def encode_module_suggestion(value: ModuleSuggestion) -> dict[str, Any]:
    operation = value.operation
    return {
        "schema": MODULE_SUGGESTION_SCHEMA,
        "suggestion_id": value.suggestion_id,
        "decision": value.decision.value,
        "objective": value.objective,
        "required_capability": value.required_capability,
        "layer": value.layer,
        "rationale": value.rationale,
        "exact_provider_refs": list(value.exact_provider_refs),
        "reuse_candidate_refs": list(value.reuse_candidate_refs),
        "remainder_refs": list(value.remainder_refs),
        "allowed_effects": list(value.allowed_effects),
        "allowed_permissions": list(value.allowed_permissions),
        "o1_required_outcomes": list(value.o1_required_outcomes),
        "o2_composition_analysis": list(value.o2_composition_analysis),
        "o2_dependencies": list(value.o2_dependencies),
        "o3_constraints": list(value.o3_constraints),
        "o3_completion_conditions": list(value.o3_completion_conditions),
        "operation": None if operation is None else {
            "module_id": operation.module_id,
            "operation_id": operation.operation_id,
            "capability": operation.capability,
            "inputs": dict(operation.inputs),
            "outputs": dict(operation.outputs),
            "effects": list(operation.effects),
            "permissions": list(operation.permissions),
            "failure_modes": list(operation.failure_modes),
            "determinism": operation.determinism,
        },
        "admission_precheck_passed": value.admission_precheck_passed,
        "policy_remainders": [_encode_remainder(item) for item in value.policy_remainders],
        "created_at": value.created_at,
        "authority": value.authority,
    }


def decode_module_suggestion(value: Mapping[str, Any]) -> ModuleSuggestion:
    if value.get("schema") != MODULE_SUGGESTION_SCHEMA:
        raise ValueError("Unsupported module suggestion schema")
    raw_operation = value.get("operation")
    operation = None
    if raw_operation is not None:
        if not isinstance(raw_operation, Mapping):
            raise TypeError("Module operation design must be an object")
        operation = ModuleOperationDesign(
            module_id=_text(raw_operation, "module_id"),
            operation_id=_text(raw_operation, "operation_id"),
            capability=_text(raw_operation, "capability"),
            inputs=_text_mapping(raw_operation, "inputs"),
            outputs=_text_mapping(raw_operation, "outputs"),
            effects=_text_tuple(raw_operation, "effects"),
            permissions=_text_tuple(raw_operation, "permissions"),
            failure_modes=_text_tuple(raw_operation, "failure_modes"),
            determinism=_text(raw_operation, "determinism"),
        )
    precheck = value.get("admission_precheck_passed")
    if precheck is not None and not isinstance(precheck, bool):
        raise TypeError("Admission precheck must be boolean or null")
    return ModuleSuggestion(
        suggestion_id=_text(value, "suggestion_id"),
        decision=ModuleSuggestionDecision(_text(value, "decision")),
        objective=_text(value, "objective"),
        required_capability=_text(value, "required_capability"),
        layer=_text(value, "layer"),
        rationale=_text(value, "rationale"),
        exact_provider_refs=_text_tuple(value, "exact_provider_refs"),
        reuse_candidate_refs=_text_tuple(value, "reuse_candidate_refs"),
        remainder_refs=_text_tuple(value, "remainder_refs"),
        allowed_effects=_text_tuple(value, "allowed_effects"),
        allowed_permissions=_text_tuple(value, "allowed_permissions"),
        o1_required_outcomes=_text_tuple(value, "o1_required_outcomes"),
        o2_composition_analysis=_text_tuple(value, "o2_composition_analysis"),
        o2_dependencies=_text_tuple(value, "o2_dependencies"),
        o3_constraints=_text_tuple(value, "o3_constraints"),
        o3_completion_conditions=_text_tuple(value, "o3_completion_conditions"),
        operation=operation,
        admission_precheck_passed=precheck,
        policy_remainders=tuple(
            _decode_remainder(item)
            for item in _mapping_tuple(value, "policy_remainders")
        ),
        created_at=_text(value, "created_at"),
        authority=_text(value, "authority"),
    )


def _anchor_suggestion(
    request: Mapping[str, Any],
    proposed: Mapping[str, Any],
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    decision = ModuleSuggestionDecision(_text(proposed, "decision"))
    if decision is ModuleSuggestionDecision.REJECTED_PROPOSAL:
        raise ValueError("The model cannot issue host policy decisions")
    o1 = _semantic_text_tuple(proposed, "o1_required_outcomes")
    o2_analysis = _semantic_text_tuple(proposed, "o2_composition_analysis")
    o2_dependencies = _semantic_text_tuple(proposed, "o2_dependencies")
    o3_constraints = _semantic_text_tuple(proposed, "o3_constraints")
    o3_completion = _semantic_text_tuple(proposed, "o3_completion_conditions")
    raw_rationale = proposed.get("rationale")
    rationale = (
        raw_rationale.strip()
        if isinstance(raw_rationale, str) and raw_rationale.strip()
        else (
            o2_analysis[0]
            if o2_analysis else "No new module was justified by the supplied gap."
        )
    )
    common = {
        "schema": MODULE_SUGGESTION_SCHEMA,
        "suggestion_id": f"module-suggestion:{uuid4()}",
        "decision": decision.value,
        "objective": request["objective"],
        "required_capability": request["required_capability"],
        "layer": MODULE_LAYER,
        "rationale": rationale,
        "exact_provider_refs": list(request["exact_provider_refs"]),
        "reuse_candidate_refs": list(request["reuse_candidate_refs"]),
        "remainder_refs": [item["remainder_id"] for item in request["remainders"]],
        "allowed_effects": list(request["allowed_effects"]),
        "allowed_permissions": list(request["allowed_permissions"]),
        "o1_required_outcomes": list(o1),
        "o2_composition_analysis": list(o2_analysis),
        "o2_dependencies": list(o2_dependencies),
        "o3_constraints": list(o3_constraints),
        "o3_completion_conditions": list(o3_completion),
        "policy_remainders": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": MODULE_SUGGESTION_AUTHORITY,
        "model": response.get("model"),
    }
    if decision is ModuleSuggestionDecision.NO_NEW_MODULE:
        return {**common, "operation": None, "admission_precheck_passed": None}
    module_id = _text(proposed, "module_id")
    operation_id = _text(proposed, "operation_id")
    return {
        **common,
        "operation": {
            "module_id": module_id,
            "operation_id": operation_id,
            "capability": request["required_capability"],
            "inputs": dict(request["input_schemas"]),
            "outputs": {"result": request["output_schema"]},
            "effects": list(_empty_or_text_tuple(proposed, "effects")),
            "permissions": list(_empty_or_text_tuple(proposed, "permissions")),
            "failure_modes": list(_semantic_text_tuple(proposed, "failure_modes")),
            "determinism": _text(proposed, "determinism"),
        },
        "admission_precheck_passed": None,
    }


def _validate_request(value: Mapping[str, Any]) -> None:
    if value.get("authority") != "MODULE_GAP_REQUEST_ONLY":
        raise PermissionError("Module suggestion request authority was altered")
    if _text(value, "layer") != MODULE_LAYER:
        raise PermissionError("Module suggestion escaped below-controller layer")
    _text(value, "objective")
    _text(value, "required_capability")
    _text(value, "output_schema")
    if _text_tuple(value, "exact_provider_refs"):
        raise ValueError("Exact providers must be handled deterministically")
    _mapping_tuple(value, "remainders")
    _mapping_tuple(value, "inventory")


def _extract_json_object(content: str) -> Mapping[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    candidate = fenced.group(1) if fenced else cleaned
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model response contains no JSON object")
        value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, Mapping):
        raise TypeError("Module suggestion response must be an object")
    return value


def _encode_remainder(value: Remainder) -> dict[str, Any]:
    return {
        "remainder_id": value.remainder_id,
        "kind": value.kind.value,
        "description": value.description,
        "required_for": value.required_for,
        "resolvable": value.resolvable,
        "suggested_capability": value.suggested_capability,
        "status": value.status,
    }


def _decode_remainder(value: Mapping[str, Any]) -> Remainder:
    return Remainder(
        remainder_id=_text(value, "remainder_id"),
        kind=RemainderKind(_text(value, "kind")),
        description=_text(value, "description"),
        required_for=_text(value, "required_for"),
        resolvable=value.get("resolvable"),
        suggested_capability=value.get("suggested_capability"),
        status=_text(value, "status"),
    )


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key, ())
    if not isinstance(raw, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in raw
    ):
        raise TypeError(f"{key} must be a sequence of non-empty text")
    return tuple(dict.fromkeys(item.strip() for item in raw))


def _semantic_text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key, ())
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in raw
    ):
        raise TypeError(f"{key} must be text or a sequence of non-empty text")
    return tuple(dict.fromkeys(item.strip() for item in raw))


def _empty_or_text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key, ())
    if isinstance(raw, str):
        normalized = " ".join(raw.casefold().strip().split())
        if normalized in {"", "none", "no", "n/a", "[]", "no effects", "no permissions"}:
            return ()
        raise TypeError(f"{key} text cannot declare an operational boundary")
    return _text_tuple(value, key)


def _text_mapping(value: Mapping[str, Any], key: str) -> dict[str, str]:
    raw = value.get(key)
    if not isinstance(raw, Mapping) or any(
        not isinstance(name, str) or not name.strip()
        or not isinstance(schema, str) or not schema.strip()
        for name, schema in raw.items()
    ):
        raise TypeError(f"{key} must be a text mapping")
    return {name.strip(): schema.strip() for name, schema in raw.items()}


def _mapping_tuple(value: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key, ())
    if not isinstance(raw, (list, tuple)) or any(
        not isinstance(item, Mapping) for item in raw
    ):
        raise TypeError(f"{key} must be a sequence of objects")
    return tuple(raw)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
