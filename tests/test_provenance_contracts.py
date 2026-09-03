from __future__ import annotations

import hashlib

import pytest

from fresta_diamond.contracts import (
    ExtractedUnit,
    ProvenanceKind,
    SearchIntent,
    SourceDocument,
    TypedProvenance,
    classify_provenance,
    decode_provenance,
)
from fresta_diamond.concept_research import ConceptResearchQuery, ConceptSourceUnit
from fresta_diamond.meta_analysis import (
    ConvergenceEvidence,
    EpistemicState,
    InheritedConstraintEvidence,
    MetaAnalysisState,
    analyze_meta_analysis,
    decode_meta_analysis,
    encode_meta_analysis,
)
from fresta_diamond.ontology import ManifestationEvidence
from dataclasses import replace

from .test_meta_analysis import _constraint, _evidence, _graph


@pytest.mark.parametrize(("refs", "kind"), (
    (("memory:crystal",), ProvenanceKind.INTERNAL),
    (("https://example.test/page",), ProvenanceKind.EXTERNAL),
    (("memory:crystal", "https://example.test/page"), ProvenanceKind.MIXED),
    (("opaque-reference",), ProvenanceKind.UNKNOWN),
))
def test_provenance_classification_is_conservative(refs, kind) -> None:
    assert classify_provenance(refs) is kind
    assert decode_provenance(list(refs)).kind is kind


def test_typed_provenance_does_not_trust_claimed_domain() -> None:
    value = decode_provenance({
        "kind": "INTERNAL",
        "refs": ["https://example.test/page"],
    })
    assert value.kind is ProvenanceKind.EXTERNAL


def test_source_document_and_extracted_unit_retain_lineage() -> None:
    content = "bounded extraction"
    digest = hashlib.sha256(content.encode()).hexdigest()
    document = SourceDocument(
        document_ref="document:abc",
        locator="https://example.test/page",
        content_hash=digest,
        provenance=TypedProvenance(
            ("https://example.test/page",),
            source_lineage="lineage:document-a",
        ),
    )
    unit = ExtractedUnit(
        unit_ref="unit:1",
        source_document_ref=document.source_document_id,
        content_hash=digest,
        content=content,
        provenance=document.provenance,
        source_lineage="lineage:document-a",
    )
    assert unit.source_document_id == document.source_document_id
    assert unit.provenance.kind is ProvenanceKind.EXTERNAL
    assert unit.provenance.source_lineage == "lineage:document-a"


def test_lineage_mismatch_is_rejected_in_source_document_chain() -> None:
    with pytest.raises(ValueError, match="lineage"):
        SourceDocument(
            document_ref="document:abc",
            locator="https://example.test/page",
            content_hash=hashlib.sha256(b"bounded extraction").hexdigest(),
            provenance=TypedProvenance(
                ("https://example.test/page",),
                source_lineage="lineage:a",
            ),
            source_lineage="lineage:b",
        )


def test_concept_source_unit_exposes_document_and_unit_lineage() -> None:
    content = "A source report."
    digest = hashlib.sha256(content.encode()).hexdigest()
    unit = ConceptSourceUnit(
        source_unit_id="unit:1",
        query_id="query:features",
        title="Report",
        content=content,
        source_locator="https://example.test/report",
        source_type="WEB",
        retrieved_at="2026-09-03T00:00:00+00:00",
        content_hash=digest,
        source_lineage="lineage:report-a",
    )
    assert unit.source_document.document_ref == unit.source_locator
    assert unit.extracted_unit.source_document_ref == unit.source_locator
    assert unit.source_lineage == "lineage:report-a"
    assert unit.source_document.source_lineage == "lineage:report-a"
    assert unit.provenance.kind is ProvenanceKind.EXTERNAL


def test_manifestation_accepts_typed_lineage_without_url_inference() -> None:
    manifestation = ManifestationEvidence(
        manifestation_id="m:typed",
        object_ref="object:typed",
        description="Observed stable pattern",
        provenance=TypedProvenance(
            ("https://one.example/report",),
            source_lineage="lineage:typed",
        ),
    )

    assert manifestation.provenance == ("https://one.example/report",)
    assert manifestation.source_lineage == "lineage:typed"


def test_search_intent_is_typed_and_legacy_marker_is_derived() -> None:
    query = ConceptResearchQuery(
        "query:features",
        "bounded functional identity",
        "discover vocabulary",
        ("ACADEMIC",),
    )
    assert query.search_intent is SearchIntent.NEUTRAL
    with pytest.raises(ValueError, match="intent"):
        ConceptResearchQuery(
            "query:label",
            "candidate",
            "recognition",
            ("ACADEMIC",),
            reveals_candidate_label=True,
            intent=SearchIntent.NEUTRAL,
        )


def test_meta_analysis_remains_phi_open_with_typed_unknown_provenance() -> None:
    first = _graph("a:1", constitutional=True)
    second = _graph("a:2")
    second = replace(second, manifestations=(ManifestationEvidence(
        manifestation_id="m:a:2",
        object_ref="object:a:2",
        description="Observed stable pattern",
        provenance=("opaque:a:2",),
        source_lineage="lineage:a:2",
    ),))
    report = analyze_meta_analysis(
        meta_analysis_id="meta:test",
        objective="Compare bounded analyses",
        analyses=(first, second),
        convergence_evidence=(
            ConvergenceEvidence(
                "evidence:1",
                (first.analysis_id, second.analysis_id),
                "p",
                "O2",
            ),
        ),
        inherited_constraints=_constraint(),
    )
    assert report.phi_open is True
    assert report.state is MetaAnalysisState.COHERENT_CANDIDATE
    assert report.epistemic_state in {
        EpistemicState.INSUFFICIENT_GROUNDING,
        EpistemicState.UNCLASSIFIED,
    }
    assert "SATURATION_NOT_ESTABLISHED_BY_META_ANALYSIS_CONTRACT" in (
        report.saturation_diagnostics
    )
    assert "CONSTITUENT_ANALYSES_VALIDATED" in report.revalidation_diagnostics
    assert decode_meta_analysis(encode_meta_analysis(report)) == report
