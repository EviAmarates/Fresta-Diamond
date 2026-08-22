from __future__ import annotations

import pytest

from fresta_diamond.attention_memory import AttentionMemory
from fresta_diamond.attention_projection import (
    AttentionCandidate,
    AttentionEvidenceState,
    AttentionItemKind,
    AttentionProjectionError,
    AttentionProjectionState,
    AttentionProjector,
    estimated_tokens,
)


def active_context(tmp_path, **refs):
    return AttentionMemory(tmp_path / "attention").create(
        context_id="projection-task",
        objective="Explain the active system coherently",
        scope="scope:projection",
        summary="The previous step validated the internal concept",
        **refs,
    )


def candidate(
    item_ref,
    *,
    kind=AttentionItemKind.CONCEPT,
    content="Bounded evidence",
    state=AttentionEvidenceState.VALIDATED,
    relevance=0.5,
    roles=(),
    dependencies=(),
    scope="scope:projection",
):
    return AttentionCandidate(
        item_ref=item_ref,
        kind=kind,
        content=content,
        scope=scope,
        authority="SOURCE_AUTHORITY_PRESERVED",
        evidence_state=state,
        relevance=relevance,
        contextual_roles=roles,
        dependency_refs=dependencies,
        provenance=(f"origin:{item_ref}",),
    )


def test_projection_preserves_mandatory_items_and_dependency_order(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        checkpoint_ref="checkpoint:task",
        remainder_refs=("remainder:open",),
        validated_refs=("concept:car@2",),
    )
    values = (
        candidate(
            "concept:car@2",
            content="A car is a bounded functional concept.",
            relevance=1,
            roles=(3,),
            dependencies=("crystal:engine",),
        ),
        candidate(
            "crystal:engine",
            kind=AttentionItemKind.CRYSTAL,
            content="The coordinated engine transforms energy.",
            relevance=0.8,
            roles=(1,),
        ),
        candidate(
            "checkpoint:task",
            kind=AttentionItemKind.CHECKPOINT,
            content="Resume after validating the concept.",
            state=AttentionEvidenceState.PROVISIONAL,
            relevance=0,
            roles=(3,),
        ),
        candidate(
            "remainder:open",
            kind=AttentionItemKind.REMAINDER,
            content="External recognition remains open.",
            state=AttentionEvidenceState.DEFERRED,
            relevance=0,
            roles=(2,),
        ),
    )
    projection = AttentionProjector().project(
        context,
        tuple(reversed(values)),
        token_budget=500,
    )

    refs = tuple(item.item_ref for item in projection.selected)
    assert projection.state is AttentionProjectionState.READY
    assert projection.injection_ready is True
    assert projection.continuation_checkpoint is None
    assert refs.index("checkpoint:task") < refs.index("concept:car@2")
    assert refs.index("remainder:open") < refs.index("concept:car@2")
    assert refs.index("crystal:engine") < refs.index("concept:car@2")
    assert "roles=O3" in projection.rendered_context
    assert projection.used_tokens <= projection.token_budget
    assert estimated_tokens(projection.rendered_context) <= (
        projection.used_tokens
    )


def test_missing_checkpoint_blocks_injection(tmp_path) -> None:
    context = active_context(
        tmp_path,
        checkpoint_ref="checkpoint:missing",
        validated_refs=("concept:available",),
    )
    projection = AttentionProjector().project(
        context,
        (candidate("concept:available"),),
        token_budget=300,
    )

    assert projection.state is AttentionProjectionState.BLOCKED
    assert projection.injection_ready is False
    assert projection.rendered_context == ""
    assert projection.missing_required_refs == ("checkpoint:missing",)
    assert projection.continuation_checkpoint is not None
    assert "MISSING_REQUIRED" in projection.continuation_checkpoint.reasons


def test_dependency_group_never_enters_partially(tmp_path) -> None:
    context = active_context(
        tmp_path,
        selected_refs=("concept:large",),
        validated_refs=("crystal:large",),
    )
    projection = AttentionProjector().project(
        context,
        (
            candidate(
                "concept:large",
                content="C" * 240,
                dependencies=("crystal:large",),
            ),
            candidate(
                "crystal:large",
                kind=AttentionItemKind.CRYSTAL,
                content="E" * 240,
            ),
        ),
        token_budget=120,
    )

    assert projection.state is AttentionProjectionState.BLOCKED
    assert projection.selected == ()
    assert set(projection.overflow_refs) == {
        "concept:large",
        "crystal:large",
    }
    assert set(projection.continuation_checkpoint.pending_refs) == {
        "concept:large",
        "crystal:large",
    }


def test_optional_overflow_is_partial_and_keeps_continuation(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        validated_refs=("concept:small",),
        source_refs=("source:large",),
    )
    projection = AttentionProjector().project(
        context,
        (
            candidate(
                "concept:small",
                content="Small validated concept.",
                relevance=1,
            ),
            candidate(
                "source:large",
                kind=AttentionItemKind.SOURCE,
                content="S" * 600,
                state=AttentionEvidenceState.PROVISIONAL,
                relevance=1,
            ),
        ),
        token_budget=150,
    )

    assert projection.state is AttentionProjectionState.PARTIAL
    assert projection.injection_ready is True
    assert projection.continuation_required is True
    assert tuple(item.item_ref for item in projection.selected) == (
        "concept:small",
    )
    assert projection.overflow_refs == ("source:large",)
    assert projection.continuation_checkpoint is not None
    assert projection.continuation_checkpoint.reasons == ("TOKEN_BUDGET",)
    assert projection.continuation_checkpoint.completed_refs == (
        "concept:small",
    )
    assert projection.continuation_checkpoint.pending_refs == (
        "source:large",
    )


def test_projection_is_deterministic_across_candidate_input_order(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        validated_refs=("concept:a", "concept:b"),
    )
    candidates = (
        candidate("concept:b", relevance=0.4),
        candidate("concept:a", relevance=0.9),
    )
    projector = AttentionProjector()

    left = projector.project(context, candidates, token_budget=400)
    right = projector.project(
        context,
        tuple(reversed(candidates)),
        token_budget=400,
    )

    assert left == right
    assert tuple(item.item_ref for item in left.selected) == (
        "concept:a",
        "concept:b",
    )


def test_scope_and_evidence_policy_mismatches_stay_visible(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        validated_refs=("concept:wrong-state", "concept:wrong-scope"),
    )
    projection = AttentionProjector().project(
        context,
        (
            candidate(
                "concept:wrong-state",
                state=AttentionEvidenceState.DEFERRED,
            ),
            candidate(
                "concept:wrong-scope",
                scope="scope:other",
            ),
        ),
        token_budget=400,
    )

    assert projection.state is AttentionProjectionState.PARTIAL
    assert projection.selected == ()
    assert projection.excluded_policy_refs == ("concept:wrong-state",)
    assert projection.excluded_scope_refs == ("concept:wrong-scope",)
    assert set(projection.unresolved_optional_refs) == {
        "concept:wrong-state",
        "concept:wrong-scope",
    }


def test_policy_invalid_dependency_excludes_its_dependent_root(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        validated_refs=("concept:root", "crystal:invalid"),
    )
    projection = AttentionProjector().project(
        context,
        (
            candidate(
                "concept:root",
                dependencies=("crystal:invalid",),
            ),
            candidate(
                "crystal:invalid",
                kind=AttentionItemKind.CRYSTAL,
                state=AttentionEvidenceState.DEFERRED,
            ),
        ),
        token_budget=400,
    )

    assert projection.selected == ()
    assert projection.excluded_policy_refs == ("crystal:invalid",)
    assert set(projection.unresolved_optional_refs) == {
        "concept:root",
        "crystal:invalid",
    }


def test_dependency_cycles_and_unnominated_candidates_fail_closed(
    tmp_path,
) -> None:
    context = active_context(
        tmp_path,
        validated_refs=("concept:a", "concept:b"),
    )
    with pytest.raises(AttentionProjectionError, match="cycle"):
        AttentionProjector().project(
            context,
            (
                candidate("concept:a", dependencies=("concept:b",)),
                candidate("concept:b", dependencies=("concept:a",)),
            ),
            token_budget=400,
        )
    with pytest.raises(AttentionProjectionError, match="not nominated"):
        AttentionProjector().project(
            context,
            (
                candidate("concept:a"),
                candidate("concept:b"),
                candidate("concept:invented"),
            ),
            token_budget=400,
        )


def test_suspended_context_and_oversized_base_cannot_be_injected(
    tmp_path,
) -> None:
    store = AttentionMemory(tmp_path / "attention")
    active = store.create(
        context_id="large-objective",
        objective="O" * 400,
        scope="scope:projection",
        summary="S" * 400,
    )
    oversized = AttentionProjector().project(
        active,
        (),
        token_budget=32,
    )
    assert oversized.state is AttentionProjectionState.BLOCKED
    assert oversized.used_tokens == 0

    suspended = store.suspend(active.context_id, reason="SWITCH")
    with pytest.raises(AttentionProjectionError, match="Only active"):
        AttentionProjector().project(
            suspended,
            (),
            token_budget=400,
        )
