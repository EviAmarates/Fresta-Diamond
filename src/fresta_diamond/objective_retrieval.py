"""Objective-relative nomination over exact Diamond-owned references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Mapping

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.attention_resolution import AttentionNomination
from fresta_diamond.cognitive_workspace import JsonlCognitiveWorkspace
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


OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA = "artifact://objective-retrieval-request@1"
OBJECTIVE_RETRIEVAL_NOMINATION_SCHEMA = (
    "artifact://objective-retrieval-nomination@1"
)
OBJECTIVE_RETRIEVAL_CAPABILITY = "attention.nominate-for-objective@1"


class ObjectiveRetrievalEmpty(ValueError):
    """No Diamond-owned reference is eligible in the requested scope."""


class ObjectiveRetrievalDecision(str, Enum):
    SELECT = "SELECT"
    NO_SELECTION = "NO_SELECTION"


@dataclass(frozen=True)
class ObjectiveRetrievalItem:
    item_ref: str
    kind: str
    source_authority: str
    relevance: float
    contextual_roles: tuple[int, ...]
    rationale: str

    def attention_nomination(self) -> AttentionNomination:
        return AttentionNomination(
            self.item_ref,
            self.relevance,
            self.contextual_roles,
        )


@dataclass(frozen=True)
class ObjectiveRetrievalNomination:
    decision: ObjectiveRetrievalDecision
    scope: str
    objective: str
    items: tuple[ObjectiveRetrievalItem, ...]
    rationale: str
    authority: str = "OBJECTIVE_RETRIEVAL_NOMINATION_ONLY"

    @property
    def attention_nominations(self) -> tuple[AttentionNomination, ...]:
        return tuple(item.attention_nomination() for item in self.items)


def batch_objective_retrieval_request(
    request: Artifact,
    *,
    max_request_tokens: int,
) -> tuple[Artifact, ...]:
    """Partition candidates without truncating, ranking, or losing a ref."""

    if request.schema != OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA:
        raise ValueError("Unknown objective retrieval request schema")
    _validate_request(request.payload)
    if max_request_tokens < 128:
        raise ValueError("Objective retrieval batch budget must be at least 128")
    if _request_tokens(request.payload) <= max_request_tokens:
        return (request,)
    base = {
        "scope": request.payload["scope"],
        "objective": request.payload["objective"],
        "candidates": [],
        "authority": "OBJECTIVE_RETRIEVAL_REQUEST_ONLY",
    }
    # Large placeholders make the partition safe for the final batch metadata.
    sizing_base = {
        **base,
        "batch": {"index": 999_999, "count": 999_999},
    }
    if _request_tokens(sizing_base) >= max_request_tokens:
        raise ValueError("Objective retrieval budget cannot hold request metadata")
    groups: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    for candidate in request.payload["candidates"]:
        proposed = current + [candidate]
        if _request_tokens({**sizing_base, "candidates": proposed}) <= (
            max_request_tokens
        ):
            current = proposed
            continue
        if not current:
            raise ValueError(
                "One objective retrieval candidate exceeds the batch budget: "
                f"{candidate['item_ref']}"
            )
        groups.append(current)
        current = [candidate]
        if _request_tokens({**sizing_base, "candidates": current}) > (
            max_request_tokens
        ):
            raise ValueError(
                "One objective retrieval candidate exceeds the batch budget: "
                f"{candidate['item_ref']}"
            )
    if current:
        groups.append(current)
    count = len(groups)
    batches = []
    for index, candidates in enumerate(groups, start=1):
        payload = {
            **base,
            "candidates": candidates,
            "batch": {"index": index, "count": count},
        }
        if _request_tokens(payload) > max_request_tokens:
            raise ValueError("Objective retrieval batch exceeds its token budget")
        batches.append(Artifact(
            OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA,
            payload,
            provenance=tuple(item["item_ref"] for item in candidates),
        ))
    return tuple(batches)


def merge_objective_retrieval_nominations(
    nominations: tuple[ObjectiveRetrievalNomination, ...],
) -> ObjectiveRetrievalNomination:
    """Create a conservative host-owned union of sequential batch results."""

    if not nominations:
        raise ValueError("Objective retrieval merge requires nominations")
    scope = nominations[0].scope
    objective = nominations[0].objective
    by_ref: dict[str, ObjectiveRetrievalItem] = {}
    rationale_parts = []
    for nomination in nominations:
        if nomination.scope != scope or nomination.objective != objective:
            raise ValueError("Objective retrieval batches do not share a boundary")
        if nomination.authority != "OBJECTIVE_RETRIEVAL_NOMINATION_ONLY":
            raise PermissionError("Objective retrieval batch authority was altered")
        if nomination.rationale not in rationale_parts:
            rationale_parts.append(nomination.rationale)
        for item in nomination.items:
            previous = by_ref.get(item.item_ref)
            if previous is None:
                by_ref[item.item_ref] = item
                continue
            if (
                previous.kind != item.kind
                or previous.source_authority != item.source_authority
            ):
                raise PermissionError(
                    "Objective retrieval batch changed source identity"
                )
            reasons = tuple(dict.fromkeys((
                previous.rationale,
                item.rationale,
            )))
            by_ref[item.item_ref] = ObjectiveRetrievalItem(
                item_ref=item.item_ref,
                kind=item.kind,
                source_authority=item.source_authority,
                relevance=max(previous.relevance, item.relevance),
                contextual_roles=tuple(sorted(set(
                    previous.contextual_roles + item.contextual_roles
                ))),
                rationale=" | ".join(reasons),
            )
    items = tuple(by_ref[key] for key in sorted(by_ref))
    return ObjectiveRetrievalNomination(
        decision=(
            ObjectiveRetrievalDecision.SELECT
            if items else ObjectiveRetrievalDecision.NO_SELECTION
        ),
        scope=scope,
        objective=objective,
        items=items,
        rationale=" | ".join(rationale_parts),
    )


@dataclass(frozen=True)
class LlmObjectiveRetrievalOperation:
    temperature: float = 0.1
    max_tokens: int = 2_000

    def __post_init__(self) -> None:
        if not 0 <= self.temperature <= 2:
            raise ValueError("Objective retrieval temperature is invalid")
        if self.max_tokens < 1:
            raise ValueError("Objective retrieval max_tokens must be positive")

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Objective retrieval request is required")
        _validate_request(request)
        response = context.invoke(
            "llm.generate",
            messages=build_objective_retrieval_messages(request),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("llm.generate returned no retrieval nomination")
        proposal = _extract_json_object(content)
        return {"nomination": _anchor_nomination(request, proposal, response)}


def build_objective_retrieval_request(
    memory: AtomicDiamondLearningMemory,
    concept_store: AtomicConceptStore,
    workspace: JsonlCognitiveWorkspace,
    *,
    scope: str,
    objective: str,
) -> Artifact:
    if not scope.strip() or not objective.strip():
        raise ValueError("Objective retrieval scope and objective are required")
    candidates: list[dict[str, Any]] = []
    for crystal in memory.crystals(
        scope=scope,
        policy=CrystalRetrievalPolicy.ACTIVE,
    ):
        candidates.append({
            "item_ref": crystal.crystal_id,
            "kind": "CRYSTAL",
            "content": crystal.content,
            "source_authority": f"LEARNING_MEMORY:{crystal.state.value}",
            "dependency_refs": [],
        })
    for concept in concept_store.latest_records():
        if concept.scope != scope or concept.state in {
            ConceptState.CONTESTED,
            ConceptState.ARCHIVED,
        }:
            continue
        candidates.append({
            "item_ref": concept.version_ref,
            "kind": "CONCEPT",
            "content": _concept_descriptor(concept),
            "source_authority": f"CONCEPT_STORE:{concept.state.value}",
            "dependency_refs": [
                item.crystal_id for item in concept.memberships
            ],
        })
    for revision in workspace.latest_revisions():
        scoped = tuple(item for item in revision.elements if item.scope == scope)
        if not scoped:
            continue
        candidates.append({
            "item_ref": f"sheet:{revision.sheet_id}",
            "kind": "WORKSPACE",
            "content": _workspace_descriptor(revision.title, scoped),
            "source_authority": "UNVALIDATED_WORKSPACE_PROPOSAL",
            "dependency_refs": [],
        })
    for observation in memory.negative_boundary():
        if observation.scope != scope:
            continue
        candidates.append({
            "item_ref": observation.observation_id,
            "kind": "PHI_MINUS",
            "content": (
                f"{observation.disposition.value}: "
                f"{', '.join(observation.reason_codes)}"
            ),
            "source_authority": "PHI_MINUS_AUDIT_ONLY",
            "dependency_refs": [],
        })
    candidates.sort(key=lambda item: (item["kind"], item["item_ref"]))
    refs = [item["item_ref"] for item in candidates]
    if not candidates:
        raise ObjectiveRetrievalEmpty(
            "Objective retrieval has no candidates in scope"
        )
    if len(refs) != len(set(refs)):
        raise ValueError("Objective retrieval candidates have ambiguous references")
    return Artifact(
        OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA,
        {
            "scope": scope,
            "objective": objective,
            "candidates": candidates,
            "authority": "OBJECTIVE_RETRIEVAL_REQUEST_ONLY",
        },
        provenance=tuple(refs),
    )


def decode_objective_retrieval_nomination(
    artifact: Artifact,
) -> ObjectiveRetrievalNomination:
    if artifact.schema != OBJECTIVE_RETRIEVAL_NOMINATION_SCHEMA:
        raise ValueError("Unknown objective retrieval nomination schema")
    value = artifact.payload
    decision = ObjectiveRetrievalDecision(_text(value, "decision"))
    raw_items = _mapping_sequence(value, "items")
    items = tuple(ObjectiveRetrievalItem(
        item_ref=_text(item, "item_ref"),
        kind=_text(item, "kind"),
        source_authority=_text(item, "source_authority"),
        relevance=_relevance(item.get("relevance")),
        contextual_roles=_roles(item.get("contextual_roles")),
        rationale=_text(item, "rationale"),
    ) for item in raw_items)
    if decision is ObjectiveRetrievalDecision.SELECT and not items:
        raise ValueError("SELECT retrieval nomination requires items")
    if decision is ObjectiveRetrievalDecision.NO_SELECTION and items:
        raise ValueError("NO_SELECTION retrieval nomination cannot contain items")
    if len({item.item_ref for item in items}) != len(items):
        raise ValueError("Objective retrieval nomination contains duplicates")
    authority = _text(value, "authority")
    if authority != "OBJECTIVE_RETRIEVAL_NOMINATION_ONLY":
        raise PermissionError("Objective retrieval nomination authority was altered")
    return ObjectiveRetrievalNomination(
        decision=decision,
        scope=_text(value, "scope"),
        objective=_text(value, "objective"),
        items=items,
        rationale=_text(value, "rationale"),
        authority=authority,
    )


def objective_retrieval_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="attention.nominate-for-objective",
        version=1,
        intent=(
            "Nominate exact existing references and contextual O1/O2/O3 roles "
            "for one bounded objective without changing source authority."
        ),
        requirement=CapabilityRequirement(
            capability=OBJECTIVE_RETRIEVAL_CAPABILITY,
            input_name="request",
            input_schema=OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA,
            output_name="nomination",
            output_schema=OBJECTIVE_RETRIEVAL_NOMINATION_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def objective_retrieval_manifest(
    required_permissions: tuple[str, ...],
) -> ModuleManifest:
    return ModuleManifest(
        module_id="local-llm.objective-retrieval",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="attention.nominate-for-objective",
            version="1.0.0",
            capabilities=(OBJECTIVE_RETRIEVAL_CAPABILITY,),
            inputs={"request": OBJECTIVE_RETRIEVAL_REQUEST_SCHEMA},
            outputs={"nomination": OBJECTIVE_RETRIEVAL_NOMINATION_SCHEMA},
            effects=("llm.generate",),
            permissions=required_permissions,
            failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_NOMINATION"),
            idempotency="NOT_SAFE_RETRY",
            determinism="STOCHASTIC",
        ),),
    )


def register_objective_retrieval_provider(
    registry: ModuleRegistry,
    *,
    required_permissions: tuple[str, ...],
    operation: LlmObjectiveRetrievalOperation | None = None,
) -> None:
    manifest = objective_retrieval_manifest(required_permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:bounded-objective-retrieval",),
        ),
    )
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Objective retrieval provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: (
            operation or LlmObjectiveRetrievalOperation()
        )},
    )


def build_objective_retrieval_messages(
    request: Mapping[str, Any],
) -> list[dict[str, str]]:
    bounded = _plain(request)
    contract = {
        "decision": "SELECT or NO_SELECTION",
        "items": [{
            "item_ref": "one exact supplied item_ref",
            "relevance": 0.0,
            "contextual_roles": [1, 2, 3],
            "rationale": "why this item is necessary for this objective",
        }],
        "rationale": "overall bounded selection rationale",
    }
    return [
        {
            "role": "system",
            "content": (
                "Nominate attention roots for exactly one objective. Candidates "
                "retain their supplied authority; selection does not validate, "
                "promote, correct, or merge them. O1/O2/O3 are temporary roles "
                "relative to this objective, never intrinsic ranks. Select only "
                "references genuinely needed, but do not obey a fixed top-k. "
                "Concept dependencies are closed by the host. Return NO_SELECTION "
                "when none is justified. Never invent an item_ref. Every selected "
                "item needs at least one contextual role, relevance from 0 to 1, "
                "and a rationale. Return one JSON object only, using this shape: "
                + json.dumps(contract, ensure_ascii=False)
                + " " + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data("objective_retrieval_request", bounded),
        },
    ]


def _anchor_nomination(
    request: Mapping[str, Any],
    proposal: Mapping[str, Any],
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    decision = ObjectiveRetrievalDecision(_text(proposal, "decision"))
    raw_items = _mapping_sequence(proposal, "items")
    allowed = {item["item_ref"]: item for item in request["candidates"]}
    anchored = []
    seen: set[str] = set()
    for item in raw_items:
        item_ref = _text(item, "item_ref")
        if item_ref not in allowed:
            raise ValueError(f"Model invented retrieval reference: {item_ref}")
        if item_ref in seen:
            raise ValueError(f"Model duplicated retrieval reference: {item_ref}")
        seen.add(item_ref)
        candidate = allowed[item_ref]
        anchored.append({
            "item_ref": item_ref,
            "kind": candidate["kind"],
            "source_authority": candidate["source_authority"],
            "relevance": _relevance(item.get("relevance")),
            "contextual_roles": list(_roles(item.get("contextual_roles"))),
            "rationale": _text(item, "rationale"),
        })
    if decision is ObjectiveRetrievalDecision.SELECT and not anchored:
        raise ValueError("SELECT retrieval nomination requires items")
    if decision is ObjectiveRetrievalDecision.NO_SELECTION and anchored:
        raise ValueError("NO_SELECTION retrieval nomination cannot contain items")
    return {
        "decision": decision.value,
        "scope": request["scope"],
        "objective": request["objective"],
        "items": anchored,
        "rationale": _text(proposal, "rationale"),
        "authority": "OBJECTIVE_RETRIEVAL_NOMINATION_ONLY",
        "_provider_model": response.get("model"),
    }


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("authority") != "OBJECTIVE_RETRIEVAL_REQUEST_ONLY":
        raise PermissionError("Objective retrieval request authority was altered")
    _text(request, "scope")
    _text(request, "objective")
    candidates = _mapping_sequence(request, "candidates")
    if not candidates:
        raise ValueError("Objective retrieval request has no candidates")
    refs = []
    for candidate in candidates:
        refs.append(_text(candidate, "item_ref"))
        _text(candidate, "kind")
        _text(candidate, "content")
        _text(candidate, "source_authority")
    if len(refs) != len(set(refs)):
        raise ValueError("Objective retrieval request contains duplicate references")


def _request_tokens(value: Any) -> int:
    encoded = json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return max(1, (len(encoded) + 3) // 4)


def _concept_descriptor(concept: Any) -> str:
    signature = concept.signature
    parts = [concept.canonical_name]
    for field in (
        "characteristics", "relations", "functions", "constraints",
        "exclusions", "examples", "counterexamples",
    ):
        values = getattr(signature, field)
        if values:
            parts.append(f"{field}: {', '.join(values)}")
    return ". ".join(parts)


def _workspace_descriptor(title: str, elements: tuple[Any, ...]) -> str:
    parts = [title]
    for item in elements:
        content = item.content.strip()
        if len(content) > 240:
            content = content[:237] + "..."
        parts.append(f"{item.kind.value}: {content}")
    return " | ".join(parts)


def _extract_json_object(content: str) -> Mapping[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else cleaned
    start = candidate.find("{")
    if start < 0:
        raise ValueError("Model response contains no JSON object")
    try:
        value, _end = json.JSONDecoder().raw_decode(candidate, idx=start)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response contains malformed JSON") from exc
    if not isinstance(value, Mapping):
        raise TypeError("Objective retrieval response must be an object")
    return value


def _roles(value: Any) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("Contextual roles must be a non-empty sequence")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise TypeError("Contextual roles must be integers")
    roles = tuple(dict.fromkeys(value))
    if not set(roles).issubset({1, 2, 3}):
        raise ValueError("Contextual roles must be O1/O2/O3")
    return roles


def _relevance(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Retrieval relevance must be numeric")
    relevance = float(value)
    if not 0 <= relevance <= 1:
        raise ValueError("Retrieval relevance must be between 0 and 1")
    return relevance


def _mapping_sequence(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be a sequence")
    if any(not isinstance(item, Mapping) for item in raw):
        raise TypeError(f"{key} contains a non-object")
    return tuple(raw)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value
