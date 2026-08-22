"""Append-only in-memory event journal for one or more bounded executions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Any, Protocol
from uuid import uuid4


class JournalEventKind(str, Enum):
    MODULE_DISCOVERED = "MODULE_DISCOVERED"
    MODULE_ADMITTED = "MODULE_ADMITTED"
    MODULE_REJECTED = "MODULE_REJECTED"
    FIREWALL_ATTESTED = "FIREWALL_ATTESTED"
    FIREWALL_DEVELOPMENT_BYPASS = "FIREWALL_DEVELOPMENT_BYPASS"
    FIREWALL_INTERVENED = "FIREWALL_INTERVENED"
    PLAN_PROPOSED = "PLAN_PROPOSED"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    PLAN_REJECTED = "PLAN_REJECTED"
    AUTHORIZATION_GRANTED = "AUTHORIZATION_GRANTED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    OPERATION_STARTED = "OPERATION_STARTED"
    OPERATION_OUTPUT = "OPERATION_OUTPUT"
    OPERATION_FAILED = "OPERATION_FAILED"
    EFFECT_REQUESTED = "EFFECT_REQUESTED"
    EFFECT_COMMITTED = "EFFECT_COMMITTED"
    EFFECT_REJECTED = "EFFECT_REJECTED"
    ONTOLOGY_EVALUATED = "ONTOLOGY_EVALUATED"
    EPISTEMIC_EVALUATED = "EPISTEMIC_EVALUATED"
    OBJECTIVE_COMPLETED = "OBJECTIVE_COMPLETED"
    OBJECTIVE_OPEN = "OBJECTIVE_OPEN"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    EXECUTION_PAUSED = "EXECUTION_PAUSED"
    EXECUTION_RESUMED = "EXECUTION_RESUMED"
    JOURNAL_ARCHIVE_FAILED = "JOURNAL_ARCHIVE_FAILED"
    CHECKPOINT_PERSISTENCE_FAILED = "CHECKPOINT_PERSISTENCE_FAILED"
    PHI_MINUS_RECORDED = "PHI_MINUS_RECORDED"


JOURNAL_SEGMENT_SCHEMA = "fresta://journal-segment@1"


@dataclass(frozen=True)
class JournalEvent:
    event_id: str
    sequence: int
    kind: JournalEventKind
    correlation_id: str
    subject_ref: str
    recorded_at: str
    payload: Mapping[str, Any]
    causation_id: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("Journal sequence must be positive")
        if not self.event_id.strip():
            raise ValueError("Journal event ID is required")
        if not self.correlation_id.strip() or not self.subject_ref.strip():
            raise ValueError("Journal correlation and subject references are required")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))


@dataclass(frozen=True)
class JournalSegment:
    segment_id: str
    correlation_id: str
    created_at: str
    previous_segment_hash: str | None
    content_hash: str
    events: tuple[JournalEvent, ...]
    schema: str = JOURNAL_SEGMENT_SCHEMA

    @property
    def first_sequence(self) -> int:
        return self.events[0].sequence

    @property
    def last_sequence(self) -> int:
        return self.events[-1].sequence


class JournalArchiveError(RuntimeError):
    """Archive could not preserve or verify the append-only history."""


class JournalArchive(Protocol):
    def archive(self, events: tuple[JournalEvent, ...]) -> JournalSegment:
        """Seal and persist one non-empty correlated event segment."""


class EventJournal:
    """Thread-safe append-only journal with caller-independent event snapshots."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or _utc_now
        self._events: list[JournalEvent] = []
        self._event_ids: set[str] = set()
        self._lock = Lock()

    @property
    def position(self) -> int:
        with self._lock:
            return len(self._events)

    @property
    def events(self) -> tuple[JournalEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @property
    def last_event_id(self) -> str | None:
        with self._lock:
            return self._events[-1].event_id if self._events else None

    def append(
        self,
        kind: JournalEventKind,
        *,
        correlation_id: str,
        subject_ref: str,
        payload: Mapping[str, Any] | None = None,
        causation_id: str | None = None,
    ) -> JournalEvent:
        with self._lock:
            if causation_id is not None and causation_id not in self._event_ids:
                raise ValueError("Causation event does not exist in this journal")
            event_id = self._id_factory()
            if not isinstance(event_id, str) or not event_id.strip():
                raise ValueError("Journal ID factory returned an invalid ID")
            if event_id in self._event_ids:
                raise ValueError(f"Duplicate journal event ID: {event_id}")
            event = JournalEvent(
                event_id=event_id,
                sequence=len(self._events) + 1,
                kind=kind,
                correlation_id=correlation_id,
                subject_ref=subject_ref,
                recorded_at=self._clock(),
                payload=payload or {},
                causation_id=causation_id,
            )
            self._events.append(event)
            self._event_ids.add(event_id)
            return event

    def events_since(self, position: int) -> tuple[JournalEvent, ...]:
        if position < 0:
            raise ValueError("Journal position cannot be negative")
        with self._lock:
            if position > len(self._events):
                raise ValueError("Journal position is beyond the current event stream")
            return tuple(self._events[position:])

    def for_correlation(self, correlation_id: str) -> tuple[JournalEvent, ...]:
        with self._lock:
            return tuple(
                event for event in self._events
                if event.correlation_id == correlation_id
            )


class JsonlJournalArchive:
    """Single-process append-only JSONL archive with a tamper-evident hash chain."""

    def __init__(
        self,
        root: str | Path,
        *,
        filename: str = "journal-segments.jsonl",
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._root = Path(root)
        self._path = self._root / filename
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or _utc_now
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def archive(self, events: tuple[JournalEvent, ...]) -> JournalSegment:
        if not events:
            raise JournalArchiveError("Cannot archive an empty journal segment")
        correlation_ids = {event.correlation_id for event in events}
        if len(correlation_ids) != 1:
            raise JournalArchiveError(
                "One journal segment cannot mix correlation IDs"
            )
        if tuple(event.sequence for event in events) != tuple(
            range(events[0].sequence, events[-1].sequence + 1)
        ):
            raise JournalArchiveError("Journal segment sequences are not contiguous")

        with self._lock:
            existing = self._read_verified_unlocked()
            previous_hash = (
                existing[-1].content_hash if existing else None
            )
            segment_id = self._id_factory()
            if not isinstance(segment_id, str) or not segment_id.strip():
                raise JournalArchiveError("Archive ID factory returned an invalid ID")
            if any(item.segment_id == segment_id for item in existing):
                raise JournalArchiveError(f"Duplicate journal segment ID: {segment_id}")

            body = {
                "schema": JOURNAL_SEGMENT_SCHEMA,
                "segment_id": segment_id,
                "correlation_id": next(iter(correlation_ids)),
                "created_at": self._clock(),
                "previous_segment_hash": previous_hash,
                "events": [_event_to_data(event) for event in events],
            }
            content_hash = _hash_body(body)
            record = {**body, "content_hash": content_hash}
            try:
                self._root.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(_canonical_json(record) + "\n")
                    stream.flush()
            except OSError as exc:
                raise JournalArchiveError(
                    f"Could not append journal segment: {type(exc).__name__}"
                ) from exc
            return _segment_from_record(record)

    def segments(self) -> tuple[JournalSegment, ...]:
        with self._lock:
            return self._read_verified_unlocked()

    def for_correlation(self, correlation_id: str) -> tuple[JournalSegment, ...]:
        return tuple(
            segment for segment in self.segments()
            if segment.correlation_id == correlation_id
        )

    def _read_verified_unlocked(self) -> tuple[JournalSegment, ...]:
        if not self._path.exists():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise JournalArchiveError(
                f"Could not read journal archive: {type(exc).__name__}"
            ) from exc

        segments: list[JournalSegment] = []
        previous_hash: str | None = None
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise JournalArchiveError(
                    f"Empty record in journal archive at line {line_number}"
                )
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("record is not an object")
                content_hash = record.pop("content_hash")
                if not isinstance(content_hash, str):
                    raise TypeError("content_hash is not text")
                if _hash_body(record) != content_hash:
                    raise JournalArchiveError(
                        f"Journal hash mismatch at line {line_number}"
                    )
                if record.get("previous_segment_hash") != previous_hash:
                    raise JournalArchiveError(
                        f"Journal chain mismatch at line {line_number}"
                    )
                record["content_hash"] = content_hash
                segment = _segment_from_record(record)
            except JournalArchiveError:
                raise
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise JournalArchiveError(
                    f"Malformed journal record at line {line_number}: {exc}"
                ) from exc
            segments.append(segment)
            previous_hash = segment.content_hash
        return tuple(segments)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({
        str(key): _freeze_value(item) for key, item in dict(value).items()
    })


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _event_to_data(event: JournalEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "sequence": event.sequence,
        "kind": event.kind.value,
        "correlation_id": event.correlation_id,
        "subject_ref": event.subject_ref,
        "recorded_at": event.recorded_at,
        "payload": _thaw_value(event.payload),
        "causation_id": event.causation_id,
    }


def _event_from_data(value: Mapping[str, Any]) -> JournalEvent:
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise TypeError("event payload is not an object")
    causation_id = value.get("causation_id")
    if causation_id is not None and not isinstance(causation_id, str):
        raise TypeError("event causation_id is not text or null")
    return JournalEvent(
        event_id=_record_text(value, "event_id"),
        sequence=int(value["sequence"]),
        kind=JournalEventKind(_record_text(value, "kind")),
        correlation_id=_record_text(value, "correlation_id"),
        subject_ref=_record_text(value, "subject_ref"),
        recorded_at=_record_text(value, "recorded_at"),
        payload=payload,
        causation_id=causation_id,
    )


def _segment_from_record(value: Mapping[str, Any]) -> JournalSegment:
    if value.get("schema") != JOURNAL_SEGMENT_SCHEMA:
        raise ValueError("unknown journal segment schema")
    raw_events = value.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("journal segment events must be a non-empty array")
    events = tuple(
        _event_from_data(item)
        for item in raw_events
        if isinstance(item, Mapping)
    )
    if len(events) != len(raw_events):
        raise TypeError("journal segment contains a non-object event")
    correlation_id = _record_text(value, "correlation_id")
    if any(event.correlation_id != correlation_id for event in events):
        raise ValueError("journal segment mixes correlation IDs")
    previous_hash = value.get("previous_segment_hash")
    if previous_hash is not None and not isinstance(previous_hash, str):
        raise TypeError("previous_segment_hash is not text or null")
    return JournalSegment(
        segment_id=_record_text(value, "segment_id"),
        correlation_id=correlation_id,
        created_at=_record_text(value, "created_at"),
        previous_segment_hash=previous_hash,
        content_hash=_record_text(value, "content_hash"),
        events=events,
    )


def _record_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_thaw_value(item) for item in value)
    if isinstance(value, Enum):
        return value.value
    return value
