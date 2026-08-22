"""Append-only journal ordering, isolation, causality, and effect audit."""

from __future__ import annotations

import pytest

from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.journal import EventJournal, JournalEventKind
from fresta_diamond.journal import (
    JournalArchiveError,
    JsonlJournalArchive,
)
from fresta_diamond.registry import ModuleRegistry


INPUT = "artifact://journal-input@1"
OUTPUT = "artifact://journal-output@1"


def deterministic_journal() -> EventJournal:
    sequence = iter(f"event-{index}" for index in range(1, 100))
    return EventJournal(
        id_factory=lambda: next(sequence),
        clock=lambda: "2026-07-25T00:00:00+00:00",
    )


def system(
    handler,
    *,
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> tuple[ModuleRegistry, BlueprintSpec]:
    operation = OperationContract(
        operation_id="journal.run",
        version="1.0.0",
        capabilities=("journal.test@1",),
        inputs={"source": INPUT},
        outputs={"result": OUTPUT},
        effects=effects,
        permissions=permissions,
    )
    manifest = ModuleManifest(
        module_id="journal-provider",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )
    registry = ModuleRegistry()
    registry.discover(manifest)
    registry.verify(manifest.module_id)
    registry.enable(manifest.module_id, {operation.operation_id: handler})
    blueprint = BlueprintSpec(
        blueprint_id="journal-blueprint",
        version=1,
        intent="Produce one auditable output",
        requirement=CapabilityRequirement(
            "journal.test@1", "source", INPUT, "result", OUTPUT
        ),
        allowed_effects=effects,
        granted_permissions=permissions,
    )
    return registry, blueprint


def inputs() -> dict[str, Artifact]:
    return {"source": Artifact(INPUT, {"text": "private input"})}


def test_journal_takes_deeply_immutable_snapshots() -> None:
    journal = deterministic_journal()
    original = {"nested": {"items": ["first"]}}

    event = journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:one",
        subject_ref="plan:one",
        payload=original,
    )
    original["nested"]["items"].append("mutated")

    assert event.sequence == 1
    assert event.event_id == "event-1"
    assert event.payload["nested"]["items"] == ("first",)
    with pytest.raises(TypeError):
        event.payload["new"] = "forbidden"
    with pytest.raises(TypeError):
        event.payload["nested"]["new"] = "forbidden"


def test_journal_rejects_unknown_causation_and_duplicate_ids() -> None:
    journal = EventJournal(
        id_factory=lambda: "same-id",
        clock=lambda: "now",
    )

    with pytest.raises(ValueError, match="Causation event"):
        journal.append(
            JournalEventKind.PLAN_VALIDATED,
            correlation_id="plan:one",
            subject_ref="plan:one",
            causation_id="missing",
        )

    journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:one",
        subject_ref="plan:one",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        journal.append(
            JournalEventKind.PLAN_VALIDATED,
            correlation_id="plan:one",
            subject_ref="plan:one",
            causation_id="same-id",
        )


def test_controller_emits_ordered_causal_phase_and_operation_events() -> None:
    journal = deterministic_journal()
    registry, blueprint = system(
        lambda data, _context: {"result": {"text": data["source"]["text"]}}
    )

    result = DiamondController(registry, journal=journal).execute(
        blueprint, "journal one result", inputs()
    )

    assert [event.kind for event in result.journal_events] == [
        JournalEventKind.FIREWALL_ATTESTED,
        JournalEventKind.PLAN_PROPOSED,
        JournalEventKind.PLAN_VALIDATED,
        JournalEventKind.AUTHORIZATION_GRANTED,
        JournalEventKind.OPERATION_STARTED,
        JournalEventKind.OPERATION_OUTPUT,
        JournalEventKind.ONTOLOGY_EVALUATED,
        JournalEventKind.EPISTEMIC_EVALUATED,
        JournalEventKind.OBJECTIVE_COMPLETED,
    ]
    assert [event.sequence for event in result.journal_events] == list(range(1, 10))
    assert {
        event.correlation_id for event in result.journal_events
    } == {result.plan.plan_id}
    assert result.journal_events[0].causation_id is None
    for previous, current in zip(
        result.journal_events,
        result.journal_events[1:],
    ):
        assert current.causation_id == previous.event_id


def test_effect_events_record_authority_not_sensitive_arguments() -> None:
    journal = deterministic_journal()
    observed = {}

    def adapter(_grant, path):
        observed["path"] = path
        return {"text": "bounded"}

    def handler(_inputs, context):
        return {
            "result": context.invoke("network.read", "/private/source")
        }

    registry, blueprint = system(
        handler,
        effects=("network.read",),
        permissions=("network.host:example.org",),
    )
    broker = EffectBroker({"network.read": adapter})

    result = DiamondController(
        registry,
        effect_broker=broker,
        journal=journal,
    ).execute(blueprint, "use a bounded effect", inputs())

    requested = next(
        event for event in result.journal_events
        if event.kind is JournalEventKind.EFFECT_REQUESTED
    )
    committed = next(
        event for event in result.journal_events
        if event.kind is JournalEventKind.EFFECT_COMMITTED
    )
    operation_started = next(
        event for event in result.journal_events
        if event.kind is JournalEventKind.OPERATION_STARTED
    )

    assert observed["path"] == "/private/source"
    assert requested.causation_id == operation_started.event_id
    assert committed.causation_id == requested.event_id
    assert "/private/source" not in repr(requested.payload)
    assert requested.payload["grant_id"] == result.authorization.grants[
        result.plan.nodes[0].node_id
    ].grant_id


def test_rejected_effect_and_failed_operation_remain_visible() -> None:
    journal = deterministic_journal()

    def handler(_inputs, context):
        context.invoke("filesystem.write", "secret")
        return {"result": {"text": "unreachable"}}

    registry, blueprint = system(handler)
    broker = EffectBroker({"filesystem.write": lambda *_: None})

    result = DiamondController(
        registry,
        effect_broker=broker,
        journal=journal,
    ).execute(blueprint, "attempt an ungranted effect", inputs())

    kinds = [event.kind for event in result.journal_events]
    assert JournalEventKind.EFFECT_REQUESTED in kinds
    assert JournalEventKind.EFFECT_REJECTED in kinds
    assert JournalEventKind.OPERATION_FAILED in kinds
    assert JournalEventKind.OBJECTIVE_OPEN in kinds
    rejected = next(
        event for event in result.journal_events
        if event.kind is JournalEventKind.EFFECT_REJECTED
    )
    assert rejected.payload["reason"] == "EFFECT_NOT_GRANTED"


def test_shared_journal_returns_only_events_from_each_controller_call() -> None:
    journal = deterministic_journal()
    registry, blueprint = system(
        lambda *_: {"result": {"text": "ok"}}
    )
    controller = DiamondController(registry, journal=journal)

    first = controller.execute(blueprint, "first", inputs())
    second = controller.execute(blueprint, "second", inputs())

    assert len(first.journal_events) == 9
    assert len(second.journal_events) == 9
    assert first.journal_events[-1].sequence == 9
    assert second.journal_events[0].sequence == 10
    assert first.plan.plan_id != second.plan.plan_id
    assert len(journal.for_correlation(first.plan.plan_id)) == 9
    assert len(journal.for_correlation(second.plan.plan_id)) == 9


def test_controller_without_journal_preserves_existing_observable_contract() -> None:
    registry, blueprint = system(
        lambda *_: {"result": {"text": "ok"}}
    )

    result = DiamondController(registry).execute(blueprint, "no journal", inputs())

    assert result.journal_events == ()


def test_jsonl_archive_is_lazy_persistent_and_round_trips(tmp_path) -> None:
    journal = deterministic_journal()
    first = journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:one",
        subject_ref="plan:one",
        payload={"nested": {"value": 1}},
    )
    second = journal.append(
        JournalEventKind.PLAN_VALIDATED,
        correlation_id="plan:one",
        subject_ref="plan:one",
        causation_id=first.event_id,
    )
    segment_ids = iter(("segment-1", "segment-2"))
    archive = JsonlJournalArchive(
        tmp_path / "archive",
        id_factory=lambda: next(segment_ids),
        clock=lambda: "2026-07-25T01:00:00+00:00",
    )

    assert archive.path.exists() is False
    segment = archive.archive((first, second))
    reloaded = JsonlJournalArchive(archive.path.parent).segments()

    assert archive.path.exists() is True
    assert segment.segment_id == "segment-1"
    assert segment.first_sequence == 1
    assert segment.last_sequence == 2
    assert reloaded == (segment,)
    assert reloaded[0].events[0].payload["nested"]["value"] == 1


def test_archive_chains_segments_and_queries_without_activating_all_history(
    tmp_path,
) -> None:
    archive_ids = iter(("segment-a", "segment-b"))
    archive = JsonlJournalArchive(
        tmp_path,
        id_factory=lambda: next(archive_ids),
        clock=lambda: "now",
    )
    journal = deterministic_journal()
    first = journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:a",
        subject_ref="plan:a",
    )
    second = journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:b",
        subject_ref="plan:b",
    )

    segment_a = archive.archive((first,))
    segment_b = archive.archive((second,))

    assert segment_a.previous_segment_hash is None
    assert segment_b.previous_segment_hash == segment_a.content_hash
    assert archive.for_correlation("plan:a") == (segment_a,)
    assert archive.for_correlation("plan:b") == (segment_b,)


def test_archive_detects_historical_tampering(tmp_path) -> None:
    archive = JsonlJournalArchive(
        tmp_path,
        id_factory=lambda: "segment-one",
        clock=lambda: "now",
    )
    journal = deterministic_journal()
    event = journal.append(
        JournalEventKind.PLAN_PROPOSED,
        correlation_id="plan:one",
        subject_ref="plan:one",
        payload={"state": "PROPOSED"},
    )
    archive.archive((event,))
    contents = archive.path.read_text(encoding="utf-8")
    archive.path.write_text(
        contents.replace('"PROPOSED"', '"REWRITTEN"'),
        encoding="utf-8",
    )

    with pytest.raises(JournalArchiveError, match="hash mismatch"):
        archive.segments()


def test_archive_rejects_mixed_execution_segment(tmp_path) -> None:
    journal = deterministic_journal()
    events = (
        journal.append(
            JournalEventKind.PLAN_PROPOSED,
            correlation_id="plan:a",
            subject_ref="plan:a",
        ),
        journal.append(
            JournalEventKind.PLAN_PROPOSED,
            correlation_id="plan:b",
            subject_ref="plan:b",
        ),
    )

    with pytest.raises(JournalArchiveError, match="mix correlation"):
        JsonlJournalArchive(tmp_path).archive(events)


def test_controller_can_seal_and_archive_its_own_execution(tmp_path) -> None:
    journal = deterministic_journal()
    archive = JsonlJournalArchive(
        tmp_path,
        id_factory=lambda: "segment-controller",
        clock=lambda: "now",
    )
    registry, blueprint = system(
        lambda *_: {"result": {"text": "ok"}}
    )

    result = DiamondController(
        registry,
        journal=journal,
        journal_archive=archive,
    ).execute(blueprint, "archive this execution", inputs())

    assert result.archived_journal_segment is not None
    assert result.archived_journal_segment.events == result.journal_events
    assert archive.for_correlation(result.plan.plan_id) == (
        result.archived_journal_segment,
    )


def test_archive_failure_keeps_technical_result_but_opens_operational_axis() -> None:
    class FailingArchive:
        def archive(self, _events):
            raise JournalArchiveError("disk unavailable")

    journal = deterministic_journal()
    registry, blueprint = system(
        lambda *_: {"result": {"text": "already produced"}}
    )

    result = DiamondController(
        registry,
        journal=journal,
        journal_archive=FailingArchive(),
    ).execute(blueprint, "require an archive", inputs())

    assert result.execution.closure.technical_completed is True
    assert result.execution.closure.operational_converged is False
    assert result.execution.closure.stopping_reason == "JOURNAL_ARCHIVE_FAILED"
    assert result.execution.artifacts["result"].payload["text"] == "already produced"
    assert result.archived_journal_segment is None
    assert result.journal_events[-1].kind is JournalEventKind.JOURNAL_ARCHIVE_FAILED
