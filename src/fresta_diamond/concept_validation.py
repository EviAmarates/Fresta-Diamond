"""Deterministic, provenance-aware validation for Diamond concepts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptAxisState,
    ConceptRecord,
    ConceptState,
    DerivationContribution,
    DerivationSeal,
    DerivationSourceKind,
    MembershipState,
    concept_targets,
    membership_target,
)
from fresta_diamond.contracts import Remainder, RemainderKind
from fresta_diamond.epistemology import (
    EpistemicEvidenceGraph,
    EpistemicValidationReport,
    EpistemicValidator,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)
from fresta_diamond.ontology import (
    OntologicalValidator,
    StructuralEvidenceGraph,
    StructuralValidationReport,
)


CONCEPT_VALIDATION_REPORT_SCHEMA = (
    "fresta://diamond-concept-validation-report@1"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


@dataclass(frozen=True)
class ConceptValidationReport:
    validation_id: str
    concept_ref: str
    analysis_id: str
    local_fit: ConceptAxisState
    structural_state: ConceptAxisState
    recognition_state: ConceptAxisState
    definition_state: ConceptAxisState
    recommended_state: ConceptState
    supported_memberships: tuple[str, ...]
    supported_targets: tuple[str, ...]
    seal_digests: tuple[str, ...]
    structural_report: StructuralValidationReport
    epistemic_report: EpistemicValidationReport
    active_remainders: tuple[Remainder, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.validation_id):
            raise ValueError("Concept validation ID is invalid")
        if not all((
            self.concept_ref.strip(),
            self.analysis_id.strip(),
            self.created_at.strip(),
        )):
            raise ValueError("Concept validation references are required")
        if self.promotion_authority is not False:
            raise PermissionError(
                "Concept validation reports cannot grant authority"
            )
        if self.structural_report.analysis_id != self.analysis_id:
            raise ValueError("Structural report belongs to another analysis")
        if self.epistemic_report.analysis_id != self.analysis_id:
            raise ValueError("Epistemic report belongs to another analysis")
        if self.recommended_state is ConceptState.VALIDATED and not (
            self.local_fit is ConceptAxisState.SUPPORTED
            and self.structural_state is ConceptAxisState.SUPPORTED
            and self.definition_state is ConceptAxisState.SUPPORTED
            and self.epistemic_report.epistemic_closed
            and not self.active_remainders
        ):
            raise ValueError("Validated recommendation is not fully supported")


@dataclass(frozen=True)
class ConceptValidationOutcome:
    report: ConceptValidationReport
    record: ConceptRecord
    report_path: Path
    concept_path: Path | None


class ConceptValidationError(RuntimeError):
    """Concept validation or its audit record violated the contract."""


class ConceptValidator:
    """Cross-check seals, committed crystals, and independently validated graphs."""

    def __init__(
        self,
        memory: AtomicDiamondLearningMemory,
        *,
        ontological_validator: OntologicalValidator | None = None,
        epistemic_validator: EpistemicValidator | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._memory = memory
        self._ontological = ontological_validator or OntologicalValidator()
        self._epistemic = epistemic_validator or EpistemicValidator()
        self._id_factory = id_factory or (
            lambda: f"concept-validation:{uuid4()}"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def validate(
        self,
        concept: ConceptRecord,
        *,
        seals: tuple[DerivationSeal, ...],
        structural_graph: StructuralEvidenceGraph,
        epistemic_graph: EpistemicEvidenceGraph,
    ) -> ConceptValidationReport:
        if concept.state is not ConceptState.CANDIDATE:
            raise ConceptValidationError(
                "Only a concept candidate can enter first validation"
            )
        structural = self._ontological.validate(structural_graph)
        epistemic = self._epistemic.validate(epistemic_graph)
        remainders: list[Remainder] = []
        expected_object = concept.version_ref

        if structural_graph.analysis_id != epistemic_graph.analysis_id:
            remainders.append(_contradiction(
                "Structural and epistemic graphs use different analyses",
                concept.version_ref,
            ))
        if (
            structural_graph.object_ref != expected_object
            or epistemic_graph.object_ref != expected_object
        ):
            remainders.append(_scope(
                "Concept validation graph targets another object",
                concept.version_ref,
            ))
        if (
            structural_graph.scope != concept.scope
            or epistemic_graph.scope != concept.scope
        ):
            remainders.append(_scope(
                "Concept validation graph lies outside the concept scope",
                concept.version_ref,
            ))
        remainders.extend(structural.active_remainders)
        remainders.extend(epistemic.active_remainders)

        active_crystals = {
            item.crystal_id: item
            for item in self._memory.crystals(
                scope=concept.scope,
                policy=CrystalRetrievalPolicy.ACTIVE,
            )
        }
        member_ids = {item.crystal_id for item in concept.memberships}
        missing_active = member_ids - set(active_crystals)
        for crystal_id in sorted(missing_active):
            remainders.append(_missing(
                "Concept membership is not active validation evidence",
                membership_target(crystal_id),
            ))

        provenance_refs = {
            provenance
            for crystal_id in member_ids & set(active_crystals)
            for provenance in active_crystals[crystal_id].provenance
        }
        allowed_source_refs = member_ids | provenance_refs
        for manifestation in structural_graph.manifestations:
            unknown = set(manifestation.provenance) - allowed_source_refs
            if unknown:
                remainders.append(_missing(
                    "Structural graph contains uncommitted provenance",
                    manifestation.manifestation_id,
                ))
        for event in epistemic_graph.evidence_events:
            if event.source_locator not in allowed_source_refs:
                remainders.append(_missing(
                    "Epistemic graph contains uncommitted provenance",
                    event.evidence_id,
                ))
        if any(
            claim.subject_ref != expected_object
            for claim in epistemic_graph.claims
        ):
            remainders.append(_scope(
                "Epistemic claim targets another subject",
                concept.version_ref,
            ))

        required_targets = set(concept_targets(concept))
        positive_targets: set[str] = set()
        contested_targets: set[str] = set()
        seen_seals: set[str] = set()
        seal_digests: list[str] = []
        for seal in seals:
            if seal.seal_id in seen_seals:
                remainders.append(_contradiction(
                    "Duplicate derivation seal ID",
                    seal.seal_id,
                ))
                continue
            seen_seals.add(seal.seal_id)
            seal_digests.append(seal.digest)
            if seal.target_ref not in required_targets:
                remainders.append(_missing(
                    "Derivation seal targets no current concept part",
                    seal.target_ref,
                ))
            if seal.analysis_id != structural_graph.analysis_id:
                remainders.append(_scope(
                    "Derivation seal belongs to another analysis",
                    seal.seal_id,
                ))
            if seal.scope != concept.scope:
                remainders.append(_scope(
                    "Derivation seal lies outside the concept scope",
                    seal.seal_id,
                ))
            self._validate_sources(
                seal,
                member_ids=member_ids,
                provenance_refs=provenance_refs,
                remainders=remainders,
            )
            if seal.contribution is DerivationContribution.COUNTEREVIDENCE:
                contested_targets.add(seal.target_ref)
            else:
                positive_targets.add(seal.target_ref)

        for target in sorted(required_targets - positive_targets):
            remainders.append(_missing(
                "Concept part has no positive derivation seal",
                target,
            ))
        for target in sorted(contested_targets):
            remainders.append(_contradiction(
                "Live counterevidence contests a concept part",
                target,
            ))

        membership_targets = {
            membership_target(item.crystal_id): item.crystal_id
            for item in concept.memberships
        }
        signature_targets = required_targets - set(membership_targets)
        has_contradiction = any(
            item.kind is RemainderKind.CONTRADICTION
            for item in remainders
        )
        local_fit = _axis(
            required=set(membership_targets),
            positive=positive_targets,
            contested=contested_targets,
            blocked=bool(missing_active),
        )
        definition_state = _axis(
            required=signature_targets,
            positive=positive_targets,
            contested=contested_targets,
        )
        structural_state = (
            ConceptAxisState.CONTESTED
            if has_contradiction
            else (
                ConceptAxisState.SUPPORTED
                if structural.structural_closed
                else ConceptAxisState.INDETERMINATE
            )
        )
        clean = not remainders
        recommended = (
            ConceptState.CONTESTED
            if has_contradiction
            else (
                ConceptState.VALIDATED
                if (
                    clean
                    and local_fit is ConceptAxisState.SUPPORTED
                    and definition_state is ConceptAxisState.SUPPORTED
                    and structural_state is ConceptAxisState.SUPPORTED
                    and epistemic.epistemic_closed
                )
                else ConceptState.CANDIDATE
            )
        )
        validation_id = self._id_factory()
        if not isinstance(validation_id, str) or not _SAFE_ID.fullmatch(
            validation_id
        ):
            raise ConceptValidationError("Validator generated an invalid ID")
        return ConceptValidationReport(
            validation_id=validation_id,
            concept_ref=concept.version_ref,
            analysis_id=structural_graph.analysis_id,
            local_fit=local_fit,
            structural_state=structural_state,
            recognition_state=ConceptAxisState.NOT_EVALUATED,
            definition_state=definition_state,
            recommended_state=recommended,
            supported_memberships=tuple(sorted(
                crystal_id
                for target, crystal_id in membership_targets.items()
                if target in positive_targets and target not in contested_targets
            )),
            supported_targets=tuple(sorted(
                positive_targets - contested_targets
            )),
            seal_digests=tuple(sorted(seal_digests)),
            structural_report=structural,
            epistemic_report=epistemic,
            active_remainders=tuple(remainders),
            created_at=self._clock(),
        )

    @staticmethod
    def _validate_sources(
        seal: DerivationSeal,
        *,
        member_ids: set[str],
        provenance_refs: set[str],
        remainders: list[Remainder],
    ) -> None:
        for source in seal.sources:
            if source.kind is DerivationSourceKind.MEMORY_CRYSTAL:
                valid = source.source_ref in member_ids
            elif source.kind is DerivationSourceKind.DOCUMENT:
                valid = (
                    source.source_ref.startswith("document:")
                    and source.source_ref in provenance_refs
                )
            elif source.kind is DerivationSourceKind.WORKSPACE:
                valid = (
                    source.source_ref.startswith("workspace:")
                    and source.source_ref in provenance_refs
                )
            elif source.kind is DerivationSourceKind.WEB_SOURCE:
                valid = (
                    source.source_ref.startswith(("http://", "https://", "web:"))
                    and source.source_ref in provenance_refs
                )
            else:
                valid = False
            if not valid:
                remainders.append(_missing(
                    "Derivation seal contains unavailable, unlearned, or "
                    "kind-mismatched evidence",
                    seal.seal_id,
                ))


class AtomicConceptValidationArchive:
    """Append-only report archive independent from promoted concept versions."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def save(self, report: ConceptValidationReport) -> Path:
        payload = encode_concept_validation_report(report)
        sealed = {**payload, "content_hash": _hash_body(payload)}
        self._root.mkdir(parents=True, exist_ok=True)
        filename = (
            sha256(report.validation_id.encode("utf-8")).hexdigest()[:24]
            + ".json"
        )
        final = self._root / filename
        pending = self._root / f"{filename}.pending"
        if final.exists() or pending.exists():
            raise ConceptValidationError("Validation report already exists")
        try:
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(_canonical_json(sealed) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, final)
        except OSError as exc:
            raise ConceptValidationError(
                f"Could not persist validation report: {type(exc).__name__}"
            ) from exc
        return final

    def load(self, validation_id: str) -> ConceptValidationReport:
        filename = (
            sha256(validation_id.encode("utf-8")).hexdigest()[:24]
            + ".json"
        )
        path = self._root / filename
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("report is not an object")
            content_hash = raw.pop("content_hash")
            if content_hash != _hash_body(raw):
                raise ConceptValidationError("Validation report hash mismatch")
            report = decode_concept_validation_report(raw)
            if report.validation_id != validation_id:
                raise ConceptValidationError(
                    "Validation report identity mismatch"
                )
            return report
        except ConceptValidationError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ConceptValidationError(
                f"Malformed validation report: {exc}"
            ) from exc


class ConceptValidationService:
    """Persist a report, then version a concept only when its decision warrants it."""

    def __init__(
        self,
        memory: AtomicDiamondLearningMemory,
        concept_store: AtomicConceptStore,
        *,
        validator: ConceptValidator | None = None,
        archive: AtomicConceptValidationArchive | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._store = concept_store
        self._validator = validator or ConceptValidator(memory)
        self._archive = archive or AtomicConceptValidationArchive(
            concept_store.root / "validations"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def validate_and_store(
        self,
        concept_id: str,
        *,
        seals: tuple[DerivationSeal, ...],
        structural_graph: StructuralEvidenceGraph,
        epistemic_graph: EpistemicEvidenceGraph,
    ) -> ConceptValidationOutcome:
        current = self._store.latest(concept_id)
        report = self._validator.validate(
            current,
            seals=seals,
            structural_graph=structural_graph,
            epistemic_graph=epistemic_graph,
        )
        report_path = self._archive.save(report)
        if report.recommended_state is ConceptState.CANDIDATE:
            return ConceptValidationOutcome(
                report, current, report_path, None
            )

        supported = set(report.supported_memberships)
        contested_targets = {
            item.target_ref
            for item in seals
            if item.contribution is DerivationContribution.COUNTEREVIDENCE
        }
        memberships = tuple(
            replace(
                item,
                state=(
                    MembershipState.CONTESTED
                    if membership_target(item.crystal_id) in contested_targets
                    else (
                        MembershipState.SUPPORTED
                        if item.crystal_id in supported
                        else item.state
                    )
                ),
                evidence_refs=tuple(sorted({
                    *item.evidence_refs,
                    report.analysis_id,
                    *(
                        seal.seal_id
                        for seal in seals
                        if seal.target_ref == membership_target(item.crystal_id)
                    ),
                })),
            )
            for item in current.memberships
        )
        updated = replace(
            current,
            version=current.version + 1,
            state=report.recommended_state,
            memberships=memberships,
            derivation_seals=seals,
            recognition_state=report.recognition_state,
            definition_state=report.definition_state,
            validation_refs=(report.validation_id, report.analysis_id),
            previous_version_ref=current.version_ref,
            revision_reason=(
                "deterministic contextual concept validation"
                if report.recommended_state is ConceptState.VALIDATED
                else "concept contested by contextual validation"
            ),
            created_at=self._clock(),
        )
        if updated.state is ConceptState.VALIDATED:
            concept_path = self._store._save_validated(updated)
        else:
            concept_path = self._store.save(updated)
        return ConceptValidationOutcome(
            report, updated, report_path, concept_path
        )


def encode_concept_validation_report(
    report: ConceptValidationReport,
) -> dict[str, Any]:
    return {
        "schema": CONCEPT_VALIDATION_REPORT_SCHEMA,
        "validation_id": report.validation_id,
        "concept_ref": report.concept_ref,
        "analysis_id": report.analysis_id,
        "local_fit": report.local_fit.value,
        "structural_state": report.structural_state.value,
        "recognition_state": report.recognition_state.value,
        "definition_state": report.definition_state.value,
        "recommended_state": report.recommended_state.value,
        "supported_memberships": list(report.supported_memberships),
        "supported_targets": list(report.supported_targets),
        "seal_digests": list(report.seal_digests),
        "structural_report": _encode_structural_report(
            report.structural_report
        ),
        "epistemic_report": _encode_epistemic_report(report.epistemic_report),
        "active_remainders": [
            _encode_remainder(item) for item in report.active_remainders
        ],
        "created_at": report.created_at,
        "promotion_authority": False,
    }


def decode_concept_validation_report(
    value: Mapping[str, Any],
) -> ConceptValidationReport:
    if value.get("schema") != CONCEPT_VALIDATION_REPORT_SCHEMA:
        raise ValueError("Unknown concept validation report schema")
    if value.get("promotion_authority") is not False:
        raise PermissionError("Validation report grants authority")
    return ConceptValidationReport(
        validation_id=_text(value, "validation_id"),
        concept_ref=_text(value, "concept_ref"),
        analysis_id=_text(value, "analysis_id"),
        local_fit=ConceptAxisState(_text(value, "local_fit")),
        structural_state=ConceptAxisState(_text(value, "structural_state")),
        recognition_state=ConceptAxisState(_text(value, "recognition_state")),
        definition_state=ConceptAxisState(_text(value, "definition_state")),
        recommended_state=ConceptState(_text(value, "recommended_state")),
        supported_memberships=_text_tuple(value, "supported_memberships"),
        supported_targets=_text_tuple(value, "supported_targets"),
        seal_digests=_text_tuple(value, "seal_digests"),
        structural_report=_decode_structural_report(
            _mapping(value, "structural_report")
        ),
        epistemic_report=_decode_epistemic_report(
            _mapping(value, "epistemic_report")
        ),
        active_remainders=tuple(
            _decode_remainder(item)
            for item in _mapping_tuple(value, "active_remainders")
        ),
        created_at=_text(value, "created_at"),
        promotion_authority=False,
    )


def _axis(
    *,
    required: set[str],
    positive: set[str],
    contested: set[str],
    blocked: bool = False,
) -> ConceptAxisState:
    if required & contested:
        return ConceptAxisState.CONTESTED
    if not blocked and required and required <= positive:
        return ConceptAxisState.SUPPORTED
    return ConceptAxisState.INDETERMINATE


def _missing(description: str, required_for: str) -> Remainder:
    return Remainder(
        kind=RemainderKind.MISSING_EVIDENCE,
        description=description,
        required_for=required_for,
        resolvable=True,
    )


def _scope(description: str, required_for: str) -> Remainder:
    return Remainder(
        kind=RemainderKind.INVALID_SCOPE,
        description=description,
        required_for=required_for,
        resolvable=True,
    )


def _contradiction(description: str, required_for: str) -> Remainder:
    return Remainder(
        kind=RemainderKind.CONTRADICTION,
        description=description,
        required_for=required_for,
        resolvable=True,
    )


def _encode_structural_report(
    report: StructuralValidationReport,
) -> dict[str, Any]:
    return {
        "analysis_id": report.analysis_id,
        "object_ref": report.object_ref,
        "reciprocal_structure_valid": report.reciprocal_structure_valid,
        "constitutional_closed": report.constitutional_closed,
        "structural_closed": report.structural_closed,
        "active_remainders": [
            _encode_remainder(item) for item in report.active_remainders
        ],
        "used_manifestations": list(report.used_manifestations),
        "used_relations": list(report.used_relations),
        "used_constraints": list(report.used_constraints),
        "used_filters": list(report.used_filters),
        "used_costs": list(report.used_costs),
    }


def _decode_structural_report(
    value: Mapping[str, Any],
) -> StructuralValidationReport:
    return StructuralValidationReport(
        analysis_id=_text(value, "analysis_id"),
        object_ref=_text(value, "object_ref"),
        reciprocal_structure_valid=_boolean(
            value, "reciprocal_structure_valid"
        ),
        constitutional_closed=_optional_boolean(
            value, "constitutional_closed"
        ),
        structural_closed=_boolean(value, "structural_closed"),
        active_remainders=tuple(
            _decode_remainder(item)
            for item in _mapping_tuple(value, "active_remainders")
        ),
        used_manifestations=_text_tuple(value, "used_manifestations"),
        used_relations=_text_tuple(value, "used_relations"),
        used_constraints=_text_tuple(value, "used_constraints"),
        used_filters=_text_tuple(value, "used_filters"),
        used_costs=_text_tuple(value, "used_costs"),
    )


def _encode_epistemic_report(
    report: EpistemicValidationReport,
) -> dict[str, Any]:
    return {
        "analysis_id": report.analysis_id,
        "object_ref": report.object_ref,
        "epistemic_closed": report.epistemic_closed,
        "claim_reports": [
            {
                "claim_id": item.claim_id,
                "claim_mode": item.claim_mode.value,
                "burden_satisfied": item.burden_satisfied,
                "supporting_evidence": list(item.supporting_evidence),
                "contradicting_evidence": list(
                    item.contradicting_evidence
                ),
                "active_remainders": [
                    _encode_remainder(remainder)
                    for remainder in item.active_remainders
                ],
            }
            for item in report.claim_reports
        ],
        "active_remainders": [
            _encode_remainder(item) for item in report.active_remainders
        ],
        "used_evidence": list(report.used_evidence),
    }


def _decode_epistemic_report(
    value: Mapping[str, Any],
) -> EpistemicValidationReport:
    from fresta_diamond.epistemology import ClaimBurdenReport, ClaimMode

    return EpistemicValidationReport(
        analysis_id=_text(value, "analysis_id"),
        object_ref=_text(value, "object_ref"),
        epistemic_closed=_boolean(value, "epistemic_closed"),
        claim_reports=tuple(
            ClaimBurdenReport(
                claim_id=_text(item, "claim_id"),
                claim_mode=ClaimMode(_text(item, "claim_mode")),
                burden_satisfied=_boolean(item, "burden_satisfied"),
                supporting_evidence=_text_tuple(
                    item, "supporting_evidence"
                ),
                contradicting_evidence=_text_tuple(
                    item, "contradicting_evidence"
                ),
                active_remainders=tuple(
                    _decode_remainder(remainder)
                    for remainder in _mapping_tuple(
                        item, "active_remainders"
                    )
                ),
            )
            for item in _mapping_tuple(value, "claim_reports")
        ),
        active_remainders=tuple(
            _decode_remainder(item)
            for item in _mapping_tuple(value, "active_remainders")
        ),
        used_evidence=_text_tuple(value, "used_evidence"),
    )


def _encode_remainder(value: Remainder) -> dict[str, Any]:
    return {
        "kind": value.kind.value,
        "description": value.description,
        "required_for": value.required_for,
        "resolvable": value.resolvable,
        "suggested_capability": value.suggested_capability,
        "remainder_id": value.remainder_id,
        "status": value.status,
    }


def _decode_remainder(value: Mapping[str, Any]) -> Remainder:
    return Remainder(
        kind=RemainderKind(_text(value, "kind")),
        description=_text(value, "description"),
        required_for=_text(value, "required_for"),
        resolvable=_optional_boolean(value, "resolvable"),
        suggested_capability=_optional_text(value, "suggested_capability"),
        remainder_id=_text(value, "remainder_id"),
        status=_text(value, "status"),
    )


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise TypeError(f"{key} must be an object")
    return item


def _mapping_tuple(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, list) or any(
        not isinstance(item, Mapping) for item in raw
    ):
        raise TypeError(f"{key} must contain objects")
    return tuple(raw)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, list) or any(
        not isinstance(item, str) for item in raw
    ):
        raise TypeError(f"{key} must contain text")
    return tuple(raw)


def _boolean(value: Mapping[str, Any], key: str) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise TypeError(f"{key} must be boolean")
    return item


def _optional_boolean(value: Mapping[str, Any], key: str) -> bool | None:
    item = value.get(key)
    if item is not None and not isinstance(item, bool):
        raise TypeError(f"{key} must be boolean or null")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise TypeError(f"{key} must be text or null")
    return item
