"""Persistent, bounded attention contexts over existing Diamond memory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any
from uuid import uuid4


ATTENTION_CONTEXT_SCHEMA = "fresta://diamond-attention-context@1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_UNSET = object()


class AttentionState(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"
    ABANDONED = "ABANDONED"


class AttentionTransition(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SUSPENDED = "SUSPENDED"
    REACTIVATED = "REACTIVATED"
    ARCHIVED = "ARCHIVED"
    ABANDONED = "ABANDONED"
    SUCCESSOR_PREPARED = "SUCCESSOR_PREPARED"


class AttentionReusePolicy(str, Enum):
    NOTHING = "NOTHING"
    SOURCES_ONLY = "SOURCES_ONLY"
    VALIDATED_ONLY = "VALIDATED_ONLY"
    SELECTED_ITEMS = "SELECTED_ITEMS"
    FULL_CHECKPOINT = "FULL_CHECKPOINT"


@dataclass(frozen=True)
class AttentionContextRevision:
    context_id: str
    revision_id: str
    revision_number: int
    state: AttentionState
    transition: AttentionTransition
    objective: str
    scope: str
    summary: str
    source_refs: tuple[str, ...] = ()
    validated_refs: tuple[str, ...] = ()
    selected_refs: tuple[str, ...] = ()
    workspace_sheet_refs: tuple[str, ...] = ()
    active_sheet_ref: str | None = None
    remainder_refs: tuple[str, ...] = ()
    checkpoint_ref: str | None = None
    previous_revision_id: str | None = None
    predecessor_context_id: str | None = None
    successor_context_id: str | None = None
    suspension_reason: str | None = None
    abandonment_reason: str | None = None
    reuse_policy: AttentionReusePolicy = AttentionReusePolicy.NOTHING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    authority: str = "ATTENTION_PROJECTION_ONLY"

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.context_id):
            raise ValueError("Attention context ID is invalid")
        if not _SAFE_ID.fullmatch(self.revision_id):
            raise ValueError("Attention revision ID is invalid")
        if self.revision_number < 1:
            raise ValueError("Attention revision number must be positive")
        if not all((
            self.objective.strip(),
            self.scope.strip(),
            self.summary.strip(),
            self.created_at.strip(),
        )):
            raise ValueError(
                "Attention objective, scope, summary, and timestamp are required"
            )
        if self.authority != "ATTENTION_PROJECTION_ONLY":
            raise PermissionError("Attention context cannot grant memory authority")
        for name, value in (
            ("previous_revision_id", self.previous_revision_id),
            ("predecessor_context_id", self.predecessor_context_id),
            ("successor_context_id", self.successor_context_id),
        ):
            if value is not None and not _SAFE_ID.fullmatch(value):
                raise ValueError(f"{name} is invalid")
        for values in (
            self.source_refs,
            self.validated_refs,
            self.selected_refs,
            self.workspace_sheet_refs,
            self.remainder_refs,
        ):
            if any(not item.strip() for item in values):
                raise ValueError("Attention references cannot be empty")
            if len(values) != len(set(values)):
                raise ValueError("Attention references must be unique")
        if self.active_sheet_ref is not None:
            if not self.active_sheet_ref.strip():
                raise ValueError("Active sheet ref cannot be empty")
            if self.active_sheet_ref not in self.workspace_sheet_refs:
                raise ValueError(
                    "Active sheet must be one of the workspace sheet refs"
                )
        if (
            self.state is AttentionState.SUSPENDED
            and self.transition is AttentionTransition.SUSPENDED
            and not self.suspension_reason
        ):
            raise ValueError("Suspending attention requires a reason")
        if self.transition is AttentionTransition.SUCCESSOR_PREPARED:
            if (
                self.state is not AttentionState.SUSPENDED
                or self.predecessor_context_id is None
            ):
                raise ValueError(
                    "A prepared successor must be suspended and name its predecessor"
                )
        if self.state is AttentionState.ABANDONED:
            if self.transition is not AttentionTransition.ABANDONED:
                raise ValueError("Abandoned attention requires ABANDONED transition")
            if not self.abandonment_reason:
                raise ValueError("Abandoned attention requires a reason")
        elif self.abandonment_reason is not None:
            raise ValueError("Only abandoned attention has an abandonment reason")
        if (
            self.successor_context_id is not None
            and self.state is not AttentionState.ABANDONED
        ):
            raise ValueError("Only abandoned attention may name a successor")

    @property
    def context_ref(self) -> str:
        return f"attention:{self.context_id}@{self.revision_number}"


@dataclass(frozen=True)
class AttentionRestartOutcome:
    abandoned: AttentionContextRevision
    successor: AttentionContextRevision


class AttentionMemoryError(RuntimeError):
    """Attention history or a requested lifecycle transition is invalid."""


class AttentionMemory:
    """Append-only attention lifecycle with at most one foreground context."""

    def __init__(
        self,
        root: str | Path,
        *,
        filename: str = "attention-contexts.jsonl",
        id_factory: Callable[[], str] | None = None,
        revision_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._path = self._root / filename
        self._id_factory = id_factory or (
            lambda: f"context:{uuid4()}"
        )
        self._revision_id_factory = revision_id_factory or (
            lambda: f"attention-revision:{uuid4()}"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def create(
        self,
        *,
        objective: str,
        scope: str,
        summary: str,
        context_id: str | None = None,
        source_refs: tuple[str, ...] = (),
        validated_refs: tuple[str, ...] = (),
        selected_refs: tuple[str, ...] = (),
        workspace_sheet_refs: tuple[str, ...] = (),
        active_sheet_ref: str | None = None,
        remainder_refs: tuple[str, ...] = (),
        checkpoint_ref: str | None = None,
    ) -> AttentionContextRevision:
        with self._lock:
            records = self._read_verified_unlocked()
            if self._active_from(records) is not None:
                raise AttentionMemoryError(
                    "Suspend, archive, or abandon the active context first"
                )
            revision = AttentionContextRevision(
                context_id=context_id or self._new_context_id(),
                revision_id=self._new_revision_id(),
                revision_number=1,
                state=AttentionState.ACTIVE,
                transition=AttentionTransition.CREATED,
                objective=objective,
                scope=scope,
                summary=summary,
                source_refs=source_refs,
                validated_refs=validated_refs,
                selected_refs=selected_refs,
                workspace_sheet_refs=workspace_sheet_refs,
                active_sheet_ref=active_sheet_ref,
                remainder_refs=remainder_refs,
                checkpoint_ref=checkpoint_ref,
                reuse_policy=AttentionReusePolicy.NOTHING,
                created_at=self._clock(),
            )
            self._append_unlocked(revision, records)
            return revision

    def update(
        self,
        context_id: str,
        *,
        summary: str,
        source_refs: tuple[str, ...] | None = None,
        validated_refs: tuple[str, ...] | None = None,
        selected_refs: tuple[str, ...] | None = None,
        workspace_sheet_refs: tuple[str, ...] | None = None,
        active_sheet_ref: str | None | object = _UNSET,
        remainder_refs: tuple[str, ...] | None = None,
        checkpoint_ref: str | None = None,
    ) -> AttentionContextRevision:
        with self._lock:
            records = self._read_verified_unlocked()
            current = self._latest_required(context_id, records)
            if current.state is not AttentionState.ACTIVE:
                raise AttentionMemoryError("Only active attention can be updated")
            revision = self._next(
                current,
                transition=AttentionTransition.UPDATED,
                summary=summary,
                source_refs=(
                    current.source_refs
                    if source_refs is None else source_refs
                ),
                validated_refs=(
                    current.validated_refs
                    if validated_refs is None else validated_refs
                ),
                selected_refs=(
                    current.selected_refs
                    if selected_refs is None else selected_refs
                ),
                workspace_sheet_refs=(
                    current.workspace_sheet_refs
                    if workspace_sheet_refs is None else workspace_sheet_refs
                ),
                active_sheet_ref=(
                    current.active_sheet_ref
                    if active_sheet_ref is _UNSET else active_sheet_ref
                ),
                remainder_refs=(
                    current.remainder_refs
                    if remainder_refs is None else remainder_refs
                ),
                checkpoint_ref=(
                    current.checkpoint_ref
                    if checkpoint_ref is None else checkpoint_ref
                ),
            )
            self._append_unlocked(revision, records)
            return revision

    def suspend(
        self,
        context_id: str,
        *,
        reason: str,
        summary: str | None = None,
        checkpoint_ref: str | None = None,
    ) -> AttentionContextRevision:
        return self._transition(
            context_id,
            expected=(AttentionState.ACTIVE,),
            state=AttentionState.SUSPENDED,
            transition=AttentionTransition.SUSPENDED,
            summary=summary,
            checkpoint_ref=checkpoint_ref,
            suspension_reason=reason,
        )

    def reactivate(
        self,
        context_id: str,
        *,
        summary: str | None = None,
        source_refs: tuple[str, ...] | None = None,
        validated_refs: tuple[str, ...] | None = None,
        selected_refs: tuple[str, ...] | None = None,
        workspace_sheet_refs: tuple[str, ...] | None = None,
        active_sheet_ref: str | None | object = _UNSET,
        remainder_refs: tuple[str, ...] | None = None,
        checkpoint_ref: str | None = None,
    ) -> AttentionContextRevision:
        with self._lock:
            records = self._read_verified_unlocked()
            current = self._latest_required(context_id, records)
            if current.state is not AttentionState.SUSPENDED:
                raise AttentionMemoryError(
                    "Only suspended attention can be reactivated"
                )
            active = self._active_from(records)
            if active is not None:
                raise AttentionMemoryError(
                    "Another attention context is already active"
                )
            revision = self._next(
                current,
                state=AttentionState.ACTIVE,
                transition=AttentionTransition.REACTIVATED,
                summary=summary or current.summary,
                suspension_reason=None,
                source_refs=(
                    current.source_refs if source_refs is None else source_refs
                ),
                validated_refs=(
                    current.validated_refs
                    if validated_refs is None else validated_refs
                ),
                selected_refs=(
                    current.selected_refs
                    if selected_refs is None else selected_refs
                ),
                workspace_sheet_refs=(
                    current.workspace_sheet_refs
                    if workspace_sheet_refs is None else workspace_sheet_refs
                ),
                active_sheet_ref=(
                    current.active_sheet_ref
                    if active_sheet_ref is _UNSET else active_sheet_ref
                ),
                remainder_refs=(
                    current.remainder_refs
                    if remainder_refs is None else remainder_refs
                ),
                checkpoint_ref=(
                    current.checkpoint_ref
                    if checkpoint_ref is None else checkpoint_ref
                ),
            )
            self._append_unlocked(revision, records)
            return revision

    def archive(
        self,
        context_id: str,
        *,
        summary: str | None = None,
    ) -> AttentionContextRevision:
        return self._transition(
            context_id,
            expected=(AttentionState.ACTIVE, AttentionState.SUSPENDED),
            state=AttentionState.ARCHIVED,
            transition=AttentionTransition.ARCHIVED,
            summary=summary,
            suspension_reason=None,
        )

    def abandon(
        self,
        context_id: str,
        *,
        reason: str,
        reuse_policy: AttentionReusePolicy,
        summary: str | None = None,
    ) -> AttentionContextRevision:
        return self._transition(
            context_id,
            expected=(AttentionState.ACTIVE, AttentionState.SUSPENDED),
            state=AttentionState.ABANDONED,
            transition=AttentionTransition.ABANDONED,
            summary=summary,
            suspension_reason=None,
            abandonment_reason=reason,
            reuse_policy=reuse_policy,
        )

    def restart(
        self,
        context_id: str,
        *,
        reason: str,
        reuse_policy: AttentionReusePolicy,
        objective: str,
        scope: str | None = None,
        summary: str = "Fresh attention context",
        selected_refs: tuple[str, ...] = (),
        successor_context_id: str | None = None,
    ) -> AttentionRestartOutcome:
        with self._lock:
            records = self._read_verified_unlocked()
            current = self._latest_required(context_id, records)
            if current.state not in {
                AttentionState.ACTIVE,
                AttentionState.SUSPENDED,
            }:
                raise AttentionMemoryError(
                    "Only open attention can be restarted"
                )
            active = self._active_from(records)
            if active is not None and active.context_id != current.context_id:
                raise AttentionMemoryError(
                    "Suspend the current foreground before restarting "
                    "another context"
                )
            successor_id = successor_context_id or self._new_context_id()
            carried = self._carried_refs(
                current,
                reuse_policy,
                selected_refs,
            )
            prepared = AttentionContextRevision(
                context_id=successor_id,
                revision_id=self._new_revision_id(),
                revision_number=1,
                state=AttentionState.SUSPENDED,
                transition=AttentionTransition.SUCCESSOR_PREPARED,
                objective=objective,
                scope=scope or current.scope,
                summary=summary,
                source_refs=carried["source_refs"],
                validated_refs=carried["validated_refs"],
                selected_refs=carried["selected_refs"],
                workspace_sheet_refs=carried["workspace_sheet_refs"],
                active_sheet_ref=carried["active_sheet_ref"],
                remainder_refs=carried["remainder_refs"],
                checkpoint_ref=carried["checkpoint_ref"],
                predecessor_context_id=current.context_id,
                suspension_reason="WAITING_FOR_PREDECESSOR_ABANDONMENT",
                reuse_policy=reuse_policy,
                created_at=self._clock(),
            )
            self._append_unlocked(prepared, records)
            records = self._read_verified_unlocked()
            abandoned = self._next(
                current,
                state=AttentionState.ABANDONED,
                transition=AttentionTransition.ABANDONED,
                successor_context_id=successor_id,
                suspension_reason=None,
                abandonment_reason=reason,
                reuse_policy=reuse_policy,
            )
            self._append_unlocked(abandoned, records)
            records = self._read_verified_unlocked()
            successor = self._next(
                prepared,
                state=AttentionState.ACTIVE,
                transition=AttentionTransition.REACTIVATED,
                suspension_reason=None,
            )
            self._append_unlocked(successor, records)
            return AttentionRestartOutcome(abandoned, successor)

    def active(self) -> AttentionContextRevision | None:
        with self._lock:
            return self._active_from(self._read_verified_unlocked())

    def latest(self, context_id: str) -> AttentionContextRevision:
        with self._lock:
            return self._latest_required(
                context_id,
                self._read_verified_unlocked(),
            )

    def history(
        self,
        context_id: str,
    ) -> tuple[AttentionContextRevision, ...]:
        with self._lock:
            records = self._read_verified_unlocked()
        return tuple(
            revision for revision, _hash in records
            if revision.context_id == context_id
        )

    def contexts(
        self,
        *,
        state: AttentionState | None = None,
    ) -> tuple[AttentionContextRevision, ...]:
        with self._lock:
            records = self._read_verified_unlocked()
        latest: dict[str, AttentionContextRevision] = {}
        for revision, _hash in records:
            latest[revision.context_id] = revision
        result = tuple(latest.values())
        if state is not None:
            result = tuple(item for item in result if item.state is state)
        return tuple(sorted(result, key=lambda item: item.context_id))

    def _transition(
        self,
        context_id: str,
        *,
        expected: tuple[AttentionState, ...],
        state: AttentionState,
        transition: AttentionTransition,
        summary: str | None,
        **changes: Any,
    ) -> AttentionContextRevision:
        with self._lock:
            records = self._read_verified_unlocked()
            current = self._latest_required(context_id, records)
            if current.state not in expected:
                raise AttentionMemoryError(
                    f"Invalid attention transition from {current.state.value}"
                )
            if (
                "checkpoint_ref" in changes
                and changes["checkpoint_ref"] is None
            ):
                changes["checkpoint_ref"] = current.checkpoint_ref
            revision = self._next(
                current,
                state=state,
                transition=transition,
                summary=summary or current.summary,
                **changes,
            )
            self._append_unlocked(revision, records)
            return revision

    def _next(
        self,
        current: AttentionContextRevision,
        **changes: Any,
    ) -> AttentionContextRevision:
        return replace(
            current,
            revision_id=self._new_revision_id(),
            revision_number=current.revision_number + 1,
            previous_revision_id=current.revision_id,
            created_at=self._clock(),
            **changes,
        )

    @staticmethod
    def _carried_refs(
        current: AttentionContextRevision,
        policy: AttentionReusePolicy,
        selected_refs: tuple[str, ...],
    ) -> dict[str, Any]:
        empty = {
            "source_refs": (),
            "validated_refs": (),
            "selected_refs": (),
            "workspace_sheet_refs": (),
            "active_sheet_ref": None,
            "remainder_refs": (),
            "checkpoint_ref": None,
        }
        if policy is AttentionReusePolicy.NOTHING:
            return empty
        if policy is AttentionReusePolicy.SOURCES_ONLY:
            return {**empty, "source_refs": current.source_refs}
        if policy is AttentionReusePolicy.VALIDATED_ONLY:
            return {**empty, "validated_refs": current.validated_refs}
        if policy is AttentionReusePolicy.FULL_CHECKPOINT:
            return {
                "source_refs": current.source_refs,
                "validated_refs": current.validated_refs,
                "selected_refs": current.selected_refs,
                "workspace_sheet_refs": current.workspace_sheet_refs,
                "active_sheet_ref": current.active_sheet_ref,
                "remainder_refs": current.remainder_refs,
                "checkpoint_ref": current.checkpoint_ref,
            }
        available = set((
            *current.source_refs,
            *current.validated_refs,
            *current.selected_refs,
            *current.workspace_sheet_refs,
            *current.remainder_refs,
        ))
        if not selected_refs or not set(selected_refs).issubset(available):
            raise AttentionMemoryError(
                "SELECTED_ITEMS requires existing explicit references"
            )
        return {**empty, "selected_refs": tuple(dict.fromkeys(selected_refs))}

    def _append_unlocked(
        self,
        revision: AttentionContextRevision,
        records: tuple[tuple[AttentionContextRevision, str], ...],
    ) -> None:
        self._validate_append(revision, records)
        previous_hash = records[-1][1] if records else None
        history = tuple(
            item for item in records
            if item[0].context_id == revision.context_id
        )
        parent_hash = history[-1][1] if history else None
        body = {
            **encode_attention_context(revision),
            "previous_record_hash": previous_hash,
            "parent_revision_hash": parent_hash,
        }
        content_hash = _hash_body(body)
        record = {**body, "content_hash": content_hash}
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            with self._path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                stream.write(_canonical_json(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, TypeError, ValueError) as exc:
            raise AttentionMemoryError(
                f"Could not persist attention revision: {type(exc).__name__}"
            ) from exc

    def _validate_append(
        self,
        revision: AttentionContextRevision,
        records: tuple[tuple[AttentionContextRevision, str], ...],
    ) -> None:
        if any(
            item.revision_id == revision.revision_id
            for item, _hash in records
        ):
            raise AttentionMemoryError("Attention revision already exists")
        history = [
            item for item, _hash in records
            if item.context_id == revision.context_id
        ]
        if not history:
            if (
                revision.revision_number != 1
                or revision.previous_revision_id is not None
            ):
                raise AttentionMemoryError(
                    "New attention must begin at revision 1"
                )
            allowed_new = {
                (
                    AttentionState.ACTIVE,
                    AttentionTransition.CREATED,
                ),
                (
                    AttentionState.SUSPENDED,
                    AttentionTransition.SUCCESSOR_PREPARED,
                ),
            }
            if (revision.state, revision.transition) not in allowed_new:
                raise AttentionMemoryError(
                    "Invalid initial attention state or transition"
                )
            if revision.predecessor_context_id is not None:
                predecessor = next((
                    item for item, _hash in reversed(records)
                    if item.context_id == revision.predecessor_context_id
                ), None)
                if predecessor is None or predecessor.state not in {
                    AttentionState.ACTIVE,
                    AttentionState.SUSPENDED,
                }:
                    raise AttentionMemoryError(
                        "Prepared successor lacks an open predecessor"
                    )
        else:
            parent = history[-1]
            if revision.revision_number != parent.revision_number + 1:
                raise AttentionMemoryError(
                    "Attention revision number is not contiguous"
                )
            if revision.previous_revision_id != parent.revision_id:
                raise AttentionMemoryError(
                    "Attention revision does not extend its latest parent"
                )
            if parent.state in {
                AttentionState.ARCHIVED,
                AttentionState.ABANDONED,
            }:
                raise AttentionMemoryError(
                    f"{parent.state.value} attention is immutable"
                )
            allowed = {
                AttentionState.ACTIVE: {
                    (
                        AttentionState.ACTIVE,
                        AttentionTransition.UPDATED,
                    ),
                    (
                        AttentionState.SUSPENDED,
                        AttentionTransition.SUSPENDED,
                    ),
                    (
                        AttentionState.ARCHIVED,
                        AttentionTransition.ARCHIVED,
                    ),
                    (
                        AttentionState.ABANDONED,
                        AttentionTransition.ABANDONED,
                    ),
                },
                AttentionState.SUSPENDED: {
                    (
                        AttentionState.ACTIVE,
                        AttentionTransition.REACTIVATED,
                    ),
                    (
                        AttentionState.ARCHIVED,
                        AttentionTransition.ARCHIVED,
                    ),
                    (
                        AttentionState.ABANDONED,
                        AttentionTransition.ABANDONED,
                    ),
                },
            }
            if (
                revision.state,
                revision.transition,
            ) not in allowed[parent.state]:
                raise AttentionMemoryError(
                    "Invalid attention lifecycle transition"
                )
            if revision.successor_context_id is not None:
                successor = next((
                    item for item, _hash in reversed(records)
                    if item.context_id == revision.successor_context_id
                ), None)
                if (
                    successor is None
                    or successor.predecessor_context_id
                    != revision.context_id
                ):
                    raise AttentionMemoryError(
                        "Abandoned context names an invalid successor"
                    )
        latest: dict[str, AttentionContextRevision] = {}
        for item, _hash in records:
            latest[item.context_id] = item
        latest[revision.context_id] = revision
        active = [
            item for item in latest.values()
            if item.state is AttentionState.ACTIVE
        ]
        if len(active) > 1:
            raise AttentionMemoryError(
                "Attention memory permits only one active foreground context"
            )

    def _read_verified_unlocked(
        self,
    ) -> tuple[tuple[AttentionContextRevision, str], ...]:
        if not self._path.exists():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AttentionMemoryError(
                f"Could not read attention history: {type(exc).__name__}"
            ) from exc
        records: list[tuple[AttentionContextRevision, str]] = []
        previous_hash: str | None = None
        latest_hash: dict[str, str] = {}
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise AttentionMemoryError(
                    f"Empty attention record at line {line_number}"
                )
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("record is not an object")
                content_hash = record.pop("content_hash")
                if _hash_body(record) != content_hash:
                    raise AttentionMemoryError(
                        f"Attention hash mismatch at line {line_number}"
                    )
                if record.get("previous_record_hash") != previous_hash:
                    raise AttentionMemoryError(
                        f"Attention chain mismatch at line {line_number}"
                    )
                revision = decode_attention_context(record)
                if record.get("parent_revision_hash") != latest_hash.get(
                    revision.context_id
                ):
                    raise AttentionMemoryError(
                        f"Attention parent mismatch at line {line_number}"
                    )
                self._validate_append(revision, tuple(records))
            except AttentionMemoryError:
                raise
            except (
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                raise AttentionMemoryError(
                    f"Malformed attention record at line {line_number}: {exc}"
                ) from exc
            records.append((revision, content_hash))
            latest_hash[revision.context_id] = content_hash
            previous_hash = content_hash
        return tuple(records)

    @staticmethod
    def _active_from(
        records: tuple[tuple[AttentionContextRevision, str], ...],
    ) -> AttentionContextRevision | None:
        latest: dict[str, AttentionContextRevision] = {}
        for revision, _hash in records:
            latest[revision.context_id] = revision
        active = [
            item for item in latest.values()
            if item.state is AttentionState.ACTIVE
        ]
        if len(active) > 1:
            raise AttentionMemoryError("Attention history has multiple active contexts")
        return active[0] if active else None

    @staticmethod
    def _latest_required(
        context_id: str,
        records: tuple[tuple[AttentionContextRevision, str], ...],
    ) -> AttentionContextRevision:
        matches = [
            item for item, _hash in records
            if item.context_id == context_id
        ]
        if not matches:
            raise AttentionMemoryError(f"Unknown attention context: {context_id}")
        return matches[-1]

    def _new_context_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
            raise AttentionMemoryError("Context ID factory returned an invalid ID")
        return value

    def _new_revision_id(self) -> str:
        value = self._revision_id_factory()
        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
            raise AttentionMemoryError("Revision ID factory returned an invalid ID")
        return value


def encode_attention_context(
    value: AttentionContextRevision,
) -> dict[str, Any]:
    return {
        "schema": ATTENTION_CONTEXT_SCHEMA,
        "context_id": value.context_id,
        "revision_id": value.revision_id,
        "revision_number": value.revision_number,
        "state": value.state.value,
        "transition": value.transition.value,
        "objective": value.objective,
        "scope": value.scope,
        "summary": value.summary,
        "source_refs": list(value.source_refs),
        "validated_refs": list(value.validated_refs),
        "selected_refs": list(value.selected_refs),
        "workspace_sheet_refs": list(value.workspace_sheet_refs),
        "active_sheet_ref": value.active_sheet_ref,
        "remainder_refs": list(value.remainder_refs),
        "checkpoint_ref": value.checkpoint_ref,
        "previous_revision_id": value.previous_revision_id,
        "predecessor_context_id": value.predecessor_context_id,
        "successor_context_id": value.successor_context_id,
        "suspension_reason": value.suspension_reason,
        "abandonment_reason": value.abandonment_reason,
        "reuse_policy": value.reuse_policy.value,
        "created_at": value.created_at,
        "authority": value.authority,
    }


def decode_attention_context(
    value: Mapping[str, Any],
) -> AttentionContextRevision:
    if value.get("schema") != ATTENTION_CONTEXT_SCHEMA:
        raise ValueError("Unknown attention context schema")
    return AttentionContextRevision(
        context_id=_text(value, "context_id"),
        revision_id=_text(value, "revision_id"),
        revision_number=_integer(value, "revision_number"),
        state=AttentionState(_text(value, "state")),
        transition=AttentionTransition(_text(value, "transition")),
        objective=_text(value, "objective"),
        scope=_text(value, "scope"),
        summary=_text(value, "summary"),
        source_refs=_text_tuple(value, "source_refs"),
        validated_refs=_text_tuple(value, "validated_refs"),
        selected_refs=_text_tuple(value, "selected_refs"),
        workspace_sheet_refs=_text_tuple(value, "workspace_sheet_refs"),
        active_sheet_ref=_optional_text(value, "active_sheet_ref"),
        remainder_refs=_text_tuple(value, "remainder_refs"),
        checkpoint_ref=_optional_text(value, "checkpoint_ref"),
        previous_revision_id=_optional_text(value, "previous_revision_id"),
        predecessor_context_id=_optional_text(
            value, "predecessor_context_id"
        ),
        successor_context_id=_optional_text(value, "successor_context_id"),
        suspension_reason=_optional_text(value, "suspension_reason"),
        abandonment_reason=_optional_text(value, "abandonment_reason"),
        reuse_policy=AttentionReusePolicy(_text(value, "reuse_policy")),
        created_at=_text(value, "created_at"),
        authority=_text(value, "authority"),
    )


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
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid references")
    return tuple(items)
