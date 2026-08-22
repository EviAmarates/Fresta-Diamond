from __future__ import annotations

import json

import pytest

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.concepts import AtomicConceptStore
from fresta_diamond.contracts import ExecutionState
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.objective_retrieval import (
    LlmObjectiveRetrievalOperation,
    ObjectiveRetrievalDecision,
    ObjectiveRetrievalItem,
    ObjectiveRetrievalNomination,
    batch_objective_retrieval_request,
    build_objective_retrieval_request,
    decode_objective_retrieval_nomination,
    merge_objective_retrieval_nominations,
    objective_retrieval_blueprint,
    register_objective_retrieval_provider,
)
from fresta_diamond.registry import ModuleRegistry

from .test_concepts import committed_memory


PERMISSIONS = ("llm.model:objective-retrieval-test",)


def environment(tmp_path, *, objective: str):
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    workspace = JsonlCognitiveWorkspace(tmp_path / "workspace")
    workspace.save(SheetRevision(
        sheet_id="ontology-heuristic",
        revision_number=1,
        title="Unvalidated filtration heuristic",
        state=SheetState.STAGED,
        elements=(SheetElement(
            element_id="hypothesis:filter",
            kind=SheetElementKind.HYPOTHESIS,
            content="The filter is proposed as a condition on differentiation.",
            scope="scope:cars",
            provenance=("catalog:notebooklm",),
        ),),
    ))
    request = build_objective_retrieval_request(
        memory,
        store,
        workspace,
        scope="scope:cars",
        objective=objective,
    )
    return memory, store, workspace, request


def execute(tmp_path, objective, response_factory):
    _, _, _, request = environment(tmp_path, objective=objective)
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(response_factory(request.payload)),
            "model": "objective-retrieval-test",
        }

    registry = ModuleRegistry()
    register_objective_retrieval_provider(
        registry,
        required_permissions=PERMISSIONS,
        operation=LlmObjectiveRetrievalOperation(max_tokens=500),
    )
    result = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": adapter}),
    ).execute(
        objective_retrieval_blueprint(PERMISSIONS),
        objective,
        {"request": request},
    )
    return request, result, calls


@pytest.mark.parametrize(("objective", "roles"), (
    ("Describe the selected manifestation.", (1,)),
    ("Relate the selected evidence to another object.", (2,)),
    ("Use the selected evidence as a constraint on admissibility.", (3,)),
))
def test_same_reference_can_receive_different_objective_roles(
    tmp_path,
    objective,
    roles,
) -> None:
    def response(request):
        crystal = next(
            item for item in request["candidates"] if item["kind"] == "CRYSTAL"
        )
        return {
            "decision": "SELECT",
            "items": [{
                "item_ref": crystal["item_ref"],
                "relevance": 0.9,
                "contextual_roles": list(roles),
                "rationale": "Its role is relative to the supplied objective.",
            }],
            "rationale": "One bounded root is sufficient for this test.",
        }

    request, result, calls = execute(tmp_path, objective, response)

    assert len(calls) == 1
    assert result.execution.state is ExecutionState.COMPLETED
    nomination = decode_objective_retrieval_nomination(
        result.execution.artifacts["nomination"]
    )
    assert nomination.items[0].contextual_roles == roles
    assert nomination.items[0].source_authority.startswith("LEARNING_MEMORY:")
    assert nomination.scope == request.payload["scope"]
    assert nomination.objective == objective


def test_request_exposes_all_eligible_roots_without_top_k(tmp_path) -> None:
    _, _, _, request = environment(tmp_path, objective="Review available roots")

    candidates = request.payload["candidates"]
    assert len([item for item in candidates if item["kind"] == "CRYSTAL"]) == 2
    assert len([item for item in candidates if item["kind"] == "WORKSPACE"]) == 1
    assert any(
        item["item_ref"] == "sheet:ontology-heuristic"
        and item["source_authority"] == "UNVALIDATED_WORKSPACE_PROPOSAL"
        for item in candidates
    )


def test_model_cannot_invent_retrieval_reference(tmp_path) -> None:
    def response(_request):
        return {
            "decision": "SELECT",
            "items": [{
                "item_ref": "crystal:invented",
                "relevance": 1.0,
                "contextual_roles": [3],
                "rationale": "Invented reference.",
            }],
            "rationale": "Attempt to escape the candidate boundary.",
        }

    _, result, calls = execute(tmp_path, "Reject invention", response)

    assert len(calls) == 1
    assert result.execution.state is ExecutionState.FAILED
    assert "nomination" not in result.execution.artifacts
    assert any(
        "invented retrieval reference" in item.description.lower()
        for item in result.execution.remainders
    )


def test_model_may_refuse_selection_without_fabricating_relevance(tmp_path) -> None:
    def response(_request):
        return {
            "decision": "NO_SELECTION",
            "items": [],
            "rationale": "No supplied root is justified for this objective.",
        }

    _, result, _ = execute(tmp_path, "Unrelated bounded objective", response)
    nomination = decode_objective_retrieval_nomination(
        result.execution.artifacts["nomination"]
    )

    assert nomination.decision is ObjectiveRetrievalDecision.NO_SELECTION
    assert nomination.items == ()


def test_selected_root_requires_a_contextual_role(tmp_path) -> None:
    def response(request):
        return {
            "decision": "SELECT",
            "items": [{
                "item_ref": request["candidates"][0]["item_ref"],
                "relevance": 0.5,
                "contextual_roles": [],
                "rationale": "Missing relational role.",
            }],
            "rationale": "Malformed selection.",
        }

    _, result, _ = execute(tmp_path, "Require relational role", response)

    assert result.execution.state is ExecutionState.FAILED
    assert any(
        "contextual roles" in item.description.lower()
        for item in result.execution.remainders
    )


def test_request_batching_preserves_every_exact_ref_once(tmp_path) -> None:
    _, _, _, request = environment(tmp_path, objective="Review all roots")

    batches = batch_objective_retrieval_request(
        request,
        max_request_tokens=160,
    )

    assert len(batches) > 1
    original = tuple(
        item["item_ref"] for item in request.payload["candidates"]
    )
    partitioned = tuple(
        item["item_ref"]
        for batch in batches
        for item in batch.payload["candidates"]
    )
    assert partitioned == original
    assert len(partitioned) == len(set(partitioned))
    assert tuple(batch.payload["batch"]["index"] for batch in batches) == (
        tuple(range(1, len(batches) + 1))
    )
    assert all(
        batch.payload["batch"]["count"] == len(batches)
        for batch in batches
    )


def test_batch_merge_is_conservative_and_preserves_authority() -> None:
    selected = ObjectiveRetrievalNomination(
        decision=ObjectiveRetrievalDecision.SELECT,
        scope="scope:test",
        objective="Explain one object",
        items=(ObjectiveRetrievalItem(
            item_ref="crystal:a",
            kind="CRYSTAL",
            source_authority="LEARNING_MEMORY:PROVISIONAL",
            relevance=0.8,
            contextual_roles=(1,),
            rationale="Needed as a manifestation.",
        ),),
        rationale="The first batch contains one relevant root.",
    )
    empty = ObjectiveRetrievalNomination(
        decision=ObjectiveRetrievalDecision.NO_SELECTION,
        scope="scope:test",
        objective="Explain one object",
        items=(),
        rationale="The second batch contains no relevant root.",
    )

    merged = merge_objective_retrieval_nominations((selected, empty))

    assert merged.decision is ObjectiveRetrievalDecision.SELECT
    assert merged.items == selected.items
    assert merged.items[0].source_authority == "LEARNING_MEMORY:PROVISIONAL"
    assert "first batch" in merged.rationale.lower()
    assert "second batch" in merged.rationale.lower()


def test_batching_rejects_one_candidate_larger_than_budget(tmp_path) -> None:
    _, _, _, request = environment(tmp_path, objective="Review all roots")
    oversized = dict(request.payload)
    candidates = [dict(item) for item in oversized["candidates"]]
    candidates[0]["content"] = "x" * 4_000
    oversized["candidates"] = candidates

    with pytest.raises(ValueError, match="candidate exceeds"):
        batch_objective_retrieval_request(
            type(request)(request.schema, oversized),
            max_request_tokens=300,
        )
