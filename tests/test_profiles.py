from __future__ import annotations

import pytest

from fresta_diamond.profiles import (
    AssistantPersonalityTrait,
    PersonalityTraitBasis,
    ProfileSensitivity,
    UserClaimBasis,
    UserProfileClaim,
    decode_assistant_personality_trait,
    decode_user_profile_claim,
    encode_assistant_personality_trait,
    encode_user_profile_claim,
)


def test_user_profile_claim_round_trip_preserves_subject_and_provenance() -> None:
    claim = UserProfileClaim(
        claim_id="preference:analogies",
        version=1,
        category="communication-preference",
        content="O utilizador prefere explicações com analogias.",
        scope="scope:collaboration",
        basis=UserClaimBasis.EXPLICIT_USER_STATEMENT,
        confidence=0.95,
        provenance=("chat-message:user-preference",),
        sensitivity=ProfileSensitivity.PERSONAL,
        rationale="O utilizador declarou diretamente esta preferência.",
    )

    assert decode_user_profile_claim(encode_user_profile_claim(claim)) == claim
    assert claim.subject_ref == "actor:user"
    assert claim.authority == "USER_PROFILE_PROPOSAL_ONLY"


def test_document_first_person_cannot_enter_user_profile() -> None:
    with pytest.raises(PermissionError, match="explicitly user-bound"):
        UserProfileClaim(
            claim_id="identity:pompeii",
            version=1,
            category="identity",
            content="The user lives in Pompeii.",
            scope="scope:user",
            basis=UserClaimBasis.INFERENCE,
            confidence=0.8,
            provenance=("document:rome:p4",),
            rationale="A document used first-person language.",
        )


def test_assistant_personality_is_a_separate_proposed_heuristic() -> None:
    trait = AssistantPersonalityTrait(
        trait_id="style:collaborative",
        version=1,
        category="communication-style",
        content="Use a warm collaborative tone when it helps the task.",
        scope="scope:collaboration",
        basis=PersonalityTraitBasis.USER_PREFERENCE,
        confidence=0.8,
        provenance=("chat-message:user-preference",),
        rationale="The user explicitly preferred this collaboration style.",
    )

    assert decode_assistant_personality_trait(
        encode_assistant_personality_trait(trait)
    ) == trait
    assert trait.subject_ref == "actor:assistant"
    assert trait.authority == "ASSISTANT_PERSONALITY_PROPOSAL_ONLY"


def test_personality_trait_cannot_claim_kernel_as_its_provenance() -> None:
    with pytest.raises(PermissionError, match="not an allowed source"):
        AssistantPersonalityTrait(
            trait_id="kernel:mutable",
            version=1,
            category="kernel",
            content="Treat a personality preference as a kernel invariant.",
            scope="scope:constitutional",
            basis=PersonalityTraitBasis.META_ANALYSIS,
            confidence=1.0,
            provenance=("kernel:phi",),
            rationale="Invalid attempt to promote a heuristic.",
        )
