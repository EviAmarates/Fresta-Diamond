"""Separate ontological coherence from social identity authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fresta_diamond.meta_analysis import MetaAnalysisReport, MetaAnalysisState


class SocialIdentityState(str, Enum):
    COHERENT_CANDIDATE = "COHERENT_CANDIDATE"
    ACTIVE_SOCIAL_IDENTITY = "ACTIVE_SOCIAL_IDENTITY"


@dataclass(frozen=True)
class AuthorityEvidence:
    authority_ref: str
    consent_ref: str
    scope: str
    revocation_ref: str | None = None

    def __post_init__(self) -> None:
        if not all((
            self.authority_ref.strip(),
            self.consent_ref.strip(),
            self.scope.strip(),
        )):
            raise ValueError("Social identity authority evidence is incomplete")


@dataclass(frozen=True)
class SocialIdentityCandidate:
    identity_id: str
    subject_ref: str
    meta_analysis_id: str
    state: SocialIdentityState
    phi_open: bool = True
    authority: str = "SOCIAL_IDENTITY_CANDIDATE_ONLY"

    def __post_init__(self) -> None:
        if not self.identity_id.strip() or not self.subject_ref.strip():
            raise ValueError("Social identity identity and subject are required")
        if not self.meta_analysis_id.strip():
            raise ValueError("Social identity requires a meta-analysis reference")
        if not self.phi_open:
            raise PermissionError("Social identity cannot close Phi")
        if self.state is SocialIdentityState.ACTIVE_SOCIAL_IDENTITY:
            raise PermissionError(
                "Active social identity must be created by the authority gatekeeper"
            )
        if self.authority != "SOCIAL_IDENTITY_CANDIDATE_ONLY":
            raise PermissionError("Identity candidates cannot grant authority")


class SocialIdentityAuthorityGatekeeper:
    """Promote a coherent candidate only with separate constitutive authority."""

    def activate(
        self,
        candidate: SocialIdentityCandidate,
        *,
        meta_analysis: MetaAnalysisReport,
        authority: AuthorityEvidence,
        confirmation: str,
    ) -> SocialIdentityCandidate:
        if candidate.meta_analysis_id != meta_analysis.meta_analysis_id:
            raise PermissionError("Identity candidate and analysis do not match")
        if meta_analysis.state is not MetaAnalysisState.COHERENT_CANDIDATE:
            raise PermissionError("Only coherent identity candidates can be activated")
        if confirmation != "ACTIVATE":
            raise PermissionError("Social identity activation requires ACTIVATE")
        if authority.scope != candidate.subject_ref:
            raise PermissionError("Identity authority scope does not match subject")
        return _ActiveSocialIdentity(
            identity_id=candidate.identity_id,
            subject_ref=candidate.subject_ref,
            meta_analysis_id=candidate.meta_analysis_id,
            state=SocialIdentityState.ACTIVE_SOCIAL_IDENTITY,
            phi_open=True,
            authority="SOCIAL_IDENTITY_ACTIVE_BY_EXPLICIT_AUTHORITY",
        )


class _ActiveSocialIdentity(SocialIdentityCandidate):
    def __post_init__(self) -> None:
        if not self.phi_open:
            raise PermissionError("Social identity cannot close Phi")
        if self.state is not SocialIdentityState.ACTIVE_SOCIAL_IDENTITY:
            raise ValueError("Internal active identity state is invalid")
        if self.authority != "SOCIAL_IDENTITY_ACTIVE_BY_EXPLICIT_AUTHORITY":
            raise PermissionError("Active identity authority is invalid")
