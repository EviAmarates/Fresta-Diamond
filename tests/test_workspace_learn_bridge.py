from __future__ import annotations

from dataclasses import replace

import pytest

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.contracts import Artifact, ExecutionState, PlanState
from fresta_diamond.controller import DiamondController
from fresta_diamond.learning import (
    LEARNING_PROPOSAL_SCHEMA,
    build_workspace_learn_request,
    register_workspace_learn_provider,
)
from fresta_diamond.registry import ModuleRegistry


def selection(tmp_path):
    workspace = JsonlCognitiveWorkspace(tmp_path)
    workspace.save(SheetRevision(
        sheet_id="cars",
        revision_id="cars-v1",
        revision_number=1,
        title="Cars",
        state=SheetState.STAGED,
        elements=(
            SheetElement(
                element_id="claim:engine",
                kind=SheetElementKind.CLAIM,
                content="Um motor transforma energia.",
                scope="scope:cars",
                provenance=("document:mechanics:paragraph-4",),
                contextual_roles=(1,),
            ),
            SheetElement(
                element_id="hypothesis:identity",
                kind=SheetElementKind.HYPOTHESIS,
                content="A identidade funcional depende de componentes.",
                scope="scope:cars",
                provenance=("workspace:reasoning-turn-2",),
                contextual_roles=(2, 3),
            ),
        ),
    ))
    return workspace.select(
        "cars",
        ("claim:engine", "hypothesis:identity"),
        objective="Avaliar os dois candidatos sem os assumir como verdade.",
    )


def test_selection_runs_through_normal_controller_as_a_proposal(tmp_path) -> None:
    selected, artifact = selection(tmp_path)
    request = build_workspace_learn_request(selected, artifact)
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)

    result = DiamondController(registry).execute(
        request.blueprint,
        request.objective,
        request.inputs,
    )

    assert result.plan.state is PlanState.VALIDATED
    assert result.execution.state is ExecutionState.COMPLETED
    proposal = result.execution.artifacts["learning_proposal"]
    assert proposal.schema == LEARNING_PROPOSAL_SCHEMA
    assert proposal.payload["proposal_state"] == "PROPOSED"
    assert proposal.payload["promotion_authority"] is False
    assert len(proposal.payload["candidates"]) == 2
    assert all(
        item["status"] == "UNVALIDATED"
        for item in proposal.payload["candidates"]
    )
    assert proposal.payload["required_evaluations"] == (
        "GATEKEEPER",
        "THREE_ORDERS",
        "EPISTEMIC_BURDEN",
    )


def test_technical_intake_does_not_fabricate_epistemic_or_structural_closure(
    tmp_path,
) -> None:
    selected, artifact = selection(tmp_path)
    request = build_workspace_learn_request(selected, artifact)
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)

    result = DiamondController(registry).execute(
        request.blueprint, request.objective, request.inputs
    )

    assert result.execution.closure.technical_completed is True
    assert result.execution.closure.structural_closed is None
    assert result.execution.closure.constitutional_closed is None
    assert result.execution.closure.epistemic_closed is None
    assert result.ontological_reports == ()
    assert result.epistemic_reports == ()


def test_bridge_rejects_relabelled_selection_contract(tmp_path) -> None:
    selected, artifact = selection(tmp_path)

    with pytest.raises(ValueError, match="IDs"):
        build_workspace_learn_request(
            replace(selected, selection_id="different-selection"),
            artifact,
        )
    with pytest.raises(ValueError, match="objectives"):
        build_workspace_learn_request(
            replace(selected, objective="A different objective"),
            artifact,
        )


def test_runtime_rejects_selection_that_claims_promotion_authority(tmp_path) -> None:
    selected, artifact = selection(tmp_path)
    forged = Artifact(
        schema=artifact.schema,
        payload={**artifact.payload, "authority": "CONFIRMED"},
        provenance=artifact.provenance,
    )
    with pytest.raises(PermissionError, match="authority"):
        build_workspace_learn_request(selected, forged)


def test_proposal_preserves_source_identity_without_treating_sheet_as_evidence(
    tmp_path,
) -> None:
    selected, artifact = selection(tmp_path)
    request = build_workspace_learn_request(selected, artifact)
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)

    result = DiamondController(registry).execute(
        request.blueprint, request.objective, request.inputs
    )
    proposal = result.execution.artifacts["learning_proposal"].payload

    assert proposal["source_sheet_id"] == "cars"
    assert proposal["source_revision_id"] == "cars-v1"
    assert proposal["candidates"][0]["provenance"] == (
        "document:mechanics:paragraph-4",
    )
    assert "evidence_events" not in proposal
    assert "epistemic_closed" not in proposal
    assert "accepted" not in {key.lower() for key in proposal}


def test_learning_proposal_is_deeply_immutable(tmp_path) -> None:
    selected, artifact = selection(tmp_path)
    request = build_workspace_learn_request(selected, artifact)
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)
    proposal = DiamondController(registry).execute(
        request.blueprint, request.objective, request.inputs
    ).execution.artifacts["learning_proposal"]

    with pytest.raises(TypeError):
        proposal.payload["candidates"][0]["status"] = "ACCEPTED"
    with pytest.raises(AttributeError):
        proposal.payload["required_evaluations"].append("SELF_CONFIRM")
