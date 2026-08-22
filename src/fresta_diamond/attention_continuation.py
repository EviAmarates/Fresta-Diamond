"""Immutable persistence for bounded attention continuation checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol

from fresta_diamond.attention_projection import AttentionProjectionCheckpoint


ATTENTION_CONTINUATION_SCHEMA = (
    "fresta://diamond-attention-continuation@1"
)


@dataclass(frozen=True)
class StoredAttentionContinuationRef:
    checkpoint_id: str
    content_hash: str
    schema: str = ATTENTION_CONTINUATION_SCHEMA


class AttentionContinuationStoreError(RuntimeError):
    """An attention continuation could not be persisted or verified."""


class AttentionContinuationStore(Protocol):
    def save(
        self,
        checkpoint: AttentionProjectionCheckpoint,
    ) -> StoredAttentionContinuationRef:
        """Persist an immutable continuation checkpoint."""

    def load(
        self,
        checkpoint_id: str,
    ) -> AttentionProjectionCheckpoint:
        """Load and verify one immutable continuation checkpoint."""

    def for_context(
        self,
        context_ref: str,
    ) -> tuple[AttentionProjectionCheckpoint, ...]:
        """Return verified continuations recorded for one context revision."""


class JsonAttentionContinuationStore:
    """One canonical, hash-verified JSON file per continuation checkpoint."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def save(
        self,
        checkpoint: AttentionProjectionCheckpoint,
    ) -> StoredAttentionContinuationRef:
        body = encode_attention_continuation(checkpoint)
        content_hash = _hash_body(body)
        record = {**body, "content_hash": content_hash}
        path = self._path(checkpoint.checkpoint_id)
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            if path.exists():
                current = self.load(checkpoint.checkpoint_id)
                current_body = encode_attention_continuation(current)
                if _hash_body(current_body) != content_hash:
                    raise AttentionContinuationStoreError(
                        "Continuation checkpoint ID already has different content"
                    )
                return StoredAttentionContinuationRef(
                    checkpoint.checkpoint_id,
                    content_hash,
                )
            temporary = path.with_suffix(
                f".{os.getpid()}.tmp"
            )
            with temporary.open(
                "x",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                stream.write(_canonical_json(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except AttentionContinuationStoreError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise AttentionContinuationStoreError(
                "Could not persist attention continuation: "
                f"{type(exc).__name__}"
            ) from exc
        return StoredAttentionContinuationRef(
            checkpoint.checkpoint_id,
            content_hash,
        )

    def load(
        self,
        checkpoint_id: str,
    ) -> AttentionProjectionCheckpoint:
        path = self._path(checkpoint_id)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, Mapping):
                raise TypeError("Continuation record must be an object")
            stored_hash = _required_text(record, "content_hash")
            body = {
                key: value
                for key, value in record.items()
                if key != "content_hash"
            }
            if _hash_body(body) != stored_hash:
                raise AttentionContinuationStoreError(
                    "Attention continuation hash mismatch"
                )
            checkpoint = decode_attention_continuation(body)
            if checkpoint.checkpoint_id != checkpoint_id:
                raise AttentionContinuationStoreError(
                    "Attention continuation ID mismatch"
                )
            return checkpoint
        except FileNotFoundError as exc:
            raise AttentionContinuationStoreError(
                f"Attention continuation does not exist: {checkpoint_id}"
            ) from exc
        except AttentionContinuationStoreError:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AttentionContinuationStoreError(
                "Could not verify attention continuation: "
                f"{type(exc).__name__}"
            ) from exc

    def for_context(
        self,
        context_ref: str,
    ) -> tuple[AttentionProjectionCheckpoint, ...]:
        if not context_ref.strip():
            raise ValueError("Attention context ref is required")
        if not self._root.exists():
            return ()
        values: list[AttentionProjectionCheckpoint] = []
        try:
            paths = tuple(sorted(self._root.glob("*.json")))
        except OSError as exc:
            raise AttentionContinuationStoreError(
                "Could not enumerate attention continuations"
            ) from exc
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(record, Mapping):
                    raise TypeError("Continuation record must be an object")
                checkpoint_id = _required_text(record, "checkpoint_id")
                if path != self._path(checkpoint_id):
                    raise AttentionContinuationStoreError(
                        "Attention continuation filename does not match its ID"
                    )
                checkpoint = self.load(checkpoint_id)
            except AttentionContinuationStoreError:
                raise
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise AttentionContinuationStoreError(
                    "Could not enumerate verified continuations: "
                    f"{type(exc).__name__}"
                ) from exc
            if checkpoint.context_ref == context_ref:
                values.append(checkpoint)
        return tuple(sorted(values, key=lambda item: item.checkpoint_id))

    def _path(self, checkpoint_id: str) -> Path:
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("Attention continuation ID is required")
        digest = sha256(checkpoint_id.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"


def encode_attention_continuation(
    value: AttentionProjectionCheckpoint,
) -> dict[str, Any]:
    return {
        "schema": ATTENTION_CONTINUATION_SCHEMA,
        "checkpoint_id": value.checkpoint_id,
        "context_ref": value.context_ref,
        "completed_refs": list(value.completed_refs),
        "pending_refs": list(value.pending_refs),
        "blocked_refs": list(value.blocked_refs),
        "reasons": list(value.reasons),
        "token_budget": value.token_budget,
        "authority": value.authority,
    }


def decode_attention_continuation(
    value: Mapping[str, Any],
) -> AttentionProjectionCheckpoint:
    if value.get("schema") != ATTENTION_CONTINUATION_SCHEMA:
        raise ValueError("Unsupported attention continuation schema")
    token_budget = value.get("token_budget")
    if not isinstance(token_budget, int) or isinstance(token_budget, bool):
        raise TypeError("Attention continuation token_budget must be an integer")
    return AttentionProjectionCheckpoint(
        checkpoint_id=_required_text(value, "checkpoint_id"),
        context_ref=_required_text(value, "context_ref"),
        completed_refs=_text_tuple(value, "completed_refs"),
        pending_refs=_text_tuple(value, "pending_refs"),
        blocked_refs=_text_tuple(value, "blocked_refs"),
        reasons=_text_tuple(value, "reasons"),
        token_budget=token_budget,
        authority=_required_text(value, "authority"),
    )


def _required_text(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{key} must be non-empty text")
    return result


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    result = value.get(key)
    if not isinstance(result, list) or any(
        not isinstance(item, str) or not item.strip()
        for item in result
    ):
        raise TypeError(f"{key} must be an array of non-empty text")
    return tuple(result)


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
