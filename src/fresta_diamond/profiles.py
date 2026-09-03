"""Versioned profile proposals kept outside learning memory and attention."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any, Callable, Generic, Mapping, TypeVar


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


ProfileRecord = TypeVar("ProfileRecord", UserProfileClaim, AssistantPersonalityTrait)


class ProfileStoreError(RuntimeError):
    """A profile or personality history could not be persisted or verified."""


@dataclass(frozen=True)
class ProfileInspection:
    record_id: str
    version_refs: tuple[str, ...]
    states: tuple[ProfileState, ...]
    latest_version: int
    latest_state: ProfileState


class ProfileAdoptionGatekeeper:
    """Explicit authority boundary for promoting one stored proposal."""

    def __init__(self, store: "_VersionedProfileStore[ProfileRecord]") -> None:
        self._store = store

    def adopt(
        self,
        record_id: str,
        *,
        confirmation: str,
    ) -> ProfileRecord:
        if confirmation != "ADOPT":
            raise PermissionError(
                "Profile adoption requires explicit ADOPT confirmation"
            )
        current = self._store.latest(record_id)
        if current.state is not ProfileState.PROPOSED:
            raise PermissionError("Only PROPOSED profile records can be adopted")
        adopted = replace(current, version=current.version + 1,
                          previous_version_ref=current.version_ref,
                          state=ProfileState.ACTIVE)
        self._store._save_active(adopted)
        return adopted


class _VersionedProfileStore(Generic[ProfileRecord]):
    def __init__(
        self,
        root: str | Path,
        *,
        encode: Callable[[ProfileRecord], dict[str, Any]],
        decode: Callable[[Mapping[str, Any]], ProfileRecord],
        record_id: Callable[[ProfileRecord], str],
        version_ref: Callable[[ProfileRecord], str],
        filename_prefix: str,
    ) -> None:
        self._root = Path(root).resolve()
        self._records = self._root / "records"
        self._pending = self._root / "pending"
        self._encode = encode
        self._decode = decode
        self._record_id = record_id
        self._version_ref = version_ref
        self._filename_prefix = filename_prefix
        self._lock = Lock()

    @property
    def root(self) -> Path:
        return self._root

    def gatekeeper(self) -> ProfileAdoptionGatekeeper:
        return ProfileAdoptionGatekeeper(self)

    def save(self, record: ProfileRecord) -> Path:
        """Persist a proposal; activation belongs to a separate authority."""
        if record.state is ProfileState.ACTIVE:
            raise PermissionError(
                "Public profile writes cannot persist ACTIVE records"
            )
        return self._save(record)

    def _save_active(self, record: ProfileRecord) -> Path:
        if record.state is not ProfileState.ACTIVE:
            raise ProfileStoreError("Internal active write requires ACTIVE state")
        return self._save(record)

    def _save(self, record: ProfileRecord) -> Path:
        record_id = self._record_id(record)
        with self._lock:
            history = self.history(record_id)
            if not history:
                if record.version != 1 or record.previous_version_ref is not None:
                    raise ProfileStoreError("Initial profile version is invalid")
            else:
                previous = history[-1]
                if record.version != previous.version + 1:
                    raise ProfileStoreError("Profile version is not sequential")
                if record.previous_version_ref != self._version_ref(previous):
                    raise ProfileStoreError("Profile version lineage is invalid")
            payload = self._encode(record)
            sealed = {**payload, "content_hash": _hash_body(payload)}
            filename = (
                f"{self._filename_prefix}-{_filename_id(record_id)}"
                f".v{record.version}.json"
            )
            pending = self._pending / f"{filename}.pending"
            final = self._records / filename
            if pending.exists() or final.exists():
                raise ProfileStoreError("Profile version already exists")
            try:
                self._pending.mkdir(parents=True, exist_ok=True)
                with pending.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(_canonical_json(sealed) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                self._records.mkdir(parents=True, exist_ok=True)
                os.replace(pending, final)
            except OSError as exc:
                raise ProfileStoreError(
                    f"Could not persist profile record: {type(exc).__name__}"
                ) from exc
            return final

    def records(self) -> tuple[ProfileRecord, ...]:
        if not self._records.exists():
            return ()
        values = tuple(
            self._read(path)
            for path in self._records.glob(f"{self._filename_prefix}-*.json")
            if path.is_file()
        )
        refs = [self._version_ref(item) for item in values]
        if len(refs) != len(set(refs)):
            raise ProfileStoreError("Duplicate profile version reference")
        return tuple(sorted(values, key=lambda item: (
            self._record_id(item), item.version
        )))

    def inspect(self, record_id: str | None = None) -> tuple[ProfileInspection, ...]:
        """Verify and expose versioned state without changing authority."""
        ids = (
            (record_id,)
            if record_id is not None
            else tuple(dict.fromkeys(self._record_id(item) for item in self.records()))
        )
        inspections = []
        for current_id in ids:
            history = self.history(current_id)
            if not history:
                raise ProfileStoreError(f"Unknown profile record: {current_id}")
            latest = self.latest(current_id)
            inspections.append(ProfileInspection(
                record_id=current_id,
                version_refs=tuple(self._version_ref(item) for item in history),
                states=tuple(item.state for item in history),
                latest_version=latest.version,
                latest_state=latest.state,
            ))
        return tuple(inspections)

    def history(self, record_id: str) -> tuple[ProfileRecord, ...]:
        return tuple(
            item for item in self.records() if self._record_id(item) == record_id
        )

    def latest(self, record_id: str) -> ProfileRecord:
        history = self.history(record_id)
        if not history:
            raise ProfileStoreError(f"Unknown profile record: {record_id}")
        for previous, current in zip(history, history[1:]):
            if current.version != previous.version + 1:
                raise ProfileStoreError("Profile history has a version gap")
            if current.previous_version_ref != self._version_ref(previous):
                raise ProfileStoreError("Profile history lineage mismatch")
        return history[-1]

    def _read(self, path: Path) -> ProfileRecord:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("record is not an object")
            content_hash = raw.pop("content_hash")
            if not isinstance(content_hash, str) or _hash_body(raw) != content_hash:
                raise ProfileStoreError(f"Profile record hash mismatch: {path.name}")
            record = self._decode(raw)
            expected = (
                f"{self._filename_prefix}-{_filename_id(self._record_id(record))}"
                f".v{record.version}.json"
            )
            if path.name != expected:
                raise ProfileStoreError("Profile record filename mismatch")
            return record
        except ProfileStoreError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProfileStoreError(
                f"Malformed profile record {path.name}: {exc}"
            ) from exc


class UserProfileStore(_VersionedProfileStore[UserProfileClaim]):
    def __init__(self, root: str | Path) -> None:
        super().__init__(
            root,
            encode=encode_user_profile_claim,
            decode=decode_user_profile_claim,
            record_id=lambda item: item.claim_id,
            version_ref=lambda item: item.version_ref,
            filename_prefix="claim",
        )


class AssistantPersonalityStore(_VersionedProfileStore[AssistantPersonalityTrait]):
    def __init__(self, root: str | Path) -> None:
        super().__init__(
            root,
            encode=encode_assistant_personality_trait,
            decode=decode_assistant_personality_trait,
            record_id=lambda item: item.trait_id,
            version_ref=lambda item: item.version_ref,
            filename_prefix="trait",
        )


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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _filename_id(record_id: str) -> str:
    return record_id.replace(":", "%3A")
