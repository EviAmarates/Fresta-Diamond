"""Deterministic learning Gatekeeper and isolated append-only crystal store."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol
from uuid import uuid4

from fresta_diamond.contracts import (
    Artifact,
    ControllerResult,
    ExecutionState,
    RemainderKind,
)
from fresta_diamond.constitutional_firewall import nominate_constitutional_risks
from fresta_diamond.epistemology import (
    ClaimMode,
    EpistemicEvidenceDecodeError,
    decode_epistemic_evidence_graph,
)
from fresta_diamond.learning import LEARNING_PROPOSAL_SCHEMA
from fresta_diamond.ontology import STRUCTURAL_EVIDENCE_SCHEMA


CRYSTALLIZATION_BATCH_SCHEMA = "fresta://learning-crystallization-batch@1"
GATE_VERSION = "diamond-crystallization-gate@1"


class CrystalState(str, Enum):
    ACCEPTED = "ACCEPTED"
    PROVISIONAL = "PROVISIONAL"
    DEFERRED = "DEFERRED"
    QUARANTINED = "QUARANTINED"
    PHI_MINUS = "PHI_MINUS"


@dataclass(frozen=True)
class LearningCrystal:
    crystal_id: str
    candidate_ref: str
    source_element_id: str
    content: str
    scope: str
    provenance: tuple[str, ...]
    state: CrystalState
    claim_mode: ClaimMode | None
    reason_codes: tuple[str, ...]
    source_proposal_id: str
    structural_artifact_id: str | None
    epistemic_artifact_id: str | None
    parent_crystal_id: str | None = None


@dataclass(frozen=True)
class CrystallizationBatch:
    proposal_id: str
    crystals: tuple[LearningCrystal, ...]
    batch_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    gate_version: str = GATE_VERSION


class CrystallizationGate:
    """Derive candidate states without treating execution as confirmation."""

    _hard_failures = frozenset({
        RemainderKind.CONTRADICTION,
        RemainderKind.INVALID_SCOPE,
        RemainderKind.INVALID_DIRECTION,
        RemainderKind.POLICY_VIOLATION,
    })
    _provisional_modes = frozenset({
        ClaimMode.ATTESTATION,
        ClaimMode.HYPOTHESIS,
        ClaimMode.FORECAST,
    })

    def evaluate(
        self,
        proposal_artifact: Artifact,
        result: ControllerResult,
    ) -> CrystallizationBatch:
        if proposal_artifact.schema != LEARNING_PROPOSAL_SCHEMA:
            raise ValueError("Crystallization requires a learning proposal artifact")
        proposal = proposal_artifact.payload
        proposal_id = _text(proposal, "proposal_id")
        if proposal.get("promotion_authority") is not False:
            raise PermissionError("Learning proposal attempted to grant promotion")
        candidates = _object_sequence(proposal, "candidates")
        sheet_id = _text(proposal, "source_sheet_id")

        structural = result.execution.artifacts.get("structural_evidence")
        epistemic = result.execution.artifacts.get("epistemic_evidence")
        structural_report = (
            result.ontological_reports[0]
            if len(result.ontological_reports) == 1 else None
        )
        epistemic_report = (
            result.epistemic_reports[0]
            if len(result.epistemic_reports) == 1 else None
        )
        graph = None
        if epistemic is not None:
            try:
                graph = decode_epistemic_evidence_graph(epistemic.payload)
            except EpistemicEvidenceDecodeError:
                graph = None
        claims = {item.subject_ref: item for item in graph.claims} if graph else {}
        claim_reports = (
            {item.claim_id: item for item in epistemic_report.claim_reports}
            if epistemic_report is not None else {}
        )
        boundary_tampered = self._boundary_tampered(
            proposal_id, structural, epistemic
        )

        crystals = []
        for candidate in candidates:
            element_id = _text(candidate, "source_element_id")
            expected_subject = f"workspace-element:{sheet_id}:{element_id}"
            claim = claims.get(expected_subject)
            claim_report = (
                claim_reports.get(claim.claim_id) if claim is not None else None
            )
            state, reasons = self._derive_state(
                result=result,
                candidate=candidate,
                claim=claim,
                claim_report=claim_report,
                structural_report=structural_report,
                boundary_tampered=boundary_tampered,
            )
            crystals.append(LearningCrystal(
                crystal_id=str(uuid4()),
                candidate_ref=f"sheet-element:{sheet_id}:{element_id}",
                source_element_id=element_id,
                content=_text(candidate, "content"),
                scope=_text(candidate, "scope"),
                provenance=_text_sequence(candidate, "provenance"),
                state=state,
                claim_mode=claim.claim_mode if claim is not None else None,
                reason_codes=reasons,
                source_proposal_id=proposal_id,
                structural_artifact_id=(
                    structural.artifact_id if structural is not None else None
                ),
                epistemic_artifact_id=(
                    epistemic.artifact_id if epistemic is not None else None
                ),
            ))
        return CrystallizationBatch(
            proposal_id=proposal_id,
            crystals=tuple(crystals),
        )

    def _derive_state(
        self,
        *,
        result: ControllerResult,
        candidate: Mapping[str, Any],
        claim: Any,
        claim_report: Any,
        structural_report: Any,
        boundary_tampered: bool,
    ) -> tuple[CrystalState, tuple[str, ...]]:
        if boundary_tampered:
            return CrystalState.QUARANTINED, ("TRUSTED_BOUNDARY_MISMATCH",)
        if claim is not None and claim.content != _text(candidate, "content"):
            return CrystalState.QUARANTINED, ("CANDIDATE_CONTENT_MISMATCH",)
        if nominate_constitutional_risks(
            _text(candidate, "content")
        ).activated:
            return (
                CrystalState.QUARANTINED,
                ("CONSTITUTIONAL_SOURCE_REVIEW_REQUIRED",),
            )
        if result.execution.state is not ExecutionState.COMPLETED:
            if any(
                item.kind in self._hard_failures
                for item in result.execution.remainders
            ):
                return CrystalState.QUARANTINED, ("EXECUTION_POLICY_FAILURE",)
            return CrystalState.DEFERRED, ("EXECUTION_INCOMPLETE",)
        if structural_report is None:
            return CrystalState.DEFERRED, ("STRUCTURAL_EVALUATION_MISSING",)
        if any(
            item.kind in self._hard_failures
            for item in structural_report.active_remainders
        ):
            return CrystalState.QUARANTINED, ("STRUCTURAL_CONTRADICTION",)
        if not structural_report.structural_closed:
            return CrystalState.DEFERRED, ("STRUCTURAL_EVIDENCE_INCOMPLETE",)
        if claim is None or claim_report is None:
            return CrystalState.DEFERRED, ("EPISTEMIC_CLAIM_MISSING",)
        if (
            claim_report.contradicting_evidence
            or any(
                item.kind in self._hard_failures
                for item in claim_report.active_remainders
            )
        ):
            return CrystalState.QUARANTINED, ("LIVE_CONTRADICTION",)
        if not claim_report.burden_satisfied:
            return CrystalState.DEFERRED, ("EPISTEMIC_BURDEN_INCOMPLETE",)
        if claim.claim_mode in self._provisional_modes:
            return (
                CrystalState.PROVISIONAL,
                (f"{claim.claim_mode.value}_BURDEN_SATISFIED",),
            )
        return (
            CrystalState.ACCEPTED,
            (f"{claim.claim_mode.value}_BURDEN_SATISFIED",),
        )

    @staticmethod
    def _boundary_tampered(
        proposal_id: str,
        structural: Artifact | None,
        epistemic: Artifact | None,
    ) -> bool:
        if structural is None or epistemic is None:
            return False
        trusted = structural.payload.get("_learning_proposal")
        if not isinstance(trusted, Mapping):
            return True
        if trusted.get("proposal_id") != proposal_id:
            return True
        expected_object = f"learning-proposal:{proposal_id}"
        return (
            structural.schema != STRUCTURAL_EVIDENCE_SCHEMA
            or structural.payload.get("object_ref") != expected_object
            or epistemic.payload.get("object_ref") != expected_object
        )


@dataclass(frozen=True)
class StoredCrystallizationBatch:
    batch: CrystallizationBatch
    content_hash: str
    schema: str = CRYSTALLIZATION_BATCH_SCHEMA


class CrystalStoreError(RuntimeError):
    """A crystallization history could not be persisted or verified."""


class LearningCrystalStore(Protocol):
    def crystallize(
        self,
        proposal_artifact: Artifact,
        result: ControllerResult,
    ) -> StoredCrystallizationBatch:
        """Derive and append one gate-controlled batch."""


class JsonlLearningCrystalStore:
    """Isolated test store; accepts controller results, not caller-made states."""

    def __init__(
        self,
        root: str | Path,
        *,
        gate: CrystallizationGate | None = None,
        filename: str = "learning-crystals.jsonl",
    ) -> None:
        self._root = Path(root)
        self._path = self._root / filename
        self._gate = gate or CrystallizationGate()
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def crystallize(
        self,
        proposal_artifact: Artifact,
        result: ControllerResult,
    ) -> StoredCrystallizationBatch:
        proposed = self._gate.evaluate(proposal_artifact, result)
        with self._lock:
            records = self._read_verified_unlocked()
            latest: dict[str, LearningCrystal] = {}
            for record in records:
                for crystal in record.batch.crystals:
                    latest[crystal.candidate_ref] = crystal
            linked = replace(
                proposed,
                crystals=tuple(
                    replace(
                        crystal,
                        parent_crystal_id=(
                            latest[crystal.candidate_ref].crystal_id
                            if crystal.candidate_ref in latest else None
                        ),
                    )
                    for crystal in proposed.crystals
                ),
            )
            previous_hash = records[-1].content_hash if records else None
            body = {
                **encode_crystallization_batch(linked),
                "previous_record_hash": previous_hash,
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
                raise CrystalStoreError(
                    f"Could not persist crystallization: {type(exc).__name__}"
                ) from exc
            return StoredCrystallizationBatch(linked, content_hash)

    def batches(self) -> tuple[StoredCrystallizationBatch, ...]:
        with self._lock:
            return self._read_verified_unlocked()

    def history(self, candidate_ref: str) -> tuple[LearningCrystal, ...]:
        return tuple(
            crystal
            for record in self.batches()
            for crystal in record.batch.crystals
            if crystal.candidate_ref == candidate_ref
        )

    def latest(self, candidate_ref: str) -> LearningCrystal:
        history = self.history(candidate_ref)
        if not history:
            raise CrystalStoreError(f"Unknown candidate: {candidate_ref}")
        return history[-1]

    def _read_verified_unlocked(
        self,
    ) -> tuple[StoredCrystallizationBatch, ...]:
        if not self._path.exists():
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CrystalStoreError(
                f"Could not read crystallization history: {type(exc).__name__}"
            ) from exc
        records = []
        previous_hash = None
        seen_crystals = set()
        latest: dict[str, LearningCrystal] = {}
        for line_number, line in enumerate(lines, start=1):
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise TypeError("record is not an object")
                content_hash = raw.pop("content_hash")
                if not isinstance(content_hash, str):
                    raise TypeError("content_hash is not text")
                if _hash_body(raw) != content_hash:
                    raise CrystalStoreError(
                        f"Crystal history hash mismatch at line {line_number}"
                    )
                if raw.get("previous_record_hash") != previous_hash:
                    raise CrystalStoreError(
                        f"Crystal history chain mismatch at line {line_number}"
                    )
                batch = decode_crystallization_batch(raw)
                for crystal in batch.crystals:
                    if crystal.crystal_id in seen_crystals:
                        raise CrystalStoreError("Duplicate crystal ID")
                    expected_parent = (
                        latest[crystal.candidate_ref].crystal_id
                        if crystal.candidate_ref in latest else None
                    )
                    if crystal.parent_crystal_id != expected_parent:
                        raise CrystalStoreError("Crystal lineage mismatch")
                    seen_crystals.add(crystal.crystal_id)
                    latest[crystal.candidate_ref] = crystal
            except CrystalStoreError:
                raise
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise CrystalStoreError(
                    f"Malformed crystal record at line {line_number}: {exc}"
                ) from exc
            records.append(StoredCrystallizationBatch(batch, content_hash))
            previous_hash = content_hash
        return tuple(records)


def encode_crystallization_batch(batch: CrystallizationBatch) -> dict[str, Any]:
    return {
        "schema": CRYSTALLIZATION_BATCH_SCHEMA,
        "batch_id": batch.batch_id,
        "created_at": batch.created_at,
        "gate_version": batch.gate_version,
        "proposal_id": batch.proposal_id,
        "crystals": [
            {
                "crystal_id": item.crystal_id,
                "candidate_ref": item.candidate_ref,
                "source_element_id": item.source_element_id,
                "content": item.content,
                "scope": item.scope,
                "provenance": list(item.provenance),
                "state": item.state.value,
                "claim_mode": (
                    item.claim_mode.value if item.claim_mode is not None else None
                ),
                "reason_codes": list(item.reason_codes),
                "source_proposal_id": item.source_proposal_id,
                "structural_artifact_id": item.structural_artifact_id,
                "epistemic_artifact_id": item.epistemic_artifact_id,
                "parent_crystal_id": item.parent_crystal_id,
            }
            for item in batch.crystals
        ],
    }


def decode_crystallization_batch(value: Mapping[str, Any]) -> CrystallizationBatch:
    if value.get("schema") != CRYSTALLIZATION_BATCH_SCHEMA:
        raise ValueError("unknown crystallization batch schema")
    crystals = []
    for item in _object_sequence(value, "crystals"):
        raw_mode = item.get("claim_mode")
        if raw_mode is not None and not isinstance(raw_mode, str):
            raise TypeError("claim_mode must be text or null")
        crystals.append(LearningCrystal(
            crystal_id=_text(item, "crystal_id"),
            candidate_ref=_text(item, "candidate_ref"),
            source_element_id=_text(item, "source_element_id"),
            content=_text(item, "content"),
            scope=_text(item, "scope"),
            provenance=_text_sequence(item, "provenance"),
            state=CrystalState(_text(item, "state")),
            claim_mode=ClaimMode(raw_mode) if raw_mode is not None else None,
            reason_codes=_text_sequence(item, "reason_codes"),
            source_proposal_id=_text(item, "source_proposal_id"),
            structural_artifact_id=_optional_text(item, "structural_artifact_id"),
            epistemic_artifact_id=_optional_text(item, "epistemic_artifact_id"),
            parent_crystal_id=_optional_text(item, "parent_crystal_id"),
        ))
    return CrystallizationBatch(
        batch_id=_text(value, "batch_id"),
        created_at=_text(value, "created_at"),
        gate_version=_text(value, "gate_version"),
        proposal_id=_text(value, "proposal_id"),
        crystals=tuple(crystals),
    )


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


def _text_sequence(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid text")
    return tuple(items)


def _object_sequence(
    value: Mapping[str, Any],
    key: str,
) -> tuple[Mapping[str, Any], ...]:
    items = value.get(key)
    if not isinstance(items, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, Mapping) for item in items):
        raise TypeError(f"{key} must contain objects")
    return tuple(items)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()
