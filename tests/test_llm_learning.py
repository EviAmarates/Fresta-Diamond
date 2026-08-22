from __future__ import annotations

import json

from fresta_diamond.contracts import Artifact, ExecutionState
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.llm_learning import (
    LEARNING_REPAIR_REQUEST_SCHEMA,
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    build_learning_epistemic_messages,
    learning_repair_action_catalog,
    learning_evaluation_blueprint,
    learning_repair_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.prompt_boundary import read_inert_data


PERMISSIONS = ("llm.model:qwen/qwen3-14b",)


def test_learning_prompt_supplies_kernel_classification_catalog() -> None:
    candidate_proposal = proposal()
    messages = build_learning_epistemic_messages(
        candidate_proposal.payload,
        tuple(candidate_proposal.payload["candidates"]),
        "scope:cars",
    )
    system_message = messages[0]["content"]

    assert '"classification_id":"ATTESTATION"' in system_message
    assert '"classification_id":"DEFER"' in system_message
    assert "never invent or rename a classification" in system_message
    assert '"classification_id":"one exact catalog ID"' in system_message


def test_repair_catalog_is_relative_to_each_remainder_and_keeps_defer() -> None:
    catalog = learning_repair_action_catalog((
        {
            "kind": "UNUSED_EVIDENCE",
            "required_for": "manifestation:2",
            "description": "Selected manifestation is unused",
        },
        {
            "kind": "MISSING_EVIDENCE",
            "required_for": "analysis:risk",
            "description": "Source lacks an explicit authority limitation",
        },
    ))

    assert catalog[0]["target_id"] == "remainder:1"
    assert [item["action_id"] for item in catalog[0]["allowed_actions"]] == [
        "REMOVE_REDUNDANT_EVIDENCE",
        "REBUILD_CANONICAL_CHAIN",
        "DEFER_REPAIR",
    ]
    assert "CLASSIFY_UNTRUSTED_SOURCE" in {
        item["action_id"] for item in catalog[1]["allowed_actions"]
    }


def proposal(*, second_scope: str = "scope:cars") -> Artifact:
    return Artifact(
        schema="artifact://learning-proposal@1",
        payload={
            "proposal_id": "learn-proposal:test",
            "selection_id": "selection:test",
            "source_sheet_id": "cars",
            "source_revision_id": "cars-v1",
            "objective": "Evaluate two bounded candidates",
            "proposal_state": "PROPOSED",
            "promotion_authority": False,
            "candidates": [
                {
                    "candidate_id": "candidate:engine",
                    "source_element_id": "claim:engine",
                    "kind": "CLAIM",
                    "content": "Um motor transforma energia.",
                    "scope": "scope:cars",
                    "provenance": ["document:mechanics:p4"],
                    "contextual_roles": [1],
                    "status": "UNVALIDATED",
                },
                {
                    "candidate_id": "candidate:identity",
                    "source_element_id": "hypothesis:identity",
                    "kind": "HYPOTHESIS",
                    "content": "A identidade funcional depende de componentes.",
                    "scope": second_scope,
                    "provenance": ["workspace:reasoning:2"],
                    "contextual_roles": [2, 3],
                    "status": "UNVALIDATED",
                },
            ],
        },
    )


def structural_response(*, provenance: str = "document:mechanics:p4") -> dict:
    return {
        "analysis_id": "model",
        "object_ref": "model",
        "scope": "scope:cars",
        "analysis_depth": "CONTEXTUAL",
        "manifestations": [{
            "manifestation_id": "m1",
            "object_ref": "model",
            "description": "Energy transformation and functional identity candidates",
            "provenance": [provenance],
        }],
        "relations": [{
            "relation_id": "r1",
            "manifestation_id": "m1",
            "constraint_id": "c1",
            "forward_justification": "Components constrain the proposed function.",
            "constraint_effect": "Only arrangements supporting conversion remain admissible.",
            "return_witness": "The bounded proposal still describes a functional system.",
            "excluded_cost_id": "cost1",
            "scope": "scope:cars",
        }],
        "constraints": [{
            "constraint_id": "c1",
            "description": "Functional coherence under the selected automobile scope.",
            "scope": "scope:cars",
        }],
        "filters": [{
            "filter_id": "f1",
            "constraint_id": "c1",
            "manifestation_id": "m1",
            "excluded_cost_id": "cost1",
            "selection_justification": "Selects coherent functional arrangements.",
        }],
        "excluded_costs": [{
            "cost_id": "cost1",
            "description": "Loss of the proposed function.",
            "excluded_alternatives": ["arrangements with no coherent energy conversion"],
        }],
        "groundings": [],
        "advisory_model_closed": True,
    }


def epistemic_response(*, claim_mode: str = "ATTESTATION") -> dict:
    return {
        "candidate_assessments": [
            {
                "source_element_id": "claim:engine",
                "claim_mode": claim_mode,
                "premise_refs": [],
                "applied_constraints": [],
                "derivation_direction": None,
                "test_criterion": None,
                "horizon": None,
                "assumptions": [],
                "counterexample_searches": [],
            },
            {
                "source_element_id": "hypothesis:identity",
                "claim_mode": "OBSERVATION",
                "premise_refs": [],
                "applied_constraints": [],
                "derivation_direction": None,
                "test_criterion": "Fails if component replacement never affects identity.",
                "horizon": None,
                "assumptions": [],
                "counterexample_searches": [],
            },
        ]
    }


def system(
    *,
    invented_provenance: bool = False,
    initial_claim_mode: str = "ATTESTATION",
    wrong_assessment_id: bool = False,
):
    registry = ModuleRegistry()
    manifest = llm_learning_manifest(PERMISSIONS)
    registry.discover(manifest)
    assert registry.verify(manifest.module_id).admitted is True
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: LlmLearningStructuralOperation(
                max_tokens=500
            ),
            manifest.operations[1].operation_id: LlmLearningEpistemicOperation(),
            manifest.operations[2].operation_id: LlmLearningRepairOperation(
                max_tokens=500
            ),
        },
    )
    calls = []

    def adapter(_grant, **kwargs):
        messages = kwargs["messages"]
        calls.append(messages)
        claim_mode = (
            initial_claim_mode if len(calls) == 1 else "ATTESTATION"
        )
        value = {
            "structural_evidence": structural_response(
                provenance=(
                    "invented:source"
                    if invented_provenance else "document:mechanics:p4"
                )
            ),
            "candidate_assessments": epistemic_response(claim_mode=claim_mode)[
                "candidate_assessments"
            ],
        }
        if len(calls) > 1:
            repair = read_inert_data(messages[1]["content"], "learning_repair")
            value["repair_actions"] = [{
                "target_id": target["target_id"],
                "action_id": target["allowed_actions"][0]["action_id"],
                "rationale": "Apply the smallest allowed correction.",
            } for target in repair["repair_action_catalog"]]
        if wrong_assessment_id:
            value["candidate_assessments"][0]["source_element_id"] = (
                "candidate:invented"
            )
        return {
            "content": json.dumps(value),
            "model": "qwen/qwen3-14b",
            "usage": {"total_tokens": 100},
        }

    controller = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": adapter}),
    )
    return controller, calls


def test_one_llm_bundle_is_split_and_independently_validated() -> None:
    controller, calls = system()

    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Evaluate one learning proposal",
        {"learning_proposal": proposal()},
    )

    assert len(calls) == 1
    assert result.execution.state is ExecutionState.COMPLETED
    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.constitutional_closed is None
    assert result.execution.closure.epistemic_closed is True


def test_known_redundant_assessment_wrapper_is_normalized_without_new_ids() -> None:
    controller, calls = system()
    original_adapter = controller._effect_broker._adapters["llm.generate"]

    def wrapped(grant, **kwargs):
        response = original_adapter(grant, **kwargs)
        value = json.loads(response["content"])
        value["candidate_assessments"] = {
            "candidate_assessments": value["candidate_assessments"]
        }
        return {**response, "content": json.dumps(value)}

    controller._effect_broker = EffectBroker({"llm.generate": wrapped})
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Evaluate one wrapped learning proposal",
        {"learning_proposal": proposal()},
    )

    assert len(calls) == 1
    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.epistemic_closed is True
    assert len(result.ontological_reports) == 1
    assert len(result.epistemic_reports) == 1


def test_hypothesis_kind_cannot_be_relabelled_as_observation() -> None:
    controller, _calls = system()
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Preserve candidate epistemic mode",
        {"learning_proposal": proposal()},
    )

    graph = result.execution.artifacts["epistemic_evidence"].payload
    hypothesis = next(
        item for item in graph["claims"]
        if item["subject_ref"].endswith("hypothesis:identity")
    )
    assert hypothesis["claim_mode"] == "HYPOTHESIS"
    assert hypothesis["owner_ref"] == "owner:unassigned"


def test_document_provenance_never_becomes_user_identity() -> None:
    controller, _calls = system()
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Keep actors distinct",
        {"learning_proposal": proposal()},
    )

    events = result.execution.artifacts["epistemic_evidence"].payload[
        "evidence_events"
    ]
    document_event = next(
        item for item in events
        if item["source_locator"] == "document:mechanics:p4"
    )
    assert document_event["source_actor"] == "source:document"
    assert "user" not in document_event["source_actor"]


def test_invented_structural_provenance_is_removed_and_cannot_close() -> None:
    controller, _calls = system(invented_provenance=True)
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Reject invented provenance",
        {"learning_proposal": proposal()},
    )

    assert result.execution.state is ExecutionState.COMPLETED
    assert result.execution.closure.structural_closed is False
    assert result.execution.artifacts["structural_evidence"].payload[
        "manifestations"
    ][0]["provenance"] == ()


def test_mixed_scope_proposal_fails_before_calling_model() -> None:
    controller, calls = system()
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Do not mix scopes",
        {"learning_proposal": proposal(second_scope="scope:engines")},
    )

    assert calls == []
    assert result.execution.state is ExecutionState.FAILED
    assert result.execution.closure.operational_converged is False


def test_validator_remainder_can_drive_one_sequential_repair_call() -> None:
    controller, calls = system(initial_claim_mode="OBSERVATION")
    learning = proposal()
    first = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Evaluate then repair if needed",
        {"learning_proposal": learning},
    )
    assert first.execution.closure.structural_closed is True
    assert first.execution.closure.epistemic_closed is False
    assert len(calls) == 1
    structural = first.execution.artifacts["structural_evidence"]
    repair_request = Artifact(
        schema=LEARNING_REPAIR_REQUEST_SCHEMA,
        payload={
            "learning_proposal": learning.payload,
            "original_bundle": structural.payload["_provider_bundle"],
            "parent_artifact_id": structural.artifact_id,
            "repair_attempt": 1,
            "validator_remainders": [
                {
                    "kind": item.kind.value,
                    "required_for": item.required_for,
                    "description": item.description,
                }
                for item in first.execution.remainders
            ],
        },
    )

    repaired = controller.execute(
        learning_repair_blueprint(PERMISSIONS),
        "Repair only the rejected evidence",
        {"repair_request": repair_request},
    )

    assert len(calls) == 2
    repair = read_inert_data(calls[1][1]["content"], "learning_repair")
    assert repair["validator_remainders"]
    assert "OBSERVATION requires a direct observation event" in (
        calls[1][1]["content"]
    )
    assert repaired.execution.closure.structural_closed is True
    assert repaired.execution.closure.epistemic_closed is True
    assert repaired.execution.artifacts["structural_evidence"].payload[
        "_repair_attempt"
    ] == 1
    assert repaired.execution.artifacts["structural_evidence"].payload[
        "_repair_actions"
    ]
    assert repaired.execution.artifacts["structural_evidence"].payload[
        "_repair_action_errors"
    ] == ()


def test_missing_candidate_assessment_remains_repairable_not_technical_failure() -> None:
    controller, _calls = system(wrong_assessment_id=True)
    result = controller.execute(
        learning_evaluation_blueprint(PERMISSIONS),
        "Preserve malformed semantic output for repair",
        {"learning_proposal": proposal()},
    )

    assert result.execution.state is ExecutionState.COMPLETED
    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.epistemic_closed is False
    epistemic = result.execution.artifacts["epistemic_evidence"]
    assert any(
        "Missing candidate assessment" in item
        for item in epistemic.payload["_assessment_errors"]
    )
    assert result.execution.artifacts["structural_evidence"].payload[
        "_provider_bundle"
    ]
