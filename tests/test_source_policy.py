from __future__ import annotations

from hashlib import sha256

import pytest

from fresta_diamond.concept_research import ConceptSourceUnit
from fresta_diamond.source_policy import (
    EvidenceCoverageState,
    ExternalLibrarySpec,
    ExternalEvidenceAssessor,
    ExternalEvidencePolicy,
    ResearchStopDecision,
    default_external_libraries,
    source_family,
)


def unit(
    query_id: str,
    locator: str,
    source_type: str = "ACADEMIC",
    source_lineage: str | None = None,
):
    content = f"Evidence from {locator}"
    return ConceptSourceUnit(
        source_unit_id=sha256(locator.encode()).hexdigest(),
        query_id=query_id,
        title="External evidence",
        content=content,
        source_locator=locator,
        source_type=source_type,
        retrieved_at="2026-07-26T18:00:00+00:00",
        content_hash=sha256(content.encode()).hexdigest(),
        source_lineage=source_lineage,
    )


def test_subdomains_of_one_publisher_are_not_independent() -> None:
    assessment = ExternalEvidenceAssessor().assess((
        unit("query:features", "https://en.wikipedia.org/wiki/Car"),
        unit("query:label", "https://pt.wikipedia.org/wiki/Automovel"),
    ))

    assert assessment.source_families == ("wikipedia.org",)
    assert assessment.coverage_state is EvidenceCoverageState.INSUFFICIENT
    assert assessment.stop_decision is ResearchStopDecision.CONTINUE_RESEARCH
    assert "INDEPENDENT_SOURCE_FAMILIES" in assessment.unmet_requirements


def test_independent_families_and_query_roles_are_sufficient() -> None:
    assessment = ExternalEvidenceAssessor().assess((
        unit(
            "query:features",
            "https://research.example/article",
            source_lineage="lineage:research",
        ),
        unit(
            "query:label",
            "https://reference.test/automobile",
            "ENCYCLOPEDIC",
            "lineage:reference",
        ),
    ))

    assert assessment.coverage_state is EvidenceCoverageState.SUFFICIENT
    assert assessment.stop_decision is ResearchStopDecision.STOP_SUFFICIENT
    assert assessment.unmet_requirements == ()


def test_distinct_urls_do_not_establish_independence() -> None:
    assessment = ExternalEvidenceAssessor().assess((
        unit("query:features", "https://one.example/article"),
        unit("query:label", "https://two.example/entry", "ENCYCLOPEDIC"),
    ))

    assert assessment.source_families == ("one.example", "two.example")
    assert assessment.source_lineages == ()
    assert "SOURCE_LINEAGE_REQUIRED" in assessment.unmet_requirements
    assert "INDEPENDENT_SOURCE_FAMILIES" in assessment.unmet_requirements


def test_conflict_has_priority_over_sufficient_coverage() -> None:
    assessment = ExternalEvidenceAssessor().assess(
        (
            unit("query:features", "https://research.example/article"),
            unit("query:label", "https://reference.test/automobile"),
        ),
        conflict_detected=True,
    )

    assert assessment.coverage_state is EvidenceCoverageState.CONFLICTED
    assert assessment.stop_decision is ResearchStopDecision.REVIEW_CONFLICT


def test_budget_stops_an_insufficient_research_cycle() -> None:
    policy = ExternalEvidencePolicy(
        minimum_source_units=2,
        minimum_source_families=2,
        max_source_units=2,
    )
    assessment = ExternalEvidenceAssessor(policy).assess((
        unit("query:features", "https://a.wikipedia.org/one"),
        unit("query:features", "https://b.wikipedia.org/two"),
    ))

    assert assessment.coverage_state is EvidenceCoverageState.INSUFFICIENT
    assert assessment.stop_decision is ResearchStopDecision.STOP_BUDGET
    assert assessment.budget_reached is True


def test_common_multilevel_suffix_and_ip_are_stable() -> None:
    assert source_family("https://catalogue.cam.ac.uk/item") == "cam.ac.uk"
    assert source_family("https://127.0.0.1/report") == "127.0.0.1"


def test_default_external_libraries_are_replaceable_heuristics() -> None:
    libraries = default_external_libraries()

    assert {item.library_id for item in libraries} == {
        "openalex",
        "crossref",
        "core",
        "doaj",
        "perseus",
        "internet-archive",
    }
    assert all(item.authority == "EXTERNAL_HEURISTIC_ONLY" for item in libraries)


def test_external_library_cannot_grant_authority() -> None:
    with pytest.raises(PermissionError, match="cannot grant authority"):
        ExternalLibrarySpec(
            "unsafe",
            ("ACADEMIC",),
            "https://example.test",
            authority="PROMOTION_AUTHORITY",
        )
