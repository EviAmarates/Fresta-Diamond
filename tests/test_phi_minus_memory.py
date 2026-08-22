from __future__ import annotations

import pytest

from fresta_diamond.contracts import Artifact
from fresta_diamond.crystallization import CrystallizationGate
from fresta_diamond.phi_minus import (
    JsonlPhiMinusMemory,
    NegativeBoundaryDisposition,
    PhiMinusDeriver,
    PhiMinusMemoryError,
    decode_phi_minus_observation,
    encode_phi_minus_observation,
)
from .test_learning_crystal_gate import evaluated


def test_positive_crystals_do_not_create_negative_boundary_memory(tmp_path) -> None:
    proposal, result = evaluated()
    batch = CrystallizationGate().evaluate(proposal, result)
    memory = JsonlPhiMinusMemory(tmp_path)

    observations = memory.record(batch, result)

    assert observations == ()
    assert memory.path.exists() is False


def test_deferred_candidate_is_indeterminate_not_justified_phi_minus(
    tmp_path,
) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    batch = CrystallizationGate().evaluate(proposal, result)
    memory = JsonlPhiMinusMemory(tmp_path)

    observations = memory.record(batch, result)
    engine = next(
        item for item in observations
        if item.source_element_id == "claim:engine"
    )

    assert engine.disposition is NegativeBoundaryDisposition.INDETERMINATE
    assert engine.phi_minus_justified is False
    assert engine.reason_codes == ("EPISTEMIC_BURDEN_INCOMPLETE",)
    assert "MISSING_EVIDENCE" in engine.remainder_kinds
    assert engine.promotion_authority is False


def test_quarantined_boundary_is_a_justified_exclusion(tmp_path) -> None:
    proposal, result = evaluated()
    changed = [dict(item) for item in proposal.payload["candidates"]]
    changed[0]["content"] = "Rewritten after validation"
    forged = Artifact(
        schema=proposal.schema,
        payload={**proposal.payload, "candidates": changed},
    )
    batch = CrystallizationGate().evaluate(forged, result)
    memory = JsonlPhiMinusMemory(tmp_path)

    observations = memory.record(batch, result)
    engine = next(
        item for item in observations
        if item.source_element_id == "claim:engine"
    )

    assert engine.disposition is NegativeBoundaryDisposition.EXCLUDED
    assert engine.phi_minus_justified is True
    assert engine.reason_codes == ("CANDIDATE_CONTENT_MISMATCH",)


def test_memory_round_trips_and_retrieves_only_matching_scope(tmp_path) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    batch = CrystallizationGate().evaluate(proposal, result)
    memory = JsonlPhiMinusMemory(tmp_path)
    recorded = memory.record(batch, result)

    reloaded = JsonlPhiMinusMemory(tmp_path)

    assert reloaded.observations() == recorded
    assert reloaded.for_scope("scope:cars") == recorded
    assert reloaded.for_scope("scope:other") == ()
    first = recorded[0]
    assert reloaded.for_candidate(first.candidate_ref) == (first,)
    assert reloaded.for_scope(
        "scope:cars",
        disposition=NegativeBoundaryDisposition.EXCLUDED,
    ) == ()


def test_same_batch_cannot_be_counted_twice_as_independent_evidence(
    tmp_path,
) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    batch = CrystallizationGate().evaluate(proposal, result)
    memory = JsonlPhiMinusMemory(tmp_path)
    memory.record(batch, result)

    with pytest.raises(PhiMinusMemoryError, match="already recorded"):
        memory.record(batch, result)


def test_codec_rejects_attempted_promotion_authority() -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    batch = CrystallizationGate().evaluate(proposal, result)
    observation = PhiMinusDeriver().derive(batch, result)[0]
    encoded = encode_phi_minus_observation(observation)
    encoded["promotion_authority"] = True

    with pytest.raises(PermissionError, match="grants authority"):
        decode_phi_minus_observation(encoded)
