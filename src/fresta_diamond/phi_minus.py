"""Conservative Φ− boundary observations derived after crystallization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from fresta_diamond.contracts import ControllerResult
from fresta_diamond.crystallization import (
    CrystalState,
    CrystallizationBatch,
    LearningCrystal,
)
from fresta_diamond.journal import (
    EventJournal,
    JournalArchiveError,
    JournalEvent,
    JournalEventKind,
    JsonlJournalArchive,
)


PHI_MINUS_OBSERVATION_SCHEMA = "fresta://phi-minus-observation@1"


class NegativeBoundaryDisposition(str, Enum):
    """Outcome of checking the negative side of one candidate boundary."""

    EXCLUDED = "EXCLUDED"
    INDETERMINATE = "INDETERMINATE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class PhiMinusObservation:
    """Auditable negative-boundary result with no rule-promotion authority."""

    observation_id: str
    batch_id: str
    proposal_id: str
    candidate_ref: str
    source_element_id: str
    scope: str
    provenance: tuple[str, ...]
    disposition: NegativeBoundaryDisposition
    phi_minus_justified: bool
    reason_codes: tuple[str, ...]
    remainder_kinds: tuple[str, ...]
    source_crystal_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        required = (
            self.observation_id,
            self.batch_id,
            self.proposal_id,
            self.candidate_ref,
            self.source_element_id,
            self.scope,
            self.source_crystal_id,
            self.created_at,
        )
        if any(not item.strip() for item in required):
            raise ValueError("Φ− observation references must be non-empty")
        if self.promotion_authority is not False:
            raise PermissionError("Φ− observations cannot grant rule promotion")
        if self.phi_minus_justified != (
            self.disposition is NegativeBoundaryDisposition.EXCLUDED
        ):
            raise ValueError(
                "Only an EXCLUDED boundary may be justified as Φ−"
            )
        if not self.reason_codes:
            raise ValueError("Φ− observation requires at least one reason")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "remainder_kinds", tuple(self.remainder_kinds))


class PhiMinusMemoryError(RuntimeError):
    """The negative-boundary history could not be preserved safely."""


class PhiMinusDeriver:
    """Map Gatekeeper outcomes onto the negative frontier without an LLM."""

    def derive(
        self,
        batch: CrystallizationBatch,
        result: ControllerResult,
    ) -> tuple[PhiMinusObservation, ...]:
        remainder_kinds = tuple(sorted({
            item.kind.value for item in result.execution.remainders
        }))
        observations = []
        for crystal in batch.crystals:
            disposition = self._disposition(crystal)
            if disposition is None:
                continue
            observations.append(PhiMinusObservation(
                observation_id=f"phi-minus:{uuid4()}",
                batch_id=batch.batch_id,
                proposal_id=batch.proposal_id,
                candidate_ref=crystal.candidate_ref,
                source_element_id=crystal.source_element_id,
                scope=crystal.scope,
                provenance=crystal.provenance,
                disposition=disposition,
                phi_minus_justified=(
                    disposition is NegativeBoundaryDisposition.EXCLUDED
                ),
                reason_codes=crystal.reason_codes,
                remainder_kinds=remainder_kinds,
                source_crystal_id=crystal.crystal_id,
            ))
        return tuple(observations)

    @staticmethod
    def _disposition(
        crystal: LearningCrystal,
    ) -> NegativeBoundaryDisposition | None:
        if crystal.state in {CrystalState.QUARANTINED, CrystalState.PHI_MINUS}:
            return NegativeBoundaryDisposition.EXCLUDED
        if crystal.state is CrystalState.DEFERRED:
            return NegativeBoundaryDisposition.INDETERMINATE
        return None


class JsonlPhiMinusMemory:
    """Append-only Φ− audit built on the existing sealed journal archive."""

    def __init__(
        self,
        root: str | Path,
        *,
        deriver: PhiMinusDeriver | None = None,
        journal: EventJournal | None = None,
    ) -> None:
        self._journal = journal or EventJournal()
        self._archive = JsonlJournalArchive(
            root,
            filename="phi-minus-segments.jsonl",
        )
        self._deriver = deriver or PhiMinusDeriver()

    @property
    def path(self) -> Path:
        return self._archive.path

    def record(
        self,
        batch: CrystallizationBatch,
        result: ControllerResult,
    ) -> tuple[PhiMinusObservation, ...]:
        if any(item.batch_id == batch.batch_id for item in self.observations()):
            raise PhiMinusMemoryError(
                f"Crystallization batch already recorded: {batch.batch_id}"
            )
        observations = self._deriver.derive(batch, result)
        if not observations:
            return ()
        events = tuple(
            self._journal.append(
                JournalEventKind.PHI_MINUS_RECORDED,
                correlation_id=f"learn-proposal:{batch.proposal_id}",
                subject_ref=observation.candidate_ref,
                payload=encode_phi_minus_observation(observation),
            )
            for observation in observations
        )
        try:
            self._archive.archive(events)
        except JournalArchiveError as exc:
            raise PhiMinusMemoryError(
                f"Could not archive Φ− observations: {type(exc).__name__}"
            ) from exc
        return observations

    def observations(self) -> tuple[PhiMinusObservation, ...]:
        values = []
        for segment in self._archive.segments():
            for event in segment.events:
                if event.kind is JournalEventKind.PHI_MINUS_RECORDED:
                    values.append(_observation_from_event(event))
        return tuple(values)

    def for_scope(
        self,
        scope: str,
        *,
        disposition: NegativeBoundaryDisposition | None = None,
    ) -> tuple[PhiMinusObservation, ...]:
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("Φ− retrieval scope is required")
        return tuple(
            item
            for item in self.observations()
            if item.scope == scope
            and (disposition is None or item.disposition is disposition)
        )

    def for_candidate(
        self,
        candidate_ref: str,
    ) -> tuple[PhiMinusObservation, ...]:
        if not isinstance(candidate_ref, str) or not candidate_ref.strip():
            raise ValueError("Φ− candidate reference is required")
        return tuple(
            item
            for item in self.observations()
            if item.candidate_ref == candidate_ref
        )


def encode_phi_minus_observation(
    observation: PhiMinusObservation,
) -> dict[str, Any]:
    return {
        "schema": PHI_MINUS_OBSERVATION_SCHEMA,
        "observation_id": observation.observation_id,
        "batch_id": observation.batch_id,
        "proposal_id": observation.proposal_id,
        "candidate_ref": observation.candidate_ref,
        "source_element_id": observation.source_element_id,
        "scope": observation.scope,
        "provenance": list(observation.provenance),
        "disposition": observation.disposition.value,
        "phi_minus_justified": observation.phi_minus_justified,
        "reason_codes": list(observation.reason_codes),
        "remainder_kinds": list(observation.remainder_kinds),
        "source_crystal_id": observation.source_crystal_id,
        "created_at": observation.created_at,
        "promotion_authority": False,
    }


def decode_phi_minus_observation(
    value: Mapping[str, Any],
) -> PhiMinusObservation:
    if value.get("schema") != PHI_MINUS_OBSERVATION_SCHEMA:
        raise ValueError("Unknown Φ− observation schema")
    promotion = value.get("promotion_authority")
    if promotion is not False:
        raise PermissionError("Persisted Φ− observation grants authority")
    return PhiMinusObservation(
        observation_id=_text(value, "observation_id"),
        batch_id=_text(value, "batch_id"),
        proposal_id=_text(value, "proposal_id"),
        candidate_ref=_text(value, "candidate_ref"),
        source_element_id=_text(value, "source_element_id"),
        scope=_text(value, "scope"),
        provenance=_text_tuple(value, "provenance"),
        disposition=NegativeBoundaryDisposition(_text(value, "disposition")),
        phi_minus_justified=_boolean(value, "phi_minus_justified"),
        reason_codes=_text_tuple(value, "reason_codes"),
        remainder_kinds=_text_tuple(value, "remainder_kinds", allow_empty=True),
        source_crystal_id=_text(value, "source_crystal_id"),
        created_at=_text(value, "created_at"),
        promotion_authority=promotion,
    )


def _observation_from_event(event: JournalEvent) -> PhiMinusObservation:
    if event.kind is not JournalEventKind.PHI_MINUS_RECORDED:
        raise ValueError("Journal event is not a Φ− observation")
    return decode_phi_minus_observation(event.payload)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _text_tuple(
    value: Mapping[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if not allow_empty and not raw:
        raise ValueError(f"{key} cannot be empty")
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ValueError(f"{key} contains invalid text")
    return tuple(raw)


def _boolean(value: Mapping[str, Any], key: str) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise TypeError(f"{key} must be boolean")
    return item
