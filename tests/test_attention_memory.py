from __future__ import annotations

import json

import pytest

from fresta_diamond.attention_memory import (
    AttentionMemory,
    AttentionMemoryError,
    AttentionReusePolicy,
    AttentionState,
    AttentionTransition,
    decode_attention_context,
    encode_attention_context,
)


def memory(tmp_path):
    counter = iter(range(1, 100))
    return AttentionMemory(
        tmp_path / "attention",
        revision_id_factory=lambda: f"revision:{next(counter)}",
        clock=lambda: "2026-07-26T21:00:00+00:00",
    )


def test_suspend_switch_and_reactivate_preserve_separate_contexts(
    tmp_path,
) -> None:
    store = memory(tmp_path)
    first = store.create(
        context_id="learn-pipeline",
        objective="Repair the learn pipeline",
        scope="scope:learn",
        summary="Tracing card validation",
        checkpoint_ref="checkpoint:learn:1",
        validated_refs=("concept:card-quality@2",),
    )
    with pytest.raises(AttentionMemoryError, match="active context first"):
        store.create(
            context_id="concept-research",
            objective="Research concepts",
            scope="scope:concepts",
            summary="New task",
        )

    suspended = store.suspend(
        first.context_id,
        reason="USER_CHANGED_TASK",
    )
    second = store.create(
        context_id="concept-research",
        objective="Research concepts",
        scope="scope:concepts",
        summary="Checking source diversity",
    )
    store.suspend(second.context_id, reason="RETURN_TO_PREVIOUS_TASK")
    restored = store.reactivate(first.context_id)

    assert suspended.state is AttentionState.SUSPENDED
    assert suspended.checkpoint_ref == "checkpoint:learn:1"
    assert restored.state is AttentionState.ACTIVE
    assert restored.transition is AttentionTransition.REACTIVATED
    assert store.active() == restored
    assert store.latest(second.context_id).state is AttentionState.SUSPENDED


def test_reactivate_can_atomically_replace_attention_refs(tmp_path) -> None:
    store = memory(tmp_path)
    created = store.create(
        context_id="bounded-batches",
        objective="Process bounded batches",
        scope="scope:batches",
        summary="Two refs are initially active.",
        workspace_sheet_refs=("sheet:a", "sheet:b"),
        selected_refs=("crystal:old",),
    )
    sleeping = store.suspend(created.context_id, reason="TOKEN_BUDGET:test")

    resumed = store.reactivate(
        created.context_id,
        summary="Only the pending sheet remains.",
        workspace_sheet_refs=("sheet:b",),
        selected_refs=(),
        validated_refs=("concept:validated@2",),
    )

    assert resumed.revision_number == 3
    assert resumed.previous_revision_id == sleeping.revision_id
    assert resumed.workspace_sheet_refs == ("sheet:b",)
    assert resumed.selected_refs == ()
    assert resumed.validated_refs == ("concept:validated@2",)
    assert len(store.history(created.context_id)) == 3


def test_active_sheet_is_versioned_with_attention_and_must_be_in_workspace(
    tmp_path,
) -> None:
    store = memory(tmp_path)
    first_ref = "sheet-revision:sheet-v1:sha256:" + "a" * 64
    second_ref = "sheet-revision:sheet-v2:sha256:" + "b" * 64
    created = store.create(
        context_id="active-sheet-task",
        objective="Maintain one active scratch sheet",
        scope="scope:sheet",
        summary="The first exact sheet revision is active.",
        workspace_sheet_refs=(first_ref,),
        active_sheet_ref=first_ref,
    )
    updated = store.update(
        created.context_id,
        summary="The scratch sheet evolved.",
        workspace_sheet_refs=(second_ref,),
        active_sheet_ref=second_ref,
    )

    assert decode_attention_context(encode_attention_context(updated)) == updated
    assert updated.active_sheet_ref == second_ref
    invalid_store = memory(tmp_path / "invalid")
    with pytest.raises(ValueError, match="workspace sheet refs"):
        invalid_store.create(
            context_id="invalid-active-sheet",
            objective="Reject a detached active sheet",
            scope="scope:sheet",
            summary="Invalid.",
            active_sheet_ref=first_ref,
        )


def test_archive_is_terminal_but_remains_queryable(tmp_path) -> None:
    store = memory(tmp_path)
    created = store.create(
        context_id="finished-task",
        objective="Finish a bounded task",
        scope="scope:task",
        summary="Work completed",
    )
    archived = store.archive(created.context_id)

    assert archived.state is AttentionState.ARCHIVED
    assert store.contexts(state=AttentionState.ARCHIVED) == (archived,)
    assert len(store.history(created.context_id)) == 2
    with pytest.raises(AttentionMemoryError, match="suspended"):
        store.reactivate(created.context_id)


def test_restart_abandons_old_path_and_reuses_only_sources(tmp_path) -> None:
    store = memory(tmp_path)
    old = store.create(
        context_id="confused-analysis",
        objective="Analyse an unstable hypothesis",
        scope="scope:hypothesis",
        summary="The reasoning mixed incompatible premises",
        source_refs=("source:paper:a", "source:paper:b"),
        validated_refs=("concept:stable@3",),
        selected_refs=("workspace:draft:item",),
        workspace_sheet_refs=("sheet:draft",),
        remainder_refs=("remainder:contradiction",),
        checkpoint_ref="checkpoint:confused",
    )
    outcome = store.restart(
        old.context_id,
        reason="INVALID_PREMISE",
        reuse_policy=AttentionReusePolicy.SOURCES_ONLY,
        objective="Reanalyse from clean evidence",
        summary="Fresh analysis using sources without old conclusions",
        successor_context_id="clean-analysis",
    )

    assert outcome.abandoned.state is AttentionState.ABANDONED
    assert outcome.abandoned.successor_context_id == "clean-analysis"
    assert outcome.abandoned.abandonment_reason == "INVALID_PREMISE"
    assert outcome.successor.state is AttentionState.ACTIVE
    assert outcome.successor.predecessor_context_id == old.context_id
    assert outcome.successor.source_refs == old.source_refs
    assert outcome.successor.validated_refs == ()
    assert outcome.successor.selected_refs == ()
    assert outcome.successor.workspace_sheet_refs == ()
    assert outcome.successor.remainder_refs == ()
    assert outcome.successor.checkpoint_ref is None
    assert len(store.history("clean-analysis")) == 2
    assert len(store.history(old.context_id)) == 2


def test_selected_restart_rejects_unknown_items_without_partial_successor(
    tmp_path,
) -> None:
    store = memory(tmp_path)
    old = store.create(
        context_id="selective-restart",
        objective="Restart selectively",
        scope="scope:selective",
        summary="Select known material",
        source_refs=("source:known",),
    )

    with pytest.raises(AttentionMemoryError, match="existing explicit"):
        store.restart(
            old.context_id,
            reason="TOO_MUCH_NOISE",
            reuse_policy=AttentionReusePolicy.SELECTED_ITEMS,
            objective="Clean selective restart",
            selected_refs=("source:invented",),
            successor_context_id="should-not-exist",
        )

    assert store.latest(old.context_id) == old
    with pytest.raises(AttentionMemoryError, match="Unknown"):
        store.latest("should-not-exist")


@pytest.mark.parametrize(
    ("policy", "selected", "expected"),
    (
        (
            AttentionReusePolicy.NOTHING,
            (),
            ((), (), (), (), (), None),
        ),
        (
            AttentionReusePolicy.VALIDATED_ONLY,
            (),
            ((), ("concept:validated@2",), (), (), (), None),
        ),
        (
            AttentionReusePolicy.SELECTED_ITEMS,
            ("source:one", "remainder:open"),
            (
                (),
                (),
                ("source:one", "remainder:open"),
                (),
                (),
                None,
            ),
        ),
        (
            AttentionReusePolicy.FULL_CHECKPOINT,
            (),
            (
                ("source:one",),
                ("concept:validated@2",),
                ("selection:item",),
                ("sheet:working",),
                ("remainder:open",),
                "checkpoint:full",
            ),
        ),
    ),
)
def test_restart_reuse_policies_are_exact(
    tmp_path,
    policy,
    selected,
    expected,
) -> None:
    store = memory(tmp_path / policy.value)
    old = store.create(
        context_id=f"old-{policy.value.lower()}",
        objective="Test an exact reuse boundary",
        scope="scope:reuse",
        summary="Original context",
        source_refs=("source:one",),
        validated_refs=("concept:validated@2",),
        selected_refs=("selection:item",),
        workspace_sheet_refs=("sheet:working",),
        remainder_refs=("remainder:open",),
        checkpoint_ref="checkpoint:full",
    )
    outcome = store.restart(
        old.context_id,
        reason="CONTROLLED_RESTART",
        reuse_policy=policy,
        objective="Fresh bounded context",
        selected_refs=selected,
        successor_context_id=f"new-{policy.value.lower()}",
    )
    successor = outcome.successor

    assert (
        successor.source_refs,
        successor.validated_refs,
        successor.selected_refs,
        successor.workspace_sheet_refs,
        successor.remainder_refs,
        successor.checkpoint_ref,
    ) == expected


def test_suspended_context_cannot_restart_behind_another_foreground(
    tmp_path,
) -> None:
    store = memory(tmp_path)
    old = store.create(
        context_id="old-task",
        objective="Old task",
        scope="scope:old",
        summary="Paused",
    )
    store.suspend(old.context_id, reason="SWITCH")
    current = store.create(
        context_id="current-task",
        objective="Current task",
        scope="scope:current",
        summary="Foreground",
    )

    with pytest.raises(AttentionMemoryError, match="foreground"):
        store.restart(
            old.context_id,
            reason="NEW_INFORMATION",
            reuse_policy=AttentionReusePolicy.NOTHING,
            objective="Restart old task",
            successor_context_id="old-task-v2",
        )

    assert store.active() == current
    with pytest.raises(AttentionMemoryError, match="Unknown"):
        store.latest("old-task-v2")


def test_attention_codec_and_archive_detect_tampering(tmp_path) -> None:
    store = memory(tmp_path)
    created = store.create(
        context_id="tamper-test",
        objective="Preserve attention history",
        scope="scope:audit",
        summary="Auditable projection",
    )
    assert decode_attention_context(encode_attention_context(created)) == created

    lines = store.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["summary"] = "Rewritten history"
    store.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(AttentionMemoryError, match="hash mismatch"):
        store.contexts()
