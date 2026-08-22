"""Finite operational budgets pause and resume without fabricating closure."""

from __future__ import annotations

from dataclasses import replace

import pytest

from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ExecutionState,
    ModuleManifest,
    OperationContract,
    RemainderKind,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.journal import EventJournal, JournalEventKind, JsonlJournalArchive
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.workspace import (
    CheckpointStoreError,
    ExecutionBudget,
    JsonCheckpointStore,
)


RAW = "artifact://checkpoint-raw@1"
NORMALIZED = "artifact://checkpoint-normalized@1"
RELATIONS = "artifact://checkpoint-relations@1"
ANSWER = "artifact://checkpoint-answer@1"


def add_provider(registry, module_id, operation, handler) -> None:
    manifest = ModuleManifest(
        module_id=module_id,
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )
    registry.discover(manifest)
    registry.verify(module_id)
    registry.enable(module_id, {operation.operation_id: handler})


def system(calls: list[str]) -> tuple[ModuleRegistry, BlueprintSpec]:
    registry = ModuleRegistry()
    normalize = OperationContract(
        "normalize",
        "1.0.0",
        ("normalize@1",),
        {"source": RAW},
        {"normalized": NORMALIZED},
    )
    relate = OperationContract(
        "relate",
        "1.0.0",
        ("relate@1",),
        {"normalized": NORMALIZED},
        {"relations": RELATIONS},
    )
    answer = OperationContract(
        "answer",
        "1.0.0",
        ("answer@1",),
        {"relations": RELATIONS},
        {"answer": ANSWER},
    )

    def normalize_handler(inputs, _context):
        calls.append("normalize")
        return {"normalized": {"text": inputs["source"]["text"].lower()}}

    def relate_handler(inputs, _context):
        calls.append("relate")
        return {"relations": {"tokens": inputs["normalized"]["text"].split()}}

    def answer_handler(inputs, _context):
        calls.append("answer")
        return {"answer": {"text": "|".join(inputs["relations"]["tokens"])}}

    add_provider(registry, "normalize-provider", normalize, normalize_handler)
    add_provider(registry, "relate-provider", relate, relate_handler)
    add_provider(registry, "answer-provider", answer, answer_handler)
    blueprint = BlueprintSpec(
        "checkpoint-chain",
        1,
        "Complete a three-operation chain across finite episodes",
        requirements=(
            CapabilityRequirement(
                "answer@1", "relations", RELATIONS, "answer", ANSWER
            ),
            CapabilityRequirement(
                "normalize@1", "source", RAW, "normalized", NORMALIZED
            ),
            CapabilityRequirement(
                "relate@1", "normalized", NORMALIZED, "relations", RELATIONS
            ),
        ),
    )
    return registry, blueprint


def source() -> dict[str, Artifact]:
    return {"source": Artifact(RAW, {"text": "HELLO CHECKPOINT"})}


def test_budget_contract_is_finite_without_becoming_truth() -> None:
    assert ExecutionBudget(1).remaining_operations == 1
    consumed = ExecutionBudget(1).consume_operation()
    assert consumed.exhausted is True
    with pytest.raises(ValueError, match="exhausted"):
        consumed.consume_operation()
    with pytest.raises(ValueError, match="negative"):
        ExecutionBudget(-1)


def test_zero_budget_pauses_before_any_operation() -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)

    result = DiamondController(registry).execute(
        blueprint,
        "pause immediately",
        source(),
        budget=ExecutionBudget(0),
    )

    assert calls == []
    assert result.execution.state is ExecutionState.PAUSED
    assert result.execution.closure.technical_completed is False
    assert result.execution.closure.operational_converged is False
    assert result.execution.closure.stopping_reason == "BUDGET_EXHAUSTED"
    assert result.execution.checkpoint is not None
    assert result.execution.checkpoint.completed_node_ids == ()
    assert len(result.execution.checkpoint.next_node_ids) == 3


def test_three_episodes_resume_frontier_without_repeating_completed_nodes() -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    controller = DiamondController(registry)

    first = controller.execute(
        blueprint,
        "complete slowly",
        source(),
        budget=ExecutionBudget(1),
    )
    assert calls == ["normalize"]
    assert first.execution.state is ExecutionState.PAUSED
    first_checkpoint = first.execution.checkpoint
    assert first_checkpoint is not None
    assert len(first_checkpoint.completed_node_ids) == 1
    assert len(first_checkpoint.next_node_ids) == 2
    assert any(
        item.kind is RemainderKind.BUDGET_EXHAUSTED
        for item in first.execution.remainders
    )

    second = controller.resume(
        first_checkpoint,
        blueprint,
        budget=ExecutionBudget(1),
    )
    assert calls == ["normalize", "relate"]
    assert second.execution.state is ExecutionState.PAUSED
    second_checkpoint = second.execution.checkpoint
    assert second_checkpoint is not None
    assert second_checkpoint.previous_checkpoint_id == first_checkpoint.checkpoint_id
    assert len(second_checkpoint.completed_node_ids) == 2

    third = controller.resume(
        second_checkpoint,
        blueprint,
        budget=ExecutionBudget(1),
    )
    assert calls == ["normalize", "relate", "answer"]
    assert third.execution.state is ExecutionState.COMPLETED
    assert third.execution.checkpoint is None
    assert third.execution.closure.operational_converged is True
    assert third.execution.artifacts["answer"].payload["text"] == "hello|checkpoint"
    assert not any(
        item.kind is RemainderKind.BUDGET_EXHAUSTED
        for item in third.execution.remainders
    )


def test_checkpoint_segments_link_pause_and_resume_history(tmp_path) -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    journal = EventJournal()
    archive = JsonlJournalArchive(tmp_path)
    controller = DiamondController(
        registry,
        journal=journal,
        journal_archive=archive,
    )

    first = controller.execute(
        blueprint,
        "archive pauses",
        source(),
        budget=ExecutionBudget(1),
    )
    checkpoint = first.execution.checkpoint
    assert checkpoint is not None
    assert checkpoint.journal_segment_hash == (
        first.archived_journal_segment.content_hash
    )
    assert JournalEventKind.CHECKPOINT_CREATED in {
        item.kind for item in first.journal_events
    }
    assert JournalEventKind.EXECUTION_PAUSED in {
        item.kind for item in first.journal_events
    }

    second = controller.resume(
        checkpoint,
        blueprint,
        budget=ExecutionBudget(2),
    )
    assert second.execution.state is ExecutionState.COMPLETED
    assert second.journal_events[0].kind is JournalEventKind.FIREWALL_ATTESTED
    assert second.journal_events[1].kind is JournalEventKind.EXECUTION_RESUMED
    assert second.journal_events[1].payload["previous_segment_hash"] == (
        first.archived_journal_segment.content_hash
    )
    segments = archive.for_correlation(first.plan.plan_id)
    assert len(segments) == 2
    assert segments[1].previous_segment_hash == segments[0].content_hash


def test_resume_revalidates_provider_availability() -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    controller = DiamondController(registry)
    first = controller.execute(
        blueprint,
        "pause then lose provider",
        source(),
        budget=ExecutionBudget(1),
    )
    checkpoint = first.execution.checkpoint
    assert checkpoint is not None
    registry.disable("relate-provider")

    resumed = controller.resume(
        checkpoint,
        blueprint,
        budget=ExecutionBudget(2),
    )

    assert calls == ["normalize"]
    assert resumed.execution.state is ExecutionState.OPEN
    assert resumed.execution.closure.operational_converged is False
    assert any(
        item.kind is RemainderKind.MISSING_CAPABILITY
        for item in resumed.execution.remainders
    )


def test_resume_rejects_a_checkpoint_relabelled_for_another_blueprint() -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    controller = DiamondController(registry)
    first = controller.execute(
        blueprint,
        "pause",
        source(),
        budget=ExecutionBudget(0),
    )
    checkpoint = first.execution.checkpoint
    assert checkpoint is not None
    other = replace(blueprint, blueprint_id="other-blueprint")

    with pytest.raises(ValueError, match="IDs"):
        controller.resume(checkpoint, other, budget=ExecutionBudget(1))


def test_persisted_checkpoint_survives_a_simulated_process_restart(tmp_path) -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    archive_root = tmp_path / "journal"
    checkpoint_root = tmp_path / "checkpoints"
    first_controller = DiamondController(
        registry,
        journal=EventJournal(),
        journal_archive=JsonlJournalArchive(archive_root),
        checkpoint_store=JsonCheckpointStore(checkpoint_root),
    )

    first = first_controller.execute(
        blueprint,
        "survive restart",
        source(),
        budget=ExecutionBudget(1),
    )
    assert calls == ["normalize"]
    assert first.stored_checkpoint is not None
    persisted_id = first.stored_checkpoint.checkpoint_id

    # New journal, archive object, store object, and controller simulate restart.
    loaded = JsonCheckpointStore(checkpoint_root).load(persisted_id)
    resumed = DiamondController(
        registry,
        journal=EventJournal(),
        journal_archive=JsonlJournalArchive(archive_root),
        checkpoint_store=JsonCheckpointStore(checkpoint_root),
    ).resume(loaded, blueprint, budget=ExecutionBudget(2))

    assert calls == ["normalize", "relate", "answer"]
    assert resumed.execution.state is ExecutionState.COMPLETED
    assert resumed.execution.artifacts["answer"].payload["text"] == "hello|checkpoint"
    assert resumed.journal_events[0].kind is JournalEventKind.FIREWALL_ATTESTED
    assert resumed.journal_events[1].kind is JournalEventKind.EXECUTION_RESUMED
    assert resumed.journal_events[1].payload["previous_segment_hash"] == (
        loaded.journal_segment_hash
    )


def test_checkpoint_store_is_lazy_immutable_and_detects_tampering(tmp_path) -> None:
    calls: list[str] = []
    registry, blueprint = system(calls)
    paused = DiamondController(registry).execute(
        blueprint,
        "create checkpoint",
        source(),
        budget=ExecutionBudget(1),
    )
    checkpoint = paused.execution.checkpoint
    assert checkpoint is not None
    store = JsonCheckpointStore(tmp_path / "store")

    assert store.root.exists() is False
    reference = store.save(checkpoint)
    assert store.load(reference.checkpoint_id) == checkpoint
    with pytest.raises(CheckpointStoreError, match="already exists"):
        store.save(checkpoint)

    path = store.root / f"{checkpoint.checkpoint_id}.json"
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace('"reason":"BUDGET_EXHAUSTED"', '"reason":"REWRITTEN"'),
        encoding="utf-8",
    )
    with pytest.raises(CheckpointStoreError, match="hash mismatch"):
        store.load(checkpoint.checkpoint_id)


def test_checkpoint_persistence_failure_stays_visible_without_losing_frontier(
    tmp_path,
) -> None:
    class FailingStore:
        def save(self, _checkpoint):
            raise CheckpointStoreError("storage unavailable")

        def load(self, _checkpoint_id):
            raise AssertionError("not used")

    calls: list[str] = []
    registry, blueprint = system(calls)
    controller = DiamondController(
        registry,
        journal=EventJournal(),
        journal_archive=JsonlJournalArchive(tmp_path / "journal"),
        checkpoint_store=FailingStore(),
    )

    result = controller.execute(
        blueprint,
        "fail durable checkpoint",
        source(),
        budget=ExecutionBudget(1),
    )

    assert calls == ["normalize"]
    assert result.execution.state is ExecutionState.PAUSED
    assert result.execution.checkpoint is not None
    assert result.stored_checkpoint is None
    assert result.execution.closure.operational_converged is False
    assert result.execution.closure.stopping_reason == "CHECKPOINT_PERSISTENCE_FAILED"
    assert result.journal_events[-1].kind is (
        JournalEventKind.CHECKPOINT_PERSISTENCE_FAILED
    )
    assert any(
        item.kind is RemainderKind.EXTERNAL_UNCERTAINTY
        for item in result.execution.remainders
    )
