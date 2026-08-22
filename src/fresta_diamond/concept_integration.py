"""Learn external concept sources and update only external concept axes."""

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

from fresta_diamond.cognitive_workspace import JsonlCognitiveWorkspace
from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptAxisState,
    ConceptRecord,
    ConceptState,
    DerivationContribution,
    DerivationSeal,
    DerivationSource,
    DerivationSourceKind,
    definition_target,
    recognition_target,
)
from fresta_diamond.concept_research import (
    CONCEPT_SOURCE_UNITS_SCHEMA,
    ConceptSourceUnit,
    decode_source_units,
    stage_source_units,
)
from fresta_diamond.concept_validation import ConceptValidationReport
from fresta_diamond.contracts import (
    Artifact,
    ControllerResult,
    Remainder,
    RemainderKind,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.crystallization import CrystalState, LearningCrystal
from fresta_diamond.effects import EffectBroker
from fresta_diamond.learning import (
    build_workspace_learn_request,
    register_workspace_learn_provider,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    StoredLearningCommit,
)
from fresta_diamond.llm_learning import (
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    learning_evaluation_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.source_policy import (
    EvidenceCoverageState,
    ExternalEvidenceAssessor,
    ExternalEvidencePolicy,
    ResearchStopDecision,
)


CONCEPT_RECOGNITION_REPORT_SCHEMA = (
    "fresta://diamond-concept-recognition-report@2"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


@dataclass(frozen=True)
class ExternalConceptLearningOutcome:
    source_artifact_id: str
    sheet_revision_id: str
    selection_id: str
    proposal_id: str
    result: ControllerResult
    stored_commit: StoredLearningCommit
    model_call_count: int


class ConceptSourceLearner:
    """Run externally found source units through the ordinary learning path."""

    def __init__(
        self,
        llm_adapter: Callable[..., Mapping[str, Any]],
        *,
        required_permissions: tuple[str, ...],
        max_tokens: int = 4_000,
        sheet_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not required_permissions:
            raise ValueError("External source learning requires model permission")
        self._adapter = llm_adapter
        self._permissions = required_permissions
        self._max_tokens = max_tokens
        self._sheet_id_factory = sheet_id_factory or (
            lambda: f"concept-source-learning-{uuid4()}"
        )

    def learn(
        self,
        *,
        concept: ConceptRecord,
        source_artifact: Artifact,
        workspace: JsonlCognitiveWorkspace,
        memory: AtomicDiamondLearningMemory,
    ) -> ExternalConceptLearningOutcome:
        if source_artifact.schema != CONCEPT_SOURCE_UNITS_SCHEMA:
            raise ValueError("External learning requires concept source units")
        if source_artifact.payload.get("concept_ref") != concept.version_ref:
            raise ValueError("External sources belong to another concept version")
        units = decode_source_units(source_artifact)
        if not units:
            raise ValueError("External source learning requires source units")
        sheet = stage_source_units(
            workspace,
            source_artifact,
            sheet_id=self._sheet_id_factory(),
            concept_ref=concept.version_ref,
            title=f"Research for {concept.canonical_name}",
        )
        selection, selection_artifact = workspace.select(
            sheet.sheet_id,
            tuple(item.element_id for item in sheet.elements),
            objective=(
                "Evaluate external source reports as attestations for "
                f"{concept.version_ref}; preserve every source locator."
            ),
        )
        request = build_workspace_learn_request(selection, selection_artifact)
        registry = ModuleRegistry()
        register_workspace_learn_provider(registry)
        intake = DiamondController(registry).execute(
            request.blueprint,
            request.objective,
            request.inputs,
        )
        proposal = intake.execution.artifacts["learning_proposal"]

        manifest = llm_learning_manifest(self._permissions)
        registry.discover(manifest)
        admission = registry.verify(manifest.module_id)
        if not admission.admitted:
            raise RuntimeError("External-source learning provider was rejected")
        registry.enable(
            manifest.module_id,
            {
                manifest.operations[0].operation_id: (
                    LlmLearningStructuralOperation(max_tokens=self._max_tokens)
                ),
                manifest.operations[1].operation_id: (
                    LlmLearningEpistemicOperation()
                ),
                manifest.operations[2].operation_id: (
                    LlmLearningRepairOperation(max_tokens=self._max_tokens)
                ),
            },
        )
        calls = 0

        def counted_adapter(grant: Any, **kwargs: Any) -> Mapping[str, Any]:
            nonlocal calls
            calls += 1
            return self._adapter(grant, **kwargs)

        result = DiamondController(
            registry,
            effect_broker=EffectBroker({
                "llm.generate": counted_adapter
            }),
        ).execute(
            learning_evaluation_blueprint(self._permissions),
            request.objective,
            {"learning_proposal": proposal},
        )
        stored = memory.commit(proposal, result)
        expected_elements = {
            f"source-unit:{item.source_unit_id}" for item in units
        }
        actual_elements = {
            item.source_element_id
            for item in stored.commit.crystallization.crystals
        }
        if actual_elements != expected_elements:
            raise RuntimeError(
                "External learning commit lost or invented source units"
            )
        return ExternalConceptLearningOutcome(
            source_artifact_id=source_artifact.artifact_id,
            sheet_revision_id=sheet.revision_id,
            selection_id=selection.selection_id,
            proposal_id=stored.commit.proposal_id,
            result=result,
            stored_commit=stored,
            model_call_count=calls,
        )


@dataclass(frozen=True)
class ConceptRecognitionReport:
    recognition_id: str
    concept_ref: str
    prior_validation_id: str
    research_request_id: str
    learning_commit_id: str
    analysis_id: str
    recognition_state: ConceptAxisState
    external_definition_state: ConceptAxisState
    external_crystal_ids: tuple[str, ...]
    source_locators: tuple[str, ...]
    source_families: tuple[str, ...]
    source_types: tuple[str, ...]
    query_ids: tuple[str, ...]
    evidence_coverage_state: EvidenceCoverageState
    research_stop_decision: ResearchStopDecision
    unmet_requirements: tuple[str, ...] = ()
    active_remainders: tuple[Remainder, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.recognition_id):
            raise ValueError("Concept recognition ID is invalid")
        if not all((
            self.concept_ref.strip(),
            self.prior_validation_id.strip(),
            self.research_request_id.strip(),
            self.learning_commit_id.strip(),
            self.analysis_id.strip(),
            self.created_at.strip(),
        )):
            raise ValueError("Concept recognition references are required")
        if self.promotion_authority is not False:
            raise PermissionError("Recognition reports cannot promote memory")


@dataclass(frozen=True)
class ConceptRecognitionOutcome:
    report: ConceptRecognitionReport
    record: ConceptRecord
    report_path: Path
    concept_path: Path | None


class ConceptRecognitionError(RuntimeError):
    """External recognition could not be safely derived or archived."""


class ConceptRecognitionValidator:
    """Interpret learned external crystals without revisiting local-fit authority."""

    def __init__(
        self,
        memory: AtomicDiamondLearningMemory,
        *,
        evidence_policy: ExternalEvidencePolicy | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._memory = memory
        self._evidence_assessor = ExternalEvidenceAssessor(evidence_policy)
        self._id_factory = id_factory or (
            lambda: f"concept-recognition:{uuid4()}"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def validate(
        self,
        concept: ConceptRecord,
        *,
        prior_validation: ConceptValidationReport,
        source_artifact: Artifact,
        learning: ExternalConceptLearningOutcome,
    ) -> ConceptRecognitionReport:
        if concept.state is not ConceptState.VALIDATED:
            raise ConceptRecognitionError(
                "External recognition requires a locally validated concept"
            )
        if concept.recognition_state is ConceptAxisState.CONTESTED:
            raise ConceptRecognitionError(
                "Contested recognition requires explicit repair"
            )
        prior_applies = (
            prior_validation.validation_id in concept.validation_refs
            and prior_validation.local_fit is ConceptAxisState.SUPPORTED
            and prior_validation.structural_state is ConceptAxisState.SUPPORTED
        )
        if not prior_applies:
            raise ConceptRecognitionError(
                "Concept lacks its supporting internal validation"
            )
        if source_artifact.payload.get("concept_ref") != concept.version_ref:
            raise ConceptRecognitionError(
                "External sources belong to another concept version"
            )
        units = decode_source_units(source_artifact)
        by_element = {
            f"source-unit:{item.source_unit_id}": item for item in units
        }
        supplied = learning.stored_commit
        committed = {
            item.commit.commit_id: item for item in self._memory.commits()
        }
        canonical = committed.get(supplied.commit.commit_id)
        if canonical is None:
            raise ConceptRecognitionError(
                "External learning commit is not present in memory"
            )
        if (
            canonical.content_hash != supplied.content_hash
            or canonical.commit != supplied.commit
        ):
            raise ConceptRecognitionError(
                "External learning outcome does not match committed memory"
            )
        commit = canonical.commit
        if commit.proposal_id != learning.proposal_id:
            raise ConceptRecognitionError(
                "External learning outcome and commit differ"
            )
        remainders: list[Remainder] = []
        positive: list[tuple[LearningCrystal, ConceptSourceUnit]] = []
        contested = False
        for crystal in commit.crystallization.crystals:
            unit = by_element.get(crystal.source_element_id)
            if unit is None:
                remainders.append(_contradiction(
                    "External crystal references an unknown source unit",
                    crystal.crystal_id,
                ))
                contested = True
                continue
            if unit.source_locator not in crystal.provenance:
                remainders.append(_missing(
                    "External crystal lost its source locator",
                    crystal.crystal_id,
                ))
                continue
            if crystal.scope != concept.scope:
                remainders.append(_scope(
                    "External crystal lies outside the concept scope",
                    crystal.crystal_id,
                ))
                continue
            if crystal.state in {
                CrystalState.ACCEPTED,
                CrystalState.PROVISIONAL,
            }:
                positive.append((crystal, unit))
            elif crystal.state in {
                CrystalState.QUARANTINED,
                CrystalState.PHI_MINUS,
            }:
                contested = True
                remainders.append(_contradiction(
                    "External source was excluded by learning",
                    crystal.crystal_id,
                ))
            else:
                remainders.append(_missing(
                    "External source remains deferred",
                    crystal.crystal_id,
                ))
        if len(positive) != len(units):
            missing = set(by_element) - {
                item.source_element_id for item, _unit in positive
            }
            for element_id in sorted(missing):
                if not any(
                    remainder.required_for == element_id
                    for remainder in remainders
                ):
                    remainders.append(_missing(
                        "Source unit has no active learned crystal",
                        element_id,
                    ))

        structural_closed = (
            len(learning.result.ontological_reports) == 1
            and learning.result.ontological_reports[0].structural_closed
        )
        epistemic_closed = (
            len(learning.result.epistemic_reports) == 1
            and learning.result.epistemic_reports[0].epistemic_closed
        )
        if not structural_closed:
            remainders.append(_missing(
                "External learning lacks structural closure",
                concept.version_ref,
            ))
        if not epistemic_closed:
            remainders.append(_missing(
                "External learning lacks epistemic closure",
                concept.version_ref,
            ))
        if commit.negative_boundary:
            if any(
                item.phi_minus_justified
                for item in commit.negative_boundary
            ):
                contested = True

        positive_units = tuple(unit for _crystal, unit in positive)
        assessment = self._evidence_assessor.assess(
            positive_units,
            conflict_detected=contested,
        )
        locators = {unit.source_locator for unit in positive_units}
        query_ids = set(assessment.query_ids)
        source_types = set(assessment.source_types)
        coverage_complete = not assessment.unmet_requirements
        has_neutral = bool(
            query_ids & {
                "query:features",
                "query:relations",
                "query:boundaries",
            }
        )
        has_label = "query:label" in query_ids
        recognition_state = (
            ConceptAxisState.CONTESTED
            if contested
            else (
                ConceptAxisState.SUPPORTED
                if (
                    structural_closed
                    and epistemic_closed
                    and coverage_complete
                    and has_label
                )
                else ConceptAxisState.INDETERMINATE
            )
        )
        definition_state = (
            ConceptAxisState.CONTESTED
            if contested
            else (
                ConceptAxisState.SUPPORTED
                if (
                    structural_closed
                    and epistemic_closed
                    and coverage_complete
                    and has_neutral
                    and len(query_ids) >= 2
                )
                else ConceptAxisState.INDETERMINATE
            )
        )
        if assessment.unmet_requirements:
            remainders.append(_missing(
                "External evidence has not met its diversity and coverage policy",
                concept.version_ref,
            ))
        if not has_label:
            remainders.append(_missing(
                "External recognition lacks the label query",
                recognition_target(concept.concept_id),
            ))
        if not has_neutral:
            remainders.append(_missing(
                "External definition lacks neutral characteristic evidence",
                definition_target(concept.concept_id),
            ))
        recognition_id = self._id_factory()
        if not isinstance(recognition_id, str) or not _SAFE_ID.fullmatch(
            recognition_id
        ):
            raise ConceptRecognitionError(
                "Recognition validator generated an invalid ID"
            )
        analysis_id = (
            learning.result.ontological_reports[0].analysis_id
            if learning.result.ontological_reports
            else f"analysis:missing:{commit.commit_id}"
        )
        return ConceptRecognitionReport(
            recognition_id=recognition_id,
            concept_ref=concept.version_ref,
            prior_validation_id=prior_validation.validation_id,
            research_request_id=_text(
                source_artifact.payload, "request_id"
            ),
            learning_commit_id=commit.commit_id,
            analysis_id=analysis_id,
            recognition_state=recognition_state,
            external_definition_state=definition_state,
            external_crystal_ids=tuple(sorted(
                crystal.crystal_id for crystal, _unit in positive
            )),
            source_locators=tuple(sorted(locators)),
            source_families=assessment.source_families,
            source_types=tuple(sorted(source_types)),
            query_ids=tuple(sorted(query_ids)),
            evidence_coverage_state=assessment.coverage_state,
            research_stop_decision=assessment.stop_decision,
            unmet_requirements=assessment.unmet_requirements,
            active_remainders=tuple(remainders),
            created_at=self._clock(),
        )


class AtomicConceptRecognitionArchive:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def save(self, report: ConceptRecognitionReport) -> Path:
        body = encode_concept_recognition_report(report)
        sealed = {**body, "content_hash": _hash_body(body)}
        self._root.mkdir(parents=True, exist_ok=True)
        filename = (
            sha256(report.recognition_id.encode("utf-8")).hexdigest()[:24]
            + ".json"
        )
        final = self._root / filename
        pending = self._root / f"{filename}.pending"
        if final.exists() or pending.exists():
            raise ConceptRecognitionError("Recognition report already exists")
        try:
            with pending.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(_canonical_json(sealed) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, final)
        except OSError as exc:
            raise ConceptRecognitionError(
                f"Could not persist recognition report: {type(exc).__name__}"
            ) from exc
        return final

    def load(self, recognition_id: str) -> ConceptRecognitionReport:
        filename = (
            sha256(recognition_id.encode("utf-8")).hexdigest()[:24]
            + ".json"
        )
        path = self._root / filename
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise TypeError("recognition report is not an object")
            content_hash = raw.pop("content_hash")
            if content_hash != _hash_body(raw):
                raise ConceptRecognitionError(
                    "Recognition report hash mismatch"
                )
            report = decode_concept_recognition_report(raw)
            if report.recognition_id != recognition_id:
                raise ConceptRecognitionError(
                    "Recognition report identity mismatch"
                )
            return report
        except ConceptRecognitionError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ConceptRecognitionError(
                f"Malformed recognition report: {exc}"
            ) from exc


class ConceptRecognitionService:
    def __init__(
        self,
        memory: AtomicDiamondLearningMemory,
        concept_store: AtomicConceptStore,
        *,
        validator: ConceptRecognitionValidator | None = None,
        archive: AtomicConceptRecognitionArchive | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._store = concept_store
        self._validator = validator or ConceptRecognitionValidator(memory)
        self._archive = archive or AtomicConceptRecognitionArchive(
            concept_store.root / "recognition"
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    def validate_and_store(
        self,
        concept_id: str,
        *,
        prior_validation: ConceptValidationReport,
        source_artifact: Artifact,
        learning: ExternalConceptLearningOutcome,
    ) -> ConceptRecognitionOutcome:
        current = self._store.latest(concept_id)
        report = self._validator.validate(
            current,
            prior_validation=prior_validation,
            source_artifact=source_artifact,
            learning=learning,
        )
        report_path = self._archive.save(report)
        if (
            report.recognition_state is ConceptAxisState.INDETERMINATE
            and report.external_definition_state
            is ConceptAxisState.INDETERMINATE
        ):
            return ConceptRecognitionOutcome(
                report, current, report_path, None
            )

        units = {
            f"source-unit:{item.source_unit_id}": item
            for item in decode_source_units(source_artifact)
        }
        crystals = {
            item.source_element_id: item
            for item in learning.stored_commit.commit.crystallization.crystals
            if item.crystal_id in set(report.external_crystal_ids)
        }
        new_seals: list[DerivationSeal] = []
        for index, (element_id, crystal) in enumerate(
            sorted(crystals.items()), start=1
        ):
            unit = units[element_id]
            target = (
                recognition_target(current.concept_id)
                if unit.query_id == "query:label"
                else definition_target(current.concept_id)
            )
            new_seals.append(DerivationSeal(
                seal_id=f"seal:external:{report.recognition_id}:{index}",
                target_ref=target,
                contribution=DerivationContribution.CORROBORATION,
                sources=(
                    DerivationSource(
                        crystal.crystal_id,
                        DerivationSourceKind.MEMORY_CRYSTAL,
                    ),
                    DerivationSource(
                        unit.source_locator,
                        DerivationSourceKind.WEB_SOURCE,
                    ),
                ),
                analysis_id=report.analysis_id,
                scope=current.scope,
                created_at=self._clock(),
            ))
        updated = replace(
            current,
            version=current.version + 1,
            derivation_seals=(
                current.derivation_seals + tuple(new_seals)
            ),
            recognition_state=report.recognition_state,
            definition_state=(
                report.external_definition_state
                if report.external_definition_state
                is not ConceptAxisState.INDETERMINATE
                else current.definition_state
            ),
            validation_refs=tuple(dict.fromkeys((
                *current.validation_refs,
                report.recognition_id,
                report.analysis_id,
            ))),
            previous_version_ref=current.version_ref,
            revision_reason="external concept recognition review",
            created_at=self._clock(),
        )
        concept_path = self._store._save_validated(updated)
        return ConceptRecognitionOutcome(
            report, updated, report_path, concept_path
        )


def encode_concept_recognition_report(
    report: ConceptRecognitionReport,
) -> dict[str, Any]:
    return {
        "schema": CONCEPT_RECOGNITION_REPORT_SCHEMA,
        "recognition_id": report.recognition_id,
        "concept_ref": report.concept_ref,
        "prior_validation_id": report.prior_validation_id,
        "research_request_id": report.research_request_id,
        "learning_commit_id": report.learning_commit_id,
        "analysis_id": report.analysis_id,
        "recognition_state": report.recognition_state.value,
        "external_definition_state": (
            report.external_definition_state.value
        ),
        "external_crystal_ids": list(report.external_crystal_ids),
        "source_locators": list(report.source_locators),
        "source_families": list(report.source_families),
        "source_types": list(report.source_types),
        "query_ids": list(report.query_ids),
        "evidence_coverage_state": report.evidence_coverage_state.value,
        "research_stop_decision": report.research_stop_decision.value,
        "unmet_requirements": list(report.unmet_requirements),
        "active_remainders": [
            _encode_remainder(item) for item in report.active_remainders
        ],
        "created_at": report.created_at,
        "promotion_authority": False,
    }


def decode_concept_recognition_report(
    value: Mapping[str, Any],
) -> ConceptRecognitionReport:
    if value.get("schema") != CONCEPT_RECOGNITION_REPORT_SCHEMA:
        raise ValueError("Unknown concept recognition report schema")
    if value.get("promotion_authority") is not False:
        raise PermissionError("Recognition report grants authority")
    return ConceptRecognitionReport(
        recognition_id=_text(value, "recognition_id"),
        concept_ref=_text(value, "concept_ref"),
        prior_validation_id=_text(value, "prior_validation_id"),
        research_request_id=_text(value, "research_request_id"),
        learning_commit_id=_text(value, "learning_commit_id"),
        analysis_id=_text(value, "analysis_id"),
        recognition_state=ConceptAxisState(
            _text(value, "recognition_state")
        ),
        external_definition_state=ConceptAxisState(
            _text(value, "external_definition_state")
        ),
        external_crystal_ids=_text_tuple(value, "external_crystal_ids"),
        source_locators=_text_tuple(value, "source_locators"),
        source_families=_text_tuple(value, "source_families"),
        source_types=_text_tuple(value, "source_types"),
        query_ids=_text_tuple(value, "query_ids"),
        evidence_coverage_state=EvidenceCoverageState(
            _text(value, "evidence_coverage_state")
        ),
        research_stop_decision=ResearchStopDecision(
            _text(value, "research_stop_decision")
        ),
        unmet_requirements=_text_tuple(value, "unmet_requirements"),
        active_remainders=tuple(
            _decode_remainder(item)
            for item in _mapping_tuple(value, "active_remainders")
        ),
        created_at=_text(value, "created_at"),
        promotion_authority=False,
    )


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


def _mapping_tuple(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, list) or any(
        not isinstance(item, Mapping) for item in raw
    ):
        raise TypeError(f"{key} must contain objects")
    return tuple(raw)


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
