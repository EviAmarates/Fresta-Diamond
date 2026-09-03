"""Conservative escalation policy for firewall-confirmed severe risk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from fresta_diamond.contracts import (
    ExecutionPlan,
    PlanState,
    Remainder,
    RemainderKind,
)
from fresta_diamond.constitutional_firewall import (
    FirewallAttestation,
    FirewallDecision,
)
from fresta_diamond.journal import EventJournal, JournalArchive, JournalEventKind
from fresta_diamond.meta_analysis import (
    EpistemicState,
    LensAssessment,
    MetaAnalysisReport,
    MetaAnalysisState,
    RecoverabilityState,
)
from fresta_diamond.meta_memory import MetaMemoryStore, StoredMetaAnalysis
from fresta_diamond.workspace import (
    CheckpointStore,
    ExecutionBudget,
    RuntimeCheckpoint,
    StoredCheckpointRef,
)


class FirewallRiskSeverity(str, Enum):
    NONE = "NONE"
    REVIEW = "REVIEW"
    GRAVE = "GRAVE"


@dataclass(frozen=True)
class FirewallEscalation:
    severity: FirewallRiskSeverity
    decision: FirewallDecision
    requires_checkpoint: bool
    requires_meta_analysis: bool
    phi_closed: bool = False

    def __post_init__(self) -> None:
        if self.requires_meta_analysis and not self.requires_checkpoint:
            raise ValueError("Meta-analysis escalation requires a checkpoint")
        if self.phi_closed:
            raise PermissionError("Risk escalation cannot close Phi")


@dataclass(frozen=True)
class FirewallEscalationMetaAnalysisInput:
    objective: str
    attestation: FirewallAttestation

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("Firewall escalation requires an objective")


@dataclass(frozen=True)
class FirewallEscalationMetaAnalysisReport:
    consultative_input: FirewallEscalationMetaAnalysisInput
    escalation: FirewallEscalation
    consultative_checkpoint: RuntimeCheckpoint | None
    stored_checkpoint: StoredCheckpointRef | None
    meta_analysis_report: MetaAnalysisReport | None
    stored_meta_analysis: StoredMetaAnalysis | None
    journal_event_ids: tuple[str, ...]
    journal_segment_hash: str | None = None
    controller_integration_pending: bool = False

    def __post_init__(self) -> None:
        if self.escalation.decision is FirewallDecision.DENY:
            if self.consultative_checkpoint is None:
                raise ValueError("Deny escalation requires a checkpoint")
            if self.meta_analysis_report is None:
                raise ValueError("Deny escalation requires a consultative report")
        if self.escalation.decision is not FirewallDecision.DENY:
            if self.consultative_checkpoint is not None or self.meta_analysis_report is not None:
                raise ValueError("Only deny escalation creates consultative artifacts")
        if self.meta_analysis_report is not None and not self.meta_analysis_report.phi_open:
            raise PermissionError("Consultative meta-analysis cannot close Phi")

    @property
    def phi_open(self) -> bool:
        if self.meta_analysis_report is None:
            return True
        return self.meta_analysis_report.phi_open


def assess_firewall_escalation(
    decision: FirewallDecision,
) -> FirewallEscalation:
    """Map firewall decisions to a conservative, non-authoritative escalation."""

    if decision is FirewallDecision.DENY:
        return FirewallEscalation(
            FirewallRiskSeverity.GRAVE,
            decision,
            requires_checkpoint=True,
            requires_meta_analysis=True,
        )
    if decision is FirewallDecision.QUARANTINE:
        return FirewallEscalation(
            FirewallRiskSeverity.REVIEW,
            decision,
            requires_checkpoint=False,
            requires_meta_analysis=False,
        )
    return FirewallEscalation(
        FirewallRiskSeverity.NONE,
        decision,
        requires_checkpoint=False,
        requires_meta_analysis=False,
    )


class FirewallEscalationService:
    """Persist conservative firewall escalations without claiming authority."""

    def __init__(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        journal: EventJournal | None = None,
        journal_archive: JournalArchive | None = None,
        meta_memory_store: MetaMemoryStore | None = None,
        checkpoint_id_factory: Callable[[], str] | None = None,
        meta_analysis_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if journal_archive is not None and journal is None:
            raise ValueError("Journal archive requires an injected EventJournal")
        self._checkpoint_store = checkpoint_store
        self._journal = journal
        self._journal_archive = journal_archive
        self._meta_memory_store = meta_memory_store
        self._checkpoint_id_factory = checkpoint_id_factory or (lambda: str(uuid4()))
        self._meta_analysis_id_factory = meta_analysis_id_factory or (lambda: str(uuid4()))

    def consult(
        self,
        consultative_input: FirewallEscalationMetaAnalysisInput,
    ) -> FirewallEscalationMetaAnalysisReport:
        escalation = assess_firewall_escalation(consultative_input.attestation.decision)
        if escalation.decision is not FirewallDecision.DENY:
            return FirewallEscalationMetaAnalysisReport(
                consultative_input=consultative_input,
                escalation=escalation,
                consultative_checkpoint=None,
                stored_checkpoint=None,
                meta_analysis_report=None,
                stored_meta_analysis=None,
                journal_event_ids=(),
                controller_integration_pending=False,
            )

        checkpoint = self._build_checkpoint(consultative_input)
        checkpoint_hash = _checkpoint_content_hash(checkpoint)
        stored_checkpoint = (
            self._checkpoint_store.save(checkpoint)
            if self._checkpoint_store is not None
            else None
        )

        journal_position = self._journal.position if self._journal is not None else 0
        journal_event_ids: list[str] = []
        checkpoint_event_id = self._record(
            JournalEventKind.CHECKPOINT_CREATED,
            consultative_input.attestation.analysis_id,
            checkpoint.checkpoint_id,
            {
                "objective": consultative_input.objective,
                "analysis_id": consultative_input.attestation.analysis_id,
                "decision": consultative_input.attestation.decision.value,
                "severity": escalation.severity.value,
                "checkpoint_id": checkpoint.checkpoint_id,
                "checkpoint_content_hash": (
                    stored_checkpoint.content_hash
                    if stored_checkpoint is not None
                    else checkpoint_hash
                ),
                "controller_integration_pending": True,
                "phi_open": True,
            },
        )
        if checkpoint_event_id is not None:
            journal_event_ids.append(checkpoint_event_id)

        meta_analysis_id = self._meta_analysis_id_factory()
        meta_report = self._build_meta_analysis_report(
            consultative_input,
            escalation,
            checkpoint,
            meta_analysis_id,
        )
        stored_meta_analysis = (
            self._meta_memory_store.save(meta_report)
            if self._meta_memory_store is not None
            else None
        )

        escalation_event_id = self._record(
            JournalEventKind.FIREWALL_ESCALATION_RECORDED,
            consultative_input.attestation.analysis_id,
            meta_report.meta_analysis_id,
            {
                "objective": consultative_input.objective,
                "analysis_id": consultative_input.attestation.analysis_id,
                "decision": consultative_input.attestation.decision.value,
                "severity": escalation.severity.value,
                "checkpoint_id": checkpoint.checkpoint_id,
                "checkpoint_content_hash": (
                    stored_checkpoint.content_hash
                    if stored_checkpoint is not None
                    else checkpoint_hash
                ),
                "meta_analysis_id": meta_report.meta_analysis_id,
                "meta_analysis_version_ref": (
                    stored_meta_analysis.version_ref
                    if stored_meta_analysis is not None
                    else None
                ),
                "phi_open": meta_report.phi_open,
                "controller_integration_pending": True,
            },
        )
        if escalation_event_id is not None:
            journal_event_ids.append(escalation_event_id)

        journal_segment_hash = None
        if self._journal is not None and self._journal_archive is not None:
            journal_segment_hash = self._archive_consultation(
                journal_position,
            )

        return FirewallEscalationMetaAnalysisReport(
            consultative_input=consultative_input,
            escalation=escalation,
            consultative_checkpoint=checkpoint,
            stored_checkpoint=stored_checkpoint,
            meta_analysis_report=meta_report,
            stored_meta_analysis=stored_meta_analysis,
            journal_event_ids=tuple(journal_event_ids),
            journal_segment_hash=journal_segment_hash,
            controller_integration_pending=True,
        )

    def _build_checkpoint(
        self,
        consultative_input: FirewallEscalationMetaAnalysisInput,
    ) -> RuntimeCheckpoint:
        return RuntimeCheckpoint(
            plan=ExecutionPlan(
                blueprint_id="firewall-escalation",
                blueprint_version=1,
                objective=consultative_input.objective,
                nodes=(),
                external_artifacts={},
                state=PlanState.PROPOSED,
            ),
            completed_node_ids=(),
            next_node_ids=(),
            artifacts_by_ref={},
            public_outputs={},
            budget=ExecutionBudget(0),
            active_remainders=(
                Remainder(
                    kind=RemainderKind.EXTERNAL_UNCERTAINTY,
                    description=(
                        "Firewall DENY requires consultative review before "
                        "any continuation"
                    ),
                    required_for=consultative_input.objective,
                    resolvable=False,
                ),
            ),
            checkpoint_id=self._checkpoint_id_factory(),
        )

    def _build_meta_analysis_report(
        self,
        consultative_input: FirewallEscalationMetaAnalysisInput,
        escalation: FirewallEscalation,
        checkpoint: RuntimeCheckpoint,
        meta_analysis_id: str,
    ) -> MetaAnalysisReport:
        return MetaAnalysisReport(
            meta_analysis_id=meta_analysis_id,
            objective=(
                "Consultative firewall review only: "
                f"{consultative_input.objective}"
            ),
            constituent_analysis_ids=(
                consultative_input.attestation.analysis_id,
                f"checkpoint:{checkpoint.checkpoint_id}",
            ),
            convergence_evidence=(),
            inherited_constraints=(),
            state=MetaAnalysisState.INCOMPLETE,
            phi_anchored=False,
            remainders=(
                f"Firewall {escalation.decision.value} triggered consultative "
                "checkpoint preservation",
            ),
            epistemic_state=EpistemicState.INSUFFICIENT_GROUNDING,
            epistemic_gaps=("FIREWALL_DENY_CONSULTATIVE_REVIEW",),
            saturation_diagnostics=(
                f"FIREWALL_{escalation.severity.value}_REMAINS_CONSULTATIVE",
            ),
            revalidation_diagnostics=(
                "CONSTITUTIVE_REVIEW_PENDING",
            ),
            lens_assessment=LensAssessment(
                state=RecoverabilityState.AT_RISK,
                signals=("FIREWALL_DENY_CONSULTATIVE_REVIEW",),
            ),
        )

    def _record(
        self,
        kind: JournalEventKind,
        correlation_id: str,
        subject_ref: str,
        payload: dict[str, Any],
    ) -> str | None:
        if self._journal is None:
            return None
        return self._journal.append(
            kind,
            correlation_id=correlation_id,
            subject_ref=subject_ref,
            payload=payload,
        ).event_id

    def _archive_consultation(self, journal_position: int) -> str | None:
        if self._journal is None or self._journal_archive is None:
            return None
        segments = self._journal.events_since(journal_position)
        if not segments:
            return None
        return self._journal_archive.archive(segments).content_hash


def _checkpoint_content_hash(checkpoint: RuntimeCheckpoint) -> str:
    return sha256(
        json.dumps(
            encode_runtime_checkpoint(checkpoint),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def encode_runtime_checkpoint(checkpoint: RuntimeCheckpoint) -> dict[str, Any]:
    from fresta_diamond.workspace import encode_runtime_checkpoint as _encode

    return _encode(checkpoint)
