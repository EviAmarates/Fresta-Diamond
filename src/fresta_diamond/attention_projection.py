"""Objective-relative, dependency-preserving attention projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from math import ceil, isfinite
from hashlib import sha256

from fresta_diamond.attention_memory import (
    AttentionContextRevision,
    AttentionState,
)


class AttentionItemKind(str, Enum):
    CHECKPOINT = "CHECKPOINT"
    REMAINDER = "REMAINDER"
    CONCEPT = "CONCEPT"
    CRYSTAL = "CRYSTAL"
    WORKSPACE = "WORKSPACE"
    SOURCE = "SOURCE"
    PHI_MINUS = "PHI_MINUS"
    NOTE = "NOTE"


class AttentionEvidenceState(str, Enum):
    VALIDATED = "VALIDATED"
    PROVISIONAL = "PROVISIONAL"
    DEFERRED = "DEFERRED"
    NEGATIVE = "NEGATIVE"
    UNVALIDATED_WORKSPACE = "UNVALIDATED_WORKSPACE"


class AttentionProjectionState(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class AttentionCandidate:
    item_ref: str
    kind: AttentionItemKind
    content: str
    scope: str
    authority: str
    evidence_state: AttentionEvidenceState
    relevance: float
    contextual_roles: tuple[int, ...] = ()
    dependency_refs: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((
            self.item_ref.strip(),
            self.content.strip(),
            self.scope.strip(),
            self.authority.strip(),
        )):
            raise ValueError("Attention candidate fields are required")
        if not isfinite(self.relevance) or not 0 <= self.relevance <= 1:
            raise ValueError("Attention relevance must be between zero and one")
        if not set(self.contextual_roles).issubset({1, 2, 3}):
            raise ValueError("Contextual roles must be O1/O2/O3")
        if len(self.contextual_roles) != len(set(self.contextual_roles)):
            raise ValueError("Contextual roles must be unique")
        if len(self.dependency_refs) != len(set(self.dependency_refs)):
            raise ValueError("Attention dependencies must be unique")
        if self.item_ref in self.dependency_refs:
            raise ValueError("Attention candidate cannot depend on itself")
        for values in (self.dependency_refs, self.provenance):
            if any(not value.strip() for value in values):
                raise ValueError("Attention references cannot be empty")


@dataclass(frozen=True)
class ProjectedAttentionItem:
    item_ref: str
    kind: AttentionItemKind
    content: str
    authority: str
    evidence_state: AttentionEvidenceState
    contextual_roles: tuple[int, ...]
    dependency_refs: tuple[str, ...]
    provenance: tuple[str, ...]
    estimated_tokens: int


@dataclass(frozen=True)
class AttentionProjectionCheckpoint:
    checkpoint_id: str
    context_ref: str
    completed_refs: tuple[str, ...]
    pending_refs: tuple[str, ...]
    blocked_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    token_budget: int
    authority: str = "ATTENTION_CONTINUATION_ONLY"

    def __post_init__(self) -> None:
        if not self.checkpoint_id.strip() or not self.context_ref.strip():
            raise ValueError("Attention projection checkpoint IDs are required")
        if not self.pending_refs and not self.blocked_refs:
            raise ValueError("Continuation checkpoint requires unfinished work")
        if self.authority != "ATTENTION_CONTINUATION_ONLY":
            raise PermissionError(
                "Attention continuation cannot grant memory authority"
            )


@dataclass(frozen=True)
class AttentionProjection:
    context_ref: str
    objective: str
    scope: str
    state: AttentionProjectionState
    token_budget: int
    base_tokens: int
    used_tokens: int
    selected: tuple[ProjectedAttentionItem, ...]
    missing_required_refs: tuple[str, ...]
    unresolved_optional_refs: tuple[str, ...]
    overflow_refs: tuple[str, ...]
    excluded_scope_refs: tuple[str, ...]
    excluded_policy_refs: tuple[str, ...]
    injection_ready: bool
    continuation_required: bool
    continuation_checkpoint: AttentionProjectionCheckpoint | None
    rendered_context: str
    authority: str = "ATTENTION_PROJECTION_ONLY"

    def __post_init__(self) -> None:
        if self.used_tokens > self.token_budget:
            raise ValueError("Attention projection exceeds its token budget")
        if self.authority != "ATTENTION_PROJECTION_ONLY":
            raise PermissionError("Attention projection cannot grant authority")
        if self.state is AttentionProjectionState.BLOCKED and self.injection_ready:
            raise ValueError("Blocked attention cannot be injected")
        if self.continuation_required != (
            self.continuation_checkpoint is not None
        ):
            raise ValueError("Attention continuation checkpoint is inconsistent")


class AttentionProjectionError(RuntimeError):
    """Candidates cannot form a safe bounded attention projection."""


class AttentionProjector:
    """Select referenced evidence in dependency-closed groups."""

    def __init__(
        self,
        *,
        token_estimator: Callable[[str], int] | None = None,
    ) -> None:
        self._estimate = token_estimator or estimated_tokens

    def project(
        self,
        context: AttentionContextRevision,
        candidates: tuple[AttentionCandidate, ...],
        *,
        token_budget: int,
    ) -> AttentionProjection:
        if context.state is not AttentionState.ACTIVE:
            raise AttentionProjectionError(
                "Only active attention may be projected into model context"
            )
        if token_budget < 32:
            raise ValueError("Attention token budget must be at least 32")
        by_ref = {item.item_ref: item for item in candidates}
        if len(by_ref) != len(candidates):
            raise AttentionProjectionError(
                "Attention candidates contain duplicate references"
            )
        referenced = self._referenced(context)
        reachable = set(referenced)
        frontier = list(referenced)
        while frontier:
            current_ref = frontier.pop()
            current = by_ref.get(current_ref)
            if current is None:
                continue
            for dependency in current.dependency_refs:
                if dependency not in reachable:
                    reachable.add(dependency)
                    frontier.append(dependency)
        invented = set(by_ref) - reachable
        if invented:
            raise AttentionProjectionError(
                "Candidates were not nominated by the attention context: "
                f"{sorted(invented)}"
            )
        base = self._render_base(context)
        base_tokens = self._estimate(base)
        if base_tokens > token_budget:
            return self._result(
                context,
                state=AttentionProjectionState.BLOCKED,
                token_budget=token_budget,
                base_tokens=base_tokens,
                selected=(),
                missing_required=(),
                unresolved_optional=(),
                overflow=(context.context_ref,),
                excluded_scope=(),
                excluded_policy=(),
                rendered="",
            )

        invalid_scope = {
            item.item_ref for item in candidates
            if item.scope != context.scope
        }
        invalid_policy = {
            item.item_ref for item in candidates
            if not self._candidate_matches_context(item, context)
        }
        excluded = invalid_scope | invalid_policy
        required = set((
            *context.selected_refs,
            *context.remainder_refs,
            *((context.checkpoint_ref,) if context.checkpoint_ref else ()),
        ))
        missing_required = (
            required - set(by_ref)
        ) | (required & excluded)
        optional_refs = referenced - required
        unresolved_optional = (
            optional_refs - set(by_ref)
        ) | (optional_refs & excluded)

        selected: list[ProjectedAttentionItem] = []
        selected_refs: set[str] = set()
        used_tokens = base_tokens
        overflow: set[str] = set()
        blocked = bool(missing_required)

        for root in self._ordered_roots(required, context, by_ref):
            if root in missing_required:
                continue
            closure, unresolved = self._dependency_closure(
                root,
                by_ref,
                context.scope,
                excluded,
            )
            if unresolved:
                missing_required.update(unresolved)
                missing_required.add(root)
                blocked = True
                continue
            group = tuple(
                item for item in closure if item.item_ref not in selected_refs
            )
            projected = tuple(self._projected(item) for item in group)
            cost = sum(item.estimated_tokens for item in projected)
            if used_tokens + cost > token_budget:
                overflow.update(item.item_ref for item in group)
                blocked = True
                continue
            selected.extend(projected)
            selected_refs.update(item.item_ref for item in group)
            used_tokens += cost

        for root in self._ordered_roots(optional_refs, context, by_ref):
            if (
                root in unresolved_optional
                or root in selected_refs
                or root in excluded
            ):
                continue
            closure, unresolved = self._dependency_closure(
                root,
                by_ref,
                context.scope,
                excluded,
            )
            if unresolved:
                unresolved_optional.update(unresolved)
                unresolved_optional.add(root)
                continue
            group = tuple(
                item for item in closure if item.item_ref not in selected_refs
            )
            projected = tuple(self._projected(item) for item in group)
            cost = sum(item.estimated_tokens for item in projected)
            if used_tokens + cost > token_budget:
                overflow.update(item.item_ref for item in group)
                continue
            selected.extend(projected)
            selected_refs.update(item.item_ref for item in group)
            used_tokens += cost

        if blocked:
            state = AttentionProjectionState.BLOCKED
        elif overflow or unresolved_optional or excluded:
            state = AttentionProjectionState.PARTIAL
        else:
            state = AttentionProjectionState.READY
        rendered = (
            self._render(base, tuple(selected))
            if state is not AttentionProjectionState.BLOCKED
            else ""
        )
        return self._result(
            context,
            state=state,
            token_budget=token_budget,
            base_tokens=base_tokens,
            selected=tuple(selected),
            missing_required=tuple(sorted(missing_required)),
            unresolved_optional=tuple(sorted(unresolved_optional)),
            overflow=tuple(sorted(overflow)),
            excluded_scope=tuple(sorted(invalid_scope)),
            excluded_policy=tuple(sorted(invalid_policy)),
            rendered=rendered,
        )

    @staticmethod
    def _referenced(context: AttentionContextRevision) -> set[str]:
        return set((
            *context.source_refs,
            *context.validated_refs,
            *context.selected_refs,
            *context.workspace_sheet_refs,
            *context.remainder_refs,
            *((context.checkpoint_ref,) if context.checkpoint_ref else ()),
        ))

    @staticmethod
    def _tier(item_ref: str, context: AttentionContextRevision) -> int:
        if item_ref == context.checkpoint_ref:
            return 0
        if item_ref in context.remainder_refs:
            return 1
        if item_ref in context.selected_refs:
            return 2
        if item_ref in context.validated_refs:
            return 3
        if item_ref in context.workspace_sheet_refs:
            return 4
        return 5

    @staticmethod
    def _candidate_matches_context(
        item: AttentionCandidate,
        context: AttentionContextRevision,
    ) -> bool:
        if (
            item.item_ref == context.checkpoint_ref
            and item.kind is not AttentionItemKind.CHECKPOINT
        ):
            return False
        if (
            item.item_ref in context.remainder_refs
            and item.kind not in {
                AttentionItemKind.REMAINDER,
                AttentionItemKind.PHI_MINUS,
            }
        ):
            return False
        if (
            item.item_ref in context.source_refs
            and item.kind is not AttentionItemKind.SOURCE
        ):
            return False
        if (
            item.item_ref in context.workspace_sheet_refs
            and item.kind is not AttentionItemKind.WORKSPACE
        ):
            return False
        if (
            item.item_ref in context.validated_refs
            and item.evidence_state is not AttentionEvidenceState.VALIDATED
        ):
            return False
        if (
            item.kind is AttentionItemKind.PHI_MINUS
            and item.evidence_state is not AttentionEvidenceState.NEGATIVE
        ):
            return False
        if (
            item.evidence_state is AttentionEvidenceState.NEGATIVE
            and item.kind not in {
                AttentionItemKind.PHI_MINUS,
                AttentionItemKind.REMAINDER,
            }
        ):
            return False
        return True

    def _ordered_roots(
        self,
        refs: set[str],
        context: AttentionContextRevision,
        by_ref: Mapping[str, AttentionCandidate],
    ) -> tuple[str, ...]:
        return tuple(sorted(
            refs,
            key=lambda item_ref: (
                self._tier(item_ref, context),
                -(
                    by_ref[item_ref].relevance
                    if item_ref in by_ref else -1
                ),
                item_ref,
            ),
        ))

    @staticmethod
    def _dependency_closure(
        root: str,
        by_ref: Mapping[str, AttentionCandidate],
        scope: str,
        excluded_refs: set[str],
    ) -> tuple[tuple[AttentionCandidate, ...], set[str]]:
        ordered: list[AttentionCandidate] = []
        visited: set[str] = set()
        visiting: set[str] = set()
        unresolved: set[str] = set()

        def visit(item_ref: str) -> None:
            if item_ref in visited or item_ref in unresolved:
                return
            if item_ref in visiting:
                raise AttentionProjectionError(
                    f"Attention dependency cycle contains {item_ref}"
                )
            item = by_ref.get(item_ref)
            if (
                item is None
                or item.scope != scope
                or item_ref in excluded_refs
            ):
                unresolved.add(item_ref)
                return
            visiting.add(item_ref)
            for dependency in sorted(item.dependency_refs):
                visit(dependency)
            visiting.remove(item_ref)
            visited.add(item_ref)
            ordered.append(item)

        visit(root)
        return tuple(ordered), unresolved

    def _projected(
        self,
        item: AttentionCandidate,
    ) -> ProjectedAttentionItem:
        rendered = self._render_item(item)
        return ProjectedAttentionItem(
            item_ref=item.item_ref,
            kind=item.kind,
            content=item.content,
            authority=item.authority,
            evidence_state=item.evidence_state,
            contextual_roles=item.contextual_roles,
            dependency_refs=item.dependency_refs,
            provenance=item.provenance,
            estimated_tokens=self._estimate("\n\n" + rendered),
        )

    @staticmethod
    def _render_base(context: AttentionContextRevision) -> str:
        return (
            f"[ATTENTION context={context.context_ref} "
            f"authority={context.authority}]\n"
            f"OBJECTIVE: {context.objective}\n"
            f"SCOPE: {context.scope}\n"
            f"CHECKPOINT SUMMARY: {context.summary}"
        )

    @staticmethod
    def _render_item(item: AttentionCandidate) -> str:
        roles = (
            ",".join(f"O{role}" for role in item.contextual_roles)
            or "UNASSIGNED"
        )
        dependencies = ",".join(item.dependency_refs) or "none"
        return (
            f"[{item.kind.value} ref={item.item_ref} roles={roles} "
            f"state={item.evidence_state.value} "
            f"authority={item.authority} dependencies={dependencies}]\n"
            f"{item.content}"
        )

    def _render(
        self,
        base: str,
        selected: tuple[ProjectedAttentionItem, ...],
    ) -> str:
        blocks = [base]
        for item in selected:
            candidate = AttentionCandidate(
                item_ref=item.item_ref,
                kind=item.kind,
                content=item.content,
                scope="render-only",
                authority=item.authority,
                evidence_state=item.evidence_state,
                relevance=0,
                contextual_roles=item.contextual_roles,
                dependency_refs=item.dependency_refs,
                provenance=item.provenance,
            )
            blocks.append(self._render_item(candidate))
        return "\n\n".join(blocks)

    @staticmethod
    def _result(
        context: AttentionContextRevision,
        *,
        state: AttentionProjectionState,
        token_budget: int,
        base_tokens: int,
        selected: tuple[ProjectedAttentionItem, ...],
        missing_required: tuple[str, ...],
        unresolved_optional: tuple[str, ...],
        overflow: tuple[str, ...],
        excluded_scope: tuple[str, ...],
        excluded_policy: tuple[str, ...],
        rendered: str,
    ) -> AttentionProjection:
        selected_refs = tuple(item.item_ref for item in selected)
        pending_refs = tuple(sorted(set(overflow)))
        blocked_refs = tuple(sorted(set((
            *missing_required,
            *unresolved_optional,
            *excluded_scope,
            *excluded_policy,
        ))))
        reasons: list[str] = []
        if overflow:
            reasons.append("TOKEN_BUDGET")
        if missing_required:
            reasons.append("MISSING_REQUIRED")
        if unresolved_optional:
            reasons.append("UNRESOLVED_OPTIONAL")
        if excluded_scope:
            reasons.append("SCOPE_MISMATCH")
        if excluded_policy:
            reasons.append("EVIDENCE_POLICY")
        continuation = None
        if state is not AttentionProjectionState.READY:
            checkpoint_body = "|".join((
                context.context_ref,
                str(token_budget),
                ",".join(selected_refs),
                ",".join(pending_refs),
                ",".join(blocked_refs),
                ",".join(reasons),
            ))
            continuation = AttentionProjectionCheckpoint(
                checkpoint_id=(
                    "attention-projection:"
                    + sha256(checkpoint_body.encode("utf-8")).hexdigest()[:24]
                ),
                context_ref=context.context_ref,
                completed_refs=selected_refs,
                pending_refs=pending_refs,
                blocked_refs=blocked_refs,
                reasons=tuple(reasons),
                token_budget=token_budget,
            )
        return AttentionProjection(
            context_ref=context.context_ref,
            objective=context.objective,
            scope=context.scope,
            state=state,
            token_budget=token_budget,
            base_tokens=base_tokens,
            used_tokens=(
                base_tokens
                + sum(item.estimated_tokens for item in selected)
                if base_tokens <= token_budget else 0
            ),
            selected=selected,
            missing_required_refs=tuple(missing_required),
            unresolved_optional_refs=tuple(unresolved_optional),
            overflow_refs=tuple(overflow),
            excluded_scope_refs=tuple(excluded_scope),
            excluded_policy_refs=tuple(excluded_policy),
            injection_ready=state is not AttentionProjectionState.BLOCKED,
            continuation_required=state is not AttentionProjectionState.READY,
            continuation_checkpoint=continuation,
            rendered_context=rendered,
        )


def estimated_tokens(value: str) -> int:
    """Conservative dependency-free estimate; adapters may inject a tokenizer."""

    return max(1, ceil(len(value.encode("utf-8")) / 4))
