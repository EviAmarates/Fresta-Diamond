"""Deterministic structural validation for the Diamond ontological boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
from typing import Any, Mapping, Sequence
import unicodedata

from fresta_diamond.contracts import (
    ExecutionResult,
    ExecutionState,
    Remainder,
    RemainderKind,
)
from fresta_diamond.constitutional_firewall import nominate_constitutional_risks


STRUCTURAL_EVIDENCE_SCHEMA = "artifact://structural-evidence-graph@1"


class ConstitutionalStage(str, Enum):
    """Computational equivalents of the constitutional dependency stages."""

    OPENNESS = "OPENNESS"
    FILTER = "FILTER"
    OBJECT = "OBJECT"


class AnalysisDepth(str, Enum):
    """How far the current bounded objective asks the analysis to ground itself."""

    CONTEXTUAL = "CONTEXTUAL"
    CONSTITUTIONAL = "CONSTITUTIONAL"


GROUNDING_DIRECTION = (
    ConstitutionalStage.OPENNESS,
    ConstitutionalStage.FILTER,
    ConstitutionalStage.OBJECT,
)
ANALYSIS_DIRECTION = tuple(reversed(GROUNDING_DIRECTION))


@dataclass(frozen=True)
class ManifestationEvidence:
    manifestation_id: str
    object_ref: str
    description: str
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class ConstraintEvidence:
    constraint_id: str
    description: str
    scope: str


@dataclass(frozen=True)
class ExcludedCostEvidence:
    cost_id: str
    description: str
    excluded_alternatives: tuple[str, ...]


@dataclass(frozen=True)
class StrongRelationEvidence:
    relation_id: str
    manifestation_id: str
    constraint_id: str
    forward_justification: str
    constraint_effect: str
    return_witness: str
    excluded_cost_id: str
    scope: str


@dataclass(frozen=True)
class FilterEvidence:
    """A contextual selection record, not the constitutional F operator itself."""

    filter_id: str
    constraint_id: str
    manifestation_id: str
    excluded_cost_id: str
    selection_justification: str


@dataclass(frozen=True)
class ConstitutionalGroundingEvidence:
    grounding_id: str
    filter_id: str
    grounding_direction: tuple[ConstitutionalStage, ...]
    analysis_direction: tuple[ConstitutionalStage, ...]
    openness_necessity: str


@dataclass(frozen=True)
class StructuralEvidenceGraph:
    analysis_id: str
    object_ref: str
    scope: str
    manifestations: tuple[ManifestationEvidence, ...]
    relations: tuple[StrongRelationEvidence, ...]
    constraints: tuple[ConstraintEvidence, ...]
    filters: tuple[FilterEvidence, ...]
    excluded_costs: tuple[ExcludedCostEvidence, ...]
    groundings: tuple[ConstitutionalGroundingEvidence, ...] = ()
    analysis_depth: AnalysisDepth = AnalysisDepth.CONTEXTUAL
    advisory_model_closed: bool | None = None


@dataclass(frozen=True)
class StructuralValidationReport:
    analysis_id: str
    object_ref: str
    reciprocal_structure_valid: bool
    constitutional_closed: bool | None
    structural_closed: bool
    active_remainders: tuple[Remainder, ...]
    used_manifestations: tuple[str, ...]
    used_relations: tuple[str, ...]
    used_constraints: tuple[str, ...]
    used_filters: tuple[str, ...]
    used_costs: tuple[str, ...]


@dataclass(frozen=True)
class OntologyEvaluation:
    execution: ExecutionResult
    reports: tuple[StructuralValidationReport, ...]


class EvidenceGraphDecodeError(ValueError):
    """Raised when a provider output is not the declared graph contract."""


class OntologicalValidator:
    """Validate a proposed witness graph without consulting an LLM verdict."""

    def validate(self, graph: StructuralEvidenceGraph) -> StructuralValidationReport:
        local: list[Remainder] = []
        constitutional: list[Remainder] = []

        if not graph.analysis_id.strip():
            local.append(self._missing("Analysis ID is required", "analysis"))
        if not graph.object_ref.strip():
            local.append(self._missing("A bounded object reference is required", "O1"))
        if not graph.scope.strip():
            local.append(self._missing("Analysis scope is required", "analysis"))

        manifestations = self._index(
            graph.manifestations, "manifestation_id", "manifestation", local
        )
        relations = self._index(graph.relations, "relation_id", "relation", local)
        constraints = self._index(
            graph.constraints, "constraint_id", "constraint", local
        )
        filters = self._index(graph.filters, "filter_id", "filter", local)
        costs = self._index(graph.excluded_costs, "cost_id", "excluded cost", local)
        groundings = self._index(
            graph.groundings, "grounding_id", "constitutional grounding", constitutional
        )

        self._require_nonempty(manifestations, "At least one O1 manifestation is required", "O1", local)
        self._require_nonempty(relations, "At least one strong O2 relation is required", "O2", local)
        self._require_nonempty(constraints, "At least one O3 constraint is required", "O3", local)
        self._require_nonempty(filters, "At least one FILTER record is required", "FILTER", local)
        self._require_nonempty(costs, "At least one excluded cost is required", "COST", local)
        if graph.analysis_depth is AnalysisDepth.CONSTITUTIONAL:
            self._require_nonempty(
                groundings,
                "Constitutional analysis requires a grounding path",
                "constitutional-closure",
                constitutional,
            )

        used_manifestations: set[str] = set()
        used_relations: set[str] = set()
        used_constraints: set[str] = set()
        used_filters: set[str] = set()
        used_costs: set[str] = set()

        for manifestation in manifestations.values():
            if not manifestation.description.strip() or not manifestation.provenance:
                local.append(self._missing(
                    "O1 requires concrete content and auditable provenance",
                    manifestation.manifestation_id,
                ))
            if manifestation.object_ref != graph.object_ref:
                local.append(self._scope(
                    "O1 object reference does not match the analyzed object",
                    manifestation.manifestation_id,
                ))

        for constraint in constraints.values():
            if not constraint.description.strip():
                local.append(self._missing(
                    "O3 constraint description is empty", constraint.constraint_id
                ))
            if constraint.scope != graph.scope:
                local.append(self._scope(
                    "O3 constraint lies outside the analysis scope",
                    constraint.constraint_id,
                ))

        for cost in costs.values():
            if not cost.description.strip() or not cost.excluded_alternatives:
                local.append(self._missing(
                    "Excluded cost requires a description and at least one alternative",
                    cost.cost_id,
                ))

        for relation in relations.values():
            manifestation = manifestations.get(relation.manifestation_id)
            constraint = constraints.get(relation.constraint_id)
            cost = costs.get(relation.excluded_cost_id)
            if manifestation is None:
                local.append(self._missing(
                    "Strong O2 references an unknown O1 manifestation",
                    relation.relation_id,
                ))
            if constraint is None:
                local.append(self._missing(
                    "Strong O2 references an unknown O3 constraint",
                    relation.relation_id,
                ))
            if cost is None:
                local.append(self._missing(
                    "Strong O2 references an unknown excluded cost",
                    relation.relation_id,
                ))
            if relation.manifestation_id == relation.constraint_id:
                local.append(Remainder(
                    kind=RemainderKind.CONTRADICTION,
                    description="Reusing one ID as O1 and O3 is not reciprocity",
                    required_for=relation.relation_id,
                    resolvable=True,
                ))
            if not all((
                relation.forward_justification.strip(),
                relation.constraint_effect.strip(),
                relation.return_witness.strip(),
            )):
                local.append(self._missing(
                    "Strong O2 requires forward justification, constraint effect, "
                    "and return witness",
                    relation.relation_id,
                ))
            if relation.scope != graph.scope:
                local.append(self._scope(
                    "Strong O2 lies outside the analysis scope", relation.relation_id
                ))

            matching_filters = [
                item for item in filters.values()
                if item.constraint_id == relation.constraint_id
                and item.manifestation_id == relation.manifestation_id
                and item.excluded_cost_id == relation.excluded_cost_id
            ]
            if not matching_filters:
                local.append(self._missing(
                    "Strong O2 has no FILTER connecting its O1, O3, and excluded cost",
                    relation.relation_id,
                ))
            else:
                used_filters.update(item.filter_id for item in matching_filters)

            if manifestation is not None:
                used_manifestations.add(manifestation.manifestation_id)
            if constraint is not None:
                used_constraints.add(constraint.constraint_id)
            if cost is not None:
                used_costs.add(cost.cost_id)
            used_relations.add(relation.relation_id)

        for filter_evidence in filters.values():
            if not filter_evidence.selection_justification.strip():
                local.append(self._missing(
                    "FILTER selection justification is empty",
                    filter_evidence.filter_id,
                ))
            if filter_evidence.manifestation_id not in manifestations:
                local.append(self._missing(
                    "FILTER references an unknown O1 manifestation",
                    filter_evidence.filter_id,
                ))
            if filter_evidence.constraint_id not in constraints:
                local.append(self._missing(
                    "FILTER references an unknown O3 constraint",
                    filter_evidence.filter_id,
                ))
            if filter_evidence.excluded_cost_id not in costs:
                local.append(self._missing(
                    "FILTER references an unknown excluded cost",
                    filter_evidence.filter_id,
                ))

        grounded_filters: set[str] = set()
        for grounding in groundings.values():
            if grounding.filter_id not in filters:
                constitutional.append(self._missing(
                    "Constitutional path references an unknown FILTER",
                    grounding.grounding_id,
                ))
            else:
                grounded_filters.add(grounding.filter_id)
            if grounding.grounding_direction != GROUNDING_DIRECTION:
                constitutional.append(self._direction(
                    "Grounding must preserve OPENNESS -> FILTER -> OBJECT",
                    grounding.grounding_id,
                ))
            if grounding.analysis_direction != ANALYSIS_DIRECTION:
                constitutional.append(self._direction(
                    "Analysis must recognize OBJECT -> FILTER -> OPENNESS",
                    grounding.grounding_id,
                ))
            if not grounding.openness_necessity.strip():
                constitutional.append(self._missing(
                    "Grounding must state why FILTER requires irreducible openness",
                    grounding.grounding_id,
                ))

        if graph.analysis_depth is AnalysisDepth.CONSTITUTIONAL or groundings:
            for filter_id in used_filters:
                if filter_id not in grounded_filters:
                    constitutional.append(self._missing(
                        "A constitutive FILTER has no continuous route to OPENNESS",
                        filter_id,
                    ))

        self._append_unused(manifestations, used_manifestations, "O1 manifestation", local)
        self._append_unused(relations, used_relations, "O2 relation", local)
        self._append_unused(constraints, used_constraints, "O3 constraint", local)
        self._append_unused(filters, used_filters, "FILTER", local)
        self._append_unused(costs, used_costs, "excluded cost", local)

        reciprocal_valid = not local
        if not groundings and graph.analysis_depth is AnalysisDepth.CONTEXTUAL:
            constitutional_closed = None
        else:
            constitutional_closed = (
                reciprocal_valid and not constitutional and bool(groundings)
            )
        structural_closed = reciprocal_valid
        remainders = tuple(local + constitutional)

        return StructuralValidationReport(
            analysis_id=graph.analysis_id,
            object_ref=graph.object_ref,
            reciprocal_structure_valid=reciprocal_valid,
            constitutional_closed=constitutional_closed,
            structural_closed=structural_closed,
            active_remainders=remainders,
            used_manifestations=tuple(sorted(used_manifestations)),
            used_relations=tuple(sorted(used_relations)),
            used_constraints=tuple(sorted(used_constraints)),
            used_filters=tuple(sorted(used_filters)),
            used_costs=tuple(sorted(used_costs)),
        )

    @staticmethod
    def _index(records, field_name, label, problems):
        indexed = {}
        for record in records:
            identifier = getattr(record, field_name)
            if not identifier.strip():
                problems.append(OntologicalValidator._missing(
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
    def _require_nonempty(records, description, required_for, problems):
        if not records:
            problems.append(OntologicalValidator._missing(description, required_for))

    @staticmethod
    def _append_unused(records, used: set[str], label: str, problems: list[Remainder]) -> None:
        for identifier in sorted(set(records) - used):
            problems.append(Remainder(
                kind=RemainderKind.UNUSED_EVIDENCE,
                description=f"Selected {label} does not participate in the closure graph",
                required_for=identifier,
                resolvable=True,
            ))

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

    @staticmethod
    def _direction(description: str, required_for: str) -> Remainder:
        return Remainder(
            kind=RemainderKind.INVALID_DIRECTION,
            description=description,
            required_for=required_for,
            resolvable=True,
        )


class OntologyEvaluator:
    """Decode and validate typed evidence artifacts after technical execution."""

    def __init__(self, validator: OntologicalValidator | None = None) -> None:
        self._validator = validator or OntologicalValidator()

    def evaluate(self, execution: ExecutionResult) -> OntologyEvaluation:
        if execution.state is not ExecutionState.COMPLETED:
            return OntologyEvaluation(execution=execution, reports=())

        candidates = tuple(
            artifact for artifact in execution.artifacts.values()
            if artifact.schema == STRUCTURAL_EVIDENCE_SCHEMA
        )
        if not candidates:
            return OntologyEvaluation(execution=execution, reports=())

        reports: list[StructuralValidationReport] = []
        problems: list[Remainder] = []
        for artifact in candidates:
            try:
                graph = decode_structural_evidence_graph(artifact.payload)
            except EvidenceGraphDecodeError as exc:
                problems.append(Remainder(
                    kind=RemainderKind.MISSING_EVIDENCE,
                    description=f"Malformed structural evidence artifact: {exc}",
                    required_for=artifact.artifact_id,
                    resolvable=True,
                ))
                continue
            report = self._validator.validate(graph)
            attribution_remainders = _validate_source_attribution(
                artifact.payload,
                graph,
            )
            if attribution_remainders:
                report = replace(
                    report,
                    reciprocal_structure_valid=False,
                    structural_closed=False,
                    constitutional_closed=(
                        False
                        if report.constitutional_closed is not None
                        else None
                    ),
                    active_remainders=(
                        report.active_remainders + attribution_remainders
                    ),
                )
            reports.append(report)
            problems.extend(report.active_remainders)

        structural_closed = (
            bool(reports)
            and len(reports) == len(candidates)
            and all(report.structural_closed for report in reports)
        )
        constitutional_verdicts = tuple(
            report.constitutional_closed for report in reports
        )
        if problems and len(reports) != len(candidates):
            constitutional_closed: bool | None = False
        elif any(verdict is False for verdict in constitutional_verdicts):
            constitutional_closed = False
        elif constitutional_verdicts and all(
            verdict is True for verdict in constitutional_verdicts
        ):
            constitutional_closed = True
        else:
            constitutional_closed = None
        closure = replace(
            execution.closure,
            structural_closed=structural_closed,
            constitutional_closed=constitutional_closed,
            active_remainders=execution.closure.active_remainders + tuple(problems),
        )
        evaluated = replace(
            execution,
            closure=closure,
            remainders=execution.remainders + tuple(problems),
        )
        return OntologyEvaluation(execution=evaluated, reports=tuple(reports))


_SOURCE_ATTRIBUTION = re.compile(
    r"\b(?:source|document|text|statement|passage|artifact|claim|request|"
    r"fonte|documento|texto|afirmacao|afirma|pedido|instrucao|conteudo)\b"
)
_AUTHORITY_LIMIT = re.compile(
    r"\b(?:has|carries|receives?|tem|carrega|recebe)\b.{0,24}"
    r"\b(?:no|zero|nenhuma|sem)\b.{0,16}\b(?:authority|autoridade)\b|"
    r"\b(?:cannot|must not|does not|do not|nao pode|nao deve|nao tem)\b"
    r".{0,72}\b(?:authority|validation|promotion|bypass|autoridade|validacao|"
    r"promocao|contorno)\b|"
    r"\b(?:unsupported|unvalidated|unverified|nao corroborad[ao]|nao valid[ao])\b"
    r".{0,60}\b(?:authority|claim|source|content|autoridade|afirmacao|fonte|conteudo)\b|"
    r"\b(?:no|without|sem)\b.{0,24}\b(?:corroboration|evidence|corroboracao|evidencia)\b|"
    r"\b(?:excluded|rejected|quarantined|recusad[ao]|excluid[ao])\b"
    r".{0,40}\b(?:validated memory|promotion|authority|memoria validada|promocao|autoridade)\b"
)


def _validate_source_attribution(
    payload: Mapping[str, Any],
    graph: StructuralEvidenceGraph,
) -> tuple[Remainder, ...]:
    """Prevent a risky source claim from becoming an unattributed relation."""

    attestation = payload.get("_source_risk_attestation")
    if attestation is None:
        return ()
    if not isinstance(attestation, Mapping) or (
        attestation.get("handling") != "ATTRIBUTED_SOURCE_CLAIM_REQUIRED"
    ):
        return (Remainder(
            kind=RemainderKind.POLICY_VIOLATION,
            description="Source-risk attestation is malformed or lost",
            required_for=graph.analysis_id,
            resolvable=True,
        ),)

    problems: list[Remainder] = []
    manifestations = " ".join(
        item.description for item in graph.manifestations
    )
    if _SOURCE_ATTRIBUTION.search(_normalized(manifestations)) is None:
        problems.append(Remainder(
            kind=RemainderKind.POLICY_VIOLATION,
            description=(
                "Risk-bearing source content must remain explicitly attributed "
                "to its source in O1"
            ),
            required_for=graph.analysis_id,
            resolvable=True,
        ))

    relational_text = " ".join((
        *(value for item in graph.relations for value in (
            item.forward_justification,
            item.constraint_effect,
            item.return_witness,
        )),
        *(item.description for item in graph.constraints),
        *(item.selection_justification for item in graph.filters),
        *(item.description for item in graph.excluded_costs),
        *(value for item in graph.excluded_costs for value in item.excluded_alternatives),
    ))
    laundered = nominate_constitutional_risks(relational_text)
    if laundered.activated:
        problems.append(Remainder(
            kind=RemainderKind.POLICY_VIOLATION,
            description=(
                "A risky source instruction reappeared as an operational O2/O3 "
                "claim instead of attributed evidence"
            ),
            required_for=graph.analysis_id,
            resolvable=True,
        ))
    if _AUTHORITY_LIMIT.search(_normalized(relational_text)) is None:
        problems.append(Remainder(
            kind=RemainderKind.MISSING_EVIDENCE,
            description=(
                "Risk-bearing source analysis lacks an explicit authority or "
                "validation limitation"
            ),
            required_for=graph.analysis_id,
            resolvable=True,
        ))
    return tuple(problems)


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


def encode_structural_evidence_graph(
    graph: StructuralEvidenceGraph,
) -> Mapping[str, Any]:
    """Encode a graph into the JSON-shaped artifact contract."""
    return {
        "analysis_id": graph.analysis_id,
        "object_ref": graph.object_ref,
        "scope": graph.scope,
        "manifestations": [
            {
                "manifestation_id": item.manifestation_id,
                "object_ref": item.object_ref,
                "description": item.description,
                "provenance": list(item.provenance),
            }
            for item in graph.manifestations
        ],
        "relations": [
            {
                "relation_id": item.relation_id,
                "manifestation_id": item.manifestation_id,
                "constraint_id": item.constraint_id,
                "forward_justification": item.forward_justification,
                "constraint_effect": item.constraint_effect,
                "return_witness": item.return_witness,
                "excluded_cost_id": item.excluded_cost_id,
                "scope": item.scope,
            }
            for item in graph.relations
        ],
        "constraints": [
            {
                "constraint_id": item.constraint_id,
                "description": item.description,
                "scope": item.scope,
            }
            for item in graph.constraints
        ],
        "filters": [
            {
                "filter_id": item.filter_id,
                "constraint_id": item.constraint_id,
                "manifestation_id": item.manifestation_id,
                "excluded_cost_id": item.excluded_cost_id,
                "selection_justification": item.selection_justification,
            }
            for item in graph.filters
        ],
        "excluded_costs": [
            {
                "cost_id": item.cost_id,
                "description": item.description,
                "excluded_alternatives": list(item.excluded_alternatives),
            }
            for item in graph.excluded_costs
        ],
        "groundings": [
            {
                "grounding_id": item.grounding_id,
                "filter_id": item.filter_id,
                "grounding_direction": [
                    stage.value for stage in item.grounding_direction
                ],
                "analysis_direction": [
                    stage.value for stage in item.analysis_direction
                ],
                "openness_necessity": item.openness_necessity,
            }
            for item in graph.groundings
        ],
        "analysis_depth": graph.analysis_depth.value,
        "advisory_model_closed": graph.advisory_model_closed,
    }


def decode_structural_evidence_graph(
    payload: Mapping[str, Any],
) -> StructuralEvidenceGraph:
    """Strictly decode the JSON-shaped provider boundary."""
    root = _require_mapping(payload, "graph")
    try:
        advisory = root.get("advisory_model_closed")
        if advisory is not None and not isinstance(advisory, bool):
            raise EvidenceGraphDecodeError(
                "advisory_model_closed must be boolean or null"
            )
        return StructuralEvidenceGraph(
            analysis_id=_required_text(root, "analysis_id"),
            object_ref=_required_text(root, "object_ref"),
            scope=_required_text(root, "scope"),
            manifestations=tuple(
                ManifestationEvidence(
                    manifestation_id=_required_text(item, "manifestation_id"),
                    object_ref=_required_text(item, "object_ref"),
                    description=_required_text(item, "description"),
                    provenance=_text_tuple(item, "provenance"),
                )
                for item in _mapping_sequence(root, "manifestations")
            ),
            relations=tuple(
                StrongRelationEvidence(
                    relation_id=_required_text(item, "relation_id"),
                    manifestation_id=_required_text(item, "manifestation_id"),
                    constraint_id=_required_text(item, "constraint_id"),
                    forward_justification=_required_text(
                        item, "forward_justification"
                    ),
                    constraint_effect=_required_text(item, "constraint_effect"),
                    return_witness=_required_text(item, "return_witness"),
                    excluded_cost_id=_required_text(item, "excluded_cost_id"),
                    scope=_required_text(item, "scope"),
                )
                for item in _mapping_sequence(root, "relations")
            ),
            constraints=tuple(
                ConstraintEvidence(
                    constraint_id=_required_text(item, "constraint_id"),
                    description=_required_text(item, "description"),
                    scope=_required_text(item, "scope"),
                )
                for item in _mapping_sequence(root, "constraints")
            ),
            filters=tuple(
                FilterEvidence(
                    filter_id=_required_text(item, "filter_id"),
                    constraint_id=_required_text(item, "constraint_id"),
                    manifestation_id=_required_text(item, "manifestation_id"),
                    excluded_cost_id=_required_text(item, "excluded_cost_id"),
                    selection_justification=_required_text(
                        item, "selection_justification"
                    ),
                )
                for item in _mapping_sequence(root, "filters")
            ),
            excluded_costs=tuple(
                ExcludedCostEvidence(
                    cost_id=_required_text(item, "cost_id"),
                    description=_required_text(item, "description"),
                    excluded_alternatives=_text_tuple(
                        item, "excluded_alternatives"
                    ),
                )
                for item in _mapping_sequence(root, "excluded_costs")
            ),
            groundings=tuple(
                ConstitutionalGroundingEvidence(
                    grounding_id=_required_text(item, "grounding_id"),
                    filter_id=_required_text(item, "filter_id"),
                    grounding_direction=_stage_tuple(
                        item, "grounding_direction"
                    ),
                    analysis_direction=_stage_tuple(item, "analysis_direction"),
                    openness_necessity=_required_text(
                        item, "openness_necessity"
                    ),
                )
                for item in _mapping_sequence(root, "groundings")
            ),
            analysis_depth=AnalysisDepth(
                root.get("analysis_depth", AnalysisDepth.CONTEXTUAL.value)
            ),
            advisory_model_closed=advisory,
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, EvidenceGraphDecodeError):
            raise
        raise EvidenceGraphDecodeError(str(exc)) from exc


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceGraphDecodeError(f"{label} must be an object")
    return value


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EvidenceGraphDecodeError(f"{key} must be non-empty text")
    return item


def _mapping_sequence(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    items = value.get(key)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise EvidenceGraphDecodeError(f"{key} must be an array")
    return tuple(_require_mapping(item, key) for item in items)


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise EvidenceGraphDecodeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise EvidenceGraphDecodeError(f"{key} must contain non-empty text")
    return tuple(items)


def _stage_tuple(
    value: Mapping[str, Any], key: str
) -> tuple[ConstitutionalStage, ...]:
    try:
        return tuple(ConstitutionalStage(item) for item in _text_tuple(value, key))
    except ValueError as exc:
        raise EvidenceGraphDecodeError(f"{key} contains an unknown stage") from exc
