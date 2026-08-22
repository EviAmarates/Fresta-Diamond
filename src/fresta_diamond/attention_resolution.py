"""Exact store adapters for materializing Diamond attention references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from fresta_diamond.attention_memory import AttentionContextRevision
from fresta_diamond.attention_continuation import (
    AttentionContinuationStore,
    StoredAttentionContinuationRef,
)
from fresta_diamond.attention_projection import (
    AttentionCandidate,
    AttentionEvidenceState,
    AttentionItemKind,
    AttentionProjection,
    AttentionProjector,
)
from fresta_diamond.cognitive_workspace import (
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetRevision,
)
from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptRecord,
    ConceptState,
    ConceptStoreError,
)
from fresta_diamond.crystallization import (
    CrystalState,
    LearningCrystal,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
    LearningMemoryError,
)
from fresta_diamond.phi_minus import PhiMinusObservation
from fresta_diamond.workspace import (
    CheckpointStoreError,
    JsonCheckpointStore,
    RuntimeCheckpoint,
)


class AttentionResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    WRONG_SCOPE = "WRONG_SCOPE"
    INELIGIBLE = "INELIGIBLE"
    AMBIGUOUS = "AMBIGUOUS"
    STORE_ERROR = "STORE_ERROR"


@dataclass(frozen=True)
class AttentionNomination:
    item_ref: str
    relevance: float = 0.5
    contextual_roles: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.item_ref.strip():
            raise ValueError("Attention nomination requires a reference")
        if not 0 <= self.relevance <= 1:
            raise ValueError("Attention nomination relevance is out of range")
        if not set(self.contextual_roles).issubset({1, 2, 3}):
            raise ValueError("Attention nomination roles must be O1/O2/O3")


@dataclass(frozen=True)
class AttentionResolutionDiagnostic:
    item_ref: str
    status: AttentionResolutionStatus
    resolver_id: str
    detail: str


@dataclass(frozen=True)
class ResolverResult:
    item_ref: str
    status: AttentionResolutionStatus
    resolver_id: str
    candidate: AttentionCandidate | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if (
            self.status is AttentionResolutionStatus.RESOLVED
        ) != (self.candidate is not None):
            raise ValueError("Resolver result and candidate are inconsistent")


class AttentionReferenceResolver(Protocol):
    resolver_id: str

    def resolve(
        self,
        item_ref: str,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        """Resolve one exact reference without performing semantic retrieval."""


@dataclass(frozen=True)
class AttentionResolution:
    context_ref: str
    requested_refs: tuple[str, ...]
    derived_refs: tuple[str, ...]
    candidates: tuple[AttentionCandidate, ...]
    diagnostics: tuple[AttentionResolutionDiagnostic, ...]

    @property
    def unresolved_refs(self) -> tuple[str, ...]:
        return tuple(
            item.item_ref for item in self.diagnostics
            if item.status is not AttentionResolutionStatus.RESOLVED
        )


@dataclass(frozen=True)
class AttentionMaterializedProjection:
    resolution: AttentionResolution
    projection: AttentionProjection
    stored_continuation: StoredAttentionContinuationRef | None = None


class LearningMemoryAttentionResolver:
    resolver_id = "learning-memory"

    def __init__(self, memory: AtomicDiamondLearningMemory) -> None:
        self._memory = memory

    def resolve(
        self,
        item_ref: str,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        try:
            crystals = {
                item.crystal_id: item
                for item in self._memory.crystals(
                    policy=CrystalRetrievalPolicy.AUDIT
                )
            }
            crystal = crystals.get(item_ref)
            if crystal is not None:
                return self._crystal(crystal, context, nomination)
            observations = {
                item.observation_id: item
                for item in self._memory.negative_boundary()
            }
            observation = observations.get(item_ref)
            if observation is not None:
                return self._observation(
                    observation,
                    context,
                    nomination,
                )
            return _miss(item_ref, self.resolver_id)
        except (LearningMemoryError, ValueError, TypeError) as exc:
            return _store_error(item_ref, self.resolver_id, exc)

    def _crystal(
        self,
        value: LearningCrystal,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        if value.scope != context.scope:
            return _wrong_scope(value.crystal_id, self.resolver_id, value.scope)
        states = {
            CrystalState.ACCEPTED: AttentionEvidenceState.VALIDATED,
            CrystalState.PROVISIONAL: AttentionEvidenceState.PROVISIONAL,
            CrystalState.DEFERRED: AttentionEvidenceState.DEFERRED,
        }
        evidence = states.get(value.state)
        if evidence is None:
            return ResolverResult(
                value.crystal_id,
                AttentionResolutionStatus.INELIGIBLE,
                self.resolver_id,
                detail=(
                    f"Excluded crystal state {value.state.value}; resolve its "
                    "Phi-minus observation instead"
                ),
            )
        return _resolved(
            AttentionCandidate(
                item_ref=value.crystal_id,
                kind=AttentionItemKind.CRYSTAL,
                content=value.content,
                scope=value.scope,
                authority=f"LEARNING_MEMORY:{value.state.value}",
                evidence_state=evidence,
                relevance=nomination.relevance,
                contextual_roles=nomination.contextual_roles,
                provenance=value.provenance,
            ),
            self.resolver_id,
        )

    def _observation(
        self,
        value: PhiMinusObservation,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        if value.scope != context.scope:
            return _wrong_scope(
                value.observation_id,
                self.resolver_id,
                value.scope,
            )
        content = (
            f"Negative boundary {value.disposition.value}: "
            f"{', '.join(value.reason_codes)}. "
            f"Candidate={value.candidate_ref}; "
            f"remainders={', '.join(value.remainder_kinds) or 'none'}."
        )
        return _resolved(
            AttentionCandidate(
                item_ref=value.observation_id,
                kind=AttentionItemKind.PHI_MINUS,
                content=content,
                scope=value.scope,
                authority="PHI_MINUS_AUDIT_ONLY",
                evidence_state=AttentionEvidenceState.NEGATIVE,
                relevance=nomination.relevance,
                contextual_roles=nomination.contextual_roles,
                provenance=value.provenance,
            ),
            self.resolver_id,
        )


class ConceptAttentionResolver:
    resolver_id = "concept-store"

    def __init__(self, store: AtomicConceptStore) -> None:
        self._store = store

    def resolve(
        self,
        item_ref: str,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        try:
            records = {
                item.version_ref: item for item in self._store.records()
            }
            value = records.get(item_ref)
            if value is None:
                return _miss(item_ref, self.resolver_id)
            if value.scope != context.scope:
                return _wrong_scope(item_ref, self.resolver_id, value.scope)
            if value.state in {
                ConceptState.CONTESTED,
                ConceptState.ARCHIVED,
            }:
                return ResolverResult(
                    item_ref,
                    AttentionResolutionStatus.INELIGIBLE,
                    self.resolver_id,
                    detail=f"Concept state is {value.state.value}",
                )
            evidence = (
                AttentionEvidenceState.VALIDATED
                if value.state in {
                    ConceptState.VALIDATED,
                    ConceptState.CRYSTALLIZED,
                }
                else AttentionEvidenceState.DEFERRED
            )
            return _resolved(
                AttentionCandidate(
                    item_ref=value.version_ref,
                    kind=AttentionItemKind.CONCEPT,
                    content=_concept_content(value),
                    scope=value.scope,
                    authority=f"CONCEPT_STORE:{value.state.value}",
                    evidence_state=evidence,
                    relevance=nomination.relevance,
                    contextual_roles=nomination.contextual_roles,
                    dependency_refs=tuple(
                        item.crystal_id for item in value.memberships
                    ),
                    provenance=tuple(dict.fromkeys(
                        source.source_ref
                        for seal in value.derivation_seals
                        for source in seal.sources
                    )),
                ),
                self.resolver_id,
            )
        except (ConceptStoreError, ValueError, TypeError) as exc:
            return _store_error(item_ref, self.resolver_id, exc)


class WorkspaceAttentionResolver:
    resolver_id = "cognitive-workspace"

    def __init__(self, workspace: JsonlCognitiveWorkspace) -> None:
        self._workspace = workspace

    def resolve(
        self,
        item_ref: str,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        if not (
            item_ref in context.workspace_sheet_refs
            or item_ref.startswith("sheet:")
        ):
            return _miss(item_ref, self.resolver_id)
        try:
            value = (
                self._workspace.resolve_reference(item_ref)
                if item_ref.startswith("sheet-revision:")
                else self._workspace.latest(item_ref.removeprefix("sheet:"))
            )
            scopes = {item.scope for item in value.elements}
            if scopes and scopes != {context.scope}:
                return _wrong_scope(
                    item_ref,
                    self.resolver_id,
                    ",".join(sorted(scopes)),
                )
            return _resolved(
                AttentionCandidate(
                    item_ref=item_ref,
                    kind=AttentionItemKind.WORKSPACE,
                    content=workspace_sheet_content(value),
                    scope=context.scope,
                    authority="UNVALIDATED_WORKSPACE_PROPOSAL",
                    evidence_state=(
                        AttentionEvidenceState.UNVALIDATED_WORKSPACE
                    ),
                    relevance=nomination.relevance,
                    contextual_roles=nomination.contextual_roles,
                    provenance=(f"sheet-revision:{value.revision_id}",),
                ),
                self.resolver_id,
            )
        except (CognitiveWorkspaceError, ValueError) as exc:
            if "Unknown sheet" in str(exc):
                return _miss(item_ref, self.resolver_id)
            return _store_error(item_ref, self.resolver_id, exc)


class CheckpointAttentionResolver:
    resolver_id = "checkpoint-store"

    def __init__(self, store: JsonCheckpointStore) -> None:
        self._store = store

    def resolve(
        self,
        item_ref: str,
        context: AttentionContextRevision,
        nomination: AttentionNomination,
    ) -> ResolverResult:
        checkpoint_id = context.checkpoint_ref
        if checkpoint_id is None:
            return _miss(item_ref, self.resolver_id)
        try:
            checkpoint = self._store.load(checkpoint_id)
        except CheckpointStoreError as exc:
            if "does not exist" in str(exc):
                return _miss(item_ref, self.resolver_id)
            return _store_error(item_ref, self.resolver_id, exc)
        if item_ref == checkpoint_id:
            return _resolved(
                AttentionCandidate(
                    item_ref=item_ref,
                    kind=AttentionItemKind.CHECKPOINT,
                    content=_checkpoint_content(checkpoint),
                    scope=context.scope,
                    authority="RUNTIME_CHECKPOINT",
                    evidence_state=AttentionEvidenceState.PROVISIONAL,
                    relevance=nomination.relevance,
                    contextual_roles=nomination.contextual_roles,
                    provenance=tuple(filter(None, (
                        checkpoint.previous_checkpoint_id,
                        checkpoint.journal_segment_hash,
                    ))),
                ),
                self.resolver_id,
            )
        remainders = {
            item.remainder_id: item for item in checkpoint.active_remainders
        }
        remainder = remainders.get(item_ref)
        if remainder is None:
            return _miss(item_ref, self.resolver_id)
        content = (
            f"{remainder.kind.value}: {remainder.description}. "
            f"Required for {remainder.required_for}; "
            f"resolvable={remainder.resolvable}; status={remainder.status}."
        )
        return _resolved(
            AttentionCandidate(
                item_ref=item_ref,
                kind=AttentionItemKind.REMAINDER,
                content=content,
                scope=context.scope,
                authority="TYPED_RUNTIME_REMAINDER",
                evidence_state=AttentionEvidenceState.DEFERRED,
                relevance=nomination.relevance,
                contextual_roles=nomination.contextual_roles,
                provenance=(f"checkpoint:{checkpoint.checkpoint_id}",),
            ),
            self.resolver_id,
        )


class CompositeAttentionResolver:
    def __init__(
        self,
        resolvers: tuple[AttentionReferenceResolver, ...],
    ) -> None:
        if not resolvers:
            raise ValueError("Composite attention resolver requires adapters")
        ids = [item.resolver_id for item in resolvers]
        if len(ids) != len(set(ids)):
            raise ValueError("Attention resolver IDs must be unique")
        self._resolvers = resolvers

    def resolve(
        self,
        context: AttentionContextRevision,
        *,
        nominations: tuple[AttentionNomination, ...] = (),
    ) -> AttentionResolution:
        hints = {item.item_ref: item for item in nominations}
        if len(hints) != len(nominations):
            raise ValueError("Attention nominations contain duplicate refs")
        requested = tuple(sorted(_context_refs(context)))
        queue = list(requested)
        seen: set[str] = set()
        candidates: dict[str, AttentionCandidate] = {}
        diagnostics: list[AttentionResolutionDiagnostic] = []
        derived: set[str] = set()
        while queue:
            item_ref = queue.pop(0)
            if item_ref in seen:
                continue
            seen.add(item_ref)
            nomination = hints.get(
                item_ref,
                AttentionNomination(item_ref),
            )
            attempts = tuple(
                resolver.resolve(item_ref, context, nomination)
                for resolver in self._resolvers
            )
            resolved = tuple(
                item for item in attempts
                if item.status is AttentionResolutionStatus.RESOLVED
            )
            if len(resolved) > 1:
                diagnostics.append(AttentionResolutionDiagnostic(
                    item_ref,
                    AttentionResolutionStatus.AMBIGUOUS,
                    "composite",
                    "Multiple stores resolved the same exact reference",
                ))
                continue
            if len(resolved) == 1:
                candidate = resolved[0].candidate
                assert candidate is not None
                candidates[item_ref] = candidate
                diagnostics.append(AttentionResolutionDiagnostic(
                    item_ref,
                    AttentionResolutionStatus.RESOLVED,
                    resolved[0].resolver_id,
                    resolved[0].detail,
                ))
                for dependency in candidate.dependency_refs:
                    if dependency not in seen and dependency not in queue:
                        queue.append(dependency)
                        if dependency not in requested:
                            derived.add(dependency)
                continue
            significant = tuple(
                item for item in attempts
                if item.status is not AttentionResolutionStatus.NOT_FOUND
            )
            chosen = (
                significant[0] if significant
                else ResolverResult(
                    item_ref,
                    AttentionResolutionStatus.NOT_FOUND,
                    "composite",
                    detail="No configured store owns this exact reference",
                )
            )
            diagnostics.append(AttentionResolutionDiagnostic(
                item_ref,
                chosen.status,
                chosen.resolver_id,
                chosen.detail,
            ))
        unused_hints = set(hints) - seen
        if unused_hints:
            raise ValueError(
                "Attention nominations were neither requested nor derived: "
                f"{sorted(unused_hints)}"
            )
        return AttentionResolution(
            context_ref=context.context_ref,
            requested_refs=requested,
            derived_refs=tuple(sorted(derived)),
            candidates=tuple(
                candidates[key] for key in sorted(candidates)
            ),
            diagnostics=tuple(diagnostics),
        )


class AttentionMaterializationService:
    def __init__(
        self,
        resolver: CompositeAttentionResolver,
        *,
        projector: AttentionProjector | None = None,
        continuation_store: AttentionContinuationStore | None = None,
    ) -> None:
        self._resolver = resolver
        self._projector = projector or AttentionProjector()
        self._continuation_store = continuation_store

    def materialize_and_project(
        self,
        context: AttentionContextRevision,
        *,
        token_budget: int,
        nominations: tuple[AttentionNomination, ...] = (),
    ) -> AttentionMaterializedProjection:
        resolution = self._resolver.resolve(
            context,
            nominations=nominations,
        )
        projection = self._projector.project(
            context,
            resolution.candidates,
            token_budget=token_budget,
        )
        stored = None
        if (
            projection.continuation_checkpoint is not None
            and self._continuation_store is not None
        ):
            stored = self._continuation_store.save(
                projection.continuation_checkpoint
            )
        return AttentionMaterializedProjection(
            resolution,
            projection,
            stored,
        )


def _context_refs(context: AttentionContextRevision) -> set[str]:
    return set((
        *context.source_refs,
        *context.validated_refs,
        *context.selected_refs,
        *context.workspace_sheet_refs,
        *context.remainder_refs,
        *((context.checkpoint_ref,) if context.checkpoint_ref else ()),
    ))


def _resolved(
    candidate: AttentionCandidate,
    resolver_id: str,
) -> ResolverResult:
    return ResolverResult(
        candidate.item_ref,
        AttentionResolutionStatus.RESOLVED,
        resolver_id,
        candidate=candidate,
    )


def _miss(item_ref: str, resolver_id: str) -> ResolverResult:
    return ResolverResult(
        item_ref,
        AttentionResolutionStatus.NOT_FOUND,
        resolver_id,
    )


def _wrong_scope(
    item_ref: str,
    resolver_id: str,
    actual_scope: str,
) -> ResolverResult:
    return ResolverResult(
        item_ref,
        AttentionResolutionStatus.WRONG_SCOPE,
        resolver_id,
        detail=f"Resolved object belongs to {actual_scope}",
    )


def _store_error(
    item_ref: str,
    resolver_id: str,
    exc: Exception,
) -> ResolverResult:
    return ResolverResult(
        item_ref,
        AttentionResolutionStatus.STORE_ERROR,
        resolver_id,
        detail=f"{type(exc).__name__}: {exc}",
    )


def _concept_content(value: ConceptRecord) -> str:
    signature = value.signature
    sections = (
        ("characteristics", signature.characteristics),
        ("relations", signature.relations),
        ("functions", signature.functions),
        ("constraints", signature.constraints),
        ("exclusions", signature.exclusions),
        ("examples", signature.examples),
        ("counterexamples", signature.counterexamples),
    )
    body = "\n".join(
        f"{name}: {'; '.join(items)}"
        for name, items in sections if items
    )
    aliases = ", ".join(value.aliases) or "none"
    return (
        f"Concept {value.canonical_name} ({value.state.value}); "
        f"aliases={aliases}; recognition={value.recognition_state.value}; "
        f"definition={value.definition_state.value}.\n{body}"
    )


def workspace_sheet_content(value: SheetRevision) -> str:
    """Render the exact representation injected for one workspace revision."""

    elements = "\n".join(
        f"- [{item.kind.value} {item.element_id}] {item.content}"
        for item in value.elements
    )
    return (
        f"Workspace sheet {value.title}; state={value.state.value}; "
        f"revision={value.revision_number}.\n{elements or '- empty'}"
    )


def _checkpoint_content(value: RuntimeCheckpoint) -> str:
    remaining = value.budget.remaining_operations
    return (
        f"Execution paused: {value.reason}. "
        f"Completed nodes={', '.join(value.completed_node_ids) or 'none'}; "
        f"next nodes={', '.join(value.next_node_ids) or 'none'}; "
        f"remaining operations={remaining}; "
        f"open remainders={len(value.active_remainders)}."
    )
