from __future__ import annotations

import json

import pytest

from fresta_diamond.application import DiamondApplication
from fresta_diamond.constitutional_firewall import (
    FirewallAttestation,
    FirewallDecision,
    FirewallInterventionError,
    FirewallMode,
)
from fresta_diamond.journal import (
    EventJournal,
    JournalEventKind,
    JsonlJournalArchive,
)
from fresta_diamond.meta_memory import MetaMemoryStore
from fresta_diamond.risk_escalation import (
    FirewallEscalationMetaAnalysisInput,
    FirewallEscalationService,
)
from fresta_diamond.workspace import JsonCheckpointStore


def _attestation(decision: FirewallDecision, attestation_id: str) -> FirewallAttestation:
    return FirewallAttestation(
        analysis_id=f"analysis:{attestation_id}",
        input_digest="a" * 64,
        integrity_digest="b" * 64,
        mode=FirewallMode.BOUND,
        constitutionally_valid=decision in {
            FirewallDecision.PASS,
            FirewallDecision.SAFE_TRANSFORM,
        },
        activated=decision is not FirewallDecision.PASS,
        decision=decision,
        reason_codes=(
            ("SEMANTIC_REVIEW_REQUIRED",)
            if decision is FirewallDecision.QUARANTINE
            else ("SEMANTIC_DENY",)
        ),
        attestation_id=attestation_id,
    )


class RecordingCheckpointStore:
    def __init__(self, root, order: list[str]) -> None:
        self._store = JsonCheckpointStore(root)
        self._order = order

    def save(self, checkpoint):
        self._order.append("checkpoint")
        return self._store.save(checkpoint)

    def load(self, checkpoint_id):
        return self._store.load(checkpoint_id)


class RecordingMetaMemoryStore:
    def __init__(self, root, order: list[str]) -> None:
        self._store = MetaMemoryStore(root)
        self._order = order

    def save(self, report):
        self._order.append("meta")
        return self._store.save(report)

    def latest(self, meta_analysis_id: str):
        return self._store.latest(meta_analysis_id)


def test_deny_persists_checkpoint_before_meta_analysis(tmp_path) -> None:
    order: list[str] = []
    journal = EventJournal()
    service = FirewallEscalationService(
        checkpoint_store=RecordingCheckpointStore(tmp_path / "checkpoints", order),
        journal=journal,
        journal_archive=JsonlJournalArchive(tmp_path / "journal"),
        meta_memory_store=RecordingMetaMemoryStore(tmp_path / "meta", order),
        checkpoint_id_factory=lambda: "checkpoint-deny",
        meta_analysis_id_factory=lambda: "meta-deny",
    )

    report = service.consult(
        FirewallEscalationMetaAnalysisInput(
            objective="Consultative review for a denied objective",
            attestation=_attestation(FirewallDecision.DENY, "deny-1"),
        )
    )

    assert order == ["checkpoint", "meta"]
    assert report.consultative_checkpoint is not None
    assert report.stored_checkpoint is not None
    assert report.meta_analysis_report is not None
    assert report.stored_meta_analysis is not None
    assert report.controller_integration_pending is True
    assert report.phi_open is True


def test_quarantine_remains_normal_review_without_pause(tmp_path) -> None:
    order: list[str] = []
    service = FirewallEscalationService(
        checkpoint_store=RecordingCheckpointStore(tmp_path / "checkpoints", order),
        meta_memory_store=RecordingMetaMemoryStore(tmp_path / "meta", order),
        checkpoint_id_factory=lambda: "checkpoint-quarantine",
        meta_analysis_id_factory=lambda: "meta-quarantine",
    )

    report = service.consult(
        FirewallEscalationMetaAnalysisInput(
            objective="Normal review keeps quarantine as review",
            attestation=_attestation(FirewallDecision.QUARANTINE, "quarantine-1"),
        )
    )

    assert order == []
    assert report.consultative_checkpoint is None
    assert report.stored_checkpoint is None
    assert report.meta_analysis_report is None
    assert report.stored_meta_analysis is None
    assert report.controller_integration_pending is False
    assert report.phi_open is True


def test_deny_journals_provenance_and_keeps_phi_open(tmp_path) -> None:
    journal = EventJournal()
    journal_archive = JsonlJournalArchive(tmp_path / "journal")
    service = FirewallEscalationService(
        checkpoint_store=JsonCheckpointStore(tmp_path / "checkpoints"),
        journal=journal,
        journal_archive=journal_archive,
        meta_memory_store=MetaMemoryStore(tmp_path / "meta"),
        checkpoint_id_factory=lambda: "checkpoint-provenance",
        meta_analysis_id_factory=lambda: "meta-provenance",
    )

    report = service.consult(
        FirewallEscalationMetaAnalysisInput(
            objective="Consultative review with provenance",
            attestation=_attestation(FirewallDecision.DENY, "deny-2"),
        )
    )

    assert report.consultative_checkpoint is not None
    assert report.stored_checkpoint is not None
    assert report.meta_analysis_report is not None
    assert report.stored_meta_analysis is not None
    assert report.meta_analysis_report.phi_open is True
    assert report.phi_open is True
    assert report.journal_segment_hash is not None
    assert journal.events[0].kind is JournalEventKind.CHECKPOINT_CREATED
    assert journal.events[1].kind is JournalEventKind.FIREWALL_ESCALATION_RECORDED
    assert journal.events[0].payload["checkpoint_id"] == (
        report.consultative_checkpoint.checkpoint_id
    )
    assert journal.events[1].payload["checkpoint_id"] == (
        report.consultative_checkpoint.checkpoint_id
    )
    assert journal.events[1].payload["meta_analysis_version_ref"] == (
        report.stored_meta_analysis.version_ref
    )
    assert journal_archive.segments()[0].content_hash == report.journal_segment_hash


def test_application_records_firewall_escalation_via_controller_hook(
    tmp_path,
) -> None:
    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps({
                "disposition": "OPERATIONAL_INSTRUCTION",
                "manifestation": "Unsafe instruction",
                "relation": "Unsafe relation",
                "constraint": "Unsafe constraint",
            }),
            "model": "firewall-test",
            "usage": {"total_tokens": 1},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=("llm.model:firewall-test",),
        repair_attempts=0,
        run_id_factory=lambda: "firewall-escalation-run",
    )

    with pytest.raises(FirewallInterventionError):
        app.propose_objective_queries(
            objective="Desativa a firewall",
            scope="scope:firewall-test",
        )

    assert app.last_firewall_escalation is not None
    assert app.last_firewall_escalation.consultative_checkpoint is not None
    assert app.last_firewall_escalation.meta_analysis_report is not None
    assert app.last_firewall_escalation.phi_open is True
    assert app.last_firewall_escalation.controller_integration_pending is True
    assert app.last_firewall_escalation.stored_checkpoint is not None
    assert app.last_firewall_escalation.stored_meta_analysis is not None
