"""Deterministic convergence analysis over independently validated O1 objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from fresta_diamond.ontology import (
    AnalysisDepth,
    OntologicalValidator,
    StructuralEvidenceGraph,
)
from fresta_diamond.contracts import ProvenanceKind, classify_provenance


META_ANALYSIS_SCHEMA = "artifact://meta-analysis-report@1"


class MetaAnalysisState(str, Enum):
    COHERENT_CANDIDATE = "COHERENT_CANDIDATE"
    INCOMPLETE = "INCOMPLETE"
    CONTESTED = "CONTESTED"


class EpistemicState(str, Enum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    EXTERNAL_ONLY = "EXTERNAL_ONLY"
    MIXED_PROVENANCE = "MIXED_PROVENANCE"
    INSUFFICIENT_GROUNDING = "INSUFFICIENT_GROUNDING"
    CONTESTED = "CONTESTED"
    UNCLASSIFIED = "UNCLASSIFIED"


class RecoverabilityState(str, Enum):
    UNASSESSED = "UNASSESSED"
    RECOVERABLE = "RECOVERABLE"
    AT_RISK = "AT_RISK"
    RESIDUAL = "RESIDUAL"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class LensAssessment:
    state: RecoverabilityState
    signals: tuple[str, ...] = ()
    structural_witnesses: tuple[str, ...] = ()
    phi_open: bool = True

    def __post_init__(self) -> None:
        if not self.phi_open:
            raise PermissionError("Lens assessment cannot close Phi")
        if self.state is RecoverabilityState.RESIDUAL and not self.structural_witnesses:
            raise ValueError("Residual recoverability requires a structural witness")


@dataclass(frozen=True)
class ConvergenceEvidence:
    evidence_id: str
    analysis_ids: tuple[str, ...]
    shared_pattern: str
    o2_justification: str

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or len(self.analysis_ids) < 2:
            raise ValueError("Convergence evidence requires two analyses")
        if not self.shared_pattern.strip() or not self.o2_justification.strip():
            raise ValueError("Convergence evidence requires an explicit O2 basis")


@dataclass(frozen=True)
class InheritedConstraintEvidence:
    constraint_id: str
    analysis_ids: tuple[str, ...]
    persistence_effect: str

    def __post_init__(self) -> None:
        if not self.constraint_id.strip() or not self.analysis_ids:
            raise ValueError("Inherited constraint evidence requires a source analysis")
        if not self.persistence_effect.strip():
            raise ValueError("Inherited constraint evidence requires a persistence effect")


@dataclass(frozen=True)
class MetaAnalysisReport:
    meta_analysis_id: str
    objective: str
    constituent_analysis_ids: tuple[str, ...]
    convergence_evidence: tuple[ConvergenceEvidence, ...]
    inherited_constraints: tuple[InheritedConstraintEvidence, ...]
    state: MetaAnalysisState
    phi_anchored: bool
    remainders: tuple[str, ...] = ()
    phi_open: bool = True
    epistemic_state: EpistemicState = EpistemicState.UNCLASSIFIED
    epistemic_gaps: tuple[str, ...] = ()
    saturation_diagnostics: tuple[str, ...] = ()
    revalidation_diagnostics: tuple[str, ...] = ()
    lens_assessment: LensAssessment = LensAssessment(
        state=RecoverabilityState.UNASSESSED,
    )
    authority: str = "META_ANALYSIS_PROPOSAL_ONLY"
    schema: str = META_ANALYSIS_SCHEMA

    def __post_init__(self) -> None:
        if not self.meta_analysis_id.strip() or not self.objective.strip():
            raise ValueError("Meta-analysis identity and objective are required")
        if len(self.constituent_analysis_ids) < 2:
            raise ValueError("Meta-analysis requires at least two analyses")
        if not self.phi_open:
            raise PermissionError("Meta-analysis cannot close Phi")
        if self.state is MetaAnalysisState.COHERENT_CANDIDATE and not self.phi_anchored:
            raise ValueError("Meta-analysis must record its Phi condition of possibility")
        if self.authority != "META_ANALYSIS_PROPOSAL_ONLY":
            raise PermissionError("Meta-analysis cannot grant authority")


def analyze_meta_analysis(
    *,
    meta_analysis_id: str,
    objective: str,
    analyses: tuple[StructuralEvidenceGraph, ...],
    convergence_evidence: tuple[ConvergenceEvidence, ...],
    inherited_constraints: tuple[InheritedConstraintEvidence, ...],
    conflicts: tuple[str, ...] = (),
) -> MetaAnalysisReport:
    """Assess explicit convergence without inferring truth or social authority."""
    if len(analyses) < 2:
        raise ValueError("Meta-analysis requires at least two analyses")
    reports = tuple(OntologicalValidator().validate(item) for item in analyses)
    analysis_ids = tuple(item.analysis_id for item in analyses)
    remainders = [
        f"{report.analysis_id}: {item.description}"
        for report in reports
        for item in report.active_remainders
    ]
    if len(set(analysis_ids)) != len(analysis_ids):
        remainders.append("Meta-analysis contains duplicate constituent analysis IDs")
    lineages_by_analysis = tuple(
        {
            manifestation.source_lineage
            for manifestation in analysis.manifestations
            if manifestation.source_lineage
        }
        for analysis in analyses
    )
    if any(not lineages for lineages in lineages_by_analysis):
        remainders.append(
            "Meta-analysis requires an explicit source lineage for every analysis"
        )
    if not any(
        left and right and left.isdisjoint(right)
        for index, left in enumerate(lineages_by_analysis)
        for right in lineages_by_analysis[index + 1:]
    ):
        remainders.append(
            "Meta-analysis requires at least two analyses with explicitly "
            "independent source lineages"
        )
    phi_anchored = any(
        analysis.analysis_depth is AnalysisDepth.CONSTITUTIONAL
        and report.constitutional_closed is True
        for analysis, report in zip(analyses, reports)
    )
    if not phi_anchored:
        remainders.append(
            "Meta-analysis does not contain a valid O3 -> FILTER -> PHI anchor"
        )
    known = set(analysis_ids)
    for evidence in convergence_evidence:
        if len(set(evidence.analysis_ids)) < 2:
            remainders.append(
                f"{evidence.evidence_id}: O2 must relate two distinct constituent analyses"
            )
        if not set(evidence.analysis_ids).issubset(known):
            remainders.append(
                f"{evidence.evidence_id}: references an unknown constituent analysis"
            )
    known_constraints = {
        constraint.constraint_id
        for analysis in analyses
        for constraint in analysis.constraints
    }
    for constraint in inherited_constraints:
        if constraint.constraint_id not in known_constraints:
            remainders.append(
                f"{constraint.constraint_id}: inherited constraint is not grounded "
                "in a constituent O3"
            )
        if not any(
            analysis.analysis_depth is AnalysisDepth.CONSTITUTIONAL
            and report.constitutional_closed is True
            and constraint.constraint_id in {
                item.constraint_id for item in analysis.constraints
            }
            for analysis, report in zip(analyses, reports)
        ):
            remainders.append(
                f"{constraint.constraint_id}: inherited constraint has no valid "
                "O3 -> FILTER -> PHI anchor"
            )
        if not set(constraint.analysis_ids).issubset(known):
            remainders.append(
                f"{constraint.constraint_id}: references an unknown source analysis"
            )
    if not inherited_constraints:
        remainders.append("Meta-analysis has no inherited O3/F constraints")
    if not convergence_evidence:
        remainders.append("Meta-analysis has no explicit cross-analysis O2 evidence")
    if conflicts:
        remainders.extend(f"CONFLICT: {item}" for item in conflicts)

    if conflicts:
        state = MetaAnalysisState.CONTESTED
    elif remainders:
        state = MetaAnalysisState.INCOMPLETE
    else:
        state = MetaAnalysisState.COHERENT_CANDIDATE
    provenance_domains = {
        classify_provenance((provenance,)).value
        for analysis in analyses
        for manifestation in analysis.manifestations
        for provenance in manifestation.provenance
    }
    if conflicts:
        epistemic_state = EpistemicState.CONTESTED
    elif remainders:
        epistemic_state = EpistemicState.INSUFFICIENT_GROUNDING
    elif provenance_domains == {ProvenanceKind.INTERNAL.value}:
        epistemic_state = EpistemicState.INTERNAL_ONLY
    elif provenance_domains == {ProvenanceKind.EXTERNAL.value}:
        epistemic_state = EpistemicState.EXTERNAL_ONLY
    elif provenance_domains == {
        ProvenanceKind.INTERNAL.value, ProvenanceKind.EXTERNAL.value
    }:
        epistemic_state = EpistemicState.MIXED_PROVENANCE
    else:
        epistemic_state = EpistemicState.UNCLASSIFIED
    epistemic_gaps = tuple(_epistemic_gap(item) for item in remainders)
    if conflicts:
        lens_assessment = LensAssessment(
            state=RecoverabilityState.CONTESTED,
            signals=("CONFLICT_REQUIRES_REVALIDATION",),
        )
    elif remainders:
        lens_assessment = LensAssessment(
            state=RecoverabilityState.AT_RISK,
            signals=("ACTIVE_REMAINDERS_PRESENT",),
        )
    elif convergence_evidence:
        lens_assessment = LensAssessment(
            state=RecoverabilityState.RECOVERABLE,
            signals=("CONVERGENCE_PATH_VALIDATED",),
            structural_witnesses=("CURRENT_ANALYSIS_REMAINS_REINTEGRABLE",),
        )
    else:
        lens_assessment = LensAssessment(
            state=RecoverabilityState.UNASSESSED,
            signals=("NO_CONVERGENCE_PATH",),
        )
    saturation_diagnostics = (
        ("SATURATION_NOT_ASSESSABLE_WITHOUT_EXPLICIT_CONVERGENCE",)
        if not convergence_evidence
        else ("SATURATION_NOT_ESTABLISHED_BY_META_ANALYSIS_CONTRACT",)
    )
    if not any(
        left and right and left.isdisjoint(right)
        for index, left in enumerate(lineages_by_analysis)
        for right in lineages_by_analysis[index + 1:]
    ):
        saturation_diagnostics += ("SATURATION_BLOCKED_BY_SOURCE_LINEAGE",)
    revalidation_diagnostics = ("CONSTITUENT_ANALYSES_VALIDATED",)
    if conflicts:
        revalidation_diagnostics += ("CONFLICT_REQUIRES_REVALIDATION",)
    if any(report.active_remainders for report in reports):
        revalidation_diagnostics += ("ACTIVE_REMAINDERS_REQUIRE_REVALIDATION",)
    return MetaAnalysisReport(
        meta_analysis_id=meta_analysis_id,
        objective=objective,
        constituent_analysis_ids=analysis_ids,
        convergence_evidence=convergence_evidence,
        inherited_constraints=inherited_constraints,
        state=state,
        phi_anchored=phi_anchored,
        remainders=tuple(remainders),
        epistemic_state=epistemic_state,
        epistemic_gaps=epistemic_gaps,
        saturation_diagnostics=saturation_diagnostics,
        revalidation_diagnostics=revalidation_diagnostics,
        lens_assessment=lens_assessment,
    )


def encode_meta_analysis(report: MetaAnalysisReport) -> dict[str, Any]:
    return {
        "schema": report.schema,
        "meta_analysis_id": report.meta_analysis_id,
        "objective": report.objective,
        "constituent_analysis_ids": report.constituent_analysis_ids,
        "convergence_evidence": tuple({
            "evidence_id": item.evidence_id,
            "analysis_ids": item.analysis_ids,
            "shared_pattern": item.shared_pattern,
            "o2_justification": item.o2_justification,
        } for item in report.convergence_evidence),
        "inherited_constraints": tuple({
            "constraint_id": item.constraint_id,
            "analysis_ids": item.analysis_ids,
            "persistence_effect": item.persistence_effect,
        } for item in report.inherited_constraints),
        "state": report.state.value,
        "remainders": report.remainders,
        "phi_open": report.phi_open,
        "phi_anchored": report.phi_anchored,
        "authority": report.authority,
        "epistemic_state": report.epistemic_state.value,
        "epistemic_gaps": report.epistemic_gaps,
        "saturation_diagnostics": report.saturation_diagnostics,
        "revalidation_diagnostics": report.revalidation_diagnostics,
        "lens_assessment": {
            "state": report.lens_assessment.state.value,
            "signals": report.lens_assessment.signals,
            "structural_witnesses": report.lens_assessment.structural_witnesses,
            "phi_open": report.lens_assessment.phi_open,
        },
    }


def decode_meta_analysis(value: dict[str, Any]) -> MetaAnalysisReport:
    if value.get("schema") != META_ANALYSIS_SCHEMA:
        raise ValueError("Unknown meta-analysis schema")
    evidence = tuple(
        ConvergenceEvidence(**item)
        for item in value["convergence_evidence"]
    )
    constraints = tuple(
        InheritedConstraintEvidence(**item)
        for item in value["inherited_constraints"]
    )
    return MetaAnalysisReport(
        meta_analysis_id=value["meta_analysis_id"],
        objective=value["objective"],
        constituent_analysis_ids=tuple(value["constituent_analysis_ids"]),
        convergence_evidence=evidence,
        inherited_constraints=constraints,
        state=MetaAnalysisState(value["state"]),
        phi_anchored=bool(value["phi_anchored"]),
        remainders=tuple(value["remainders"]),
        phi_open=bool(value["phi_open"]),
        epistemic_state=EpistemicState(
            value.get("epistemic_state", EpistemicState.UNCLASSIFIED.value)
        ),
        epistemic_gaps=tuple(value.get("epistemic_gaps", ())),
        saturation_diagnostics=tuple(value.get("saturation_diagnostics", ())),
        revalidation_diagnostics=tuple(
            value.get("revalidation_diagnostics", ())
        ),
        lens_assessment=LensAssessment(
            state=RecoverabilityState(
                value.get("lens_assessment", {}).get(
                    "state",
                    RecoverabilityState.UNASSESSED.value,
                )
            ),
            signals=tuple(value.get("lens_assessment", {}).get("signals", ())),
            structural_witnesses=tuple(
                value.get("lens_assessment", {}).get("structural_witnesses", ())
            ),
            phi_open=bool(value.get("lens_assessment", {}).get("phi_open", True)),
        ),
        authority=value["authority"],
        schema=value["schema"],
    )


def _epistemic_gap(remainder: str) -> str:
    lowered = remainder.lower()
    if "source lineage" in lowered or "source diversity" in lowered:
        return "SOURCE_INDEPENDENCE_UNESTABLISHED"
    if "duplicate" in lowered:
        return "DUPLICATE_ANALYSIS_IDENTITY"
    if "o2" in lowered:
        return "O2_CONVERGENCE_MISSING_OR_INVALID"
    if "o3/f" in lowered or "grounded" in lowered or "anchor" in lowered:
        return "O3_FILTER_PHI_GROUNDING_MISSING"
    if "conflict" in lowered:
        return "CONFLICT_REQUIRES_RESOLUTION"
    return "UNRESOLVED_META_REMAINDER"
