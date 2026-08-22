"""Lossless deterministic decomposition of oversized workspace objects."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from fresta_diamond.attention_projection import estimated_tokens
from fresta_diamond.cognitive_workspace import (
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetRevisionRef,
    SheetState,
)
from fresta_diamond.sheet_hierarchy import (
    MotherSheetOutcome,
    MotherSheetService,
    SheetSnippet,
)


DECOMPOSITION_AUTHORITY = "UNVALIDATED_WORKSPACE_DECOMPOSITION"


@dataclass(frozen=True)
class SheetDecompositionOutcome:
    """Hash-bound tree whose ordered leaves reproduce one source exactly."""

    decomposition_id: str
    source_ref: str
    source_sha256: str
    authority: str
    root: MotherSheetOutcome
    leaf_refs: tuple[SheetRevisionRef, ...]
    index_refs: tuple[SheetRevisionRef, ...]
    max_child_content_tokens: int

    def __post_init__(self) -> None:
        if not self.decomposition_id.strip() or not self.source_ref.strip():
            raise ValueError("Decomposition and source references are required")
        if self.authority != DECOMPOSITION_AUTHORITY:
            raise ValueError("A decomposition cannot grant itself authority")
        if len(self.source_sha256) != 64:
            raise ValueError("Source SHA-256 is invalid")
        if not self.leaf_refs:
            raise ValueError("A decomposition requires at least one leaf")
        if self.max_child_content_tokens < 1:
            raise ValueError("Child content token budget must be positive")


@dataclass(frozen=True)
class SheetDecompositionService:
    """Store an exact source in bounded leaves and hash-bound index sheets.

    The budget applies to leaf *content*. Attention rendering adds metadata, so
    callers should reserve prompt overhead when choosing this value.
    """

    workspace: JsonlCognitiveWorkspace

    def decompose(
        self,
        *,
        content: str,
        source_ref: str,
        mother_sheet_id: str,
        mother_revision_id: str,
        title: str,
        scope: str,
        max_child_content_tokens: int,
        max_children_per_index: int = 32,
        objective_ref: str | None = None,
        decomposition_id: str | None = None,
        author_ref: str = "actor:workspace-decomposition",
    ) -> SheetDecompositionOutcome:
        if not content.strip():
            raise ValueError("Decomposition source requires semantic content")
        for label, value in (
            ("source reference", source_ref),
            ("mother sheet ID", mother_sheet_id),
            ("mother revision ID", mother_revision_id),
            ("title", title),
            ("scope", scope),
        ):
            if not value.strip():
                raise ValueError(f"Decomposition {label} is required")
        if max_child_content_tokens < 1:
            raise ValueError("Child content token budget must be positive")
        if max_children_per_index < 2:
            raise ValueError("An index must allow at least two children")
        identity = decomposition_id or str(uuid4())
        if not identity.strip():
            raise ValueError("Decomposition ID is required")

        chunks = _lossless_chunks(content, max_child_content_tokens)
        leaf_ids = tuple(
            f"{mother_sheet_id}:leaf:{index:06d}"
            for index in range(1, len(chunks) + 1)
        )
        index_ids = _planned_index_ids(
            mother_sheet_id,
            len(chunks),
            max_children_per_index,
        )
        self._ensure_new_ids((mother_sheet_id, *leaf_ids, *index_ids))

        source_hash = sha256(content.encode("utf-8")).hexdigest()
        common_provenance = (
            source_ref,
            f"source-sha256:{source_hash}",
            f"authority:{DECOMPOSITION_AUTHORITY}",
            f"decomposition:{identity}",
        )
        leaf_refs: list[SheetRevisionRef] = []
        for ordinal, (sheet_id, chunk) in enumerate(
            zip(leaf_ids, chunks, strict=True),
            start=1,
        ):
            revision_id = f"{sheet_id}:revision:1"
            revision = SheetRevision(
                sheet_id=sheet_id,
                revision_id=revision_id,
                revision_number=1,
                title=f"{title} — part {ordinal}/{len(chunks)}",
                state=SheetState.DRAFT,
                elements=(SheetElement(
                    element_id=f"content:{ordinal:06d}",
                    kind=SheetElementKind.NOTE,
                    content=chunk,
                    scope=scope,
                    provenance=(
                        *common_provenance,
                        f"part:{ordinal}/{len(chunks)}",
                    ),
                ),),
                objective_ref=objective_ref,
                author_ref=author_ref,
            )
            self.workspace.save(revision)
            leaf_refs.append(self.workspace.reference(sheet_id, revision_id))

        hierarchy = MotherSheetService(self.workspace)
        current = tuple(leaf_refs)
        index_refs: list[SheetRevisionRef] = []
        level = 1
        while len(current) > max_children_per_index:
            next_level: list[SheetRevisionRef] = []
            for group_number, start in enumerate(
                range(0, len(current), max_children_per_index),
                start=1,
            ):
                group = current[start:start + max_children_per_index]
                sheet_id = (
                    f"{mother_sheet_id}:level:{level}:group:{group_number:06d}"
                )
                branch = self._create_index(
                    service=hierarchy,
                    refs=group,
                    sheet_id=sheet_id,
                    revision_id=f"{sheet_id}:revision:1",
                    title=f"{title} — index level {level}, group {group_number}",
                    scope=scope,
                    source_ref=source_ref,
                    source_hash=source_hash,
                    decomposition_id=identity,
                    objective_ref=objective_ref,
                    author_ref=author_ref,
                )
                index_refs.append(branch.reference)
                next_level.append(branch.reference)
            current = tuple(next_level)
            level += 1

        root = self._create_index(
            service=hierarchy,
            refs=current,
            sheet_id=mother_sheet_id,
            revision_id=mother_revision_id,
            title=title,
            scope=scope,
            source_ref=source_ref,
            source_hash=source_hash,
            decomposition_id=identity,
            objective_ref=objective_ref,
            author_ref=author_ref,
        )
        outcome = SheetDecompositionOutcome(
            decomposition_id=identity,
            source_ref=source_ref,
            source_sha256=source_hash,
            authority=DECOMPOSITION_AUTHORITY,
            root=root,
            leaf_refs=tuple(leaf_refs),
            index_refs=tuple(index_refs),
            max_child_content_tokens=max_child_content_tokens,
        )
        self.reconstruct(outcome)
        return outcome

    def reconstruct(self, outcome: SheetDecompositionOutcome) -> str:
        """Resolve exact leaves, preserve their order, and verify source hash."""

        chunks: list[str] = []
        for reference in outcome.leaf_refs:
            revision = self.workspace.resolve_reference(reference.target_ref)
            if len(revision.elements) != 1:
                raise CognitiveWorkspaceError(
                    "A decomposition leaf must contain exactly one element"
                )
            element = revision.elements[0]
            if element.kind is not SheetElementKind.NOTE:
                raise CognitiveWorkspaceError(
                    "A decomposition leaf has an unexpected element kind"
                )
            if f"source-sha256:{outcome.source_sha256}" not in element.provenance:
                raise CognitiveWorkspaceError(
                    "A decomposition leaf has incompatible provenance"
                )
            chunks.append(element.content)
        content = "".join(chunks)
        actual = sha256(content.encode("utf-8")).hexdigest()
        if actual != outcome.source_sha256:
            raise CognitiveWorkspaceError(
                "Decomposition reconstruction does not match its source hash"
            )
        return content

    def _create_index(
        self,
        *,
        service: MotherSheetService,
        refs: tuple[SheetRevisionRef, ...],
        sheet_id: str,
        revision_id: str,
        title: str,
        scope: str,
        source_ref: str,
        source_hash: str,
        decomposition_id: str,
        objective_ref: str | None,
        author_ref: str,
    ) -> MotherSheetOutcome:
        snippets = tuple(
            SheetSnippet(
                snippet_id=f"snippet:{index:06d}",
                content=_reference_preview(self.workspace, reference, index, len(refs)),
                scope=scope,
                child_ref=reference,
                provenance=(
                    source_ref,
                    f"source-sha256:{source_hash}",
                    f"authority:{DECOMPOSITION_AUTHORITY}",
                    f"decomposition:{decomposition_id}",
                ),
            )
            for index, reference in enumerate(refs, start=1)
        )
        return service.create(
            sheet_id=sheet_id,
            revision_id=revision_id,
            title=title,
            scope=scope,
            snippets=snippets,
            objective_ref=objective_ref,
            author_ref=author_ref,
        )

    def _ensure_new_ids(self, sheet_ids: tuple[str, ...]) -> None:
        if len(sheet_ids) != len(set(sheet_ids)):
            raise ValueError("Decomposition generated duplicate sheet IDs")
        existing = {item.sheet_id for item in self.workspace.latest_revisions()}
        collisions = sorted(existing.intersection(sheet_ids))
        if collisions:
            raise CognitiveWorkspaceError(
                f"Decomposition sheet already exists: {collisions[0]}"
            )


def _lossless_chunks(content: str, max_tokens: int) -> tuple[str, ...]:
    max_bytes = max_tokens * 4
    chunks: list[str] = []
    position = 0
    while position < len(content):
        end = position
        used = 0
        while end < len(content):
            width = len(content[end].encode("utf-8"))
            if used + width > max_bytes:
                break
            used += width
            end += 1
        if end == position:
            raise ValueError("Token budget cannot contain the next Unicode character")

        candidate = content[position:end]
        if end < len(content):
            minimum = position + max(1, (end - position) // 2)
            preferred = max(
                candidate.rfind("\n", minimum - position),
                candidate.rfind(" ", minimum - position),
                candidate.rfind("\t", minimum - position),
            )
            if preferred >= 0:
                end = position + preferred + 1
                candidate = content[position:end]

        if not candidate.strip():
            probe = end
            while probe < len(content) and content[probe].isspace():
                probe += 1
            if probe < len(content):
                probe += 1
            expanded = content[position:probe]
            if not expanded.strip() or len(expanded.encode("utf-8")) > max_bytes:
                raise ValueError(
                    "Whitespace run cannot fit a non-empty decomposition leaf"
                )
            end = probe
            candidate = expanded
        chunks.append(candidate)
        position = end

    if "".join(chunks) != content:
        raise AssertionError("Lossless chunking invariant failed")
    if any(estimated_tokens(item) > max_tokens for item in chunks):
        raise AssertionError("Chunking exceeded its declared content budget")
    return tuple(chunks)


def _planned_index_ids(
    mother_sheet_id: str,
    leaf_count: int,
    max_children: int,
) -> tuple[str, ...]:
    result: list[str] = []
    count = leaf_count
    level = 1
    while count > max_children:
        groups = (count + max_children - 1) // max_children
        result.extend(
            f"{mother_sheet_id}:level:{level}:group:{group:06d}"
            for group in range(1, groups + 1)
        )
        count = groups
        level += 1
    return tuple(result)


def _reference_preview(
    workspace: JsonlCognitiveWorkspace,
    reference: SheetRevisionRef,
    index: int,
    total: int,
) -> str:
    revision = workspace.resolve_reference(reference.target_ref)
    text = " ".join(item.content.strip() for item in revision.elements)
    compact = " ".join(text.split())
    preview = compact[:160]
    if len(compact) > 160:
        preview += "…"
    return f"Part {index}/{total}: {preview}"
