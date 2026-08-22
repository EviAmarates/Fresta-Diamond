"""Native, order-free concept candidates over committed Diamond crystals."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)


CONCEPT_RECORD_SCHEMA = "fresta://diamond-concept-record@1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


class ConceptState(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    CRYSTALLIZED = "CRYSTALLIZED"
    CONTESTED = "CONTESTED"
    ARCHIVED = "ARCHIVED"


class ConceptAxisState(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    SUPPORTED = "SUPPORTED"
    INDETERMINATE = "INDETERMINATE"
    CONTESTED = "CONTESTED"


class MembershipState(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    CRYSTALLIZED = "CRYSTALLIZED"
    CONTESTED = "CONTESTED"
    EXCLUDED = "EXCLUDED"


class ParentLinkState(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


class DerivationSourceKind(str, Enum):
    DOCUMENT = "DOCUMENT"
    MEMORY_CRYSTAL = "MEMORY_CRYSTAL"
    WORKSPACE = "WORKSPACE"
    WEB_SOURCE = "WEB_SOURCE"
    CONCEPT_VERSION = "CONCEPT_VERSION"


class DerivationContribution(str, Enum):
    DIRECT = "DIRECT"
    SYNTHESIS = "SYNTHESIS"
    CORROBORATION = "CORROBORATION"
    COUNTEREVIDENCE = "COUNTEREVIDENCE"


@dataclass(frozen=True)
class DerivationSource:
    source_ref: str
    kind: DerivationSourceKind

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("Derivation source reference is required")


@dataclass(frozen=True)
class DerivationSeal:
    seal_id: str
    target_ref: str
    contribution: DerivationContribution
    sources: tuple[DerivationSource, ...]
    analysis_id: str
    scope: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.seal_id):
            raise ValueError("Derivation seal ID is invalid")
        if not all((
            self.target_ref.strip(),
            self.analysis_id.strip(),
            self.scope.strip(),
            self.created_at.strip(),
        )):
            raise ValueError("Derivation seal references are required")
        sources = tuple(self.sources)
        if not sources:
            raise ValueError("Derivation seal requires at least one source")
        source_keys = {(item.kind, item.source_ref) for item in sources}
        if len(source_keys) != len(sources):
            raise ValueError("Derivation seal contains duplicate sources")
        object.__setattr__(self, "sources", sources)

    @property
    def digest(self) -> str:
        return sha256(_canonical_json({
            "seal_id": self.seal_id,
            "target_ref": self.target_ref,
            "contribution": self.contribution.value,
            "sources": [
                {"source_ref": item.source_ref, "kind": item.kind.value}
                for item in self.sources
            ],
            "analysis_id": self.analysis_id,
            "scope": self.scope,
            "created_at": self.created_at,
        }).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConceptSignature:
    characteristics: tuple[str, ...] = ()
    relations: tuple[str, ...] = ()
    functions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "characteristics",
            "relations",
            "functions",
            "constraints",
            "exclusions",
            "examples",
            "counterexamples",
        ):
            values = _clean_texts(getattr(self, field_name))
            object.__setattr__(self, field_name, values)
        structural = (
            self.characteristics
            + self.relations
            + self.functions
            + self.constraints
            + self.exclusions
        )
        if not structural:
            raise ValueError(
                "Concept signature requires at least one intensional feature"
            )


@dataclass(frozen=True)
class ConceptMembership:
    crystal_id: str
    state: MembershipState = MembershipState.CANDIDATE
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.crystal_id):
            raise ValueError("Concept membership crystal ID is invalid")
        object.__setattr__(
            self, "evidence_refs", _clean_texts(self.evidence_refs)
        )


@dataclass(frozen=True)
class ConceptParentLink:
    parent_concept_id: str
    state: ParentLinkState = ParentLinkState.CANDIDATE
    basis: str = "proposed specialization"
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.parent_concept_id):
            raise ValueError("Parent concept ID is invalid")
        if not self.basis.strip():
            raise ValueError("Parent concept link requires a basis")
        object.__setattr__(
            self, "evidence_refs", _clean_texts(self.evidence_refs)
        )


@dataclass(frozen=True)
class ConceptRecord:
    concept_id: str
    version: int
    canonical_name: str
    aliases: tuple[str, ...]
    scope: str
    state: ConceptState
    signature: ConceptSignature
    memberships: tuple[ConceptMembership, ...]
    parent_links: tuple[ConceptParentLink, ...] = ()
    derivation_seals: tuple[DerivationSeal, ...] = ()
    recognition_state: ConceptAxisState = ConceptAxisState.NOT_EVALUATED
    definition_state: ConceptAxisState = ConceptAxisState.NOT_EVALUATED
    validation_refs: tuple[str, ...] = ()
    previous_version_ref: str | None = None
    revision_reason: str = "initial proposal"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.concept_id):
            raise ValueError("Concept ID is invalid")
        if self.version < 1:
            raise ValueError("Concept version must be positive")
        if not self.canonical_name.strip() or not self.scope.strip():
            raise ValueError("Concept name and scope are required")
        if not self.revision_reason.strip() or not self.created_at.strip():
            raise ValueError("Concept revision metadata is required")
        if self.promotion_authority is not False:
            raise PermissionError("Concept records cannot grant promotion authority")
        aliases = _clean_texts(self.aliases)
        if self.canonical_name.casefold() in {
            item.casefold() for item in aliases
        }:
            raise ValueError("Canonical concept name cannot repeat as an alias")
        memberships = tuple(self.memberships)
        if len(memberships) < 2:
            raise ValueError("Concept candidates require at least two members")
        if len({item.crystal_id for item in memberships}) != len(memberships):
            raise ValueError("Concept contains duplicate memberships")
        parents = tuple(self.parent_links)
        if any(item.parent_concept_id == self.concept_id for item in parents):
            raise ValueError("Concept cannot be its own parent")
        if len({item.parent_concept_id for item in parents}) != len(parents):
            raise ValueError("Concept contains duplicate parent links")
        validation_refs = _clean_texts(self.validation_refs)
        seals = tuple(self.derivation_seals)
        if len({item.seal_id for item in seals}) != len(seals):
            raise ValueError("Concept contains duplicate derivation seals")
        if self.state is ConceptState.CANDIDATE:
            if validation_refs:
                raise ValueError("Candidate concept cannot claim validation")
            if any(
                item.state is not MembershipState.CANDIDATE
                for item in memberships
            ):
                raise ValueError(
                    "Candidate concept memberships must remain candidates"
                )
            if any(
                item.state is not ParentLinkState.CANDIDATE
                for item in parents
            ):
                raise ValueError(
                    "Candidate concept parent links must remain candidates"
                )
        if self.state is ConceptState.VALIDATED and not validation_refs:
            raise ValueError("Validated concept requires evidence references")
        if self.state is ConceptState.VALIDATED and not seals:
            raise ValueError("Validated concept requires derivation seals")
        if self.state is ConceptState.CRYSTALLIZED and len(validation_refs) < 2:
            raise ValueError(
                "Crystallized concept requires independent validation references"
            )
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "memberships", memberships)
        object.__setattr__(self, "parent_links", parents)
        object.__setattr__(self, "derivation_seals", seals)
        object.__setattr__(self, "validation_refs", validation_refs)

    @property
    def version_ref(self) -> str:
        return f"{self.concept_id}@{self.version}"


class ConceptStoreError(RuntimeError):
    """Concept history could not be safely validated or persisted."""


class ConceptCandidateBuilder:
    """Create nominations from retrievable crystals without validating them."""

    def __init__(
        self,
        memory: AtomicDiamondLearningMemory,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._memory = memory
        self._id_factory = id_factory or (
            lambda: f"concept:{uuid4()}"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def propose(
        self,
        *,
        canonical_name: str,
        scope: str,
        crystal_ids: tuple[str, ...],
        signature: ConceptSignature,
        aliases: tuple[str, ...] = (),
        parent_concept_ids: tuple[str, ...] = (),
        retrieval_policy: CrystalRetrievalPolicy = (
            CrystalRetrievalPolicy.ACTIVE
        ),
    ) -> ConceptRecord:
        available = {
            item.crystal_id: item
            for item in self._memory.crystals(
                scope=scope,
                policy=retrieval_policy,
            )
        }
        requested = tuple(dict.fromkeys(crystal_ids))
        if len(requested) < 2:
            raise ValueError("Concept proposal requires two distinct crystals")
        missing = sorted(set(requested) - set(available))
        if missing:
            raise ConceptStoreError(
                f"Concept proposal references unavailable crystals: {missing}"
            )
        concept_id = self._id_factory()
        if not isinstance(concept_id, str) or not _SAFE_ID.fullmatch(concept_id):
            raise ConceptStoreError("Concept builder generated an invalid ID")
        return ConceptRecord(
            concept_id=concept_id,
            version=1,
            canonical_name=canonical_name.strip(),
            aliases=aliases,
            scope=scope.strip(),
            state=ConceptState.CANDIDATE,
            signature=signature,
            memberships=tuple(
                ConceptMembership(crystal_id=item)
                for item in requested
            ),
            parent_links=tuple(
                ConceptParentLink(parent_concept_id=item)
                for item in dict.fromkeys(parent_concept_ids)
            ),
            revision_reason="initial candidate nomination",
            created_at=self._clock(),
        )


class AtomicConceptStore:
    """Versioned concept records; validation authority is intentionally absent."""

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._records = self._root / "records"
        self._pending = self._root / "pending"
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    @property
    def root(self) -> Path:
        return self._root

    def save(self, record: ConceptRecord) -> Path:
        if record.state in {
            ConceptState.VALIDATED,
            ConceptState.CRYSTALLIZED,
        }:
            raise PermissionError(
                "Concept validation operation is not installed"
            )
        return self._save(record)

    def _save_validated(self, record: ConceptRecord) -> Path:
        """Internal write boundary used only after deterministic validation."""

        if record.state is not ConceptState.VALIDATED:
            raise ConceptStoreError("Validated write requires VALIDATED state")
        return self._save(record)

    def _save(self, record: ConceptRecord) -> Path:
        history = self.history(record.concept_id)
        if not history:
            if record.version != 1 or record.previous_version_ref is not None:
                raise ConceptStoreError("Initial concept version is invalid")
        else:
            previous = history[-1]
            if record.version != previous.version + 1:
                raise ConceptStoreError("Concept version is not sequential")
            if record.previous_version_ref != previous.version_ref:
                raise ConceptStoreError("Concept version lineage is invalid")
        known_ids = {item.concept_id for item in self.latest_records()}
        missing_parents = {
            item.parent_concept_id for item in record.parent_links
        } - known_ids
        if missing_parents:
            raise ConceptStoreError(
                f"Unknown parent concepts: {sorted(missing_parents)}"
            )
        self._assert_acyclic(record)
        payload = encode_concept_record(record)
        content_hash = _hash_body(payload)
        sealed = {**payload, "content_hash": content_hash}
        filename = _record_filename(record.concept_id, record.version)
        pending = self._pending / f"{filename}.pending"
        final = self._records / filename
        if pending.exists() or final.exists():
            raise ConceptStoreError("Concept version already exists")
        try:
            self._pending.mkdir(parents=True, exist_ok=True)
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(_canonical_json(sealed) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._records.mkdir(parents=True, exist_ok=True)
            os.replace(pending, final)
        except OSError as exc:
            raise ConceptStoreError(
                f"Could not persist concept version: {type(exc).__name__}"
            ) from exc
        return final

    def revise(
        self,
        concept_id: str,
        *,
        canonical_name: str | None = None,
        aliases: tuple[str, ...] | None = None,
        signature: ConceptSignature | None = None,
        memberships: tuple[ConceptMembership, ...] | None = None,
        parent_links: tuple[ConceptParentLink, ...] | None = None,
        state: ConceptState | None = None,
        reason: str,
    ) -> ConceptRecord:
        previous = self.latest(concept_id)
        updated = replace(
            previous,
            version=previous.version + 1,
            canonical_name=canonical_name or previous.canonical_name,
            aliases=aliases if aliases is not None else previous.aliases,
            signature=signature or previous.signature,
            memberships=(
                memberships if memberships is not None
                else previous.memberships
            ),
            parent_links=(
                parent_links if parent_links is not None
                else previous.parent_links
            ),
            state=state or previous.state,
            previous_version_ref=previous.version_ref,
            revision_reason=reason,
            created_at=self._clock(),
        )
        self.save(updated)
        return updated

    def records(self) -> tuple[ConceptRecord, ...]:
        if not self._records.exists():
            return ()
        values = tuple(
            self._read(path)
            for path in self._records.glob("*.json")
            if path.is_file()
        )
        refs = [item.version_ref for item in values]
        if len(refs) != len(set(refs)):
            raise ConceptStoreError("Duplicate concept version reference")
        return tuple(sorted(
            values, key=lambda item: (item.concept_id, item.version)
        ))

    def history(self, concept_id: str) -> tuple[ConceptRecord, ...]:
        return tuple(
            item for item in self.records()
            if item.concept_id == concept_id
        )

    def latest(self, concept_id: str) -> ConceptRecord:
        history = self.history(concept_id)
        if not history:
            raise ConceptStoreError(f"Unknown concept: {concept_id}")
        for previous, current in zip(history, history[1:]):
            if current.version != previous.version + 1:
                raise ConceptStoreError("Concept history has a version gap")
            if current.previous_version_ref != previous.version_ref:
                raise ConceptStoreError("Concept history lineage mismatch")
        return history[-1]

    def latest_records(self) -> tuple[ConceptRecord, ...]:
        grouped: dict[str, ConceptRecord] = {}
        for item in self.records():
            current = grouped.get(item.concept_id)
            if current is None or item.version > current.version:
                grouped[item.concept_id] = item
        return tuple(
            grouped[key] for key in sorted(grouped)
        )

    def _assert_acyclic(self, replacement: ConceptRecord) -> None:
        graph = {
            item.concept_id: {
                link.parent_concept_id
                for link in item.parent_links
                if link.state is not ParentLinkState.REJECTED
            }
            for item in self.latest_records()
        }
        graph[replacement.concept_id] = {
            item.parent_concept_id
            for item in replacement.parent_links
            if item.state is not ParentLinkState.REJECTED
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ConceptStoreError("Concept hierarchy cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for parent in graph.get(node, set()):
                visit(parent)
            visiting.remove(node)
            visited.add(node)

        for concept_id in graph:
            visit(concept_id)

    @staticmethod
    def _read(path: Path) -> ConceptRecord:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("record is not an object")
            content_hash = raw.pop("content_hash")
            if not isinstance(content_hash, str):
                raise TypeError("content_hash is not text")
            if _hash_body(raw) != content_hash:
                raise ConceptStoreError(
                    f"Concept record hash mismatch: {path.name}"
                )
            record = decode_concept_record(raw)
            if path.name != _record_filename(
                record.concept_id, record.version
            ):
                raise ConceptStoreError("Concept record filename mismatch")
            return record
        except ConceptStoreError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ConceptStoreError(
                f"Malformed concept record {path.name}: {exc}"
            ) from exc


def encode_concept_record(record: ConceptRecord) -> dict[str, Any]:
    return {
        "schema": CONCEPT_RECORD_SCHEMA,
        "concept_id": record.concept_id,
        "version": record.version,
        "canonical_name": record.canonical_name,
        "aliases": list(record.aliases),
        "scope": record.scope,
        "state": record.state.value,
        "signature": {
            field_name: list(getattr(record.signature, field_name))
            for field_name in (
                "characteristics",
                "relations",
                "functions",
                "constraints",
                "exclusions",
                "examples",
                "counterexamples",
            )
        },
        "memberships": [
            {
                "crystal_id": item.crystal_id,
                "state": item.state.value,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in record.memberships
        ],
        "parent_links": [
            {
                "parent_concept_id": item.parent_concept_id,
                "state": item.state.value,
                "basis": item.basis,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in record.parent_links
        ],
        "derivation_seals": [
            {
                "seal_id": item.seal_id,
                "target_ref": item.target_ref,
                "contribution": item.contribution.value,
                "sources": [
                    {
                        "source_ref": source.source_ref,
                        "kind": source.kind.value,
                    }
                    for source in item.sources
                ],
                "analysis_id": item.analysis_id,
                "scope": item.scope,
                "created_at": item.created_at,
                "digest": item.digest,
            }
            for item in record.derivation_seals
        ],
        "recognition_state": record.recognition_state.value,
        "definition_state": record.definition_state.value,
        "validation_refs": list(record.validation_refs),
        "previous_version_ref": record.previous_version_ref,
        "revision_reason": record.revision_reason,
        "created_at": record.created_at,
        "promotion_authority": False,
    }


def decode_concept_record(value: Mapping[str, Any]) -> ConceptRecord:
    if value.get("schema") != CONCEPT_RECORD_SCHEMA:
        raise ValueError("Unknown Diamond concept schema")
    if value.get("promotion_authority") is not False:
        raise PermissionError("Persisted concept grants authority")
    if "order" in value or "order_profile" in value:
        raise ValueError("Concept records cannot carry intrinsic orders")
    signature = value.get("signature")
    memberships = value.get("memberships")
    parents = value.get("parent_links")
    seals = value.get("derivation_seals", [])
    if not isinstance(signature, Mapping):
        raise TypeError("Concept signature must be an object")
    if not all(isinstance(item, list) for item in (memberships, parents, seals)):
        raise TypeError("Concept memberships, parents, and seals must be arrays")
    if any(
        not isinstance(item, Mapping)
        for item in memberships + parents + seals
    ):
        raise TypeError("Concept membership, parent, or seal entry is invalid")
    decoded_seals = tuple(_decode_derivation_seal(item) for item in seals)
    return ConceptRecord(
        concept_id=_text(value, "concept_id"),
        version=_integer(value, "version"),
        canonical_name=_text(value, "canonical_name"),
        aliases=_text_tuple(value, "aliases"),
        scope=_text(value, "scope"),
        state=ConceptState(_text(value, "state")),
        signature=ConceptSignature(**{
            field_name: _text_tuple(signature, field_name)
            for field_name in (
                "characteristics",
                "relations",
                "functions",
                "constraints",
                "exclusions",
                "examples",
                "counterexamples",
            )
        }),
        memberships=tuple(
            ConceptMembership(
                crystal_id=_text(item, "crystal_id"),
                state=MembershipState(_text(item, "state")),
                evidence_refs=_text_tuple(item, "evidence_refs"),
            )
            for item in memberships
            if isinstance(item, Mapping)
        ),
        parent_links=tuple(
            ConceptParentLink(
                parent_concept_id=_text(item, "parent_concept_id"),
                state=ParentLinkState(_text(item, "state")),
                basis=_text(item, "basis"),
                evidence_refs=_text_tuple(item, "evidence_refs"),
            )
            for item in parents
            if isinstance(item, Mapping)
        ),
        derivation_seals=decoded_seals,
        recognition_state=ConceptAxisState(
            value.get("recognition_state", "NOT_EVALUATED")
        ),
        definition_state=ConceptAxisState(
            value.get("definition_state", "NOT_EVALUATED")
        ),
        validation_refs=_text_tuple(value, "validation_refs"),
        previous_version_ref=_optional_text(value, "previous_version_ref"),
        revision_reason=_text(value, "revision_reason"),
        created_at=_text(value, "created_at"),
        promotion_authority=False,
    )


def signature_target(field_name: str, value: str) -> str:
    allowed = {
        "characteristics",
        "relations",
        "functions",
        "constraints",
        "exclusions",
        "examples",
        "counterexamples",
    }
    if field_name not in allowed or not value.strip():
        raise ValueError("Invalid concept signature target")
    digest = sha256(" ".join(value.split()).encode("utf-8")).hexdigest()[:24]
    return f"signature:{field_name}:{digest}"


def membership_target(crystal_id: str) -> str:
    if not _SAFE_ID.fullmatch(crystal_id):
        raise ValueError("Invalid membership target")
    return f"membership:{crystal_id}"


def parent_target(concept_id: str) -> str:
    if not _SAFE_ID.fullmatch(concept_id):
        raise ValueError("Invalid parent target")
    return f"parent:{concept_id}"


def recognition_target(concept_id: str) -> str:
    if not _SAFE_ID.fullmatch(concept_id):
        raise ValueError("Invalid recognition target")
    return f"recognition:{concept_id}"


def definition_target(concept_id: str) -> str:
    if not _SAFE_ID.fullmatch(concept_id):
        raise ValueError("Invalid definition target")
    return f"definition:{concept_id}"


def concept_targets(record: ConceptRecord) -> tuple[str, ...]:
    signature = tuple(
        signature_target(field_name, value)
        for field_name in (
            "characteristics",
            "relations",
            "functions",
            "constraints",
            "exclusions",
        )
        for value in getattr(record.signature, field_name)
    )
    memberships = tuple(
        membership_target(item.crystal_id) for item in record.memberships
    )
    return signature + memberships


def _decode_derivation_seal(value: Mapping[str, Any]) -> DerivationSeal:
    raw_sources = value.get("sources")
    if not isinstance(raw_sources, list) or any(
        not isinstance(item, Mapping) for item in raw_sources
    ):
        raise TypeError("Derivation seal sources must be objects")
    seal = DerivationSeal(
        seal_id=_text(value, "seal_id"),
        target_ref=_text(value, "target_ref"),
        contribution=DerivationContribution(_text(value, "contribution")),
        sources=tuple(
            DerivationSource(
                source_ref=_text(item, "source_ref"),
                kind=DerivationSourceKind(_text(item, "kind")),
            )
            for item in raw_sources
        ),
        analysis_id=_text(value, "analysis_id"),
        scope=_text(value, "scope"),
        created_at=_text(value, "created_at"),
    )
    if value.get("digest") != seal.digest:
        raise ValueError("Derivation seal digest mismatch")
    return seal


def _clean_texts(values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not isinstance(item, str) for item in values):
        raise TypeError("Concept text collections must contain text")
    cleaned = tuple(
        dict.fromkeys(
            " ".join(item.split())
            for item in values
            if " ".join(item.split())
        )
    )
    return cleaned


def _record_filename(concept_id: str, version: int) -> str:
    key = sha256(concept_id.encode("utf-8")).hexdigest()[:24]
    return f"{key}.v{version}.json"


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key, ())
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, str) for item in raw):
        raise TypeError(f"{key} must contain text")
    return tuple(raw)


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
        raise ValueError(f"{key} must be non-empty text or null")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise TypeError(f"{key} must be an integer")
    return item


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()
