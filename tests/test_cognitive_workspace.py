from __future__ import annotations

from dataclasses import replace

import pytest

from fresta_diamond.cognitive_workspace import (
    WORKSPACE_SELECTION_SCHEMA,
    SHEET_CHILD_RELATION,
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetLink,
    SheetRevision,
    SheetRevisionRef,
    SheetState,
    decode_sheet_revision_target,
    decode_sheet_revision,
    encode_sheet_revision,
)


def element(
    element_id: str = "claim:engine",
    *,
    content: str = "O motor transforma energia.",
) -> SheetElement:
    return SheetElement(
        element_id=element_id,
        kind=SheetElementKind.CLAIM,
        content=content,
        scope="scope:automobile",
        provenance=("source:manual-note",),
        contextual_roles=(1,),
    )


def first_revision(*, links: tuple[SheetLink, ...] = ()) -> SheetRevision:
    return SheetRevision(
        sheet_id="automobiles",
        revision_id="revision-1",
        revision_number=1,
        title="Automóveis",
        state=SheetState.DRAFT,
        elements=(element(),),
        links=links,
        objective_ref="objective:understand-automobiles",
    )


def test_sheet_codec_round_trip_preserves_typed_revision() -> None:
    revision = first_revision()

    decoded = decode_sheet_revision(encode_sheet_revision(revision))

    assert decoded == revision
    assert decoded.elements[0].kind is SheetElementKind.CLAIM
    assert decoded.elements[0].contextual_roles == (1,)


def test_workspace_is_lazy_and_revisions_are_append_only(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path / "workspace")
    first = first_revision()

    assert workspace.path.exists() is False
    first_hash = workspace.save(first)
    second = replace(
        first,
        revision_id="revision-2",
        revision_number=2,
        parent_revision_id=first.revision_id,
        state=SheetState.STAGED,
        elements=(
            *first.elements,
            element("question:components", content="Quais componentes são constitutivos?"),
        ),
    )
    second_hash = workspace.save(second)

    assert first_hash != second_hash
    assert workspace.latest("automobiles") == second
    assert workspace.history("automobiles") == (first, second)
    with pytest.raises(CognitiveWorkspaceError, match="already exists"):
        workspace.save(second)


def test_revision_must_extend_latest_parent_and_state_is_monotonic(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    first = first_revision()
    workspace.save(first)

    with pytest.raises(CognitiveWorkspaceError, match="latest parent"):
        workspace.save(replace(
            first,
            revision_id="revision-2",
            revision_number=2,
            parent_revision_id="some-other-revision",
        ))

    staged = replace(
        first,
        revision_id="revision-2",
        revision_number=2,
        parent_revision_id=first.revision_id,
        state=SheetState.STAGED,
    )
    workspace.save(staged)
    proposed = replace(
        staged,
        revision_id="revision-3",
        revision_number=3,
        parent_revision_id=staged.revision_id,
        state=SheetState.PROPOSED,
    )
    workspace.save(proposed)
    with pytest.raises(CognitiveWorkspaceError, match="transition"):
        workspace.save(replace(
            proposed,
            revision_id="revision-4",
            revision_number=4,
            parent_revision_id=proposed.revision_id,
            state=SheetState.DRAFT,
        ))


def test_backlinks_are_derived_from_latest_revision_by_default(tmp_path) -> None:
    target = "concept:energy-conversion"
    old_link = SheetLink("link-1", "claim:engine", target, "relates-to")
    workspace = JsonlCognitiveWorkspace(tmp_path)
    first = first_revision(links=(old_link,))
    workspace.save(first)
    second = replace(
        first,
        revision_id="revision-2",
        revision_number=2,
        parent_revision_id=first.revision_id,
        links=(),
    )
    workspace.save(second)

    assert workspace.backlinks(target) == ()
    historical = workspace.backlinks(target, include_history=True)
    assert len(historical) == 1
    assert historical[0].source_revision_id == "revision-1"


def test_selection_is_explicitly_unvalidated_and_cannot_confirm_itself(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    workspace.save(first_revision())

    selection, artifact = workspace.select(
        "automobiles",
        ("claim:engine",),
        objective="Avaliar esta afirmação através de /learn",
    )

    assert selection.authority == "UNVALIDATED_WORKSPACE_PROPOSAL"
    assert artifact.schema == WORKSPACE_SELECTION_SCHEMA
    assert artifact.payload["authority"] == "UNVALIDATED_WORKSPACE_PROPOSAL"
    assert "ACCEPTED" not in artifact.payload.values()
    assert "CONFIRMED" not in artifact.payload.values()
    assert artifact.provenance == (
        "sheet:automobiles",
        "sheet-revision:revision-1",
    )


def test_selection_rejects_unknown_or_empty_elements(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    workspace.save(first_revision())

    with pytest.raises(CognitiveWorkspaceError, match="unknown"):
        workspace.select("automobiles", ("claim:missing",), objective="learn")
    with pytest.raises(ValueError, match="at least one"):
        workspace.select("automobiles", (), objective="learn")


def test_global_history_detects_tampering(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    workspace.save(first_revision())
    original = workspace.path.read_text(encoding="utf-8")
    workspace.path.write_text(
        original.replace("O motor transforma energia.", "Conteúdo reescrito."),
        encoding="utf-8",
    )

    with pytest.raises(CognitiveWorkspaceError, match="hash mismatch"):
        workspace.latest("automobiles")


def test_link_source_must_exist_in_same_revision() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        first_revision(links=(
            SheetLink("link-1", "claim:missing", "concept:engine", "relates-to"),
        ))


def test_mother_sheet_resolves_hash_bound_child_revision(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    child = SheetRevision(
        sheet_id="automobile-energy",
        revision_id="energy-revision-1",
        revision_number=1,
        title="Energy transformation",
        state=SheetState.DRAFT,
        elements=(element("claim:energy"),),
    )
    child_hash = workspace.save(child)
    child_ref = workspace.reference(child.sheet_id)
    mother = first_revision(links=(SheetLink(
        "link:energy-child",
        "claim:engine",
        child_ref.target_ref,
        SHEET_CHILD_RELATION,
    ),))

    workspace.save(mother)

    assert child_ref == SheetRevisionRef(
        child.sheet_id,
        child.revision_id,
        1,
        child_hash,
    )
    assert workspace.children(mother.sheet_id) == (child_ref,)
    assert workspace.resolve_reference(child_ref.target_ref) == child
    assert decode_sheet_revision_target(child_ref.target_ref) == (
        child.revision_id,
        child_hash,
    )


def test_child_link_rejects_unknown_hash_and_self_hierarchy(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    child = SheetRevision(
        sheet_id="child",
        revision_id="child-revision-1",
        revision_number=1,
        title="Child",
        state=SheetState.DRAFT,
        elements=(element(),),
    )
    workspace.save(child)
    child_ref = workspace.reference("child")
    forged = child_ref.target_ref[:-1] + (
        "0" if child_ref.target_ref[-1] != "0" else "1"
    )
    with pytest.raises(CognitiveWorkspaceError, match="existing exact revision"):
        workspace.save(first_revision(links=(SheetLink(
            "link:forged",
            "claim:engine",
            forged,
            SHEET_CHILD_RELATION,
        ),)))

    self_workspace = JsonlCognitiveWorkspace(tmp_path / "self")
    base = first_revision()
    self_workspace.save(base)
    with pytest.raises(CognitiveWorkspaceError, match="own scope child"):
        self_workspace.save(replace(
            base,
            revision_id="revision-2",
            revision_number=2,
            parent_revision_id=base.revision_id,
            links=(SheetLink(
                "link:self",
                "claim:engine",
                self_workspace.reference(base.sheet_id).target_ref,
                SHEET_CHILD_RELATION,
            ),),
        ))


def test_mother_keeps_exact_old_child_after_child_evolves(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    child = SheetRevision(
        sheet_id="child",
        revision_id="child-revision-1",
        revision_number=1,
        title="Child",
        state=SheetState.DRAFT,
        elements=(element(content="Original bounded detail."),),
    )
    workspace.save(child)
    original_ref = workspace.reference(child.sheet_id)
    mother = first_revision(links=(SheetLink(
        "link:child",
        "claim:engine",
        original_ref.target_ref,
        SHEET_CHILD_RELATION,
    ),))
    workspace.save(mother)
    evolved = replace(
        child,
        revision_id="child-revision-2",
        revision_number=2,
        parent_revision_id=child.revision_id,
        elements=(element(content="Revised bounded detail."),),
    )
    workspace.save(evolved)

    assert workspace.reference(child.sheet_id).revision_id == evolved.revision_id
    assert workspace.children(mother.sheet_id) == (original_ref,)
    assert workspace.resolve_reference(original_ref.target_ref) == child
    status, = workspace.child_statuses(mother.sheet_id)
    assert status.linked == original_ref
    assert status.latest.revision_id == evolved.revision_id
    assert status.stale is True
