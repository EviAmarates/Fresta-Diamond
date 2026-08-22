"""Claim-mode-aware epistemic evidence contracts and validation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from fresta_diamond.contracts import (
    Artifact,
    ExecutionResult,
    ExecutionState,
    Remainder,
    RemainderKind,
)


EPISTEMIC_EVIDENCE_SCHEMA = "artifact://epistemic-evidence-graph@1"


class ClaimMode(str, Enum):
    OBSERVATION = "OBSERVATION"
    ATTESTATION = "ATTESTATION"
    DERIVATION = "DERIVATION"
    HYPOTHESIS = "HYPOTHESIS"
    FORECAST = "FORECAST"
    INVARIANT = "INVARIANT"


_CLAIM_MODE_MEANINGS = {
    ClaimMode.OBSERVATION: (
        "A direct observation event exists in the current intake; a document "
        "report is not direct observation."
    ),
    ClaimMode.ATTESTATION: (
        "A bounded source reports the claim; this records what the source says, "
        "not that the claim is independently true."
    ),
    ClaimMode.DERIVATION: (
        "The claim follows through explicit premise references, applied "
        "constraints, direction, and premise evidence."
    ),
    ClaimMode.HYPOTHESIS: (
        "A testable possibility is proposed without being established; a "
        "falsifier or test criterion is required."
    ),
    ClaimMode.FORECAST: (
        "A future-resolving claim has an explicit horizon and assumptions."
    ),
    ClaimMode.INVARIANT: (
        "A claimed cross-context invariant has an explicit counterexample "
        "search and at least two independent supporting lineages."
    ),
}

if set(_CLAIM_MODE_MEANINGS) != set(ClaimMode):
    raise RuntimeError("Claim-mode classification catalog is incomplete")


def claim_mode_classification_catalog(
    *,
    available_modes: Sequence[ClaimMode] | None = None,
    include_defer: bool = True,
) -> tuple[Mapping[str, Any], ...]:
    """Return kernel-owned labels while leaving model analysis unrestricted."""

    available = set(available_modes if available_modes is not None else ClaimMode)
    catalog: list[Mapping[str, Any]] = [
        {
            "classification_id": mode.value,
            "kernel_mode": mode.value,
            "meaning": _CLAIM_MODE_MEANINGS[mode],
            "available_in_this_intake": mode in available,
        }
        for mode in ClaimMode
    ]
    if include_defer:
        catalog.append({
            "classification_id": "DEFER",
            "kernel_mode": None,
            "meaning": (
                "No available kernel mode is justified by the supplied evidence; "
                "preserve the candidate as unresolved."
            ),
            "available_in_this_intake": True,
        })
    return tuple(catalog)


class EvidenceKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    ATTESTATION = "ATTESTATION"
    PREMISE = "PREMISE"
    TEST_RESULT = "TEST_RESULT"
    COUNTEREXAMPLE_SEARCH = "COUNTEREXAMPLE_SEARCH"


class EvidenceStance(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


@dataclass(frozen=True)
class EvidenceEvent:
    evidence_id: str
    claim_id: str
    evidence_kind: EvidenceKind
    stance: EvidenceStance
    source_actor: str
    source_locator: str
    source_lineage: str
    context_id: str
    method: str
    observed_at: str
    scope: str


@dataclass(frozen=True)
class EpistemicClaim:
    claim_id: str
    content: str
    subject_ref: str
    owner_ref: str
    scope: str
    claim_mode: ClaimMode
    evidence_ids: tuple[str, ...]
    premise_refs: tuple[str, ...] = ()
    applied_constraints: tuple[str, ...] = ()
    derivation_direction: str | None = None
    test_criterion: str | None = None
    horizon: str | None = None
    assumptions: tuple[str, ...] = ()
    counterexample_searches: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpistemicEvidenceGraph:
    analysis_id: str
    object_ref: str
    scope: str
    claims: tuple[EpistemicClaim, ...]
    evidence_events: tuple[EvidenceEvent, ...]


@dataclass(frozen=True)
class ClaimBurdenReport:
    claim_id: str
    claim_mode: ClaimMode
    burden_satisfied: bool
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    active_remainders: tuple[Remainder, ...]


@dataclass(frozen=True)
class EpistemicValidationReport:
    analysis_id: str
    object_ref: str
    epistemic_closed: bool
    claim_reports: tuple[ClaimBurdenReport, ...]
    active_remainders: tuple[Remainder, ...]
    used_evidence: tuple[str, ...]


@dataclass(frozen=True)
class EpistemicEvaluation:
    execution: ExecutionResult
    reports: tuple[EpistemicValidationReport, ...]


class EpistemicEvidenceDecodeError(ValueError):
    """Raised when a provider payload violates the epistemic schema."""


class EpistemicValidator:
    """Apply deterministic minimum burdens without deciding semantic truth."""

    def validate(self, graph: EpistemicEvidenceGraph) -> EpistemicValidationReport:
        graph_remainders: list[Remainder] = []
        claims = self._index(
            graph.claims, "claim_id", "claim", graph_remainders
        )
        evidence = self._index(
            graph.evidence_events, "evidence_id", "evidence", graph_remainders
        )
        if not claims:
            graph_remainders.append(self._missing(
                "Epistemic analysis requires at least one claim",
                graph.analysis_id,
            ))

        events_by_claim: dict[str, list[EvidenceEvent]] = {
            claim_id: [] for claim_id in claims
        }
        for event in evidence.values():
            if event.scope != graph.scope:
                graph_remainders.append(self._scope(
                    "Evidence event lies outside the analysis scope",
                    event.evidence_id,
                ))
            if event.claim_id not in claims:
                graph_remainders.append(self._missing(
                    "Evidence event references an unknown claim",
                    event.evidence_id,
                ))
                continue
            events_by_claim[event.claim_id].append(event)

        used_evidence: set[str] = set()
        claim_reports: list[ClaimBurdenReport] = []
        for claim in claims.values():
            local: list[Remainder] = []
            if claim.scope != graph.scope:
                local.append(self._scope(
                    "Claim lies outside the analysis scope", claim.claim_id
                ))

            declared_events: list[EvidenceEvent] = []
            for evidence_id in claim.evidence_ids:
                event = evidence.get(evidence_id)
                if event is None:
                    local.append(self._missing(
                        "Claim references unknown evidence", claim.claim_id
                    ))
                elif event.claim_id != claim.claim_id:
                    local.append(Remainder(
                        kind=RemainderKind.CONTRADICTION,
                        description="Claim references evidence assigned to another claim",
                        required_for=claim.claim_id,
                        resolvable=True,
                    ))
                else:
                    declared_events.append(event)
                    used_evidence.add(event.evidence_id)

            undeclared = {
                item.evidence_id for item in events_by_claim.get(claim.claim_id, ())
            } - set(claim.evidence_ids)
            for evidence_id in sorted(undeclared):
                local.append(Remainder(
                    kind=RemainderKind.UNUSED_EVIDENCE,
                    description="Evidence assigned to a claim is not used by that claim",
                    required_for=evidence_id,
                    resolvable=True,
                ))

            supporting = tuple(
                item for item in declared_events
                if item.stance is EvidenceStance.SUPPORTS
            )
            contradicting = tuple(
                item for item in declared_events
                if item.stance is EvidenceStance.CONTRADICTS
            )
            if not supporting:
                local.append(self._missing(
                    "Claim has no supporting evidence", claim.claim_id
                ))
            if contradicting:
                local.append(Remainder(
                    kind=RemainderKind.CONTRADICTION,
                    description="Live counterevidence prevents epistemic closure",
                    required_for=claim.claim_id,
                    resolvable=True,
                ))

            self._apply_mode_burden(claim, supporting, local)
            claim_reports.append(ClaimBurdenReport(
                claim_id=claim.claim_id,
                claim_mode=claim.claim_mode,
                burden_satisfied=not local,
                supporting_evidence=tuple(
                    item.evidence_id for item in supporting
                ),
                contradicting_evidence=tuple(
                    item.evidence_id for item in contradicting
                ),
                active_remainders=tuple(local),
            ))
            graph_remainders.extend(local)

        for evidence_id in sorted(set(evidence) - used_evidence):
            if not any(
                remainder.required_for == evidence_id
                and remainder.kind is RemainderKind.UNUSED_EVIDENCE
                for remainder in graph_remainders
            ):
                graph_remainders.append(Remainder(
                    kind=RemainderKind.UNUSED_EVIDENCE,
                    description="Selected evidence does not support a declared claim",
                    required_for=evidence_id,
                    resolvable=True,
                ))

        return EpistemicValidationReport(
            analysis_id=graph.analysis_id,
            object_ref=graph.object_ref,
            epistemic_closed=bool(claim_reports) and not graph_remainders,
            claim_reports=tuple(claim_reports),
            active_remainders=tuple(graph_remainders),
            used_evidence=tuple(sorted(used_evidence)),
        )

    def _apply_mode_burden(
        self,
        claim: EpistemicClaim,
        supporting: tuple[EvidenceEvent, ...],
        problems: list[Remainder],
    ) -> None:
        kinds = {item.evidence_kind for item in supporting}
        if claim.claim_mode is ClaimMode.OBSERVATION:
            if EvidenceKind.OBSERVATION not in kinds:
                problems.append(self._missing(
                    "OBSERVATION requires a direct observation event",
                    claim.claim_id,
                ))
        elif claim.claim_mode is ClaimMode.ATTESTATION:
            if EvidenceKind.ATTESTATION not in kinds:
                problems.append(self._missing(
                    "ATTESTATION requires a source report event",
                    claim.claim_id,
                ))
        elif claim.claim_mode is ClaimMode.DERIVATION:
            if not claim.premise_refs:
                problems.append(self._missing(
                    "DERIVATION requires premise references", claim.claim_id
                ))
            if not claim.applied_constraints:
                problems.append(self._missing(
                    "DERIVATION requires applied constraints", claim.claim_id
                ))
            if not (claim.derivation_direction or "").strip():
                problems.append(self._missing(
                    "DERIVATION requires an auditable direction", claim.claim_id
                ))
            if EvidenceKind.PREMISE not in kinds:
                problems.append(self._missing(
                    "DERIVATION requires premise evidence", claim.claim_id
                ))
        elif claim.claim_mode is ClaimMode.HYPOTHESIS:
            if not (claim.test_criterion or "").strip():
                problems.append(self._missing(
                    "HYPOTHESIS requires a falsifier or test criterion",
                    claim.claim_id,
                ))
        elif claim.claim_mode is ClaimMode.FORECAST:
            if not (claim.horizon or "").strip():
                problems.append(self._missing(
                    "FORECAST requires a resolution horizon", claim.claim_id
                ))
            if not claim.assumptions:
                problems.append(self._missing(
                    "FORECAST requires explicit assumptions", claim.claim_id
                ))
        elif claim.claim_mode is ClaimMode.INVARIANT:
            if not claim.counterexample_searches:
                problems.append(self._missing(
                    "INVARIANT requires an explicit counterexample search",
                    claim.claim_id,
                ))
            lineages = {item.source_lineage for item in supporting}
            if len(lineages) < 2:
                problems.append(self._missing(
                    "INVARIANT requires at least two independent supporting lineages",
                    claim.claim_id,
                ))

    @staticmethod
    def _index(records, field_name, label, problems):
        indexed = {}
        for record in records:
            identifier = getattr(record, field_name)
            if not identifier.strip():
                problems.append(EpistemicValidator._missing(
                    f"{label.title()} ID is required", label
                ))
                continue
            if identifier in indexed:
                problems.append(Remainder(
                    kind=RemainderKind.CONTRADICTION,
                    description=f"Duplicate {label} ID: {identifier}",
                    required_for=identifier,
                    resolvable=True,
                ))
                continue
            indexed[identifier] = record
        return indexed

    @staticmethod
    def _missing(description: str, required_for: str) -> Remainder:
        return Remainder(
            kind=RemainderKind.MISSING_EVIDENCE,
            description=description,
            required_for=required_for,
            resolvable=True,
        )

    @staticmethod
    def _scope(description: str, required_for: str) -> Remainder:
        return Remainder(
            kind=RemainderKind.INVALID_SCOPE,
            description=description,
            required_for=required_for,
            resolvable=True,
        )


class EpistemicEvaluator:
    """Decode claim evidence artifacts and update only epistemic closure."""

    def __init__(self, validator: EpistemicValidator | None = None) -> None:
        self._validator = validator or EpistemicValidator()

    def evaluate(self, execution: ExecutionResult) -> EpistemicEvaluation:
        if execution.state is not ExecutionState.COMPLETED:
            return EpistemicEvaluation(execution=execution, reports=())

        candidates = tuple(
            artifact for artifact in execution.artifacts.values()
            if artifact.schema == EPISTEMIC_EVIDENCE_SCHEMA
        )
        if not candidates:
            return EpistemicEvaluation(execution=execution, reports=())

        reports: list[EpistemicValidationReport] = []
        problems: list[Remainder] = []
        for artifact in candidates:
            try:
                graph = decode_epistemic_evidence_graph(artifact.payload)
            except EpistemicEvidenceDecodeError as exc:
                problems.append(Remainder(
                    kind=RemainderKind.MISSING_EVIDENCE,
                    description=f"Malformed epistemic evidence artifact: {exc}",
                    required_for=artifact.artifact_id,
                    resolvable=True,
                ))
                continue
            report = self._validator.validate(graph)
            reports.append(report)
            problems.extend(report.active_remainders)

        epistemic_closed = (
            bool(reports)
            and len(reports) == len(candidates)
            and all(report.epistemic_closed for report in reports)
        )
        closure = replace(
            execution.closure,
            epistemic_closed=epistemic_closed,
            active_remainders=execution.closure.active_remainders + tuple(problems),
        )
        evaluated = replace(
            execution,
            closure=closure,
            remainders=execution.remainders + tuple(problems),
        )
        return EpistemicEvaluation(execution=evaluated, reports=tuple(reports))


def encode_epistemic_evidence_graph(
    graph: EpistemicEvidenceGraph,
) -> Mapping[str, Any]:
    return {
        "analysis_id": graph.analysis_id,
        "object_ref": graph.object_ref,
        "scope": graph.scope,
        "claims": [
            {
                "claim_id": item.claim_id,
                "content": item.content,
                "subject_ref": item.subject_ref,
                "owner_ref": item.owner_ref,
                "scope": item.scope,
                "claim_mode": item.claim_mode.value,
                "evidence_ids": list(item.evidence_ids),
                "premise_refs": list(item.premise_refs),
                "applied_constraints": list(item.applied_constraints),
                "derivation_direction": item.derivation_direction,
                "test_criterion": item.test_criterion,
                "horizon": item.horizon,
                "assumptions": list(item.assumptions),
                "counterexample_searches": list(item.counterexample_searches),
            }
            for item in graph.claims
        ],
        "evidence_events": [
            {
                "evidence_id": item.evidence_id,
                "claim_id": item.claim_id,
                "evidence_kind": item.evidence_kind.value,
                "stance": item.stance.value,
                "source_actor": item.source_actor,
                "source_locator": item.source_locator,
                "source_lineage": item.source_lineage,
                "context_id": item.context_id,
                "method": item.method,
                "observed_at": item.observed_at,
                "scope": item.scope,
            }
            for item in graph.evidence_events
        ],
    }


def decode_epistemic_evidence_graph(
    payload: Mapping[str, Any],
) -> EpistemicEvidenceGraph:
    root = _require_mapping(payload, "graph")
    try:
        return EpistemicEvidenceGraph(
            analysis_id=_required_text(root, "analysis_id"),
            object_ref=_required_text(root, "object_ref"),
            scope=_required_text(root, "scope"),
            claims=tuple(
                EpistemicClaim(
                    claim_id=_required_text(item, "claim_id"),
                    content=_required_text(item, "content"),
                    subject_ref=_required_text(item, "subject_ref"),
                    owner_ref=_required_text(item, "owner_ref"),
                    scope=_required_text(item, "scope"),
                    claim_mode=ClaimMode(_required_text(item, "claim_mode")),
                    evidence_ids=_text_tuple(item, "evidence_ids"),
                    premise_refs=_text_tuple(item, "premise_refs", required=False),
                    applied_constraints=_text_tuple(
                        item, "applied_constraints", required=False
                    ),
                    derivation_direction=_optional_text(
                        item, "derivation_direction"
                    ),
                    test_criterion=_optional_text(item, "test_criterion"),
                    horizon=_optional_text(item, "horizon"),
                    assumptions=_text_tuple(item, "assumptions", required=False),
                    counterexample_searches=_text_tuple(
                        item, "counterexample_searches", required=False
                    ),
                )
                for item in _mapping_sequence(root, "claims")
            ),
            evidence_events=tuple(
                EvidenceEvent(
                    evidence_id=_required_text(item, "evidence_id"),
                    claim_id=_required_text(item, "claim_id"),
                    evidence_kind=EvidenceKind(
                        _required_text(item, "evidence_kind")
                    ),
                    stance=EvidenceStance(_required_text(item, "stance")),
                    source_actor=_required_text(item, "source_actor"),
                    source_locator=_required_text(item, "source_locator"),
                    source_lineage=_required_text(item, "source_lineage"),
                    context_id=_required_text(item, "context_id"),
                    method=_required_text(item, "method"),
                    observed_at=_required_text(item, "observed_at"),
                    scope=_required_text(item, "scope"),
                )
                for item in _mapping_sequence(root, "evidence_events")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, EpistemicEvidenceDecodeError):
            raise
        raise EpistemicEvidenceDecodeError(str(exc)) from exc


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EpistemicEvidenceDecodeError(f"{label} must be an object")
    return value


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EpistemicEvidenceDecodeError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise EpistemicEvidenceDecodeError(f"{key} must be non-empty text or null")
    return item


def _mapping_sequence(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    items = value.get(key)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise EpistemicEvidenceDecodeError(f"{key} must be an array")
    return tuple(_require_mapping(item, key) for item in items)


def _text_tuple(
    value: Mapping[str, Any],
    key: str,
    *,
    required: bool = True,
) -> tuple[str, ...]:
    items = value.get(key, () if not required else None)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise EpistemicEvidenceDecodeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise EpistemicEvidenceDecodeError(f"{key} must contain non-empty text")
    return tuple(items)
