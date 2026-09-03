"""Deterministic, immutable inventory and diagnosis of Diamond state."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

from fresta_diamond.ontology import StructuralEvidenceGraph, OntologicalValidator

BRAIN_ANALYSIS_SCHEMA = "artifact://brain-analysis-report@1"


@dataclass(frozen=True)
class BrainAnalysisReport:
    inventory: Mapping[str, Any]
    diagnoses: tuple[str, ...]
    remainders: tuple[str, ...]
    ontology: Mapping[str, Any] = field(default_factory=dict)
    authority: str = "BRAIN_ANALYSIS_REPORT_ONLY"
    schema: str = BRAIN_ANALYSIS_SCHEMA
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.authority != "BRAIN_ANALYSIS_REPORT_ONLY":
            raise PermissionError("Brain analysis cannot grant mutation authority")
        if not self.content_hash:
            body = {
                "schema": self.schema,
                "inventory": self.inventory,
                "diagnoses": self.diagnoses,
                "remainders": self.remainders,
                "authority": self.authority,
                "ontology": self.ontology,
            }
            object.__setattr__(self, "content_hash", _digest(body))


def analyze_inventory(
    *,
    manifests: tuple[Mapping[str, Any], ...],
    learning_commit_count: int,
    concept_count: int,
    chat_count: int,
    proposed_profile_count: int,
    proposed_personality_count: int,
    ontology_graph: StructuralEvidenceGraph | None = None,
) -> BrainAnalysisReport:
    inventory = {
        "modules": manifests,
        "learning_commit_count": learning_commit_count,
        "concept_count": concept_count,
        "chat_count": chat_count,
        "proposed_profile_count": proposed_profile_count,
        "proposed_personality_count": proposed_personality_count,
    }
    diagnoses = []
    if proposed_profile_count or proposed_personality_count:
        diagnoses.append("Profile proposals await explicit controlled adoption.")
    if chat_count:
        diagnoses.append("Chat history is coordination history, not implicit memory.")
    diagnoses.append("Three-Order authority remains contextual to each bounded analysis.")
    remainders = (
        "Constitutional PHI remains open and is not represented as a finite inventory.",
        "No brain apply operation is available from this report.",
    )
    ontology = _ontology_diagnosis(ontology_graph)
    return BrainAnalysisReport(
        inventory=inventory,
        diagnoses=tuple(diagnoses),
        remainders=remainders,
        ontology=ontology,
    )


def encode_brain_analysis(report: BrainAnalysisReport) -> dict[str, Any]:
    return {
        "schema": report.schema,
        "inventory": report.inventory,
        "diagnoses": report.diagnoses,
        "remainders": report.remainders,
        "authority": report.authority,
        "ontology": report.ontology,
        "content_hash": report.content_hash,
    }


def _ontology_diagnosis(
    graph: StructuralEvidenceGraph | None,
) -> Mapping[str, Any]:
    if graph is None:
        return {
            "status": "NOT_SUPPLIED",
            "o2_strong": None,
            "o3_filter_stable_justified": None,
            "phi_open": True,
        }
    report = OntologicalValidator().validate(graph)
    descriptions = tuple(item.description for item in report.active_remainders)
    o2_strong = bool(graph.relations) and not any(
        "Strong O2" in item or "O2 relation" in item for item in descriptions
    )
    o3_stable = bool(graph.constraints and graph.filters) and not any(
        any(term in item for term in ("O3", "FILTER", "constraint"))
        for item in descriptions
    )
    return {
        "status": "ASSESSED",
        "o2_strong": o2_strong,
        "o3_filter_stable_justified": o3_stable,
        "phi_open": True,
        "structural_closed": report.structural_closed,
        "remainders": descriptions,
    }


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=list)
    return sha256(encoded.encode("utf-8")).hexdigest()
