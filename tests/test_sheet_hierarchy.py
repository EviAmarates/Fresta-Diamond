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
from fresta_diamond.sheet_hierarchy import MotherSheetService, SheetSnippet


def child(sheet_id: str, revision_id: str, content: str) -> SheetRevision:
    return SheetRevision(
        sheet_id=sheet_id,
        revision_id=revision_id,
        revision_number=1,
        title=sheet_id,
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id=f"detail:{sheet_id}",
            kind=SheetElementKind.NOTE,
            content=content,
            scope="scope:automobile",
            provenance=("document:automobile",),
        ),),
    )


def test_mother_snippets_are_hash_bound_indexes_not_copies(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    energy = child("energy", "energy:1", "Detailed energy transformation.")
    identity = child("identity", "identity:1", "Detailed functional identity.")
    workspace.save(energy)
    workspace.save(identity)
    energy_ref = workspace.reference("energy")
    identity_ref = workspace.reference("identity")

    outcome = MotherSheetService(workspace).create(
        sheet_id="automobile",
        revision_id="automobile:1",
        title="Automobile index",
        scope="scope:automobile",
        snippets=(
            SheetSnippet(
                "snippet:energy",
                "Energy is transformed into movement.",
                "scope:automobile",
                energy_ref,
            ),
            SheetSnippet(
                "snippet:identity",
                "Components sustain functional identity.",
                "scope:automobile",
                identity_ref,
            ),
        ),
    )

    assert outcome.child_refs == (energy_ref, identity_ref)
    assert workspace.children("automobile") == (energy_ref, identity_ref)
    assert all(
        item.kind is SheetElementKind.SNIPPET
        for item in outcome.revision.elements
    )
    rendered = " ".join(item.content for item in outcome.revision.elements)
    assert "Detailed energy transformation." not in rendered
    assert outcome.revision.elements[0].provenance[0] == energy_ref.target_ref


def test_snippet_status_detects_child_evolution_without_mutating_mother(
    tmp_path,
) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    first = child("energy", "energy:1", "Original detail.")
    workspace.save(first)
    original_ref = workspace.reference("energy")
    service = MotherSheetService(workspace)
    mother = service.create(
        sheet_id="automobile",
        revision_id="automobile:1",
        title="Automobile index",
        scope="scope:automobile",
        snippets=(SheetSnippet(
            "snippet:energy",
            "Original energy snippet.",
            "scope:automobile",
            original_ref,
        ),),
    )
    workspace.save(replace(
        first,
        revision_id="energy:2",
        revision_number=2,
        parent_revision_id=first.revision_id,
        elements=(replace(
            first.elements[0],
            content="Evolved detail.",
        ),),
    ))

    status, = service.snippet_statuses("automobile")

    assert status.stale is True
    assert status.linked == original_ref
    assert status.latest.revision_id == "energy:2"
    assert workspace.latest("automobile") == mother.revision
    assert status.snippet.content == "Original energy snippet."


def test_mother_rejects_duplicate_children_and_scope_drift(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    detail = child("energy", "energy:1", "Detail.")
    workspace.save(detail)
    reference = workspace.reference("energy")
    service = MotherSheetService(workspace)

    with pytest.raises(ValueError, match="child refs must be unique"):
        service.create(
            sheet_id="invalid",
            revision_id="invalid:1",
            title="Invalid",
            scope="scope:automobile",
            snippets=(
                SheetSnippet("snippet:a", "A", "scope:automobile", reference),
                SheetSnippet("snippet:b", "B", "scope:automobile", reference),
            ),
        )
    with pytest.raises(ValueError, match="scopes must match"):
        service.create(
            sheet_id="invalid-scope",
            revision_id="invalid-scope:1",
            title="Invalid scope",
            scope="scope:other",
            snippets=(SheetSnippet(
                "snippet:a",
                "A",
                "scope:automobile",
                reference,
            ),),
        )
