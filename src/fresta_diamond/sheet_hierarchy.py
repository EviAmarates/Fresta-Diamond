"""Hash-bound mother sheets, child scopes, and derived snippet status."""

from __future__ import annotations

from dataclasses import dataclass

from fresta_diamond.cognitive_workspace import (
    SHEET_CHILD_RELATION,
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetLink,
    SheetRevision,
    SheetRevisionRef,
    SheetState,
)


@dataclass(frozen=True)
class SheetSnippet:
    snippet_id: str
    content: str
    scope: str
    child_ref: SheetRevisionRef
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.snippet_id.strip() or not self.content.strip():
            raise ValueError("Sheet snippet ID and content are required")
        if not self.scope.strip():
            raise ValueError("Sheet snippet scope is required")
        if any(not item.strip() for item in self.provenance):
            raise ValueError("Sheet snippet provenance cannot be empty")


@dataclass(frozen=True)
class MotherSheetOutcome:
    revision: SheetRevision
    reference: SheetRevisionRef
    child_refs: tuple[SheetRevisionRef, ...]
    content_hash: str


@dataclass(frozen=True)
class SheetSnippetStatus:
    snippet: SheetElement
    linked: SheetRevisionRef
    latest: SheetRevisionRef

    @property
    def stale(self) -> bool:
        return self.linked != self.latest


@dataclass(frozen=True)
class MotherSheetService:
    workspace: JsonlCognitiveWorkspace

    def create(
        self,
        *,
        sheet_id: str,
        revision_id: str,
        title: str,
        scope: str,
        snippets: tuple[SheetSnippet, ...],
        objective_ref: str | None = None,
        author_ref: str = "actor:workspace-hierarchy",
        state: SheetState = SheetState.DRAFT,
    ) -> MotherSheetOutcome:
        if not snippets:
            raise ValueError("Mother sheet requires at least one child snippet")
        snippet_ids = tuple(item.snippet_id for item in snippets)
        child_targets = tuple(item.child_ref.target_ref for item in snippets)
        if len(snippet_ids) != len(set(snippet_ids)):
            raise ValueError("Mother sheet snippet IDs must be unique")
        if len(child_targets) != len(set(child_targets)):
            raise ValueError("Mother sheet child refs must be unique")
        elements = []
        links = []
        for index, snippet in enumerate(snippets, start=1):
            if snippet.scope != scope:
                raise ValueError("Mother and snippet scopes must match")
            child = self.workspace.resolve_reference(
                snippet.child_ref.target_ref
            )
            child_scopes = {item.scope for item in child.elements}
            if child_scopes and child_scopes != {scope}:
                raise CognitiveWorkspaceError(
                    "Mother and child sheet scopes do not match"
                )
            elements.append(SheetElement(
                element_id=snippet.snippet_id,
                kind=SheetElementKind.SNIPPET,
                content=snippet.content,
                scope=scope,
                provenance=tuple(dict.fromkeys((
                    snippet.child_ref.target_ref,
                    *snippet.provenance,
                ))),
            ))
            links.append(SheetLink(
                link_id=f"child:{index}:{snippet.snippet_id}",
                source_element_id=snippet.snippet_id,
                target_ref=snippet.child_ref.target_ref,
                relation=SHEET_CHILD_RELATION,
            ))
        revision = SheetRevision(
            sheet_id=sheet_id,
            revision_id=revision_id,
            revision_number=1,
            title=title,
            state=state,
            elements=tuple(elements),
            links=tuple(links),
            objective_ref=objective_ref,
            author_ref=author_ref,
        )
        content_hash = self.workspace.save(revision)
        reference = self.workspace.reference(sheet_id, revision_id)
        return MotherSheetOutcome(
            revision,
            reference,
            tuple(item.child_ref for item in snippets),
            content_hash,
        )

    def snippet_statuses(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> tuple[SheetSnippetStatus, ...]:
        mother = (
            self.workspace.latest(sheet_id)
            if revision_id is None
            else self.workspace.resolve_reference(
                self.workspace.reference(sheet_id, revision_id).target_ref
            )
        )
        by_element = {item.element_id: item for item in mother.elements}
        result = []
        for child_status, link in zip(
            self.workspace.child_statuses(sheet_id, revision_id),
            (
                item for item in mother.links
                if item.relation == SHEET_CHILD_RELATION
            ),
            strict=True,
        ):
            if link.source_element_id is None:
                raise CognitiveWorkspaceError(
                    "Mother child link has no source snippet"
                )
            snippet = by_element.get(link.source_element_id)
            if snippet is None or snippet.kind is not SheetElementKind.SNIPPET:
                raise CognitiveWorkspaceError(
                    "Mother child link does not originate from a snippet"
                )
            result.append(SheetSnippetStatus(
                snippet,
                child_status.linked,
                child_status.latest,
            ))
        return tuple(result)
