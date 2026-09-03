"""Durable cursors for bounded document-learning batches."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


@dataclass(frozen=True)
class DocumentLearningCheckpoint:
    checkpoint_id: str
    decomposition_id: str
    objective: str
    processed_leaf_refs: tuple[str, ...]
    pending_leaf_refs: tuple[str, ...]
    source_ref: str
    source_sha256: str
    root_revision_id: str
    leaf_revision_ids: tuple[str, ...]
    index_revision_ids: tuple[str, ...]
    max_child_content_tokens: int
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.checkpoint_id.strip() or not self.decomposition_id.strip():
            raise ValueError("Document checkpoint identity is required")
        if not self.objective.strip():
            raise ValueError("Document checkpoint objective is required")
        if not self.source_ref.startswith("document:"):
            raise ValueError("Document checkpoint source reference is invalid")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", _digest(_body(self)))


class DocumentLearningCheckpointStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def save(self, checkpoint: DocumentLearningCheckpoint) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{checkpoint.checkpoint_id}.json"
        body = _body(checkpoint)
        sealed = {**body, "content_hash": checkpoint.content_hash}
        if path.exists():
            current = self.load(checkpoint.checkpoint_id)
            if current != checkpoint:
                raise ValueError("Document checkpoint ID already has different content")
            return path
        path.write_text(
            json.dumps(sealed, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, checkpoint_id: str) -> DocumentLearningCheckpoint:
        path = self._root / f"{checkpoint_id}.json"
        if not path.is_file():
            raise ValueError("Unknown document learning checkpoint")
        raw = json.loads(path.read_text(encoding="utf-8"))
        content_hash = raw.pop("content_hash")
        if _digest(raw) != content_hash:
            raise ValueError("Document checkpoint hash mismatch")
        return DocumentLearningCheckpoint(
            checkpoint_id=raw["checkpoint_id"],
            decomposition_id=raw["decomposition_id"],
            objective=raw["objective"],
            processed_leaf_refs=tuple(raw["processed_leaf_refs"]),
            pending_leaf_refs=tuple(raw["pending_leaf_refs"]),
            source_ref=raw["source_ref"],
            source_sha256=raw["source_sha256"],
            root_revision_id=raw["root_revision_id"],
            leaf_revision_ids=tuple(raw["leaf_revision_ids"]),
            index_revision_ids=tuple(raw["index_revision_ids"]),
            max_child_content_tokens=raw["max_child_content_tokens"],
            content_hash=content_hash,
        )

    def checkpoints(self) -> tuple[DocumentLearningCheckpoint, ...]:
        if not self._root.exists():
            return ()
        return tuple(
            self.load(path.stem)
            for path in sorted(self._root.glob("*.json"))
            if path.is_file()
        )


def _body(value: DocumentLearningCheckpoint) -> dict[str, object]:
    return {
        "checkpoint_id": value.checkpoint_id,
        "decomposition_id": value.decomposition_id,
        "objective": value.objective,
        "processed_leaf_refs": value.processed_leaf_refs,
        "pending_leaf_refs": value.pending_leaf_refs,
        "source_ref": value.source_ref,
        "source_sha256": value.source_sha256,
        "root_revision_id": value.root_revision_id,
        "leaf_revision_ids": value.leaf_revision_ids,
        "index_revision_ids": value.index_revision_ids,
        "max_child_content_tokens": value.max_child_content_tokens,
    }


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=list)
    return sha256(encoded.encode("utf-8")).hexdigest()
