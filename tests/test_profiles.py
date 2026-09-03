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
    AssistantPersonalityStore,
    ProfileState,
    UserProfileStore,
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


def test_profile_stores_preserve_versioned_hash_lineage(tmp_path) -> None:
    store = UserProfileStore(tmp_path / "profile")
    first = UserProfileClaim(
        claim_id="preference:format",
        version=1,
        category="communication-preference",
        content="Prefer concise answers.",
        scope="scope:collaboration",
        basis=UserClaimBasis.EXPLICIT_USER_STATEMENT,
        confidence=0.9,
        provenance=("operator:user-supplied",),
    )
    second = UserProfileClaim(
        claim_id=first.claim_id,
        version=2,
        category=first.category,
        content="Prefer concise answers with rationale.",
        scope=first.scope,
        basis=first.basis,
        confidence=0.95,
        provenance=first.provenance,
        previous_version_ref=first.version_ref,
    )

    store.save(first)
    store.save(second)

    assert store.latest(first.claim_id) == second
    assert len(store.records()) == 2


def test_public_profile_store_rejects_active_records(tmp_path) -> None:
    store = AssistantPersonalityStore(tmp_path / "personality")
    trait = AssistantPersonalityTrait(
        trait_id="style:concise",
        version=1,
        category="communication-style",
        content="Prefer concise answers.",
        scope="scope:collaboration",
        basis=PersonalityTraitBasis.USER_PREFERENCE,
        confidence=0.8,
        provenance=("operator:user-supplied",),
        state=ProfileState.ACTIVE,
    )

    with pytest.raises(PermissionError, match="cannot persist ACTIVE"):
        store.save(trait)


def test_gatekeeper_requires_explicit_confirmation_and_adopts_next_version(
    tmp_path,
) -> None:
    store = UserProfileStore(tmp_path / "profile")
    claim = UserProfileClaim(
        claim_id="preference:format",
        version=1,
        category="communication-preference",
        content="Prefer concise answers.",
        scope="scope:collaboration",
        basis=UserClaimBasis.HYPOTHESIS,
        confidence=0.5,
        provenance=("chat-message:1",),
    )
    store.save(claim)

    with pytest.raises(PermissionError, match="ADOPT confirmation"):
        store.gatekeeper().adopt(claim.claim_id, confirmation="YES")

    adopted = store.gatekeeper().adopt(claim.claim_id, confirmation="ADOPT")
    assert adopted.state is ProfileState.ACTIVE
    assert adopted.version == 2
    assert adopted.previous_version_ref == claim.version_ref
    assert store.latest(claim.claim_id) == adopted


def test_gatekeeper_does_not_re_adopt_active_records(tmp_path) -> None:
    store = AssistantPersonalityStore(tmp_path / "personality")
    trait = AssistantPersonalityTrait(
        trait_id="style:concise",
        version=1,
        category="communication-style",
        content="Prefer concise answers.",
        scope="scope:collaboration",
        basis=PersonalityTraitBasis.USER_PREFERENCE,
        confidence=0.8,
        provenance=("operator:user-supplied",),
    )
    store.save(trait)
    store.gatekeeper().adopt(trait.trait_id, confirmation="ADOPT")

    with pytest.raises(PermissionError, match="Only PROPOSED"):
        store.gatekeeper().adopt(trait.trait_id, confirmation="ADOPT")


def test_profile_inspection_reports_lineage_and_states_without_mutation(
    tmp_path,
) -> None:
    store = UserProfileStore(tmp_path / "profile")
    claim = UserProfileClaim(
        claim_id="preference:inspect",
        version=1,
        category="style",
        content="Use concise answers.",
        scope="scope:collaboration",
        basis=UserClaimBasis.HYPOTHESIS,
        confidence=0.5,
        provenance=("chat-message:1",),
    )
    store.save(claim)

    report = store.inspect(claim.claim_id)

    assert report[0].version_refs == (claim.version_ref,)
    assert report[0].states == (ProfileState.PROPOSED,)
    assert report[0].latest_state is ProfileState.PROPOSED
    assert store.latest(claim.claim_id) == claim
