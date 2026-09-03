import pytest

from fresta_diamond.meta_analysis import (
    ConvergenceEvidence,
    EpistemicState,
    InheritedConstraintEvidence,
    MetaAnalysisState,
    RecoverabilityState,
    analyze_meta_analysis,
    encode_meta_analysis,
)
from fresta_diamond.ontology import (
    ConstraintEvidence,
    ExcludedCostEvidence,
    FilterEvidence,
    ManifestationEvidence,
    StrongRelationEvidence,
    StructuralEvidenceGraph,
    AnalysisDepth,
    ConstitutionalGroundingEvidence,
    ConstitutionalStage,
    GROUNDING_DIRECTION,
    ANALYSIS_DIRECTION,
)


def _graph(
    analysis_id: str,
    constraint_id: str = "f",
    *,
    constitutional: bool = False,
) -> StructuralEvidenceGraph:
    return StructuralEvidenceGraph(
        analysis_id=analysis_id,
        object_ref=f"object:{analysis_id}",
        scope="scope:meta",
        manifestations=(ManifestationEvidence(
            manifestation_id=f"m:{analysis_id}",
            object_ref=f"object:{analysis_id}",
            description="Observed stable pattern",
            provenance=(
                f"source:{analysis_id}",
            ),
            source_lineage=f"lineage:{analysis_id}",
        ),),
        relations=(StrongRelationEvidence(
            relation_id=f"r:{analysis_id}",
            manifestation_id=f"m:{analysis_id}",
            constraint_id=constraint_id,
            forward_justification="The constraint selects the pattern.",
            constraint_effect="It limits admissible transformations.",
            return_witness="The pattern persists under the constraint.",
            excluded_cost_id=f"c:{analysis_id}",
            scope="scope:meta",
        ),),
        constraints=(ConstraintEvidence(
            constraint_id=constraint_id,
            description="Inherited transmission constraint",
            scope="scope:meta",
        ),),
        filters=(FilterEvidence(
            filter_id=f"filter:{analysis_id}",
            constraint_id=constraint_id,
            manifestation_id=f"m:{analysis_id}",
            excluded_cost_id=f"c:{analysis_id}",
            selection_justification="Observed persistence is selected by the constraint.",
        ),),
        excluded_costs=(ExcludedCostEvidence(
            cost_id=f"c:{analysis_id}",
            description="Alternative pattern was not retained",
            excluded_alternatives=("alternative",),
        ),),
        groundings=(ConstitutionalGroundingEvidence(
            grounding_id=f"grounding:{analysis_id}",
            filter_id=f"filter:{analysis_id}",
            grounding_direction=GROUNDING_DIRECTION,
            analysis_direction=ANALYSIS_DIRECTION,
            openness_necessity="Filtering requires irreducible openness.",
        ),) if constitutional else (),
        analysis_depth=(
            AnalysisDepth.CONSTITUTIONAL
            if constitutional else AnalysisDepth.CONTEXTUAL
        ),
    )


def _evidence() -> tuple[ConvergenceEvidence, ...]:
    return (ConvergenceEvidence(
        evidence_id="conv:1",
        analysis_ids=("a:1", "a:2"),
        shared_pattern="Stable persistence under inherited constraint",
        o2_justification="Both analyses independently witness the same relation.",
    ),)


def _constraint() -> tuple[InheritedConstraintEvidence, ...]:
    return (InheritedConstraintEvidence(
        constraint_id="f",
        analysis_ids=("a:1", "a:2"),
        persistence_effect="Limits admissible transformations and explains persistence.",
    ),)


def test_meta_analysis_marks_convergence_as_candidate_with_phi_open() -> None:
    report = analyze_meta_analysis(
        meta_analysis_id="meta:1",
        objective="Compare persistence patterns",
        analyses=(_graph("a:1", constitutional=True), _graph("a:2")),
        convergence_evidence=_evidence(),
        inherited_constraints=_constraint(),
    )

    assert report.state is MetaAnalysisState.COHERENT_CANDIDATE
    assert report.phi_open is True
    assert report.phi_anchored is True
    assert report.authority == "META_ANALYSIS_PROPOSAL_ONLY"
    assert report.epistemic_state is EpistemicState.EXTERNAL_ONLY
    assert report.lens_assessment.state is RecoverabilityState.RECOVERABLE
    assert report.lens_assessment.phi_open is True
    assert encode_meta_analysis(report)["state"] == "COHERENT_CANDIDATE"


def test_meta_analysis_requires_explicit_o2_and_f() -> None:
    report = analyze_meta_analysis(
        meta_analysis_id="meta:incomplete",
        objective="Compare persistence patterns",
        analyses=(_graph("a:1"), _graph("a:2")),
        convergence_evidence=(),
        inherited_constraints=(),
    )

    assert report.state is MetaAnalysisState.INCOMPLETE
    assert any("O2" in item for item in report.remainders)
    assert any("O3/F" in item for item in report.remainders)
    assert report.epistemic_state is EpistemicState.INSUFFICIENT_GROUNDING
    assert "O2_CONVERGENCE_MISSING_OR_INVALID" in report.epistemic_gaps
    assert report.lens_assessment.state is RecoverabilityState.AT_RISK


def test_meta_analysis_rejects_o2_with_duplicate_analysis_reference() -> None:
    report = analyze_meta_analysis(
        meta_analysis_id="meta:duplicate-o2",
        objective="Compare persistence patterns",
        analyses=(_graph("a:1", constitutional=True), _graph("a:2")),
        convergence_evidence=(ConvergenceEvidence(
            evidence_id="conv:duplicate",
            analysis_ids=("a:1", "a:1"),
            shared_pattern="Stable persistence under inherited constraint",
            o2_justification="The same analysis is listed twice.",
        ),),
        inherited_constraints=_constraint(),
    )

    assert report.state is MetaAnalysisState.INCOMPLETE
    assert any("two distinct constituent analyses" in item for item in report.remainders)


def test_meta_analysis_requires_source_diversity() -> None:
    first = _graph("a:1")
    second = _graph("a:2")
    from dataclasses import replace
    from fresta_diamond.ontology import ManifestationEvidence

    shared = ManifestationEvidence(
        manifestation_id="m:a:2",
        object_ref="object:a:2",
        description="Observed stable pattern",
        provenance=("source:a:1",),
    )
    report = analyze_meta_analysis(
        meta_analysis_id="meta:source",
        objective="Compare persistence patterns",
        analyses=(first, replace(second, manifestations=(shared,))),
        convergence_evidence=_evidence(),
        inherited_constraints=_constraint(),
    )

    assert report.state is MetaAnalysisState.INCOMPLETE
    assert any("source lineage" in item for item in report.remainders)
    assert "SOURCE_INDEPENDENCE_UNESTABLISHED" in report.epistemic_gaps


def test_meta_analysis_rejects_ungrounded_inherited_constraint() -> None:
    report = analyze_meta_analysis(
        meta_analysis_id="meta:ungrounded",
        objective="Compare persistence patterns",
        analyses=(_graph("a:1", constitutional=True), _graph("a:2")),
        convergence_evidence=_evidence(),
        inherited_constraints=(InheritedConstraintEvidence(
            constraint_id="unseen",
            analysis_ids=("a:1",),
            persistence_effect="Proposed but not witnessed in either O3.",
        ),),
    )

    assert report.state is MetaAnalysisState.INCOMPLETE
    assert any("not grounded" in item for item in report.remainders)


def test_meta_analysis_preserves_contestation() -> None:
    report = analyze_meta_analysis(
        meta_analysis_id="meta:contested",
        objective="Compare incompatible patterns",
        analyses=(_graph("a:1"), _graph("a:2")),
        convergence_evidence=_evidence(),
        inherited_constraints=_constraint(),
        conflicts=("The two sources assign incompatible persistence mechanisms.",),
    )

    assert report.state is MetaAnalysisState.CONTESTED
    assert report.epistemic_state is EpistemicState.CONTESTED
    assert report.lens_assessment.state is RecoverabilityState.CONTESTED
    assert any(item.startswith("CONFLICT:") for item in report.remainders)


def test_meta_analysis_never_accepts_phi_closure() -> None:
    with pytest.raises(PermissionError, match="close Phi"):
        from dataclasses import replace

        report = analyze_meta_analysis(
            meta_analysis_id="meta:1",
            objective="Compare persistence patterns",
            analyses=(_graph("a:1"), _graph("a:2")),
            convergence_evidence=_evidence(),
            inherited_constraints=_constraint(),
        )
        replace(report, phi_open=False)
