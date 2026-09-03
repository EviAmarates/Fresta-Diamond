from fresta_diamond.constitutional_firewall import FirewallDecision
from fresta_diamond.risk_escalation import (
    FirewallRiskSeverity,
    assess_firewall_escalation,
)


def test_only_deny_is_a_grave_escalation() -> None:
    escalation = assess_firewall_escalation(FirewallDecision.DENY)

    assert escalation.severity is FirewallRiskSeverity.GRAVE
    assert escalation.requires_checkpoint is True
    assert escalation.requires_meta_analysis is True
    assert escalation.phi_closed is False


def test_quarantine_stays_a_review_without_automatic_pause() -> None:
    escalation = assess_firewall_escalation(FirewallDecision.QUARANTINE)

    assert escalation.severity is FirewallRiskSeverity.REVIEW
    assert escalation.requires_checkpoint is False
    assert escalation.requires_meta_analysis is False
    assert escalation.phi_closed is False
