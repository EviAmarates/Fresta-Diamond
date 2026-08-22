from __future__ import annotations

from dataclasses import replace

import pytest

from fresta_diamond.attention_memory import AttentionMemory
from fresta_diamond.attention_projection import (
    AttentionEvidenceState,
    AttentionProjectionState,
)
from fresta_diamond.attention_resolution import (
    AttentionMaterializationService,
    AttentionNomination,
    AttentionResolutionStatus,
    CheckpointAttentionResolver,
    CompositeAttentionResolver,
    ConceptAttentionResolver,
    LearningMemoryAttentionResolver,
    ResolverResult,
    WorkspaceAttentionResolver,
)
from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.concept_validation import ConceptState
from fresta_diamond.controller import DiamondController
from fresta_diamond.workspace import ExecutionBudget, JsonCheckpointStore

from .test_checkpoint_resume import source, system
from .test_concept_validation import complete_seals, evidence_graphs, service


def validated_system(tmp_path):
    memory, store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    concept = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    ).record
    assert concept.state is ConceptState.VALIDATED

    workspace = JsonlCognitiveWorkspace(tmp_path / "workspace")
    workspace.save(SheetRevision(
        sheet_id="cars",
        revision_id="revision:cars:1",
        revision_number=1,
        title="Working notes about cars",
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="note:energy",
            kind=SheetElementKind.NOTE,
            content="Check how components preserve functional identity.",
            scope=concept.scope,
            provenance=("source:operator-note",),
            contextual_roles=(2,),
        ),),
    ))

    calls: list[str] = []
    registry, blueprint = system(calls)
    paused = DiamondController(registry).execute(
        blueprint,
        "pause for attention test",
        source(),
        budget=ExecutionBudget(0),
    )
    checkpoint = paused.execution.checkpoint
    assert checkpoint is not None
    checkpoint_store = JsonCheckpointStore(tmp_path / "checkpoints")
    checkpoint_store.save(checkpoint)

    resolver = CompositeAttentionResolver((
        ConceptAttentionResolver(store),
        LearningMemoryAttentionResolver(memory),
        WorkspaceAttentionResolver(workspace),
        CheckpointAttentionResolver(checkpoint_store),
    ))
    return memory, concept, checkpoint, resolver


def context_for(
    tmp_path,
    *,
    concept_ref: str,
    checkpoint_ref: str | None = None,
    remainder_refs: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
):
    return AttentionMemory(
        tmp_path / "attention",
        id_factory=lambda: "context:cars",
        revision_id_factory=lambda: "attention-revision:cars:1",
    ).create(
        objective="Continue a bounded analysis of functional cars",
        scope="scope:cars",
        summary="Validated concept, temporary notes, and paused work.",
        source_refs=source_refs,
        validated_refs=(concept_ref,),
        workspace_sheet_refs=("sheet:cars",),
        checkpoint_ref=checkpoint_ref,
        remainder_refs=remainder_refs,
    )


def test_active_sheet_resolves_the_exact_historical_revision(tmp_path) -> None:
    workspace = JsonlCognitiveWorkspace(tmp_path / "workspace-exact")
    first = SheetRevision(
        sheet_id="scratch",
        revision_id="scratch:revision:1",
        revision_number=1,
        title="Active scratch sheet",
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="note:state",
            kind=SheetElementKind.NOTE,
            content="Original working state.",
            scope="scope:scratch",
            provenance=("operator:state-1",),
        ),),
    )
    workspace.save(first)
    exact_ref = workspace.reference(first.sheet_id).target_ref
    workspace.save(replace(
        first,
        revision_id="scratch:revision:2",
        revision_number=2,
        parent_revision_id=first.revision_id,
        elements=(replace(
            first.elements[0],
            content="Newer working state.",
            provenance=("operator:state-2",),
        ),),
    ))
    context = AttentionMemory(tmp_path / "attention-exact").create(
        objective="Read the sealed active scratch state.",
        scope="scope:scratch",
        summary="One exact sheet revision is active.",
        workspace_sheet_refs=(exact_ref,),
        active_sheet_ref=exact_ref,
    )

    resolution = CompositeAttentionResolver((
        WorkspaceAttentionResolver(workspace),
    )).resolve(context)

    candidate, = resolution.candidates
    assert candidate.item_ref == exact_ref
    assert "Original working state." in candidate.content
    assert "Newer working state." not in candidate.content
    assert context.active_sheet_ref == exact_ref


def test_materializes_exact_stores_and_derived_concept_members(tmp_path) -> None:
    memory, concept, checkpoint, resolver = validated_system(tmp_path)
    remainder_refs = tuple(
        item.remainder_id for item in checkpoint.active_remainders
    )
    context = context_for(
        tmp_path,
        concept_ref=concept.version_ref,
        checkpoint_ref=checkpoint.checkpoint_id,
        remainder_refs=remainder_refs,
        source_refs=("https://example.invalid/raw-source",),
    )
    crystal_refs = tuple(item.crystal_id for item in memory.crystals())

    result = AttentionMaterializationService(
        resolver
    ).materialize_and_project(
        context,
        token_budget=4096,
        nominations=(
            AttentionNomination(concept.version_ref, 0.9, (3,)),
            AttentionNomination(crystal_refs[0], 0.8, (1,)),
        ),
    )

    assert set(result.resolution.derived_refs) == set(crystal_refs)
    assert {
        item.item_ref for item in result.resolution.candidates
    } >= {
        concept.version_ref,
        *crystal_refs,
        "sheet:cars",
        checkpoint.checkpoint_id,
        *remainder_refs,
    }
    source_diagnostic = next(
        item for item in result.resolution.diagnostics
        if item.item_ref == "https://example.invalid/raw-source"
    )
    assert source_diagnostic.status is AttentionResolutionStatus.NOT_FOUND
    assert result.projection.state is AttentionProjectionState.PARTIAL
    assert result.projection.injection_ready is True
    assert "https://example.invalid/raw-source" not in (
        result.projection.rendered_context
    )
    selected = {item.item_ref: item for item in result.projection.selected}
    assert selected[concept.version_ref].authority.startswith("CONCEPT_STORE:")
    assert selected["sheet:cars"].authority == (
        "UNVALIDATED_WORKSPACE_PROPOSAL"
    )
    assert selected[crystal_refs[0]].contextual_roles == (1,)


def test_missing_mandatory_checkpoint_blocks_projection(tmp_path) -> None:
    _, concept, _, resolver = validated_system(tmp_path)
    context = context_for(
        tmp_path,
        concept_ref=concept.version_ref,
        checkpoint_ref="checkpoint:missing",
    )

    result = AttentionMaterializationService(
        resolver
    ).materialize_and_project(context, token_budget=2048)

    assert result.projection.state is AttentionProjectionState.BLOCKED
    assert result.projection.injection_ready is False
    assert result.projection.missing_required_refs == ("checkpoint:missing",)
    assert "checkpoint:missing" in result.resolution.unresolved_refs


def test_candidate_concept_cannot_masquerade_as_validated(tmp_path) -> None:
    memory, store, proposed, _ = service(tmp_path)
    context = context_for(tmp_path, concept_ref=proposed.version_ref)
    resolver = CompositeAttentionResolver((
        ConceptAttentionResolver(store),
        LearningMemoryAttentionResolver(memory),
    ))

    result = AttentionMaterializationService(
        resolver
    ).materialize_and_project(context, token_budget=2048)

    concept_candidate = next(
        item for item in result.resolution.candidates
        if item.item_ref == proposed.version_ref
    )
    assert concept_candidate.evidence_state is AttentionEvidenceState.DEFERRED
    assert proposed.version_ref in result.projection.excluded_policy_refs
    assert result.projection.state is AttentionProjectionState.PARTIAL


def test_wrong_scope_is_diagnostic_and_never_injected(tmp_path) -> None:
    memory, concept, _, resolver = validated_system(tmp_path)
    context = replace(
        context_for(tmp_path, concept_ref=concept.version_ref),
        scope="scope:aircraft",
    )

    resolution = resolver.resolve(context)

    concept_diagnostic = next(
        item for item in resolution.diagnostics
        if item.item_ref == concept.version_ref
    )
    assert concept_diagnostic.status is AttentionResolutionStatus.WRONG_SCOPE
    assert concept.version_ref not in {
        item.item_ref for item in resolution.candidates
    }
    assert memory.crystals()


def test_raw_source_reference_is_not_fabricated_without_source_store(
    tmp_path,
) -> None:
    _, concept, _, resolver = validated_system(tmp_path)
    raw_ref = "https://example.org/article"
    context = context_for(
        tmp_path,
        concept_ref=concept.version_ref,
        source_refs=(raw_ref,),
    )

    result = resolver.resolve(context)

    assert raw_ref in result.unresolved_refs
    assert raw_ref not in {item.item_ref for item in result.candidates}


def test_multiple_store_claims_are_reported_as_ambiguous(tmp_path) -> None:
    class DuplicateResolver:
        def __init__(self, resolver_id, candidate):
            self.resolver_id = resolver_id
            self._candidate = candidate

        def resolve(self, item_ref, _context, _nomination):
            if item_ref != self._candidate.item_ref:
                return ResolverResult(
                    item_ref,
                    AttentionResolutionStatus.NOT_FOUND,
                    self.resolver_id,
                )
            return ResolverResult(
                item_ref,
                AttentionResolutionStatus.RESOLVED,
                self.resolver_id,
                candidate=self._candidate,
            )

    _, concept, _, resolver = validated_system(tmp_path)
    context = context_for(tmp_path, concept_ref=concept.version_ref)
    candidate = next(
        item for item in resolver.resolve(context).candidates
        if item.item_ref == concept.version_ref
    )
    ambiguous = CompositeAttentionResolver((
        DuplicateResolver("duplicate-a", candidate),
        DuplicateResolver("duplicate-b", candidate),
    )).resolve(context)

    diagnostic = next(
        item for item in ambiguous.diagnostics
        if item.item_ref == concept.version_ref
    )
    assert diagnostic.status is AttentionResolutionStatus.AMBIGUOUS
    assert ambiguous.candidates == ()


def test_unused_nomination_is_rejected_after_dependency_discovery(
    tmp_path,
) -> None:
    _, concept, _, resolver = validated_system(tmp_path)
    context = context_for(tmp_path, concept_ref=concept.version_ref)

    with pytest.raises(ValueError, match="neither requested nor derived"):
        resolver.resolve(
            context,
            nominations=(AttentionNomination("crystal:not-present"),),
        )
