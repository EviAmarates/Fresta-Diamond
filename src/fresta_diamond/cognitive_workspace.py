"""Revisioned cognitive sheets with no authority to confirm their contents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol
from uuid import uuid4

from fresta_diamond.contracts import Artifact


SHEET_REVISION_SCHEMA = "fresta://cognitive-sheet-revision@1"
WORKSPACE_SELECTION_SCHEMA = "artifact://workspace-selection@1"
SHEET_CHILD_RELATION = "scope-child"
_SHEET_HASH_SEPARATOR = ":sha256:"


class SheetState(str, Enum):
    DRAFT = "DRAFT"
    STAGED = "STAGED"
    PROPOSED = "PROPOSED"


class SheetElementKind(str, Enum):
    NOTE = "NOTE"
    SNIPPET = "SNIPPET"
    WORKING_REPRESENTATION = "WORKING_REPRESENTATION"
    CLAIM = "CLAIM"
    HYPOTHESIS = "HYPOTHESIS"
    RELATION = "RELATION"
    QUESTION = "QUESTION"
    CONCEPT = "CONCEPT"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    USER_MESSAGE = "USER_MESSAGE"
    ASSISTANT_MESSAGE = "ASSISTANT_MESSAGE"


@dataclass(frozen=True)
class SheetElement:
    element_id: str
    kind: SheetElementKind
    content: str
    scope: str
    provenance: tuple[str, ...] = ()
    contextual_roles: tuple[int, ...] = ()
    language: str | None = None

    def __post_init__(self) -> None:
        if not self.element_id.strip() or not self.content.strip() or not self.scope.strip():
            raise ValueError("Sheet element ID, content, and scope are required")
        if not set(self.contextual_roles).issubset({1, 2, 3}):
            raise ValueError("Contextual roles must be a subset of O1/O2/O3")
        if self.language is not None and not self.language.strip():
            raise ValueError("Sheet element language cannot be empty")


@dataclass(frozen=True)
class SheetLink:
    link_id: str
    source_element_id: str | None
    target_ref: str
    relation: str

    def __post_init__(self) -> None:
        if not self.link_id.strip() or not self.target_ref.strip() or not self.relation.strip():
            raise ValueError("Sheet link ID, target, and relation are required")
        if self.source_element_id is not None and not self.source_element_id.strip():
            raise ValueError("Source element ID cannot be empty")


@dataclass(frozen=True)
class SheetRevision:
    sheet_id: str
    revision_number: int
    title: str
    state: SheetState
    elements: tuple[SheetElement, ...]
    links: tuple[SheetLink, ...] = ()
    parent_revision_id: str | None = None
    objective_ref: str | None = None
    author_ref: str = "actor:workspace"
    revision_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not self.sheet_id.strip() or not self.revision_id.strip():
            raise ValueError("Sheet and revision IDs are required")
        if self.revision_number < 1:
            raise ValueError("Sheet revision number must be positive")
        if not self.title.strip() or not self.author_ref.strip():
            raise ValueError("Sheet title and author are required")
        element_ids = [item.element_id for item in self.elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("Sheet revision contains duplicate element IDs")
        link_ids = [item.link_id for item in self.links]
        if len(link_ids) != len(set(link_ids)):
            raise ValueError("Sheet revision contains duplicate link IDs")
        known_elements = set(element_ids)
        if any(
            link.source_element_id is not None
            and link.source_element_id not in known_elements
            for link in self.links
        ):
            raise ValueError("Sheet link references an unknown source element")


@dataclass(frozen=True)
class SheetBacklink:
    target_ref: str
    source_sheet_id: str
    source_revision_id: str
    source_element_id: str | None
    relation: str


@dataclass(frozen=True)
class SheetRevisionRef:
    sheet_id: str
    revision_id: str
    revision_number: int
    content_hash: str

    def __post_init__(self) -> None:
        if not self.sheet_id.strip() or not self.revision_id.strip():
            raise ValueError("Sheet revision reference IDs are required")
        if self.revision_number < 1:
            raise ValueError("Sheet revision reference number must be positive")
        if (
            len(self.content_hash) != 64
            or any(item not in "0123456789abcdef" for item in self.content_hash)
        ):
            raise ValueError("Sheet revision reference hash is invalid")

    @property
    def target_ref(self) -> str:
        return (
            f"sheet-revision:{self.revision_id}"
            f"{_SHEET_HASH_SEPARATOR}{self.content_hash}"
        )


@dataclass(frozen=True)
class SheetChildStatus:
    linked: SheetRevisionRef
    latest: SheetRevisionRef

    @property
    def stale(self) -> bool:
        return self.linked != self.latest


@dataclass(frozen=True)
class WorkspaceSelection:
    sheet_id: str
    revision_id: str
    element_ids: tuple[str, ...]
    objective: str
    selection_id: str = field(default_factory=lambda: str(uuid4()))
    authority: str = "UNVALIDATED_WORKSPACE_PROPOSAL"

    def __post_init__(self) -> None:
        if not self.element_ids:
            raise ValueError("A workspace selection requires at least one element")
        if not self.objective.strip():
            raise ValueError("A workspace selection requires a bounded objective")
        if self.authority != "UNVALIDATED_WORKSPACE_PROPOSAL":
            raise ValueError("A workspace selection cannot grant itself authority")


class CognitiveWorkspaceError(RuntimeError):
    """A sheet history could not be stored or verified."""


class CognitiveWorkspace(Protocol):
    def save(self, revision: SheetRevision) -> str:
        """Append one valid sheet revision and return its content hash."""

    def latest(self, sheet_id: str) -> SheetRevision:
        """Return the latest verified revision of one sheet."""

    def latest_revisions(self) -> tuple[SheetRevision, ...]:
        """Return one verified latest revision per known sheet."""

    def reference(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> SheetRevisionRef:
        """Return one hash-bound exact revision reference."""

    def resolve_reference(self, target_ref: str) -> SheetRevision:
        """Resolve and verify one hash-bound exact revision reference."""

    def children(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> tuple[SheetRevisionRef, ...]:
        """Return the exact child revisions linked by one mother revision."""

    def child_statuses(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> tuple[SheetChildStatus, ...]:
        """Compare linked child snapshots with each child's latest revision."""


class JsonlCognitiveWorkspace:
    """Single-process append-only sheet history with a global hash chain."""

    def __init__(
        self,
        root: str | Path,
        *,
        filename: str = "sheet-revisions.jsonl",
    ) -> None:
        self._root = Path(root)
        self._path = self._root / filename
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def save(self, revision: SheetRevision) -> str:
        with self._lock:
            records = self._read_verified_unlocked()
            revisions = tuple(item[0] for item in records)
            if any(item.revision_id == revision.revision_id for item in revisions):
                raise CognitiveWorkspaceError(
                    f"Revision already exists: {revision.revision_id}"
                )
            history = tuple(
                item for item in records if item[0].sheet_id == revision.sheet_id
            )
            self._validate_successor(revision, history)
            self._validate_hierarchy_links(revision, records)
            previous_record_hash = records[-1][1] if records else None
            parent_hash = history[-1][1] if history else None
            body = {
                **encode_sheet_revision(revision),
                "previous_record_hash": previous_record_hash,
                "parent_revision_hash": parent_hash,
            }
            content_hash = _hash_body(body)
            record = {**body, "content_hash": content_hash}
            try:
                self._root.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(_canonical_json(record) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except (OSError, TypeError, ValueError) as exc:
                raise CognitiveWorkspaceError(
                    f"Could not persist sheet revision: {type(exc).__name__}"
                ) from exc
            return content_hash

    def latest(self, sheet_id: str) -> SheetRevision:
        history = self.history(sheet_id)
        if not history:
            raise CognitiveWorkspaceError(f"Unknown sheet: {sheet_id}")
        return history[-1]

    def history(self, sheet_id: str) -> tuple[SheetRevision, ...]:
        with self._lock:
            records = self._read_verified_unlocked()
        return tuple(
            revision for revision, _content_hash in records
            if revision.sheet_id == sheet_id
        )

    def latest_revisions(self) -> tuple[SheetRevision, ...]:
        with self._lock:
            records = self._read_verified_unlocked()
        latest: dict[str, SheetRevision] = {}
        for revision, _content_hash in records:
            latest[revision.sheet_id] = revision
        return tuple(latest[key] for key in sorted(latest))

    def reference(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> SheetRevisionRef:
        if not sheet_id.strip():
            raise ValueError("Sheet ID is required")
        with self._lock:
            records = self._read_verified_unlocked()
        matches = tuple(
            (revision, content_hash)
            for revision, content_hash in records
            if revision.sheet_id == sheet_id
            and (revision_id is None or revision.revision_id == revision_id)
        )
        if not matches:
            raise CognitiveWorkspaceError(
                f"Unknown sheet revision: {sheet_id}:{revision_id or 'latest'}"
            )
        revision, content_hash = matches[-1]
        return SheetRevisionRef(
            revision.sheet_id,
            revision.revision_id,
            revision.revision_number,
            content_hash,
        )

    def resolve_reference(self, target_ref: str) -> SheetRevision:
        revision_id, expected_hash = decode_sheet_revision_target(target_ref)
        with self._lock:
            records = self._read_verified_unlocked()
        matches = tuple(
            revision
            for revision, content_hash in records
            if revision.revision_id == revision_id
            and content_hash == expected_hash
        )
        if len(matches) != 1:
            raise CognitiveWorkspaceError(
                "Sheet revision reference is missing or has a stale hash"
            )
        return matches[0]

    def children(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> tuple[SheetRevisionRef, ...]:
        parent = (
            self.latest(sheet_id)
            if revision_id is None
            else next((
                item for item in self.history(sheet_id)
                if item.revision_id == revision_id
            ), None)
        )
        if parent is None:
            raise CognitiveWorkspaceError(
                f"Unknown sheet revision: {sheet_id}:{revision_id}"
            )
        result = []
        for link in parent.links:
            if link.relation != SHEET_CHILD_RELATION:
                continue
            child = self.resolve_reference(link.target_ref)
            result.append(self.reference(child.sheet_id, child.revision_id))
        return tuple(result)

    def child_statuses(
        self,
        sheet_id: str,
        revision_id: str | None = None,
    ) -> tuple[SheetChildStatus, ...]:
        return tuple(
            SheetChildStatus(child, self.reference(child.sheet_id))
            for child in self.children(sheet_id, revision_id)
        )

    def backlinks(
        self,
        target_ref: str,
        *,
        include_history: bool = False,
    ) -> tuple[SheetBacklink, ...]:
        if not target_ref.strip():
            raise ValueError("Backlink target is required")
        with self._lock:
            records = self._read_verified_unlocked()
        revisions = tuple(item[0] for item in records)
        if not include_history:
            latest: dict[str, SheetRevision] = {}
            for revision in revisions:
                latest[revision.sheet_id] = revision
            revisions = tuple(latest.values())
        result = [
            SheetBacklink(
                target_ref=link.target_ref,
                source_sheet_id=revision.sheet_id,
                source_revision_id=revision.revision_id,
                source_element_id=link.source_element_id,
                relation=link.relation,
            )
            for revision in revisions
            for link in revision.links
            if link.target_ref == target_ref
        ]
        return tuple(sorted(
            result,
            key=lambda item: (
                item.source_sheet_id,
                item.source_revision_id,
                item.source_element_id or "",
            ),
        ))

    def select(
        self,
        sheet_id: str,
        element_ids: tuple[str, ...],
        *,
        objective: str,
    ) -> tuple[WorkspaceSelection, Artifact]:
        revision = self.latest(sheet_id)
        selected_ids = tuple(dict.fromkeys(element_ids))
        by_id = {item.element_id: item for item in revision.elements}
        unknown = set(selected_ids) - set(by_id)
        if unknown:
            raise CognitiveWorkspaceError(
                f"Selection contains unknown elements: {sorted(unknown)}"
            )
        selection = WorkspaceSelection(
            sheet_id=sheet_id,
            revision_id=revision.revision_id,
            element_ids=selected_ids,
            objective=objective,
        )
        artifact = Artifact(
            schema=WORKSPACE_SELECTION_SCHEMA,
            payload={
                "selection_id": selection.selection_id,
                "sheet_id": sheet_id,
                "revision_id": revision.revision_id,
                "objective": objective,
                "authority": selection.authority,
                "elements": [
                    {
                        "element_id": by_id[item].element_id,
                        "kind": by_id[item].kind.value,
                        "content": by_id[item].content,
                        "scope": by_id[item].scope,
                        "provenance": list(by_id[item].provenance),
                        "contextual_roles": list(by_id[item].contextual_roles),
                        "language": by_id[item].language,
                    }
                    for item in selected_ids
                ],
            },
            provenance=(
                f"sheet:{sheet_id}",
                f"sheet-revision:{revision.revision_id}",
            ),
        )
        return selection, artifact

    @staticmethod
    def _validate_successor(
        revision: SheetRevision,
        history: tuple[tuple[SheetRevision, str], ...],
    ) -> None:
        if not history:
            if revision.revision_number != 1 or revision.parent_revision_id is not None:
                raise CognitiveWorkspaceError(
                    "A new sheet must begin at revision 1 without a parent"
                )
            return
        parent = history[-1][0]
        if revision.revision_number != parent.revision_number + 1:
            raise CognitiveWorkspaceError("Sheet revision number is not contiguous")
        if revision.parent_revision_id != parent.revision_id:
            raise CognitiveWorkspaceError("Sheet revision does not extend its latest parent")
        allowed = {
            SheetState.DRAFT: {SheetState.DRAFT, SheetState.STAGED},
            SheetState.STAGED: {SheetState.STAGED, SheetState.PROPOSED},
            SheetState.PROPOSED: {SheetState.PROPOSED},
        }
        if revision.state not in allowed[parent.state]:
            raise CognitiveWorkspaceError(
                f"Invalid sheet state transition: {parent.state.value} -> "
                f"{revision.state.value}"
            )

    @staticmethod
    def _validate_hierarchy_links(
        revision: SheetRevision,
        records: tuple[tuple[SheetRevision, str], ...],
    ) -> None:
        by_target = {
            SheetRevisionRef(
                item.sheet_id,
                item.revision_id,
                item.revision_number,
                content_hash,
            ).target_ref: item
            for item, content_hash in records
        }
        for link in revision.links:
            if link.relation != SHEET_CHILD_RELATION:
                continue
            child = by_target.get(link.target_ref)
            if child is None:
                raise CognitiveWorkspaceError(
                    "Scope-child link must target an existing exact revision"
                )
            if child.sheet_id == revision.sheet_id:
                raise CognitiveWorkspaceError(
                    "A sheet cannot be its own scope child"
                )

    def _read_verified_unlocked(
        self,
    ) -> tuple[tuple[SheetRevision, str], ...]:
        if not self._path.exists():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CognitiveWorkspaceError(
                f"Could not read sheet history: {type(exc).__name__}"
            ) from exc
        records: list[tuple[SheetRevision, str]] = []
        previous_hash: str | None = None
        latest_by_sheet: dict[str, tuple[SheetRevision, str]] = {}
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise CognitiveWorkspaceError(
                    f"Empty sheet record at line {line_number}"
                )
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("record is not an object")
                content_hash = record.pop("content_hash")
                if not isinstance(content_hash, str):
                    raise TypeError("content_hash is not text")
                if _hash_body(record) != content_hash:
                    raise CognitiveWorkspaceError(
                        f"Sheet history hash mismatch at line {line_number}"
                    )
                if record.get("previous_record_hash") != previous_hash:
                    raise CognitiveWorkspaceError(
                        f"Sheet history chain mismatch at line {line_number}"
                    )
                revision = decode_sheet_revision(record)
                parent = latest_by_sheet.get(revision.sheet_id)
                expected_parent_hash = parent[1] if parent else None
                if record.get("parent_revision_hash") != expected_parent_hash:
                    raise CognitiveWorkspaceError(
                        f"Sheet parent hash mismatch at line {line_number}"
                    )
                self._validate_successor(
                    revision,
                    (parent,) if parent is not None else (),
                )
            except CognitiveWorkspaceError:
                raise
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise CognitiveWorkspaceError(
                    f"Malformed sheet record at line {line_number}: {exc}"
                ) from exc
            records.append((revision, content_hash))
            latest_by_sheet[revision.sheet_id] = (revision, content_hash)
            previous_hash = content_hash
        return tuple(records)


def encode_sheet_revision(revision: SheetRevision) -> dict[str, Any]:
    return {
        "schema": SHEET_REVISION_SCHEMA,
        "sheet_id": revision.sheet_id,
        "revision_id": revision.revision_id,
        "revision_number": revision.revision_number,
        "parent_revision_id": revision.parent_revision_id,
        "created_at": revision.created_at,
        "title": revision.title,
        "state": revision.state.value,
        "objective_ref": revision.objective_ref,
        "author_ref": revision.author_ref,
        "elements": [
            {
                "element_id": item.element_id,
                "kind": item.kind.value,
                "content": item.content,
                "scope": item.scope,
                "provenance": list(item.provenance),
                "contextual_roles": list(item.contextual_roles),
                "language": item.language,
            }
            for item in revision.elements
        ],
        "links": [
            {
                "link_id": item.link_id,
                "source_element_id": item.source_element_id,
                "target_ref": item.target_ref,
                "relation": item.relation,
            }
            for item in revision.links
        ],
    }


def decode_sheet_revision(value: Mapping[str, Any]) -> SheetRevision:
    if value.get("schema") != SHEET_REVISION_SCHEMA:
        raise ValueError("unknown cognitive sheet schema")
    return SheetRevision(
        sheet_id=_text(value, "sheet_id"),
        revision_id=_text(value, "revision_id"),
        revision_number=_integer(value, "revision_number"),
        parent_revision_id=_optional_text(value, "parent_revision_id"),
        created_at=_text(value, "created_at"),
        title=_text(value, "title"),
        state=SheetState(_text(value, "state")),
        objective_ref=_optional_text(value, "objective_ref"),
        author_ref=_text(value, "author_ref"),
        elements=tuple(
            SheetElement(
                element_id=_text(item, "element_id"),
                kind=SheetElementKind(_text(item, "kind")),
                content=_text(item, "content"),
                scope=_text(item, "scope"),
                provenance=_text_tuple(item, "provenance"),
                contextual_roles=_integer_tuple(item, "contextual_roles"),
                language=_optional_text(item, "language"),
            )
            for item in _object_array(value, "elements")
        ),
        links=tuple(
            SheetLink(
                link_id=_text(item, "link_id"),
                source_element_id=_optional_text(item, "source_element_id"),
                target_ref=_text(item, "target_ref"),
                relation=_text(item, "relation"),
            )
            for item in _object_array(value, "links")
        ),
    )


def decode_sheet_revision_target(target_ref: str) -> tuple[str, str]:
    prefix = "sheet-revision:"
    if not isinstance(target_ref, str) or not target_ref.startswith(prefix):
        raise ValueError("Sheet revision target ref is invalid")
    body = target_ref.removeprefix(prefix)
    if _SHEET_HASH_SEPARATOR not in body:
        raise ValueError("Sheet revision target ref has no content hash")
    revision_id, content_hash = body.rsplit(_SHEET_HASH_SEPARATOR, 1)
    SheetRevisionRef("placeholder", revision_id, 1, content_hash)
    return revision_id, content_hash


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text or null")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise TypeError(f"{key} must be an integer")
    return item


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise TypeError(f"{key} is not an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid text")
    return tuple(items)


def _integer_tuple(value: Mapping[str, Any], key: str) -> tuple[int, ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise TypeError(f"{key} is not an array")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in items):
        raise TypeError(f"{key} contains a non-integer")
    return tuple(items)


def _object_array(
    value: Mapping[str, Any],
    key: str,
) -> tuple[Mapping[str, Any], ...]:
    items = value.get(key)
    if not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
        raise TypeError(f"{key} must be an array of objects")
    return tuple(items)
