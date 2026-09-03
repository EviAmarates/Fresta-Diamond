from fresta_diamond.brain_analysis import analyze_inventory
from fresta_diamond.ontology import (
    ConstraintEvidence,
    ExcludedCostEvidence,
    FilterEvidence,
    ManifestationEvidence,
    StrongRelationEvidence,
    StructuralEvidenceGraph,
)


def _graph(*, strong_o2: bool) -> StructuralEvidenceGraph:
    relation = StrongRelationEvidence(
        relation_id="relation:1",
        manifestation_id="manifestation:1",
        constraint_id="constraint:1",
        forward_justification="The manifestation is limited by the constraint."
        if strong_o2 else "",
        constraint_effect="The constraint changes the available object."
        if strong_o2 else "",
        return_witness="The relation is witnessed in this scope." if strong_o2 else "",
        excluded_cost_id="cost:1",
        scope="scope:test",
    )
    return StructuralEvidenceGraph(
        analysis_id="analysis:1",
        object_ref="object:1",
        scope="scope:test",
        manifestations=(ManifestationEvidence(
            "manifestation:1", "object:1", "One manifestation.", ("test:1",)
        ),),
        relations=(relation,),
        constraints=(ConstraintEvidence(
            "constraint:1", "A bounded constraint.", "scope:test"
        ),),
        filters=(FilterEvidence(
            "filter:1", "constraint:1", "manifestation:1", "cost:1",
            "Select this constraint for the bounded object.",
        ),),
        excluded_costs=(ExcludedCostEvidence(
            "cost:1", "An excluded alternative.", ("alternative:1",)
        ),),
    )


def _analyze(graph):
    return analyze_inventory(
        manifests=(),
        learning_commit_count=0,
        concept_count=0,
        chat_count=0,
        proposed_profile_count=0,
        proposed_personality_count=0,
        ontology_graph=graph,
    )


def test_brain_analysis_reports_strong_o2_and_justified_o3() -> None:
    report = _analyze(_graph(strong_o2=True))

    assert report.ontology["o2_strong"] is True
    assert report.ontology["o3_filter_stable_justified"] is True
    assert report.ontology["phi_open"] is True


def test_brain_analysis_surfaces_missing_strong_o2_without_closing_phi() -> None:
    report = _analyze(_graph(strong_o2=False))

    assert report.ontology["o2_strong"] is False
    assert report.ontology["o3_filter_stable_justified"] is False
    assert report.ontology["phi_open"] is True
    assert report.ontology["remainders"]
