"""Bounded LLM nomination of order-free concepts over committed memory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Mapping

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.concepts import AtomicConceptStore, ConceptState
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.prompt_boundary import DATA_BOUNDARY_INSTRUCTION, render_inert_data


CONCEPT_NOMINATION_REQUEST_SCHEMA = "artifact://concept-nomination-request@1"
CONCEPT_NOMINATION_SCHEMA = "artifact://concept-nomination@1"
CONCEPT_NOMINATION_CAPABILITY = "concept.nominate-from-memory@1"
_SIGNATURE_FIELDS = (
    "characteristics",
    "relations",
    "functions",
    "constraints",
    "exclusions",
    "examples",
    "counterexamples",
)


class ConceptNominationDecision(str, Enum):
    PROPOSE = "PROPOSE"
    NO_CONCEPT = "NO_CONCEPT"


@dataclass(frozen=True)
class ConceptNomination:
    decision: ConceptNominationDecision
    scope: str
    objective: str
    canonical_name: str | None
    aliases: tuple[str, ...]
    crystal_ids: tuple[str, ...]
    parent_concept_ids: tuple[str, ...]
    signature: Mapping[str, tuple[str, ...]]
    rationale: str
    authority: str = "UNVALIDATED_CONCEPT_NOMINATION"


@dataclass(frozen=True)
class LlmConceptNominationOperation:
    temperature: float = 0.1
    max_tokens: int = 2_000

    def __post_init__(self) -> None:
        if not 0 <= self.temperature <= 2:
            raise ValueError("Concept nomination temperature is invalid")
        if self.max_tokens < 1:
            raise ValueError("Concept nomination max_tokens must be positive")

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Concept nomination request is required")
        _validate_request(request)
        response = context.invoke(
            "llm.generate",
            messages=build_concept_nomination_messages(request),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("llm.generate returned no concept nomination")
        proposed = _extract_json_object(content)
        return {"nomination": _anchor_nomination(request, proposed, response)}


def build_concept_nomination_request(
    memory: AtomicDiamondLearningMemory,
    concept_store: AtomicConceptStore,
    *,
    scope: str,
    objective: str,
    crystal_ids: tuple[str, ...] | None = None,
) -> Artifact:
    if not scope.strip() or not objective.strip():
        raise ValueError("Concept nomination scope and objective are required")
    active = {
        item.crystal_id: item
        for item in memory.crystals(
            scope=scope,
            policy=CrystalRetrievalPolicy.ACTIVE,
        )
    }
    requested = tuple(dict.fromkeys(
        crystal_ids if crystal_ids is not None else tuple(active)
    ))
    if len(requested) < 2:
        raise ValueError("Concept nomination requires at least two active crystals")
    missing = sorted(set(requested) - set(active))
    if missing:
        raise ValueError(
            f"Concept nomination references unavailable crystals: {missing}"
        )
    possible_parents = tuple(
        item for item in concept_store.latest_records()
        if item.scope == scope
        and item.state in {ConceptState.VALIDATED, ConceptState.CRYSTALLIZED}
    )
    return Artifact(
        CONCEPT_NOMINATION_REQUEST_SCHEMA,
        {
            "scope": scope,
            "objective": objective,
            "crystals": [
                {
                    "crystal_id": active[item].crystal_id,
                    "content": active[item].content,
                    "state": active[item].state.value,
                    "provenance": list(active[item].provenance),
                }
                for item in requested
            ],
            "possible_parents": [
                {
                    "concept_id": item.concept_id,
                    "version_ref": item.version_ref,
                    "canonical_name": item.canonical_name,
                    "aliases": list(item.aliases),
                }
                for item in possible_parents
            ],
            "authority": "CONCEPT_NOMINATION_REQUEST_ONLY",
        },
        provenance=tuple(requested),
    )


def decode_concept_nomination(artifact: Artifact) -> ConceptNomination:
    if artifact.schema != CONCEPT_NOMINATION_SCHEMA:
        raise ValueError("Unknown concept nomination schema")
    value = artifact.payload
    decision = ConceptNominationDecision(_text(value, "decision"))
    raw_signature = value.get("signature")
    if not isinstance(raw_signature, Mapping):
        raise TypeError("Concept nomination signature must be an object")
    signature = {
        field: _text_tuple(raw_signature, field)
        for field in _SIGNATURE_FIELDS
    }
    name = value.get("canonical_name")
    if name is not None and not isinstance(name, str):
        raise TypeError("Concept nomination name must be text or null")
    return ConceptNomination(
        decision=decision,
        scope=_text(value, "scope"),
        objective=_text(value, "objective"),
        canonical_name=name.strip() if isinstance(name, str) else None,
        aliases=_text_tuple(value, "aliases"),
        crystal_ids=_text_tuple(value, "crystal_ids"),
        parent_concept_ids=_text_tuple(value, "parent_concept_ids"),
        signature=signature,
        rationale=_text(value, "rationale"),
        authority=_text(value, "authority"),
    )


def concept_nomination_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="concept.nominate-from-memory",
        version=1,
        intent=(
            "Nominate or refuse one order-free concept over committed active "
            "crystals; nomination grants no validation authority."
        ),
        requirement=CapabilityRequirement(
            capability=CONCEPT_NOMINATION_CAPABILITY,
            input_name="request",
            input_schema=CONCEPT_NOMINATION_REQUEST_SCHEMA,
            output_name="nomination",
            output_schema=CONCEPT_NOMINATION_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def concept_nomination_manifest(
    required_permissions: tuple[str, ...],
) -> ModuleManifest:
    return ModuleManifest(
        module_id="local-llm.concept-nomination",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="concept.nominate-from-memory",
            version="1.0.0",
            capabilities=(CONCEPT_NOMINATION_CAPABILITY,),
            inputs={"request": CONCEPT_NOMINATION_REQUEST_SCHEMA},
            outputs={"nomination": CONCEPT_NOMINATION_SCHEMA},
            effects=("llm.generate",),
            permissions=required_permissions,
            failure_modes=(
                "MODEL_UNAVAILABLE",
                "MALFORMED_NOMINATION",
                "INVENTED_MEMORY_REFERENCE",
            ),
            idempotency="NOT_SAFE_RETRY",
            determinism="STOCHASTIC",
        ),),
    )


def register_concept_nomination_provider(
    registry: ModuleRegistry,
    *,
    required_permissions: tuple[str, ...],
    operation: LlmConceptNominationOperation | None = None,
) -> None:
    manifest = concept_nomination_manifest(required_permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:bounded-concept-nomination",),
        ),
    )
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Concept nomination provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: (
            operation or LlmConceptNominationOperation()
        )},
    )


def build_concept_nomination_messages(
    request: Mapping[str, Any],
) -> list[dict[str, str]]:
    bounded = _plain({
            "scope": request["scope"],
            "objective": request["objective"],
            "crystals": request["crystals"],
            "possible_parents": request["possible_parents"],
        })
    return [
        {
            "role": "system",
            "content": (
                "You nominate concepts; you do not validate memory. Return one "
                "JSON object only. Use decision PROPOSE only when at least two "
                "supplied crystals support one bounded intensional concept; "
                "otherwise use NO_CONCEPT. Orders are contextual and must not "
                "appear in the concept. Never invent crystal or parent IDs. "
                "For PROPOSE return canonical_name, aliases, crystal_ids, "
                "parent_concept_ids, rationale, and signature with arrays for "
                + ", ".join(_SIGNATURE_FIELDS)
                + ". For NO_CONCEPT return a rationale and empty/null fields. "
                + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data("concept_inputs", bounded),
        },
    ]


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("authority") != "CONCEPT_NOMINATION_REQUEST_ONLY":
        raise PermissionError("Concept nomination request authority was altered")
    _text(request, "scope")
    _text(request, "objective")
    crystals = request.get("crystals")
    parents = request.get("possible_parents")
    if not isinstance(crystals, (list, tuple)) or len(crystals) < 2:
        raise ValueError("Concept nomination requires bounded crystal inputs")
    if not isinstance(parents, (list, tuple)):
        raise TypeError("Concept nomination parent inputs must be a sequence")
    ids = [_text(item, "crystal_id") for item in crystals if isinstance(item, Mapping)]
    if len(ids) != len(crystals) or len(set(ids)) != len(ids):
        raise ValueError("Concept nomination crystal inputs are invalid")


def _anchor_nomination(
    request: Mapping[str, Any],
    proposed: Mapping[str, Any],
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    decision = ConceptNominationDecision(_text(proposed, "decision"))
    available_crystals = {
        _text(item, "crystal_id")
        for item in request["crystals"]
    }
    available_parents = {
        _text(item, "concept_id")
        for item in request["possible_parents"]
    }
    rationale = _text(proposed, "rationale")
    if decision is ConceptNominationDecision.NO_CONCEPT:
        return {
            "decision": decision.value,
            "scope": request["scope"],
            "objective": request["objective"],
            "canonical_name": None,
            "aliases": [],
            "crystal_ids": [],
            "parent_concept_ids": [],
            "signature": {field: [] for field in _SIGNATURE_FIELDS},
            "rationale": rationale,
            "authority": "UNVALIDATED_CONCEPT_NOMINATION",
            "model": response.get("model"),
        }

    name = _text(proposed, "canonical_name")
    aliases = _optional_text_tuple(proposed, "aliases")
    if name.casefold() in {item.casefold() for item in aliases}:
        raise ValueError("Canonical concept name is repeated as an alias")
    crystal_ids = _optional_text_tuple(proposed, "crystal_ids")
    parent_ids = _optional_text_tuple(proposed, "parent_concept_ids")
    if len(crystal_ids) < 2:
        raise ValueError("A proposed concept requires two distinct crystal IDs")
    invented_crystals = sorted(set(crystal_ids) - available_crystals)
    invented_parents = sorted(set(parent_ids) - available_parents)
    if invented_crystals:
        raise ValueError(
            f"Concept nomination invented crystal IDs: {invented_crystals}"
        )
    if invented_parents:
        raise ValueError(
            f"Concept nomination invented parent IDs: {invented_parents}"
        )
    raw_signature = proposed.get("signature")
    if not isinstance(raw_signature, Mapping):
        raise TypeError("Proposed concept signature must be an object")
    signature = {
        field: list(_optional_text_tuple(raw_signature, field))
        for field in _SIGNATURE_FIELDS
    }
    if not any(signature[field] for field in _SIGNATURE_FIELDS[:5]):
        raise ValueError("Proposed concept lacks an intensional signature")
    return {
        "decision": decision.value,
        "scope": request["scope"],
        "objective": request["objective"],
        "canonical_name": name,
        "aliases": list(aliases),
        "crystal_ids": list(crystal_ids),
        "parent_concept_ids": list(parent_ids),
        "signature": signature,
        "rationale": rationale,
        "authority": "UNVALIDATED_CONCEPT_NOMINATION",
        "model": response.get("model"),
    }


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
        raise TypeError("Concept nomination response must be an object")
    return value


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be a sequence")
    return _clean_text_tuple(raw, key)


def _optional_text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key, ())
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be a sequence")
    return _clean_text_tuple(raw, key)


def _clean_text_tuple(raw: Any, key: str) -> tuple[str, ...]:
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError(f"{key} contains invalid text")
    return tuple(dict.fromkeys(item.strip() for item in raw))


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value
