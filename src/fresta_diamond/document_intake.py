"""Deterministic, content-addressed document intake."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fresta_diamond.contracts import (
    SourceDocument,
    TypedProvenance,
    decode_provenance,
)


DOCUMENT_INTAKE_AUTHORITY = "UNVALIDATED_DOCUMENT_INTAKE"


@dataclass(frozen=True)
class DocumentSource:
    source_ref: str
    path: str
    content: str
    content_sha256: str
    byte_length: int
    authority: str = DOCUMENT_INTAKE_AUTHORITY
    provenance: TypedProvenance | tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.authority != DOCUMENT_INTAKE_AUTHORITY:
            raise PermissionError("Document intake cannot grant learning authority")
        if not self.source_ref.startswith("document:"):
            raise ValueError("Document source reference is invalid")
        if sha256(self.content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("Document content hash does not match")
        object.__setattr__(
            self,
            "provenance",
            decode_provenance(self.provenance or (self.source_ref,)),
        )

    @property
    def source_document(self) -> SourceDocument:
        return SourceDocument(
            document_ref=self.source_ref,
            locator=self.path,
            content_hash=self.content_sha256,
            provenance=self.provenance,
            content=self.content,
        )


def read_document(path: str | Path, *, max_bytes: int = 10_000_000) -> DocumentSource:
    resolved = Path(path).resolve()
    if max_bytes < 1:
        raise ValueError("Document byte limit must be positive")
    if not resolved.is_file():
        raise ValueError("Document path must identify a regular file")
    raw = resolved.read_bytes()
    if not raw:
        raise ValueError("Document cannot be empty")
    if len(raw) > max_bytes:
        raise ValueError("Document exceeds the configured byte limit")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Document must be UTF-8 text") from exc
    content_hash = sha256(raw).hexdigest()
    return DocumentSource(
        source_ref=f"document:{content_hash}",
        path=str(resolved),
        content=content,
        content_sha256=content_hash,
        byte_length=len(raw),
    )
