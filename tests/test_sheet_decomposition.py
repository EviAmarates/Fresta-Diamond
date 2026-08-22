from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from fresta_diamond.attention_memory import (
    AttentionContextRevision,
    AttentionState,
    AttentionTransition,
)
from fresta_diamond.attention_projection import estimated_tokens
from fresta_diamond.attention_resolution import (
    AttentionNomination,
    AttentionResolutionStatus,
    WorkspaceAttentionResolver,
)
from fresta_diamond.cognitive_workspace import (
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetElementKind,
)
from fresta_diamond.sheet_decomposition import (
    DECOMPOSITION_AUTHORITY,
    SheetDecompositionService,
)


def decompose(workspace, content, **overrides):
    values = {
        "content": content,
        "source_ref": "document:test",
        "mother_sheet_id": "sheet:source-index",
        "mother_revision_id": "sheet:source-index:revision:1",
        "title": "Source index",
        "scope": "scope:test",
        "max_child_content_tokens": 8,
        "max_children_per_index": 4,
        "decomposition_id": "test-run",
    }
    values.update(overrides)
    return SheetDecompositionService(workspace).decompose(**values)


def test_decomposition_is_unicode_safe_lossless_and_hash_bound(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    content = (
        "Primeira linha com ação.\n"
        "Segunda linha com Φ, F e automóvel.\n"
        "Terceira linha mantém espaços  e ordem."
    )

    outcome = decompose(workspace, content)

    assert SheetDecompositionService(workspace).reconstruct(outcome) == content
    assert outcome.source_sha256 == sha256(content.encode("utf-8")).hexdigest()
    assert outcome.authority == DECOMPOSITION_AUTHORITY
    assert outcome.root.child_refs == outcome.leaf_refs
    assert workspace.children(outcome.root.revision.sheet_id) == outcome.leaf_refs
    for ordinal, reference in enumerate(outcome.leaf_refs, start=1):
        leaf = workspace.resolve_reference(reference.target_ref)
        assert len(leaf.elements) == 1
        assert leaf.elements[0].kind is SheetElementKind.NOTE
        assert estimated_tokens(leaf.elements[0].content) <= 8
        assert f"part:{ordinal}/{len(outcome.leaf_refs)}" in (
            leaf.elements[0].provenance
        )


def test_large_decomposition_builds_bounded_index_tree(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    content = "".join(f"segment-{number:02d};" for number in range(30))

    outcome = decompose(
        workspace,
        content,
        max_child_content_tokens=3,
        max_children_per_index=2,
    )

    assert SheetDecompositionService(workspace).reconstruct(outcome) == content
    assert outcome.index_refs
    assert len(outcome.root.child_refs) <= 2
    assert all(
        len(workspace.children(reference.sheet_id)) <= 2
        for reference in outcome.index_refs
    )
    assert set(outcome.root.child_refs).issubset(set(outcome.index_refs))


def test_reconstruction_keeps_exact_leaf_after_leaf_evolves(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    content = "A source long enough to become several exact leaves."
    outcome = decompose(workspace, content, max_child_content_tokens=4)
    original_ref = outcome.leaf_refs[0]
    original = workspace.resolve_reference(original_ref.target_ref)
    workspace.save(replace(
        original,
        revision_id=f"{original.revision_id}:revised",
        revision_number=2,
        parent_revision_id=original.revision_id,
        elements=(replace(original.elements[0], content="Replacement."),),
    ))

    assert workspace.reference(original.sheet_id) != original_ref
    assert SheetDecompositionService(workspace).reconstruct(outcome) == content


def test_exact_leaf_can_be_materialized_as_bounded_attention(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    outcome = decompose(
        workspace,
        "One bounded part, then another bounded part for attention.",
        max_child_content_tokens=4,
    )
    leaf_ref = outcome.leaf_refs[0].target_ref
    context = AttentionContextRevision(
        context_id="context:test",
        revision_id="attention-revision:test:1",
        revision_number=1,
        state=AttentionState.ACTIVE,
        transition=AttentionTransition.CREATED,
        objective="Read one exact decomposition leaf",
        scope="scope:test",
        summary="Bounded attention integration test.",
        workspace_sheet_refs=(leaf_ref,),
        active_sheet_ref=leaf_ref,
    )

    result = WorkspaceAttentionResolver(workspace).resolve(
        leaf_ref,
        context,
        AttentionNomination(leaf_ref, relevance=1.0, contextual_roles=(1,)),
    )

    assert result.status is AttentionResolutionStatus.RESOLVED
    assert result.candidate is not None
    assert workspace.resolve_reference(leaf_ref).elements[0].content in (
        result.candidate.content
    )


def test_decomposition_preflights_collisions_before_writing(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    first = decompose(workspace, "Original source content.")
    before = workspace.path.read_bytes()

    with pytest.raises(CognitiveWorkspaceError, match="already exists"):
        decompose(workspace, "A different source content.")

    assert workspace.path.read_bytes() == before
    assert SheetDecompositionService(workspace).reconstruct(first) == (
        "Original source content."
    )


def test_decomposition_rejects_lossy_or_impossible_inputs(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path)
    with pytest.raises(ValueError, match="semantic content"):
        decompose(workspace, "   \n\t")
    with pytest.raises(ValueError, match="at least two"):
        decompose(workspace, "content", max_children_per_index=1)
    with pytest.raises(ValueError, match="Whitespace run"):
        decompose(
            workspace,
            "     content",
            max_child_content_tokens=1,
            decomposition_id="whitespace-run",
            mother_sheet_id="sheet:whitespace",
            mother_revision_id="sheet:whitespace:revision:1",
        )
