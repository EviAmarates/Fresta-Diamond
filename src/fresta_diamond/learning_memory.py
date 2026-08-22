"""Atomic autonomous learning commits for the Fresta Diamond."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from fresta_diamond.contracts import Artifact, ControllerResult
from fresta_diamond.crystallization import (
    CrystalState,
    CrystallizationBatch,
    CrystallizationGate,
    LearningCrystal,
    decode_crystallization_batch,
    encode_crystallization_batch,
)
from fresta_diamond.phi_minus import (
    PhiMinusDeriver,
    PhiMinusObservation,
    decode_phi_minus_observation,
    encode_phi_minus_observation,
)


LEARNING_COMMIT_SCHEMA = "fresta://diamond-learning-commit@1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class LearningCommit:
    """One inseparable positive/negative result from a Gatekeeper batch."""

    commit_id: str
    proposal_id: str
    crystallization: CrystallizationBatch
    negative_boundary: tuple[PhiMinusObservation, ...]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.commit_id):
            raise ValueError("Learning commit ID is invalid")
        if not self.proposal_id.strip() or not self.created_at.strip():
            raise ValueError("Learning commit references are required")
        if self.promotion_authority is not False:
            raise PermissionError("Learning commits cannot grant promotion authority")
        if self.crystallization.proposal_id != self.proposal_id:
            raise ValueError("Commit and crystallization proposal IDs differ")
        object.__setattr__(
            self, "negative_boundary", tuple(self.negative_boundary)
        )
        _validate_boundary_pair(
            self.crystallization, self.negative_boundary
        )


@dataclass(frozen=True)
class StoredLearningCommit:
    commit: LearningCommit
    content_hash: str
    path: Path


class LearningMemoryError(RuntimeError):
    """A learning commit could not be safely written, read, or recovered."""


class CrystalRetrievalPolicy(str, Enum):
    ACTIVE = "ACTIVE"
    FALLBACK = "FALLBACK"
    AUDIT = "AUDIT"


class AtomicDiamondLearningMemory:
    """File-per-commit memory with recoverable prepare/finalize semantics."""

    def __init__(
        self,
        root: str | Path,
        *,
        gate: CrystallizationGate | None = None,
        deriver: PhiMinusDeriver | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
        finalizer: Callable[[Path, Path], None] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._commits = self._root / "commits"
        self._pending = self._root / "pending"
        self._gate = gate or CrystallizationGate()
        self._deriver = deriver or PhiMinusDeriver()
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )
        self._finalizer = finalizer or _atomic_finalize

    @property
    def root(self) -> Path:
        return self._root

    def commit(
        self,
        proposal_artifact: Artifact,
        result: ControllerResult,
    ) -> StoredLearningCommit:
        batch = self._gate.evaluate(proposal_artifact, result)
        return self.commit_batch(batch, result)

    def commit_batch(
        self,
        batch: CrystallizationBatch,
        result: ControllerResult,
    ) -> StoredLearningCommit:
        if any(
            item.commit.proposal_id == batch.proposal_id
            for item in self.commits()
        ):
            raise LearningMemoryError(
                f"Learning proposal already committed: {batch.proposal_id}"
            )
        commit_id = self._id_factory()
        if not isinstance(commit_id, str) or not _SAFE_ID.fullmatch(commit_id):
            raise LearningMemoryError("Learning memory generated an invalid commit ID")
        commit = LearningCommit(
            commit_id=commit_id,
            proposal_id=batch.proposal_id,
            crystallization=batch,
            negative_boundary=self._deriver.derive(batch, result),
            created_at=self._clock(),
        )
        record = encode_learning_commit(commit)
        body = dict(record)
        content_hash = _hash_body(body)
        payload = {**body, "content_hash": content_hash}
        self._pending.mkdir(parents=True, exist_ok=True)
        pending = self._pending / f"{commit_id}.json.pending"
        final = self._commits / f"{commit_id}.json"
        if pending.exists() or final.exists():
            raise LearningMemoryError(f"Duplicate learning commit ID: {commit_id}")
        try:
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(_canonical_json(payload) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._commits.mkdir(parents=True, exist_ok=True)
            self._finalizer(pending, final)
        except OSError as exc:
            raise LearningMemoryError(
                f"Learning commit remains pending: {type(exc).__name__}"
            ) from exc
        return StoredLearningCommit(commit, content_hash, final)

    def commits(self) -> tuple[StoredLearningCommit, ...]:
        if not self._commits.exists():
            return ()
        records = tuple(
            self._read_record(path)
            for path in self._commits.glob("*.json")
            if path.is_file()
        )
        proposal_ids: set[str] = set()
        commit_ids: set[str] = set()
        for record in records:
            commit = record.commit
            if commit.commit_id in commit_ids:
                raise LearningMemoryError("Duplicate learning commit ID")
            if commit.proposal_id in proposal_ids:
                raise LearningMemoryError("Duplicate committed learning proposal")
            commit_ids.add(commit.commit_id)
            proposal_ids.add(commit.proposal_id)
        return tuple(sorted(
            records,
            key=lambda item: (
                item.commit.created_at,
                item.commit.commit_id,
            ),
        ))

    def pending(self) -> tuple[StoredLearningCommit, ...]:
        if not self._pending.exists():
            return ()
        return tuple(
            self._read_record(path)
            for path in sorted(self._pending.glob("*.json.pending"))
            if path.is_file()
        )

    def recover_pending(self) -> tuple[StoredLearningCommit, ...]:
        recovered = []
        committed_proposals = {
            item.commit.proposal_id for item in self.commits()
        }
        for record in self.pending():
            commit = record.commit
            if commit.proposal_id in committed_proposals:
                raise LearningMemoryError(
                    "Pending commit duplicates an already committed proposal"
                )
            final = self._commits / f"{commit.commit_id}.json"
            if final.exists():
                raise LearningMemoryError(
                    f"Pending commit target already exists: {commit.commit_id}"
                )
            try:
                self._commits.mkdir(parents=True, exist_ok=True)
                self._finalizer(record.path, final)
            except OSError as exc:
                raise LearningMemoryError(
                    f"Could not recover pending commit: {type(exc).__name__}"
                ) from exc
            recovered_record = StoredLearningCommit(
                commit, record.content_hash, final
            )
            recovered.append(recovered_record)
            committed_proposals.add(commit.proposal_id)
        return tuple(recovered)

    def crystals(
        self,
        *,
        scope: str | None = None,
        policy: CrystalRetrievalPolicy = CrystalRetrievalPolicy.ACTIVE,
        states: tuple[CrystalState, ...] | None = None,
    ) -> tuple[LearningCrystal, ...]:
        policy = CrystalRetrievalPolicy(policy)
        if states is not None:
            allowed = set(states)
        elif policy is CrystalRetrievalPolicy.ACTIVE:
            allowed = {CrystalState.ACCEPTED, CrystalState.PROVISIONAL}
        elif policy is CrystalRetrievalPolicy.FALLBACK:
            allowed = {
                CrystalState.ACCEPTED,
                CrystalState.PROVISIONAL,
                CrystalState.DEFERRED,
            }
        else:
            allowed = set(CrystalState)
        return tuple(
            crystal
            for record in self.commits()
            for crystal in record.commit.crystallization.crystals
            if (scope is None or crystal.scope == scope)
            and crystal.state in allowed
        )

    def negative_boundary(
        self,
        *,
        scope: str | None = None,
        justified_only: bool = False,
    ) -> tuple[PhiMinusObservation, ...]:
        return tuple(
            observation
            for record in self.commits()
            for observation in record.commit.negative_boundary
            if (scope is None or observation.scope == scope)
            and (
                not justified_only or observation.phi_minus_justified
            )
        )

    def _read_record(self, path: Path) -> StoredLearningCommit:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("record is not an object")
            content_hash = raw.pop("content_hash")
            if not isinstance(content_hash, str):
                raise TypeError("content_hash is not text")
            if _hash_body(raw) != content_hash:
                raise LearningMemoryError(
                    f"Learning commit hash mismatch: {path.name}"
                )
            commit = decode_learning_commit(raw)
            expected_names = {
                f"{commit.commit_id}.json",
                f"{commit.commit_id}.json.pending",
            }
            if path.name not in expected_names:
                raise LearningMemoryError(
                    f"Learning commit filename mismatch: {path.name}"
                )
            return StoredLearningCommit(commit, content_hash, path)
        except LearningMemoryError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LearningMemoryError(
                f"Malformed learning commit {path.name}: {exc}"
            ) from exc


def encode_learning_commit(commit: LearningCommit) -> dict[str, Any]:
    return {
        "schema": LEARNING_COMMIT_SCHEMA,
        "commit_id": commit.commit_id,
        "proposal_id": commit.proposal_id,
        "created_at": commit.created_at,
        "promotion_authority": False,
        "crystallization": encode_crystallization_batch(
            commit.crystallization
        ),
        "negative_boundary": [
            encode_phi_minus_observation(item)
            for item in commit.negative_boundary
        ],
    }


def decode_learning_commit(value: Mapping[str, Any]) -> LearningCommit:
    if value.get("schema") != LEARNING_COMMIT_SCHEMA:
        raise ValueError("Unknown Diamond learning commit schema")
    if value.get("promotion_authority") is not False:
        raise PermissionError("Persisted learning commit grants authority")
    raw_batch = value.get("crystallization")
    raw_boundary = value.get("negative_boundary")
    if not isinstance(raw_batch, Mapping):
        raise TypeError("Learning commit crystallization must be an object")
    if not isinstance(raw_boundary, list):
        raise TypeError("Learning commit negative boundary must be an array")
    boundary = tuple(
        decode_phi_minus_observation(item)
        for item in raw_boundary
        if isinstance(item, Mapping)
    )
    if len(boundary) != len(raw_boundary):
        raise TypeError("Learning commit contains invalid boundary records")
    return LearningCommit(
        commit_id=_text(value, "commit_id"),
        proposal_id=_text(value, "proposal_id"),
        crystallization=decode_crystallization_batch(raw_batch),
        negative_boundary=boundary,
        created_at=_text(value, "created_at"),
        promotion_authority=False,
    )


def _validate_boundary_pair(
    batch: CrystallizationBatch,
    boundary: tuple[PhiMinusObservation, ...],
) -> None:
    crystals = {item.crystal_id: item for item in batch.crystals}
    if len(crystals) != len(batch.crystals):
        raise ValueError("Learning commit contains duplicate crystal IDs")
    seen: set[str] = set()
    for observation in boundary:
        if observation.observation_id in seen:
            raise ValueError("Learning commit contains duplicate Φ− observations")
        seen.add(observation.observation_id)
        crystal = crystals.get(observation.source_crystal_id)
        if crystal is None:
            raise ValueError("Φ− observation references an unknown crystal")
        if observation.batch_id != batch.batch_id:
            raise ValueError("Φ− observation references another batch")
        if (
            observation.proposal_id != batch.proposal_id
            or observation.candidate_ref != crystal.candidate_ref
            or observation.source_element_id != crystal.source_element_id
            or observation.scope != crystal.scope
        ):
            raise ValueError("Φ− observation boundary references diverge")
    expected = {
        item.crystal_id
        for item in batch.crystals
        if item.state in {
            CrystalState.DEFERRED,
            CrystalState.QUARANTINED,
            CrystalState.PHI_MINUS,
        }
    }
    observed = {item.source_crystal_id for item in boundary}
    if expected != observed:
        raise ValueError(
            "Learning commit does not cover its complete negative boundary"
        )


def _atomic_finalize(pending: Path, final: Path) -> None:
    os.replace(pending, final)


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
