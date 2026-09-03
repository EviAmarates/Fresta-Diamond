import pytest

from fresta_diamond.identity import (
    AuthorityEvidence,
    SocialIdentityAuthorityGatekeeper,
    SocialIdentityCandidate,
    SocialIdentityState,
)
from fresta_diamond.meta_analysis import (
    ConvergenceEvidence,
    InheritedConstraintEvidence,
    analyze_meta_analysis,
)
from .test_meta_analysis import _graph


def _meta():
    return analyze_meta_analysis(
        meta_analysis_id="meta:identity",
        objective="Assess a bounded identity pattern",
        analyses=(_graph("a:1", constitutional=True), _graph("a:2")),
        convergence_evidence=(ConvergenceEvidence(
            evidence_id="conv:identity",
            analysis_ids=("a:1", "a:2"),
            shared_pattern="Persistent bounded pattern",
            o2_justification="Independent analyses converge on the relation.",
        ),),
        inherited_constraints=(InheritedConstraintEvidence(
            constraint_id="f",
            analysis_ids=("a:1", "a:2"),
            persistence_effect="The inherited constraint explains persistence.",
        ),),
    )


def test_coherent_candidate_is_not_active_identity() -> None:
    candidate = SocialIdentityCandidate(
        identity_id="identity:1",
        subject_ref="subject:1",
        meta_analysis_id="meta:identity",
        state=SocialIdentityState.COHERENT_CANDIDATE,
    )
    assert candidate.state is SocialIdentityState.COHERENT_CANDIDATE
    assert candidate.phi_open is True


def test_activation_requires_separate_authority_and_scope() -> None:
    candidate = SocialIdentityCandidate(
        identity_id="identity:1",
        subject_ref="subject:1",
        meta_analysis_id="meta:identity",
        state=SocialIdentityState.COHERENT_CANDIDATE,
    )
    active = SocialIdentityAuthorityGatekeeper().activate(
        candidate,
        meta_analysis=_meta(),
        authority=AuthorityEvidence("authority:1", "consent:1", "subject:1"),
        confirmation="ACTIVATE",
    )
    assert active.state is SocialIdentityState.ACTIVE_SOCIAL_IDENTITY
    assert active.phi_open is True


def test_coherence_cannot_replace_authority() -> None:
    candidate = SocialIdentityCandidate(
        identity_id="identity:1",
        subject_ref="subject:1",
        meta_analysis_id="meta:identity",
        state=SocialIdentityState.COHERENT_CANDIDATE,
    )
    with pytest.raises(PermissionError, match="authority"):
        SocialIdentityAuthorityGatekeeper().activate(
            candidate,
            meta_analysis=_meta(),
            authority=AuthorityEvidence("authority:1", "consent:1", "other"),
            confirmation="ACTIVATE",
        )
