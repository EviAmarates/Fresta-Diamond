"""Executable Three-Order witness-graph contracts."""

from dataclasses import replace

from fresta_diamond.contracts import RemainderKind
from fresta_diamond.ontology import (
    ANALYSIS_DIRECTION,
    GROUNDING_DIRECTION,
    AnalysisDepth,
    ConstitutionalGroundingEvidence,
    ConstitutionalStage,
    ConstraintEvidence,
    ExcludedCostEvidence,
    FilterEvidence,
    ManifestationEvidence,
    OntologicalValidator,
    StrongRelationEvidence,
    StructuralEvidenceGraph,
)


def valid_graph(*, advisory_model_closed: bool | None = None) -> StructuralEvidenceGraph:
    return StructuralEvidenceGraph(
        analysis_id="analysis-1",
        object_ref="object:engine-state",
        scope="scope:test",
        manifestations=(
            ManifestationEvidence(
                manifestation_id="o1-state",
                object_ref="object:engine-state",
                description="The bounded engine state remains operational",
                provenance=("artifact:observation-1",),
            ),
        ),
        relations=(
            StrongRelationEvidence(
                relation_id="o2-persistence",
                manifestation_id="o1-state",
                constraint_id="o3-input-contract",
                forward_justification=(
                    "The state is assessed against the declared input contract"
                ),
                constraint_effect="Malformed inputs are not admitted",
                return_witness=(
                    "The surviving state preserves the operation's declared identity"
                ),
                excluded_cost_id="cost-malformed-inputs",
                scope="scope:test",
            ),
        ),
        constraints=(
            ConstraintEvidence(
                constraint_id="o3-input-contract",
                description="Only schema-compatible inputs preserve this operation",
                scope="scope:test",
            ),
        ),
        filters=(
            FilterEvidence(
                filter_id="filter-schema",
                constraint_id="o3-input-contract",
                manifestation_id="o1-state",
                excluded_cost_id="cost-malformed-inputs",
                selection_justification=(
                    "Schema compatibility admits the persistent operation state"
                ),
            ),
        ),
        excluded_costs=(
            ExcludedCostEvidence(
                cost_id="cost-malformed-inputs",
                description="Incompatible states are excluded from execution",
                excluded_alternatives=("artifact:malformed-state",),
            ),
        ),
        groundings=(
            ConstitutionalGroundingEvidence(
                grounding_id="grounding-schema-filter",
                filter_id="filter-schema",
                grounding_direction=GROUNDING_DIRECTION,
                analysis_direction=ANALYSIS_DIRECTION,
                openness_necessity=(
                    "Selection is possible because alternatives are not already totalized"
                ),
            ),
        ),
        advisory_model_closed=advisory_model_closed,
    )


def test_complete_graph_closes_even_when_model_advises_false() -> None:
    report = OntologicalValidator().validate(
        valid_graph(advisory_model_closed=False)
    )

    assert report.reciprocal_structure_valid is True
    assert report.constitutional_closed is True
    assert report.structural_closed is True
    assert report.active_remainders == ()


def test_model_true_cannot_replace_return_witness() -> None:
    graph = valid_graph(advisory_model_closed=True)
    broken_relation = replace(graph.relations[0], return_witness="")
    report = OntologicalValidator().validate(
        replace(graph, relations=(broken_relation,))
    )

    assert report.reciprocal_structure_valid is False
    assert report.structural_closed is False
    assert any(
        item.kind is RemainderKind.MISSING_EVIDENCE
        and "return witness" in item.description
        for item in report.active_remainders
    )


def test_weak_circle_without_filter_does_not_close() -> None:
    graph = valid_graph(advisory_model_closed=True)
    report = OntologicalValidator().validate(
        replace(graph, filters=(), groundings=())
    )

    assert report.reciprocal_structure_valid is False
    assert report.constitutional_closed is None
    assert report.structural_closed is False


def test_reversed_grounding_direction_is_rejected() -> None:
    graph = valid_graph()
    reversed_grounding = replace(
        graph.groundings[0],
        grounding_direction=ANALYSIS_DIRECTION,
        analysis_direction=GROUNDING_DIRECTION,
    )
    report = OntologicalValidator().validate(
        replace(graph, groundings=(reversed_grounding,))
    )

    assert report.reciprocal_structure_valid is True
    assert report.constitutional_closed is False
    assert report.structural_closed is True
    assert sum(
        item.kind is RemainderKind.INVALID_DIRECTION
        for item in report.active_remainders
    ) == 2


def test_unused_selected_manifestation_prevents_closure() -> None:
    graph = valid_graph()
    unused = ManifestationEvidence(
        manifestation_id="o1-unused",
        object_ref=graph.object_ref,
        description="Retrieved but not used",
        provenance=("artifact:retrieval-candidate",),
    )
    report = OntologicalValidator().validate(
        replace(graph, manifestations=graph.manifestations + (unused,))
    )

    assert report.structural_closed is False
    assert any(
        item.kind is RemainderKind.UNUSED_EVIDENCE
        and item.required_for == "o1-unused"
        for item in report.active_remainders
    )


def test_excluded_cost_must_be_concrete_and_auditable() -> None:
    graph = valid_graph()
    empty_cost = replace(graph.excluded_costs[0], excluded_alternatives=())
    report = OntologicalValidator().validate(
        replace(graph, excluded_costs=(empty_cost,))
    )

    assert report.reciprocal_structure_valid is False
    assert report.structural_closed is False


def test_symbols_are_not_required_when_computational_directions_are_preserved() -> None:
    graph = valid_graph()

    assert ConstitutionalStage.OPENNESS.value == "OPENNESS"
    assert "PHI" not in ConstitutionalStage.OPENNESS.value
    assert OntologicalValidator().validate(graph).structural_closed is True


def test_post_filter_analysis_does_not_require_constitutional_grounding() -> None:
    contextual = replace(
        valid_graph(),
        groundings=(),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
    )

    report = OntologicalValidator().validate(contextual)

    assert report.reciprocal_structure_valid is True
    assert report.structural_closed is True
    assert report.constitutional_closed is None
    assert report.active_remainders == ()


def test_constitutional_depth_requires_explicit_grounding() -> None:
    constitutional = replace(
        valid_graph(),
        groundings=(),
        analysis_depth=AnalysisDepth.CONSTITUTIONAL,
    )

    report = OntologicalValidator().validate(constitutional)

    assert report.reciprocal_structure_valid is True
    assert report.structural_closed is True
    assert report.constitutional_closed is False
    assert any(
        "requires a grounding path" in item.description
        for item in report.active_remainders
    )


def test_constitutional_closure_cannot_rest_on_invalid_local_structure() -> None:
    graph = replace(
        valid_graph(),
        analysis_depth=AnalysisDepth.CONSTITUTIONAL,
        relations=(
            replace(valid_graph().relations[0], scope="scope:invented"),
        ),
    )

    report = OntologicalValidator().validate(graph)

    assert report.structural_closed is False
    assert report.constitutional_closed is False
