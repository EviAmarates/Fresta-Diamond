from fresta_diamond.attention_memory import (
    AttentionContextRevision,
    AttentionState,
    AttentionTransition,
)
from fresta_diamond.attention_projection import AttentionEvidenceState
from fresta_diamond.attention_resolution import (
    AttentionNomination,
    AttentionResolutionStatus,
    ProfileAttentionResolver,
)
from fresta_diamond.profiles import (
    ProfileState,
    UserClaimBasis,
    UserProfileClaim,
    UserProfileStore,
)


def test_active_user_profile_resolves_through_shared_attention(tmp_path) -> None:
    store = UserProfileStore(tmp_path / "profile")
    proposal = UserProfileClaim(
        claim_id="claim:stable",
        version=1,
        category="preference",
        content="Prefers bounded and explicit explanations.",
        scope="scope:test",
        basis=UserClaimBasis.EXPLICIT_USER_STATEMENT,
        confidence=1.0,
        provenance=("operator:user-supplied",),
    )
    store.save(proposal)
    active = store.gatekeeper().adopt("claim:stable", confirmation="ADOPT")
    context = AttentionContextRevision(
        context_id="context:test",
        revision_id="attention-revision:test:1",
        revision_number=1,
        state=AttentionState.ACTIVE,
        transition=AttentionTransition.CREATED,
        objective="Use stable user preferences",
        scope="scope:test",
        summary="Profile retrieval",
    )

    result = ProfileAttentionResolver(
        store,
        resolver_id="user-profile",
        prefix="user-profile:",
    ).resolve(
        active.version_ref,
        context,
        AttentionNomination(active.version_ref, relevance=1.0, contextual_roles=(1,)),
    )

    assert result.status is AttentionResolutionStatus.RESOLVED
    assert result.candidate is not None
    assert result.candidate.evidence_state is AttentionEvidenceState.VALIDATED
    assert result.candidate.authority.endswith(ProfileState.ACTIVE.value)


def test_profile_retrieval_does_not_promote_proposals(tmp_path) -> None:
    store = UserProfileStore(tmp_path / "profile")
    proposal = UserProfileClaim(
        claim_id="claim:pending",
        version=1,
        category="preference",
        content="Pending preference.",
        scope="scope:test",
        basis=UserClaimBasis.INFERENCE,
        confidence=0.5,
        provenance=("chat-message:1",),
    )
    store.save(proposal)
    context = AttentionContextRevision(
        context_id="context:test",
        revision_id="attention-revision:test:1",
        revision_number=1,
        state=AttentionState.ACTIVE,
        transition=AttentionTransition.CREATED,
        objective="Use stable user preferences",
        scope="scope:test",
        summary="Profile retrieval",
    )

    result = ProfileAttentionResolver(
        store,
        resolver_id="user-profile",
        prefix="user-profile:",
    ).resolve(
        proposal.version_ref,
        context,
        AttentionNomination(proposal.version_ref),
    )

    assert result.status is AttentionResolutionStatus.INELIGIBLE
