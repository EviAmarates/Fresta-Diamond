from __future__ import annotations

from dataclasses import replace

import pytest

from fresta_diamond.contracts import Artifact
from fresta_diamond.crystallization import CrystalState, CrystallizationGate
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
    LearningCommit,
    LearningMemoryError,
    decode_learning_commit,
    encode_learning_commit,
)
from fresta_diamond.phi_minus import NegativeBoundaryDisposition
from .test_learning_crystal_gate import evaluated


def test_positive_and_negative_results_commit_as_one_record(tmp_path) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    memory = AtomicDiamondLearningMemory(
        tmp_path,
        id_factory=lambda: "commit-one",
        clock=lambda: "2026-07-26T00:00:00+00:00",
    )

    stored = memory.commit(proposal, result)

    assert stored.path.exists()
    assert stored.path.parent == (tmp_path / "commits").resolve()
    assert len(stored.commit.crystallization.crystals) == 2
    assert len(stored.commit.negative_boundary) == 1
    assert stored.commit.negative_boundary[0].disposition is (
        NegativeBoundaryDisposition.INDETERMINATE
    )
    assert stored.commit.promotion_authority is False
    assert memory.pending() == ()


def test_positive_commit_creates_no_false_phi_minus_observation(tmp_path) -> None:
    proposal, result = evaluated()
    memory = AtomicDiamondLearningMemory(tmp_path)

    memory.commit(proposal, result)

    assert memory.negative_boundary() == ()
    assert {
        item.state for item in memory.crystals()
    } == {CrystalState.PROVISIONAL}


def test_retrieval_is_bounded_by_scope_state_and_negative_justification(
    tmp_path,
) -> None:
    proposal, result = evaluated()
    changed = [dict(item) for item in proposal.payload["candidates"]]
    changed[0]["content"] = "Rewritten after validation"
    forged = Artifact(
        schema=proposal.schema,
        payload={**proposal.payload, "candidates": changed},
    )
    memory = AtomicDiamondLearningMemory(tmp_path)

    memory.commit(forged, result)

    quarantined = memory.crystals(
        scope="scope:cars",
        states=(CrystalState.QUARANTINED,),
    )
    excluded = memory.negative_boundary(
        scope="scope:cars",
        justified_only=True,
    )
    assert len(quarantined) == 1
    assert len(excluded) == 1
    assert excluded[0].source_crystal_id == quarantined[0].crystal_id
    assert memory.crystals(scope="scope:other") == ()


def test_retrieval_defaults_safe_and_requires_explicit_fallback_or_audit(
    tmp_path,
) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    memory = AtomicDiamondLearningMemory(tmp_path)
    memory.commit(proposal, result)

    active = memory.crystals()
    fallback = memory.crystals(policy=CrystalRetrievalPolicy.FALLBACK)
    audit = memory.crystals(policy=CrystalRetrievalPolicy.AUDIT)

    assert all(item.state is CrystalState.PROVISIONAL for item in active)
    assert {item.state for item in fallback} == {
        CrystalState.PROVISIONAL,
        CrystalState.DEFERRED,
    }
    assert audit == fallback


def test_finalize_failure_leaves_a_recoverable_complete_pending_commit(
    tmp_path,
) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")

    def fail_finalize(_pending, _final):
        raise OSError("simulated interruption")

    interrupted = AtomicDiamondLearningMemory(
        tmp_path,
        id_factory=lambda: "commit-recoverable",
        clock=lambda: "2026-07-26T00:00:00+00:00",
        finalizer=fail_finalize,
    )
    with pytest.raises(LearningMemoryError, match="remains pending"):
        interrupted.commit(proposal, result)

    assert interrupted.commits() == ()
    pending = interrupted.pending()
    assert len(pending) == 1
    assert pending[0].commit.commit_id == "commit-recoverable"

    restarted = AtomicDiamondLearningMemory(tmp_path)
    recovered = restarted.recover_pending()

    assert len(recovered) == 1
    assert recovered[0].commit == pending[0].commit
    assert restarted.pending() == ()
    assert restarted.commits()[0].commit == pending[0].commit


def test_same_proposal_cannot_be_committed_twice(tmp_path) -> None:
    proposal, result = evaluated()
    memory = AtomicDiamondLearningMemory(tmp_path)
    memory.commit(proposal, result)

    with pytest.raises(LearningMemoryError, match="already committed"):
        memory.commit(proposal, result)


def test_commit_codec_rejects_promotion_authority(tmp_path) -> None:
    proposal, result = evaluated()
    stored = AtomicDiamondLearningMemory(tmp_path).commit(proposal, result)
    encoded = encode_learning_commit(stored.commit)
    encoded["promotion_authority"] = True

    with pytest.raises(PermissionError, match="grants authority"):
        decode_learning_commit(encoded)


def test_commit_rejects_negative_observation_linked_to_unknown_crystal(
    tmp_path,
) -> None:
    proposal, result = evaluated(claim_mode="OBSERVATION")
    batch = CrystallizationGate().evaluate(proposal, result)
    stored = AtomicDiamondLearningMemory(tmp_path).commit_batch(batch, result)
    observation = stored.commit.negative_boundary[0]

    with pytest.raises(ValueError, match="unknown crystal"):
        LearningCommit(
            commit_id="invalid-link",
            proposal_id=batch.proposal_id,
            crystallization=batch,
            negative_boundary=(
                replace(observation, source_crystal_id="crystal:missing"),
            ),
        )


def test_commit_detects_historical_tampering(tmp_path) -> None:
    proposal, result = evaluated()
    memory = AtomicDiamondLearningMemory(tmp_path)
    stored = memory.commit(proposal, result)
    raw = stored.path.read_text(encoding="utf-8")
    stored.path.write_text(
        raw.replace('"PROVISIONAL"', '"ACCEPTED"', 1),
        encoding="utf-8",
    )

    with pytest.raises(LearningMemoryError, match="hash mismatch"):
        memory.commits()
