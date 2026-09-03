"""Append-only durable memory for ontology and meta-analysis reports."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from fresta_diamond.meta_analysis import (
    MetaAnalysisReport,
    decode_meta_analysis,
    encode_meta_analysis,
)


@dataclass(frozen=True)
class StoredMetaAnalysis:
    report: MetaAnalysisReport
    version: int
    content_hash: str
    path: Path

    @property
    def version_ref(self) -> str:
        return f"meta-analysis:{self.report.meta_analysis_id}@{self.version}"


class MetaMemoryStore:
    """Persist meta-analysis reports without allowing in-place replacement."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._records = self._root / "records"

    def save(self, report: MetaAnalysisReport) -> StoredMetaAnalysis:
        history = self.history(report.meta_analysis_id)
        version = len(history) + 1
        body = {
            "version": version,
            "previous_version_ref": history[-1].version_ref if history else None,
            "report": encode_meta_analysis(report),
        }
        content_hash = _hash(body)
        payload = {**body, "content_hash": content_hash}
        self._records.mkdir(parents=True, exist_ok=True)
        path = self._records / f"{_filename(report.meta_analysis_id)}.v{version}.json"
        if path.exists():
            raise ValueError("Meta-analysis version already exists")
        pending = path.with_suffix(".json.pending")
        try:
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, path)
        except OSError as exc:
            raise RuntimeError(f"Could not persist meta-analysis: {type(exc).__name__}") from exc
        return StoredMetaAnalysis(report, version, content_hash, path)

    def records(self) -> tuple[StoredMetaAnalysis, ...]:
        if not self._records.exists():
            return ()
        return tuple(
            self._read(path)
            for path in sorted(self._records.glob("*.json"))
            if path.is_file()
        )

    def history(self, meta_analysis_id: str) -> tuple[StoredMetaAnalysis, ...]:
        return tuple(item for item in self.records()
                     if item.report.meta_analysis_id == meta_analysis_id)

    def latest(self, meta_analysis_id: str) -> StoredMetaAnalysis:
        history = self.history(meta_analysis_id)
        if not history:
            raise ValueError("Unknown meta-analysis")
        return history[-1]

    def _read(self, path: Path) -> StoredMetaAnalysis:
        raw = json.loads(path.read_text(encoding="utf-8"))
        content_hash = raw.pop("content_hash")
        if _hash(raw) != content_hash:
            raise ValueError("Meta-analysis memory hash mismatch")
        report = decode_meta_analysis(raw["report"])
        return StoredMetaAnalysis(report, raw["version"], content_hash, path)


def _filename(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:32]


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=list).encode("utf-8")
    ).hexdigest()
