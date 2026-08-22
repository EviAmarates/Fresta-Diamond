"""Versioned profile proposals kept outside learning memory and attention."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Mapping


USER_PROFILE_CLAIM_SCHEMA = "fresta://diamond-user-profile-claim@1"
ASSISTANT_PERSONALITY_TRAIT_SCHEMA = (
    "fresta://diamond-assistant-personality-trait@1"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_USER_BOUND_PROVENANCE = (
    "operator:user-supplied",
    "chat-message:",
    "interaction:user:",
    "user-confirmation:",
    "user-profile:",
)
_PERSONALITY_PROVENANCE = (
    "baseline:assistant-personality",
    "operator:user-supplied",
    "chat-message:",
    "interaction:",
    "meta-analysis:",
    "assistant-personality:",
)


class ProfileState(str, Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    DEFERRED = "DEFERRED"
    CONTESTED = "CONTESTED"
    ARCHIVED = "ARCHIVED"


class ProfileSensitivity(str, Enum):
    NORMAL = "NORMAL"
    PERSONAL = "PERSONAL"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class UserClaimBasis(str, Enum):
    EXPLICIT_USER_STATEMENT = "EXPLICIT_USER_STATEMENT"
    INTERACTION_OBSERVATION = "INTERACTION_OBSERVATION"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"


class PersonalityTraitBasis(str, Enum):
    BASELINE = "BASELINE"
    USER_PREFERENCE = "USER_PREFERENCE"
    INTERACTION_PATTERN = "INTERACTION_PATTERN"
    META_ANALYSIS = "META_ANALYSIS"


@dataclass(frozen=True)
class UserProfileClaim:
    claim_id: str
    version: int
    category: str
    content: str
    scope: str
    basis: UserClaimBasis
    confidence: float
    provenance: tuple[str, ...]
    sensitivity: ProfileSensitivity = ProfileSensitivity.PERSONAL
    state: ProfileState = ProfileState.PROPOSED
    rationale: str = "Awaiting profile validation."
    previous_version_ref: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    subject_ref: str = "actor:user"
    authority: str = "USER_PROFILE_PROPOSAL_ONLY"

    def __post_init__(self) -> None:
        _validate_common(
            self.claim_id,
            self.version,
            self.category,
            self.content,
            self.scope,
            self.confidence,
            self.provenance,
            self.rationale,
            self.previous_version_ref,
            self.created_at,
        )
        if self.subject_ref != "actor:user":
            raise PermissionError("User profile claims must target actor:user")
        if self.authority != "USER_PROFILE_PROPOSAL_ONLY":
            raise PermissionError("User profile claims cannot grant authority")
        if not all(
            any(item.startswith(prefix) for prefix in _USER_BOUND_PROVENANCE)
            for item in self.provenance
        ):
            raise PermissionError(
                "User profile provenance must be explicitly user-bound"
            )
        if self.basis is UserClaimBasis.EXPLICIT_USER_STATEMENT and not any(
            item.startswith((
                "operator:user-supplied",
                "chat-message:",
                "user-confirmation:",
            ))
            for item in self.provenance
        ):
            raise PermissionError(
                "Explicit user claims require a direct user provenance"
            )

    @property
    def version_ref(self) -> str:
        return f"user-profile:{self.claim_id}@{self.version}"


@dataclass(frozen=True)
class AssistantPersonalityTrait:
    trait_id: str
    version: int
    category: str
    content: str
    scope: str
    basis: PersonalityTraitBasis
    confidence: float
    provenance: tuple[str, ...]
    state: ProfileState = ProfileState.PROPOSED
    rationale: str = "Awaiting personality validation."
    previous_version_ref: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    subject_ref: str = "actor:assistant"
    authority: str = "ASSISTANT_PERSONALITY_PROPOSAL_ONLY"

    def __post_init__(self) -> None:
        _validate_common(
            self.trait_id,
            self.version,
            self.category,
            self.content,
            self.scope,
            self.confidence,
            self.provenance,
            self.rationale,
            self.previous_version_ref,
            self.created_at,
        )
        if self.subject_ref != "actor:assistant":
            raise PermissionError(
                "Assistant personality traits must target actor:assistant"
            )
        if self.authority != "ASSISTANT_PERSONALITY_PROPOSAL_ONLY":
            raise PermissionError("Personality traits cannot grant authority")
        if not all(
            any(item.startswith(prefix) for prefix in _PERSONALITY_PROVENANCE)
            for item in self.provenance
        ):
            raise PermissionError(
                "Assistant personality provenance is not an allowed source"
            )

    @property
    def version_ref(self) -> str:
        return f"assistant-personality:{self.trait_id}@{self.version}"


def encode_user_profile_claim(value: UserProfileClaim) -> dict[str, Any]:
    return {
        "schema": USER_PROFILE_CLAIM_SCHEMA,
        "claim_id": value.claim_id,
        "version": value.version,
        "category": value.category,
        "content": value.content,
        "scope": value.scope,
        "basis": value.basis.value,
        "confidence": value.confidence,
        "provenance": list(value.provenance),
        "sensitivity": value.sensitivity.value,
        "state": value.state.value,
        "rationale": value.rationale,
        "previous_version_ref": value.previous_version_ref,
        "created_at": value.created_at,
        "subject_ref": value.subject_ref,
        "authority": value.authority,
    }


def decode_user_profile_claim(value: Mapping[str, Any]) -> UserProfileClaim:
    if value.get("schema") != USER_PROFILE_CLAIM_SCHEMA:
        raise ValueError("Unknown user profile claim schema")
    return UserProfileClaim(
        claim_id=_text(value, "claim_id"),
        version=_integer(value, "version"),
        category=_text(value, "category"),
        content=_text(value, "content"),
        scope=_text(value, "scope"),
        basis=UserClaimBasis(_text(value, "basis")),
        confidence=_number(value, "confidence"),
        provenance=_text_tuple(value, "provenance"),
        sensitivity=ProfileSensitivity(_text(value, "sensitivity")),
        state=ProfileState(_text(value, "state")),
        rationale=_text(value, "rationale"),
        previous_version_ref=_optional_text(value, "previous_version_ref"),
        created_at=_text(value, "created_at"),
        subject_ref=_text(value, "subject_ref"),
        authority=_text(value, "authority"),
    )


def encode_assistant_personality_trait(
    value: AssistantPersonalityTrait,
) -> dict[str, Any]:
    return {
        "schema": ASSISTANT_PERSONALITY_TRAIT_SCHEMA,
        "trait_id": value.trait_id,
        "version": value.version,
        "category": value.category,
        "content": value.content,
        "scope": value.scope,
        "basis": value.basis.value,
        "confidence": value.confidence,
        "provenance": list(value.provenance),
        "state": value.state.value,
        "rationale": value.rationale,
        "previous_version_ref": value.previous_version_ref,
        "created_at": value.created_at,
        "subject_ref": value.subject_ref,
        "authority": value.authority,
    }


def decode_assistant_personality_trait(
    value: Mapping[str, Any],
) -> AssistantPersonalityTrait:
    if value.get("schema") != ASSISTANT_PERSONALITY_TRAIT_SCHEMA:
        raise ValueError("Unknown assistant personality trait schema")
    return AssistantPersonalityTrait(
        trait_id=_text(value, "trait_id"),
        version=_integer(value, "version"),
        category=_text(value, "category"),
        content=_text(value, "content"),
        scope=_text(value, "scope"),
        basis=PersonalityTraitBasis(_text(value, "basis")),
        confidence=_number(value, "confidence"),
        provenance=_text_tuple(value, "provenance"),
        state=ProfileState(_text(value, "state")),
        rationale=_text(value, "rationale"),
        previous_version_ref=_optional_text(value, "previous_version_ref"),
        created_at=_text(value, "created_at"),
        subject_ref=_text(value, "subject_ref"),
        authority=_text(value, "authority"),
    )


def _validate_common(
    record_id: str,
    version: int,
    category: str,
    content: str,
    scope: str,
    confidence: float,
    provenance: tuple[str, ...],
    rationale: str,
    previous_version_ref: str | None,
    created_at: str,
) -> None:
    if not _SAFE_ID.fullmatch(record_id):
        raise ValueError("Profile record ID is invalid")
    if version < 1:
        raise ValueError("Profile record version must be positive")
    if not all((
        category.strip(), content.strip(), scope.strip(), rationale.strip(),
        created_at.strip(),
    )):
        raise ValueError("Profile record fields are required")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("Profile confidence must be numeric")
    if not 0 <= confidence <= 1:
        raise ValueError("Profile confidence must be between zero and one")
    if not provenance or any(not item.strip() for item in provenance):
        raise ValueError("Profile provenance is required")
    if len(provenance) != len(set(provenance)):
        raise ValueError("Profile provenance must be unique")
    if version == 1 and previous_version_ref is not None:
        raise ValueError("First profile version cannot name a predecessor")
    if version > 1 and (
        previous_version_ref is None or not previous_version_ref.strip()
    ):
        raise ValueError("Later profile versions require a predecessor")


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
        raise ValueError(f"{key} must be null or non-empty text")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"{key} must be an integer")
    return item


def _number(value: Mapping[str, Any], key: str) -> float:
    item = value.get(key)
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ValueError(f"{key} must be numeric")
    return float(item)


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"{key} must be an array of text")
    return tuple(raw)
