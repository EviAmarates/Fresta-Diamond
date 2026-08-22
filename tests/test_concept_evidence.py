from __future__ import annotations

import json

from fresta_diamond.concept_evidence import (
    LlmConceptStructuralOperation,
    build_concept_evidence_request,
    concept_evidence_blueprint,
    decode_concept_seals,
    register_concept_evidence_provider,
)
from fresta_diamond.contracts import ExecutionState
from fresta_diamond.concepts import ConceptState
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.epistemology import decode_epistemic_evidence_graph
from fresta_diamond.ontology import decode_structural_evidence_graph
from fresta_diamond.registry import ModuleRegistry

from .test_concept_validation import service


PERMISSIONS = ("llm.model:concept-evidence-test",)


def evidence_bundle(
    request,
    *,
    invented_source: bool = False,
    counterevidence: bool = False,
    canonical_structure: bool = False,
):
    member_ids = [item["crystal_id"] for item in request["members"]]
    source_ids = list(member_ids)
    if invented_source:
        source_ids = ["crystal:invented"]
    structural_evidence = {
            "analysis_id": "analysis:model-cannot-own-this",
            "object_ref": "concept:invented",
            "scope": "scope:invented",
            "analysis_depth": "CONTEXTUAL",
            "manifestations": [{
                "manifestation_id": "manifestation:functional-members",
                "object_ref": "concept:invented",
                "description": (
                    "The committed members manifest one bounded functional system."
                ),
                "provenance": member_ids,
            }],
            "relations": [{
                "relation_id": "relation:functional-coherence",
                "manifestation_id": "manifestation:functional-members",
                "constraint_id": "constraint:functional-coherence",
                "forward_justification": (
                    "The members jointly participate in energy transformation."
                ),
                "constraint_effect": (
                    "Only arrangements preserving the function remain."
                ),
                "return_witness": (
                    "The committed members witness the proposed concept."
                ),
                "excluded_cost_id": "cost:unrelated-collection",
                "scope": "scope:invented",
            }],
            "constraints": [{
                "constraint_id": "constraint:functional-coherence",
                "description": "Membership must preserve coherent function.",
                "scope": "scope:invented",
            }],
            "filters": [{
                "filter_id": "filter:functional-system",
                "constraint_id": "constraint:functional-coherence",
                "manifestation_id": "manifestation:functional-members",
                "excluded_cost_id": "cost:unrelated-collection",
                "selection_justification": (
                    "Selects members jointly sustaining the proposed function."
                ),
            }],
            "excluded_costs": [{
                "cost_id": "cost:unrelated-collection",
                "description": "Loss of coherent function.",
                "excluded_alternatives": ["unrelated component collections"],
            }],
            "groundings": [],
            "advisory_model_closed": True,
        }
    if canonical_structure:
        structural_evidence = {
            "assembly_id": "SINGLE_WITNESS_CHAIN",
            "source_authority_id": "ORDINARY_ATTRIBUTED_SOURCE",
            "witness": {
                "manifestation_description": (
                    "The committed members manifest one bounded functional system."
                ),
                "manifestation_provenance": member_ids,
                "forward_justification": (
                    "The members jointly participate in energy transformation."
                ),
                "constraint_effect": (
                    "Only arrangements preserving the function remain."
                ),
                "return_witness": (
                    "The committed members witness the proposed concept."
                ),
                "constraint_description": (
                    "Membership must preserve coherent function."
                ),
                "selection_justification": (
                    "Selects members jointly sustaining the proposed function."
                ),
                "excluded_cost_description": "Loss of coherent function.",
                "excluded_alternatives": ["unrelated component collections"],
            },
            "advisory_model_closed": True,
        }
    return {
        "structural_evidence": structural_evidence,
        "epistemic_derivation": {
            "content": "The committed members instantiate the candidate.",
            "derivation_direction": (
                "committed members -> constrained relation -> concept"
            ),
            "assumptions": [],
            "counterexample_searches": ["unrelated component collection"],
        },
        "derivation_seals": [
            {
                "target_ref": target,
                "contribution": (
                    "COUNTEREVIDENCE"
                    if counterevidence
                    else (
                        "DIRECT"
                        if target.startswith("membership:")
                        else "SYNTHESIS"
                    )
                ),
                "source_refs": source_ids,
            }
            for target in request["required_targets"]
        ],
    }


def execute_provider(
    tmp_path,
    *,
    invented_source: bool = False,
    counterevidence: bool = False,
    canonical_structure: bool = False,
    trailing_content: str = "",
):
    memory, store, concept, validation = service(tmp_path)
    request = build_concept_evidence_request(memory, store, concept.concept_id)
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(
                evidence_bundle(
                    request.payload,
                    invented_source=invented_source,
                    counterevidence=counterevidence,
                    canonical_structure=canonical_structure,
                )
            ) + trailing_content,
            "model": "concept-evidence-test",
        }

    registry = ModuleRegistry()
    register_concept_evidence_provider(
        registry,
        required_permissions=PERMISSIONS,
        structural=LlmConceptStructuralOperation(max_tokens=600),
    )
    result = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": adapter}),
    ).execute(
        concept_evidence_blueprint(PERMISSIONS),
        "Evaluate one concept candidate",
        {"request": request},
    )
    return memory, store, concept, validation, result, calls


def test_provider_builds_closed_evidence_with_one_model_call(tmp_path) -> None:
    _, _, concept, _, result, calls = execute_provider(tmp_path)

    assert result.execution.state is ExecutionState.COMPLETED
    assert len(calls) == 1
    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.epistemic_closed is True
    assert '"assembly_id": "SINGLE_WITNESS_CHAIN or DEFER_STRUCTURE"' in (
        calls[0]["messages"][0]["content"]
    )
    assert '"derivation_seals": [' in calls[0]["messages"][0]["content"]
    structural = result.execution.artifacts["structural_evidence"].payload
    assert structural["object_ref"] == concept.version_ref
    assert structural["scope"] == concept.scope
    assert all(
        item["object_ref"] == concept.version_ref
        for item in structural["manifestations"]
    )
    seals = decode_concept_seals(result.execution.artifacts["concept_seals"])
    assert len(seals) == len(result.execution.artifacts[
        "concept_seals"
    ].payload["seals"])
    assert not result.execution.artifacts["concept_seals"].payload["errors"]


def test_concept_canonical_structure_uses_host_owned_graph_links(tmp_path) -> None:
    _, _, _, _, result, _ = execute_provider(
        tmp_path, canonical_structure=True
    )

    structural = result.execution.artifacts["structural_evidence"].payload
    relation = structural["relations"][0]
    filter_evidence = structural["filters"][0]
    assert result.execution.closure.structural_closed is True
    assert structural["_structural_assembly_id"] == "SINGLE_WITNESS_CHAIN"
    assert relation["manifestation_id"] == filter_evidence["manifestation_id"]
    assert relation["constraint_id"] == filter_evidence["constraint_id"]
    assert relation["excluded_cost_id"] == filter_evidence["excluded_cost_id"]


def test_invented_seal_sources_are_explicit_gaps_not_authority(tmp_path) -> None:
    _, store, concept, validation, result, calls = execute_provider(
        tmp_path, invented_source=True
    )

    assert result.execution.state is ExecutionState.COMPLETED
    assert len(calls) == 1
    artifact = result.execution.artifacts["concept_seals"]
    assert decode_concept_seals(artifact) == ()
    assert artifact.payload["errors"]
    assert all(
        "crystal:invented" in error for error in artifact.payload["errors"]
    )
    outcome = validation.validate_and_store(
        concept.concept_id,
        seals=decode_concept_seals(artifact),
        structural_graph=decode_structural_evidence_graph(
            result.execution.artifacts["structural_evidence"].payload
        ),
        epistemic_graph=decode_epistemic_evidence_graph(
            result.execution.artifacts["epistemic_evidence"].payload
        ),
    )
    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert outcome.concept_path is None
    assert outcome.report_path.exists()
    assert store.latest(concept.concept_id) == concept


def test_transport_uses_first_complete_json_object_and_ignores_tail(
    tmp_path,
) -> None:
    _, _, _, _, result, calls = execute_provider(
        tmp_path,
        trailing_content="\nThe proposal above is not a validation decision.",
    )

    assert len(calls) == 1
    assert result.execution.state is ExecutionState.COMPLETED
    assert "concept_seals" in result.execution.artifacts


def test_ungrounded_model_counterevidence_cannot_contest_candidate(
    tmp_path,
) -> None:
    _, store, concept, validation, result, _ = execute_provider(
        tmp_path,
        counterevidence=True,
    )
    artifact = result.execution.artifacts["concept_seals"]

    assert decode_concept_seals(artifact) == ()
    assert all(
        "grounded negative evidence graph" in error
        for error in artifact.payload["errors"]
    )
    outcome = validation.validate_and_store(
        concept.concept_id,
        seals=(),
        structural_graph=decode_structural_evidence_graph(
            result.execution.artifacts["structural_evidence"].payload
        ),
        epistemic_graph=decode_epistemic_evidence_graph(
            result.execution.artifacts["epistemic_evidence"].payload
        ),
    )
    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert outcome.concept_path is None
    assert store.latest(concept.concept_id) == concept
