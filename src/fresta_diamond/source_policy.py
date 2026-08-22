"""Deterministic diversity and stopping policy for external concept evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from ipaddress import ip_address
from urllib.parse import urlparse

from fresta_diamond.concept_research import ConceptSourceUnit


class EvidenceCoverageState(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    SUFFICIENT = "SUFFICIENT"
    CONFLICTED = "CONFLICTED"


class ResearchStopDecision(str, Enum):
    CONTINUE_RESEARCH = "CONTINUE_RESEARCH"
    STOP_SUFFICIENT = "STOP_SUFFICIENT"
    STOP_BUDGET = "STOP_BUDGET"
    REVIEW_CONFLICT = "REVIEW_CONFLICT"


@dataclass(frozen=True)
class ExternalEvidencePolicy:
    """Minimum coverage for one bounded recognition review."""

    minimum_source_units: int = 2
    minimum_source_families: int = 2
    require_neutral_query: bool = True
    require_label_query: bool = True
    max_source_units: int = 12

    def __post_init__(self) -> None:
        if self.minimum_source_units < 1:
            raise ValueError("minimum_source_units must be positive")
        if self.minimum_source_families < 1:
            raise ValueError("minimum_source_families must be positive")
        if self.max_source_units < self.minimum_source_units:
            raise ValueError("max_source_units cannot be below the minimum")


@dataclass(frozen=True)
class ExternalEvidenceAssessment:
    coverage_state: EvidenceCoverageState
    stop_decision: ResearchStopDecision
    source_families: tuple[str, ...]
    source_family_counts: tuple[tuple[str, int], ...]
    source_types: tuple[str, ...]
    query_ids: tuple[str, ...]
    unmet_requirements: tuple[str, ...]
    source_units: int
    budget_reached: bool


class ExternalEvidenceAssessor:
    """Evaluate coverage without claiming semantic truth or source authority."""

    _NEUTRAL_QUERIES = frozenset({
        "query:features",
        "query:relations",
        "query:boundaries",
    })

    def __init__(
        self,
        policy: ExternalEvidencePolicy | None = None,
    ) -> None:
        self.policy = policy or ExternalEvidencePolicy()

    def assess(
        self,
        units: tuple[ConceptSourceUnit, ...],
        *,
        conflict_detected: bool = False,
    ) -> ExternalEvidenceAssessment:
        families = tuple(
            source_family(item.source_locator) for item in units
        )
        family_counts = Counter(families)
        query_ids = {item.query_id for item in units}
        unmet: list[str] = []
        if len(units) < self.policy.minimum_source_units:
            unmet.append("MINIMUM_SOURCE_UNITS")
        if len(family_counts) < self.policy.minimum_source_families:
            unmet.append("INDEPENDENT_SOURCE_FAMILIES")
        if (
            self.policy.require_neutral_query
            and not query_ids.intersection(self._NEUTRAL_QUERIES)
        ):
            unmet.append("NEUTRAL_QUERY_COVERAGE")
        if (
            self.policy.require_label_query
            and "query:label" not in query_ids
        ):
            unmet.append("LABEL_QUERY_COVERAGE")

        budget_reached = len(units) >= self.policy.max_source_units
        if conflict_detected:
            coverage = EvidenceCoverageState.CONFLICTED
            decision = ResearchStopDecision.REVIEW_CONFLICT
        elif not unmet:
            coverage = EvidenceCoverageState.SUFFICIENT
            decision = ResearchStopDecision.STOP_SUFFICIENT
        elif budget_reached:
            coverage = EvidenceCoverageState.INSUFFICIENT
            decision = ResearchStopDecision.STOP_BUDGET
        else:
            coverage = EvidenceCoverageState.INSUFFICIENT
            decision = ResearchStopDecision.CONTINUE_RESEARCH
        return ExternalEvidenceAssessment(
            coverage_state=coverage,
            stop_decision=decision,
            source_families=tuple(sorted(family_counts)),
            source_family_counts=tuple(sorted(family_counts.items())),
            source_types=tuple(sorted({
                item.source_type for item in units
            })),
            query_ids=tuple(sorted(query_ids)),
            unmet_requirements=tuple(unmet),
            source_units=len(units),
            budget_reached=budget_reached,
        )


_COMMON_SECOND_LEVEL_SUFFIXES = frozenset({
    "ac.uk",
    "co.jp",
    "co.uk",
    "com.au",
    "com.br",
    "com.pt",
    "edu.au",
    "gov.uk",
    "org.uk",
})


def source_family(locator: str) -> str:
    """Return a conservative hostname family; this is an audit heuristic."""

    host = (urlparse(locator).hostname or "").strip(".").lower()
    if not host:
        raise ValueError("External source has no hostname")
    if host.startswith("www."):
        host = host[4:]
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        return host
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    if last_two in _COMMON_SECOND_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two
