"""Bounded evidence proposal for deterministic concept validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping
from uuid import uuid4

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptRecord,
    ConceptState,
    DerivationContribution,
    DerivationSeal,
    DerivationSource,
    DerivationSourceKind,
    concept_targets,
)
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.epistemology import EPISTEMIC_EVIDENCE_SCHEMA
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)
from fresta_diamond.ontology import AnalysisDepth, STRUCTURAL_EVIDENCE_SCHEMA
from fresta_diamond.llm_evidence import (
    compile_structural_selection,
    source_authority_classification_catalog,
    structural_assembly_catalog,
)
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.prompt_boundary import DATA_BOUNDARY_INSTRUCTION, render_inert_data


CONCEPT_EVIDENCE_REQUEST_SCHEMA = "artifact://concept-evidence-request@1"
CONCEPT_SEALS_SCHEMA = "artifact://concept-derivation-seals@1"
CONCEPT_STRUCTURAL_CAPABILITY = "concept.propose-structural-evidence@1"
CONCEPT_EPISTEMIC_CAPABILITY = "concept.derive-epistemic-evidence@1"
CONCEPT_SEALS_CAPABILITY = "concept.anchor-derivation-seals@1"


@dataclass(frozen=True)
class LlmConceptStructuralOperation:
    temperature: float = 0.1
    max_tokens: int = 4_000

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Concept evidence request is required")
        _validate_request(request)
        response = context.invoke(
            "llm.generate",
            messages=build_concept_evidence_messages(request),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("llm.generate returned no concept evidence bundle")
        bundle = _extract_json_object(content)
        structural = bundle.get("structural_evidence")
        epistemic = bundle.get("epistemic_derivation")
        seals = bundle.get("derivation_seals")
        if not isinstance(structural, Mapping):
            raise ValueError("Concept bundle lacks structural_evidence")
        if not isinstance(epistemic, Mapping):
            raise ValueError("Concept bundle lacks epistemic_derivation")
        if not isinstance(seals, (list, tuple)):
            raise ValueError("Concept bundle lacks derivation_seals")
        return {"structural_evidence": _anchor_structural(
            request, structural, epistemic, seals, response
        )}


@dataclass(frozen=True)
class ConceptEpistemicOperation:
    """Derive the epistemic graph from trusted memory and model proposal."""

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        _context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        structural = inputs.get("structural_evidence")
        if not isinstance(structural, Mapping):
            raise ValueError("Concept structural evidence is required")
        request = structural.get("_trusted_concept_request")
        proposal = structural.get("_epistemic_derivation")
        if not isinstance(request, Mapping) or not isinstance(proposal, Mapping):
            raise ValueError("Concept evidence lost its trusted boundary")
        members = tuple(request["members"])
        constraints = tuple(
            _text(item, "constraint_id")
            for item in structural.get("constraints", ())
            if isinstance(item, Mapping)
        )
        claim_id = f"claim:{request['analysis_id']}:concept-fit"
        evidence_events = []
        evidence_ids = []
        for index, member in enumerate(members, start=1):
            evidence_id = f"evidence:{request['analysis_id']}:{index}"
            evidence_ids.append(evidence_id)
            evidence_events.append({
                "evidence_id": evidence_id,
                "claim_id": claim_id,
                "evidence_kind": "PREMISE",
                "stance": "SUPPORTS",
                "source_actor": "source:diamond-learning-memory",
                "source_locator": member["crystal_id"],
                "source_lineage": member["crystal_id"],
                "context_id": request["concept_ref"],
                "method": "committed-concept-membership",
                "observed_at": "time:unresolved",
                "scope": request["scope"],
            })
        return {"epistemic_evidence": {
            "analysis_id": request["analysis_id"],
            "object_ref": request["concept_ref"],
            "scope": request["scope"],
            "claims": [{
                "claim_id": claim_id,
                "content": _text(proposal, "content"),
                "subject_ref": request["concept_ref"],
                "owner_ref": "owner:diamond-concept-analysis",
                "scope": request["scope"],
                "claim_mode": "DERIVATION",
                "evidence_ids": evidence_ids,
                "premise_refs": [item["crystal_id"] for item in members],
                "applied_constraints": list(constraints),
                "derivation_direction": _optional_text(
                    proposal, "derivation_direction"
                ),
                "test_criterion": None,
                "horizon": None,
                "assumptions": _optional_text_list(proposal, "assumptions"),
                "counterexample_searches": _optional_text_list(
                    proposal, "counterexample_searches"
                ),
            }],
            "evidence_events": evidence_events,
            "_trusted_concept_request": request,
            "_seal_proposals": structural.get("_seal_proposals", ()),
        }}


@dataclass(frozen=True)
class ConceptSealsOperation:
    """Anchor seal targets and sources; invalid proposals become explicit gaps."""

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        _context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        epistemic = inputs.get("epistemic_evidence")
        if not isinstance(epistemic, Mapping):
            raise ValueError("Concept epistemic evidence is required")
        request = epistemic.get("_trusted_concept_request")
        proposals = epistemic.get("_seal_proposals")
        if not isinstance(request, Mapping) or not isinstance(
            proposals, (list, tuple)
        ):
            raise ValueError("Concept seals lost their trusted boundary")
        allowed_targets = set(request["required_targets"])
        source_kinds = _allowed_source_kinds(request)
        seals = []
        errors = []
        for index, item in enumerate(proposals, start=1):
            if not isinstance(item, Mapping):
                errors.append("Seal proposal is not an object")
                continue
            target = item.get("target_ref")
            if not isinstance(target, str) or target not in allowed_targets:
                errors.append(f"Unknown seal target: {target}")
                continue
            try:
                contribution = DerivationContribution(
                    _text(item, "contribution")
                )
            except ValueError:
                errors.append(f"Invalid contribution for {target}")
                continue
            if contribution is DerivationContribution.COUNTEREVIDENCE:
                errors.append(
                    f"Counterevidence for {target} requires a dedicated "
                    "grounded negative evidence graph"
                )
                continue
            raw_sources = item.get("source_refs")
            if not isinstance(raw_sources, (list, tuple)) or not raw_sources:
                errors.append(f"Missing seal sources for {target}")
                continue
            sources = []
            invented = []
            for source_ref in raw_sources:
                if not isinstance(source_ref, str) or source_ref not in source_kinds:
                    invented.append(str(source_ref))
                    continue
                sources.append({
                    "source_ref": source_ref,
                    "kind": source_kinds[source_ref].value,
                })
            if invented:
                errors.append(
                    f"Unavailable seal sources for {target}: {sorted(invented)}"
                )
                continue
            unique = {
                (source["kind"], source["source_ref"]): source
                for source in sources
            }
            seals.append({
                "seal_id": f"seal:{request['analysis_id']}:{index}",
                "target_ref": target,
                "contribution": contribution.value,
                "sources": list(unique.values()),
                "analysis_id": request["analysis_id"],
                "scope": request["scope"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        return {"concept_seals": {
            "analysis_id": request["analysis_id"],
            "concept_ref": request["concept_ref"],
            "scope": request["scope"],
            "seals": seals,
            "errors": errors,
            "authority": "ANCHORED_DERIVATION_PROPOSAL",
        }}


def build_concept_evidence_request(
    memory: AtomicDiamondLearningMemory,
    concept_store: AtomicConceptStore,
    concept_id: str,
    *,
    objective: str | None = None,
) -> Artifact:
    concept = concept_store.latest(concept_id)
    if concept.state is not ConceptState.CANDIDATE:
        raise ValueError("Only a concept candidate can request first validation")
    active = {
        item.crystal_id: item
        for item in memory.crystals(
            scope=concept.scope,
            policy=CrystalRetrievalPolicy.ACTIVE,
        )
    }
    member_ids = tuple(item.crystal_id for item in concept.memberships)
    missing = sorted(set(member_ids) - set(active))
    if missing:
        raise ValueError(
            f"Concept evidence references inactive memberships: {missing}"
        )
    analysis_id = f"concept-analysis:{uuid4()}"
    return Artifact(
        CONCEPT_EVIDENCE_REQUEST_SCHEMA,
        {
            "analysis_id": analysis_id,
            "concept_ref": concept.version_ref,
            "scope": concept.scope,
            "objective": objective or (
                "Evaluate whether committed memberships justify every part "
                "of this bounded concept candidate."
            ),
            "concept": {
                "concept_id": concept.concept_id,
                "canonical_name": concept.canonical_name,
                "aliases": list(concept.aliases),
                "signature": {
                    field: list(getattr(concept.signature, field))
                    for field in (
                        "characteristics", "relations", "functions",
                        "constraints", "exclusions", "examples",
                        "counterexamples",
                    )
                },
            },
            "members": [
                {
                    "crystal_id": active[item].crystal_id,
                    "content": active[item].content,
                    "state": active[item].state.value,
                    "provenance": list(active[item].provenance),
                }
                for item in member_ids
            ],
            "required_targets": list(concept_targets(concept)),
            "analysis_depth": "CONTEXTUAL",
            "authority": "CONCEPT_EVIDENCE_REQUEST_ONLY",
        },
        provenance=member_ids,
    )


def decode_concept_seals(artifact: Artifact) -> tuple[DerivationSeal, ...]:
    if artifact.schema != CONCEPT_SEALS_SCHEMA:
        raise ValueError("Unknown concept derivation seal schema")
    value = artifact.payload
    if value.get("authority") != "ANCHORED_DERIVATION_PROPOSAL":
        raise PermissionError("Concept seal authority was altered")
    raw = value.get("seals")
    if not isinstance(raw, (list, tuple)):
        raise TypeError("Concept seals must be a sequence")
    seals = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise TypeError("Concept seal must be an object")
        sources = item.get("sources")
        if not isinstance(sources, (list, tuple)):
            raise TypeError("Concept seal sources must be a sequence")
        seals.append(DerivationSeal(
            seal_id=_text(item, "seal_id"),
            target_ref=_text(item, "target_ref"),
            contribution=DerivationContribution(_text(item, "contribution")),
            sources=tuple(
                DerivationSource(
                    _text(source, "source_ref"),
                    DerivationSourceKind(_text(source, "kind")),
                )
                for source in sources if isinstance(source, Mapping)
            ),
            analysis_id=_text(item, "analysis_id"),
            scope=_text(item, "scope"),
            created_at=_text(item, "created_at"),
        ))
    if len(seals) != len(raw):
        raise TypeError("Concept seals contain malformed records")
    return tuple(seals)


def concept_evidence_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="concept.evaluate-candidate",
        version=1,
        intent=(
            "Propose bounded evidence and anchored derivation seals for one "
            "concept candidate; deterministic validators retain authority."
        ),
        requirements=(
            CapabilityRequirement(
                capability=CONCEPT_STRUCTURAL_CAPABILITY,
                input_name="request",
                input_schema=CONCEPT_EVIDENCE_REQUEST_SCHEMA,
                output_name="structural_evidence",
                output_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
            CapabilityRequirement(
                capability=CONCEPT_EPISTEMIC_CAPABILITY,
                input_name="structural_evidence",
                input_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                output_name="epistemic_evidence",
                output_schema=EPISTEMIC_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
            CapabilityRequirement(
                capability=CONCEPT_SEALS_CAPABILITY,
                input_name="epistemic_evidence",
                input_schema=EPISTEMIC_EVIDENCE_SCHEMA,
                output_name="concept_seals",
                output_schema=CONCEPT_SEALS_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def concept_evidence_manifest(
    required_permissions: tuple[str, ...],
) -> ModuleManifest:
    return ModuleManifest(
        module_id="local-llm.concept-evidence",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(
            OperationContract(
                operation_id="concept.propose-structural-evidence",
                version="1.0.0",
                capabilities=(CONCEPT_STRUCTURAL_CAPABILITY,),
                inputs={"request": CONCEPT_EVIDENCE_REQUEST_SCHEMA},
                outputs={"structural_evidence": STRUCTURAL_EVIDENCE_SCHEMA},
                effects=("llm.generate",),
                permissions=required_permissions,
                failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_EVIDENCE"),
                idempotency="NOT_SAFE_RETRY",
                determinism="STOCHASTIC",
            ),
            OperationContract(
                operation_id="concept.derive-epistemic-evidence",
                version="1.0.0",
                capabilities=(CONCEPT_EPISTEMIC_CAPABILITY,),
                inputs={"structural_evidence": STRUCTURAL_EVIDENCE_SCHEMA},
                outputs={"epistemic_evidence": EPISTEMIC_EVIDENCE_SCHEMA},
                failure_modes=("TRUSTED_BOUNDARY_MISSING",),
                determinism="DETERMINISTIC",
            ),
            OperationContract(
                operation_id="concept.anchor-derivation-seals",
                version="1.0.0",
                capabilities=(CONCEPT_SEALS_CAPABILITY,),
                inputs={"epistemic_evidence": EPISTEMIC_EVIDENCE_SCHEMA},
                outputs={"concept_seals": CONCEPT_SEALS_SCHEMA},
                failure_modes=("TRUSTED_BOUNDARY_MISSING",),
                determinism="DETERMINISTIC",
            ),
        ),
    )


def register_concept_evidence_provider(
    registry: ModuleRegistry,
    *,
    required_permissions: tuple[str, ...],
    structural: LlmConceptStructuralOperation | None = None,
) -> None:
    manifest = concept_evidence_manifest(required_permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:bounded-concept-evidence",),
        ),
    )
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Concept evidence provider was rejected")
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: (
                structural or LlmConceptStructuralOperation()
            ),
            manifest.operations[1].operation_id: ConceptEpistemicOperation(),
            manifest.operations[2].operation_id: ConceptSealsOperation(),
        },
    )


def build_concept_evidence_messages(
    request: Mapping[str, Any],
) -> list[dict[str, str]]:
    bounded = _plain({
        key: request[key]
        for key in (
            "analysis_id", "concept_ref", "scope", "objective", "concept",
            "members", "required_targets", "analysis_depth",
        )
    })
    response_contract = {
        "structural_evidence": {
            "assembly_id": "SINGLE_WITNESS_CHAIN or DEFER_STRUCTURE",
            "source_authority_id": "one exact source-authority catalog ID",
            "witness": {
                "manifestation_description": "non-empty bounded O1",
                "manifestation_provenance": [
                    "exact supplied crystal ID or provenance"
                ],
                "forward_justification": "non-empty",
                "constraint_effect": "non-empty",
                "return_witness": "non-empty",
                "constraint_description": "non-empty contextual O3",
                "selection_justification": "non-empty",
                "excluded_cost_description": "non-empty",
                "excluded_alternatives": ["at least one non-empty value"],
                "openness_necessity": "empty or omitted at contextual depth",
            },
            "advisory_model_closed": False,
        },
        "epistemic_derivation": {
            "content": "non-empty bounded derived claim",
            "derivation_direction": "non-empty premises -> constraint -> claim",
            "assumptions": [],
            "counterexample_searches": [],
        },
        "derivation_seals": [{
            "target_ref": "one exact supplied required target",
            "contribution": "DIRECT or SYNTHESIS or CORROBORATION",
            "source_refs": ["exact supplied crystal ID or provenance"],
        }],
    }
    return [
        {
            "role": "system",
            "content": (
                "Propose evidence for a concept candidate; do not validate or "
                "promote it. Return one JSON object with structural_evidence, "
                "epistemic_derivation, and derivation_seals. Structural "
                "evidence must select exactly one assembly_id from "
                + json.dumps(
                    structural_assembly_catalog(AnalysisDepth.CONTEXTUAL),
                    ensure_ascii=False,
                )
                + " and one source_authority_id from "
                + json.dumps(
                    source_authority_classification_catalog(),
                    ensure_ascii=False,
                )
                + ". Use SINGLE_WITNESS_CHAIN for one justified contextual "
                "O1/O2/O3 witness or DEFER_STRUCTURE when none exists. The "
                "host creates all graph IDs and links; use only supplied "
                "crystal IDs or provenance. epistemic_derivation "
                "requires content, derivation_direction, assumptions, and "
                "counterexample_searches. Each derivation seal requires an "
                "exact required target_ref, contribution DIRECT, SYNTHESIS, "
                "or CORROBORATION, and source_refs drawn only "
                "from supplied crystal IDs or provenance. Cover every target "
                "only when genuinely supported; omission must remain visible. "
                "Orders are contextual roles, never intrinsic concept ranks. "
                "Every field shown as an array MUST remain a JSON array, even "
                "when it contains exactly one item. Do not add prose, markdown, "
                "or alternate O1/O2/O3 keys. Use exactly this JSON shape: "
                + json.dumps(response_contract, ensure_ascii=False)
                + " " + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data("concept_candidate", bounded),
        },
    ]


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("authority") != "CONCEPT_EVIDENCE_REQUEST_ONLY":
        raise PermissionError("Concept evidence request authority was altered")
    for key in ("analysis_id", "concept_ref", "scope", "objective"):
        _text(request, key)
    if request.get("analysis_depth") != "CONTEXTUAL":
        raise ValueError("Concept validation currently requires contextual depth")
    members = request.get("members")
    targets = request.get("required_targets")
    if not isinstance(members, (list, tuple)) or len(members) < 2:
        raise ValueError("Concept evidence requires committed memberships")
    if not isinstance(targets, (list, tuple)) or not targets:
        raise ValueError("Concept evidence requires explicit targets")


def _anchor_structural(
    request: Mapping[str, Any],
    structural: Mapping[str, Any],
    epistemic: Mapping[str, Any],
    seals: Any,
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    allowed_sources = set(_allowed_source_kinds(request))
    graph = compile_structural_selection(
        structural,
        object_ref=request["concept_ref"],
        scope=request["scope"],
        depth=AnalysisDepth.CONTEXTUAL,
    )
    manifestations = []
    for item in _mapping_list(graph, "manifestations"):
        anchored = dict(item)
        provenance = item.get("provenance", ())
        if not isinstance(provenance, (list, tuple)):
            provenance = ()
        anchored["provenance"] = [
            source for source in provenance
            if isinstance(source, str) and source in allowed_sources
        ]
        anchored["object_ref"] = request["concept_ref"]
        manifestations.append(anchored)
    relations = [dict(item) for item in _mapping_list(graph, "relations")]
    for item in relations:
        item["scope"] = request["scope"]
    constraints = [
        dict(item) for item in _mapping_list(graph, "constraints")
    ]
    for item in constraints:
        item["scope"] = request["scope"]
    anchored = {
        **graph,
        "analysis_id": request["analysis_id"],
        "object_ref": request["concept_ref"],
        "scope": request["scope"],
        "analysis_depth": "CONTEXTUAL",
        "manifestations": manifestations,
        "relations": relations,
        "constraints": constraints,
        "filters": [
            dict(item) for item in _mapping_list(graph, "filters")
        ],
        "excluded_costs": [
            dict(item) for item in _mapping_list(graph, "excluded_costs")
        ],
        "groundings": [],
        "advisory_model_closed": bool(
            graph.get("advisory_model_closed", False)
        ),
        "_trusted_concept_request": _plain(request),
        "_epistemic_derivation": _plain(epistemic),
        "_seal_proposals": _plain(seals),
        "_provider_raw": response.get("content"),
        "_provider_model": response.get("model"),
    }
    return anchored


def _allowed_source_kinds(
    request: Mapping[str, Any],
) -> dict[str, DerivationSourceKind]:
    values: dict[str, DerivationSourceKind] = {}
    for member in request["members"]:
        crystal_id = member["crystal_id"]
        values[crystal_id] = DerivationSourceKind.MEMORY_CRYSTAL
        for source in member.get("provenance", ()):
            if source.startswith("document:"):
                kind = DerivationSourceKind.DOCUMENT
            elif source.startswith("workspace:"):
                kind = DerivationSourceKind.WORKSPACE
            elif source.startswith(("http://", "https://", "web:")):
                kind = DerivationSourceKind.WEB_SOURCE
            else:
                continue
            values[source] = kind
    return values


def _mapping_list(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be a sequence")
    items = tuple(item for item in raw if isinstance(item, Mapping))
    if len(items) != len(raw):
        raise TypeError(f"{key} contains a non-object")
    return items


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
        raise TypeError("Concept evidence response must be an object")
    return value


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text or null")
    return item.strip()


def _optional_text_list(value: Mapping[str, Any], key: str) -> list[str]:
    raw = value.get(key, ())
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be a sequence")
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError(f"{key} contains invalid text")
    return list(dict.fromkeys(item.strip() for item in raw))


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
