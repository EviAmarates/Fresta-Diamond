"""Persistent chat bindings and messages without memory-promotion authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4


CHAT_SESSION_SCHEMA = "fresta://diamond-chat-session@1"
CHAT_MESSAGE_SCHEMA = "fresta://diamond-chat-message@1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


class ChatRole(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


@dataclass(frozen=True)
class ChatSession:
    session_id: str
    context_id: str
    transcript_sheet_id: str
    scope: str
    objective: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    authority: str = "CHAT_COORDINATION_ONLY"

    def __post_init__(self) -> None:
        if not all(_SAFE_ID.fullmatch(item) for item in (
            self.session_id,
            self.context_id,
            self.transcript_sheet_id,
        )):
            raise ValueError("Chat session references are invalid")
        if not all((self.scope.strip(), self.objective.strip(), self.created_at.strip())):
            raise ValueError("Chat session scope, objective, and time are required")
        if self.authority != "CHAT_COORDINATION_ONLY":
            raise PermissionError("Chat sessions cannot grant memory authority")


@dataclass(frozen=True)
class ChatMessage:
    message_id: str
    session_id: str
    sequence: int
    role: ChatRole
    content: str
    provenance: tuple[str, ...]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    authority: str = "CHAT_MESSAGE_ONLY"

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.message_id) or not _SAFE_ID.fullmatch(
            self.session_id
        ):
            raise ValueError("Chat message references are invalid")
        if self.sequence < 1:
            raise ValueError("Chat message sequence must be positive")
        if not self.content.strip() or not self.created_at.strip():
            raise ValueError("Chat message content and time are required")
        if not self.provenance or any(not item.strip() for item in self.provenance):
            raise ValueError("Chat message provenance is required")
        expected = (
            "USER_MESSAGE_ONLY"
            if self.role is ChatRole.USER
            else "MODEL_RESPONSE_UNVALIDATED"
        )
        if self.authority != expected:
            raise PermissionError("Chat message authority does not match its role")


class ChatStoreError(RuntimeError):
    """Chat history is missing, malformed, or was modified."""


class AtomicChatStore:
    """One sealed session file plus a hash-chained message log per session."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self._lock = Lock()

    def create(
        self,
        *,
        context_id: str,
        transcript_sheet_id: str,
        scope: str,
        objective: str,
        session_id: str | None = None,
    ) -> ChatSession:
        session = ChatSession(
            session_id=session_id or f"chat:{uuid4()}",
            context_id=context_id,
            transcript_sheet_id=transcript_sheet_id,
            scope=scope,
            objective=objective,
        )
        with self._lock:
            directory = self._directory(session.session_id)
            path = directory / "session.json"
            if path.exists():
                raise ChatStoreError("Chat session already exists")
            payload = encode_chat_session(session)
            self._atomic_write(path, _sealed(payload))
        return session

    def session(self, session_id: str) -> ChatSession:
        with self._lock:
            path = self._directory(session_id) / "session.json"
            if not path.exists():
                raise ChatStoreError(f"Unknown chat session: {session_id}")
            value = self._read_sealed(path)
            session = decode_chat_session(value)
            if session.session_id != session_id:
                raise ChatStoreError("Chat session identity was altered")
            return session

    def sessions(self) -> tuple[ChatSession, ...]:
        if not self.root.exists():
            return ()
        values = []
        for path in sorted(self.root.glob("*/session.json")):
            value = self._read_sealed(path)
            session = decode_chat_session(value)
            if path != self._directory(session.session_id) / "session.json":
                raise ChatStoreError("Chat session storage identity was altered")
            values.append(session)
        return tuple(sorted(values, key=lambda item: item.created_at))

    def append(
        self,
        session_id: str,
        *,
        role: ChatRole,
        content: str,
        provenance: tuple[str, ...],
        message_id: str | None = None,
    ) -> ChatMessage:
        with self._lock:
            session_path = self._directory(session_id) / "session.json"
            if not session_path.exists():
                raise ChatStoreError(f"Unknown chat session: {session_id}")
            history = self._messages_unlocked(session_id)
            selected_id = message_id or f"chat-message:{uuid4()}"
            if any(item.message_id == selected_id for item, _hash in history):
                raise ChatStoreError("Chat message ID already exists")
            message = ChatMessage(
                message_id=selected_id,
                session_id=session_id,
                sequence=len(history) + 1,
                role=role,
                content=content.strip(),
                provenance=provenance,
                authority=(
                    "USER_MESSAGE_ONLY"
                    if role is ChatRole.USER
                    else "MODEL_RESPONSE_UNVALIDATED"
                ),
            )
            previous_hash = history[-1][1] if history else None
            payload = encode_chat_message(message)
            body = {
                "payload": payload,
                "previous_hash": previous_hash,
            }
            content_hash = _digest(body)
            path = self._directory(session_id) / f"message-{message.sequence:08d}.json"
            self._atomic_write(path, {**body, "content_hash": content_hash})
            return message

    def messages(self, session_id: str) -> tuple[ChatMessage, ...]:
        self.session(session_id)
        with self._lock:
            return tuple(item[0] for item in self._messages_unlocked(session_id))

    def _messages_unlocked(
        self,
        session_id: str,
    ) -> tuple[tuple[ChatMessage, str], ...]:
        directory = self._directory(session_id)
        previous_hash = None
        result = []
        for expected, path in enumerate(sorted(directory.glob("message-*.json")), start=1):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                body = {
                    "payload": raw["payload"],
                    "previous_hash": raw.get("previous_hash"),
                }
                content_hash = raw["content_hash"]
            except (KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
                raise ChatStoreError(f"Malformed chat message: {path.name}") from exc
            if content_hash != _digest(body) or body["previous_hash"] != previous_hash:
                raise ChatStoreError("Chat message chain verification failed")
            message = decode_chat_message(body["payload"])
            if message.session_id != session_id or message.sequence != expected:
                raise ChatStoreError("Chat message sequence or identity was altered")
            result.append((message, content_hash))
            previous_hash = content_hash
        return tuple(result)

    def _directory(self, session_id: str) -> Path:
        if not isinstance(session_id, str) or not _SAFE_ID.fullmatch(session_id):
            raise ChatStoreError("Chat session ID is invalid")
        return self.root / sha256(session_id.encode("utf-8")).hexdigest()[:32]

    def _read_sealed(self, path: Path) -> dict[str, object]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            payload = raw["payload"]
            content_hash = raw["content_hash"]
        except (KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
            raise ChatStoreError(f"Malformed chat record: {path.name}") from exc
        if not isinstance(payload, dict) or content_hash != _digest(payload):
            raise ChatStoreError("Chat record hash verification failed")
        return payload

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + f".{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


def encode_chat_session(value: ChatSession) -> dict[str, object]:
    return {
        "schema": CHAT_SESSION_SCHEMA,
        "session_id": value.session_id,
        "context_id": value.context_id,
        "transcript_sheet_id": value.transcript_sheet_id,
        "scope": value.scope,
        "objective": value.objective,
        "created_at": value.created_at,
        "authority": value.authority,
    }


def decode_chat_session(value: dict[str, object]) -> ChatSession:
    if value.get("schema") != CHAT_SESSION_SCHEMA:
        raise ValueError("Unknown chat session schema")
    return ChatSession(
        session_id=_text(value, "session_id"),
        context_id=_text(value, "context_id"),
        transcript_sheet_id=_text(value, "transcript_sheet_id"),
        scope=_text(value, "scope"),
        objective=_text(value, "objective"),
        created_at=_text(value, "created_at"),
        authority=_text(value, "authority"),
    )


def encode_chat_message(value: ChatMessage) -> dict[str, object]:
    return {
        "schema": CHAT_MESSAGE_SCHEMA,
        "message_id": value.message_id,
        "session_id": value.session_id,
        "sequence": value.sequence,
        "role": value.role.value,
        "content": value.content,
        "provenance": list(value.provenance),
        "created_at": value.created_at,
        "authority": value.authority,
    }


def decode_chat_message(value: dict[str, object]) -> ChatMessage:
    if value.get("schema") != CHAT_MESSAGE_SCHEMA:
        raise ValueError("Unknown chat message schema")
    raw_provenance = value.get("provenance")
    if not isinstance(raw_provenance, list) or any(
        not isinstance(item, str) for item in raw_provenance
    ):
        raise ValueError("Chat message provenance must be an array of text")
    sequence = value.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError("Chat message sequence must be an integer")
    return ChatMessage(
        message_id=_text(value, "message_id"),
        session_id=_text(value, "session_id"),
        sequence=sequence,
        role=ChatRole(_text(value, "role")),
        content=_text(value, "content"),
        provenance=tuple(raw_provenance),
        created_at=_text(value, "created_at"),
        authority=_text(value, "authority"),
    )


def _sealed(payload: dict[str, object]) -> dict[str, object]:
    return {"payload": payload, "content_hash": _digest(payload)}


def _digest(value: object) -> str:
    return sha256(json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _text(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item
