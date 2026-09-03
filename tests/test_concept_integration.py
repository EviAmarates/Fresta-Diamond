from __future__ import annotations

from dataclasses import replace
import json

import pytest

from fresta_diamond.cognitive_workspace import JsonlCognitiveWorkspace
from fresta_diamond.concept_integration import (
    AtomicConceptRecognitionArchive,
    ConceptRecognitionError,
    ConceptRecognitionService,
    ConceptRecognitionValidator,
    ConceptSourceLearner,
    ExternalConceptLearningOutcome,
)
from fresta_diamond.concept_research import (
    build_concept_research_request,
    concept_research_blueprint,
    decode_source_units,
    register_concept_research_provider,
    research_request_artifact,
)
from fresta_diamond.concepts import (
    ConceptAxisState,
    ConceptState,
    DerivationSourceKind,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.crystallization import CrystalState
from fresta_diamond.effects import EffectBroker
from fresta_diamond.registry import ModuleRegistry
from .test_concept_research import validated


PERMISSIONS = ("llm.model:diamond-external-replay",)


def researched(tmp_path, *, max_queries=4, same_family=False):
    concept, report = validated(tmp_path)
    request = build_concept_research_request(
        concept,
        report,
        max_queries=max_queries,
        max_results_per_query=1,
        request_id="concept-research:external-learning",
    )

    def search_adapter(_grant, *, queries, **_kwargs):
        return {"results": [
            {
                "query_id": item["query_id"],
                "title": f"External {item['query_id']}",
                "snippet": (
                    "An independent source reports a bounded automobile "
                    "definition and its functional relations."
                ),
                "url": (
                    f"https://source-{index}.evidence.example/report"
                    if same_family
                    else f"https://source-{index}.example/report"
                ),
                "source_type": (
                    "ACADEMIC" if index % 2 else "ENCYCLOPEDIC"
                ),
                "source_lineage": (
                    "lineage:shared-publisher"
                    if same_family
                    else f"lineage:external-{index}"
                ),
            }
            for index, item in enumerate(queries, start=1)
        ]}

    registry = ModuleRegistry()
    register_concept_research_provider(registry)
    result = DiamondController(
        registry,
        effect_broker=EffectBroker({
            "internet.search": search_adapter
        }),
    ).execute(
        concept_research_blueprint(),
        "Research a concept before external learning",
        {"research_request": research_request_artifact(request)},
    )
    return concept, report, result.execution.artifacts["source_units"]


def learning_adapter(
    source_artifact,
    *,
    claim_mode="ATTESTATION",
    contradictory=False,
):
    units = decode_source_units(source_artifact)
    provenance = [item.source_locator for item in units]
    constraint_id = (
        "manifestation:external-sources"
        if contradictory
        else "constraint:source-comparison"
    )
    bundle = {
        "structural_evidence": {
            "analysis_id": "analysis:external-concept-learning",
            "object_ref": "object:external-concept-sources",
            "scope": source_artifact.payload["scope"],
            "analysis_depth": "CONTEXTUAL",
            "manifestations": [{
                "manifestation_id": "manifestation:external-sources",
                "object_ref": "object:external-concept-sources",
                "description": (
                    "Independent sources report a recognized bounded concept."
                ),
                "provenance": provenance,
            }],
            "relations": [{
                "relation_id": "relation:external-convergence",
                "manifestation_id": "manifestation:external-sources",
                "constraint_id": constraint_id,
                "forward_justification": (
                    "The sources independently relate the same functional "
                    "characteristics and label."
                ),
                "constraint_effect": (
                    "Only reports preserving the bounded comparison remain."
                ),
                "return_witness": (
                    "The source set still describes the selected concept."
                ),
                "excluded_cost_id": "cost:definition-divergence",
                "scope": source_artifact.payload["scope"],
            }],
            "constraints": [{
                "constraint_id": constraint_id,
                "description": (
                    "External reports must preserve source and scope."
                ),
                "scope": source_artifact.payload["scope"],
            }],
            "filters": [{
                "filter_id": "filter:external-reports",
                "constraint_id": constraint_id,
                "manifestation_id": "manifestation:external-sources",
                "excluded_cost_id": "cost:definition-divergence",
                "selection_justification": (
                    "Selects mutually comparable external reports."
                ),
            }],
            "excluded_costs": [{
                "cost_id": "cost:definition-divergence",
                "description": "Loss of comparable conceptual content.",
                "excluded_alternatives": ["unrelated uses of the same label"],
            }],
            "groundings": [],
            "advisory_model_closed": True,
        },
        "candidate_assessments": [
            {
                "source_element_id": f"source-unit:{item.source_unit_id}",
                "claim_mode": claim_mode,
                "premise_refs": [],
                "applied_constraints": [],
                "derivation_direction": None,
                "test_criterion": None,
                "horizon": None,
                "assumptions": [],
                "counterexample_searches": [],
            }
            for item in units
        ],
    }

    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(bundle),
            "model": "diamond-external-replay",
            "usage": {"total_tokens": 100},
        }

    return adapter


def learned(
    tmp_path,
    *,
    max_queries=4,
    claim_mode="ATTESTATION",
    same_family=False,
    contradictory=False,
):
    concept, report, source_artifact = researched(
        tmp_path,
        max_queries=max_queries,
        same_family=same_family,
    )
    from fresta_diamond.learning_memory import AtomicDiamondLearningMemory
    from fresta_diamond.concepts import AtomicConceptStore

    memory = AtomicDiamondLearningMemory(tmp_path / "external-memory")
    store = AtomicConceptStore(tmp_path / "external-concepts")
    store.save(replace(
        concept,
        version=1,
        state=ConceptState.CANDIDATE,
        memberships=tuple(
            replace(item, state=item.state.__class__.CANDIDATE)
            for item in concept.memberships
        ),
        derivation_seals=(),
        recognition_state=ConceptAxisState.NOT_EVALUATED,
        definition_state=ConceptAxisState.NOT_EVALUATED,
        validation_refs=(),
        previous_version_ref=None,
        revision_reason="test reconstruction",
    ))
    store._save_validated(concept)
    learner = ConceptSourceLearner(
        learning_adapter(
            source_artifact,
            claim_mode=claim_mode,
            contradictory=contradictory,
        ),
        required_permissions=PERMISSIONS,
        sheet_id_factory=lambda: "external-concept-learning",
    )
    learning = learner.learn(
        concept=concept,
        source_artifact=source_artifact,
        workspace=JsonlCognitiveWorkspace(tmp_path / "external-workspace"),
        memory=memory,
    )
    return concept, report, source_artifact, memory, store, learning


def test_source_units_traverse_normal_learn_and_atomic_commit(tmp_path) -> None:
    concept, _report, artifact, memory, _store, learning = learned(tmp_path)
    units = decode_source_units(artifact)
    crystals = learning.stored_commit.commit.crystallization.crystals

    assert learning.model_call_count == 1
    assert len(crystals) == len(units) == 4
    assert {item.state for item in crystals} == {CrystalState.PROVISIONAL}
    assert {
        locator
        for item in crystals
        for locator in item.provenance
    } == {item.source_locator for item in units}
    assert learning.stored_commit.path.exists()
    assert len(memory.commits()) == 1
    assert concept.version == 2


def test_independent_learned_sources_update_only_external_axes(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, store, learning = learned(tmp_path)
    validator = ConceptRecognitionValidator(
        memory,
        id_factory=lambda: "recognition:automobile:v1",
        clock=lambda: "2026-07-26T18:00:00+00:00",
    )
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=validator,
        clock=lambda: "2026-07-26T18:00:00+00:00",
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )

    assert outcome.report.recognition_state is ConceptAxisState.SUPPORTED
    assert outcome.report.evidence_coverage_state.value == "SUFFICIENT"
    assert outcome.report.research_stop_decision.value == "STOP_SUFFICIENT"
    assert len(outcome.report.source_families) == 4
    assert (
        outcome.report.external_definition_state
        is ConceptAxisState.SUPPORTED
    )
    assert outcome.record.version == 3
    assert outcome.record.state is ConceptState.VALIDATED
    assert outcome.record.recognition_state is ConceptAxisState.SUPPORTED
    assert outcome.record.definition_state is ConceptAxisState.SUPPORTED
    external_seals = outcome.record.derivation_seals[
        len(concept.derivation_seals):
    ]
    assert len(external_seals) == 4
    assert all(
        {source.kind for source in seal.sources} == {
            DerivationSourceKind.MEMORY_CRYSTAL,
            DerivationSourceKind.WEB_SOURCE,
        }
        for seal in external_seals
    )
    assert outcome.report_path.exists()
    archived = AtomicConceptRecognitionArchive(
        store.root / "recognition"
    ).load(outcome.report.recognition_id)
    assert archived == outcome.report


def test_one_external_source_remains_indeterminate_without_version(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, store, learning = learned(
        tmp_path, max_queries=1
    )
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=ConceptRecognitionValidator(
            memory,
            id_factory=lambda: "recognition:insufficient",
        ),
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )

    assert outcome.report.recognition_state is ConceptAxisState.INDETERMINATE
    assert (
        outcome.report.external_definition_state
        is ConceptAxisState.INDETERMINATE
    )
    assert outcome.concept_path is None
    assert store.latest(concept.concept_id) == concept


def test_multiple_urls_from_one_source_family_are_not_independent(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, store, learning = learned(
        tmp_path,
        same_family=True,
    )
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=ConceptRecognitionValidator(
            memory,
            id_factory=lambda: "recognition:same-family",
        ),
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )

    assert outcome.report.recognition_state is ConceptAxisState.INDETERMINATE
    assert outcome.report.source_families == ("evidence.example",)
    assert "INDEPENDENT_SOURCE_FAMILIES" in (
        outcome.report.unmet_requirements
    )
    assert outcome.report.research_stop_decision.value == "CONTINUE_RESEARCH"
    assert outcome.concept_path is None


def test_deferred_external_sources_cannot_support_recognition(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, store, learning = learned(
        tmp_path, claim_mode="OBSERVATION"
    )
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=ConceptRecognitionValidator(
            memory,
            id_factory=lambda: "recognition:deferred",
        ),
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )

    assert outcome.report.recognition_state is ConceptAxisState.INDETERMINATE
    assert not outcome.report.external_crystal_ids
    assert outcome.concept_path is None


def test_external_contradiction_requires_review_instead_of_consensus(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, store, learning = learned(
        tmp_path,
        contradictory=True,
    )
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=ConceptRecognitionValidator(
            memory,
            id_factory=lambda: "recognition:conflict",
        ),
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )

    assert outcome.report.recognition_state is ConceptAxisState.CONTESTED
    assert outcome.report.evidence_coverage_state.value == "CONFLICTED"
    assert outcome.report.research_stop_decision.value == "REVIEW_CONFLICT"
    assert outcome.record.state is ConceptState.VALIDATED
    assert outcome.record.recognition_state is ConceptAxisState.CONTESTED


def test_supplied_learning_commit_must_equal_autonomous_memory(
    tmp_path,
) -> None:
    concept, prior, artifact, memory, _store, learning = learned(tmp_path)
    crystal = learning.stored_commit.commit.crystallization.crystals[0]
    forged_batch = replace(
        learning.stored_commit.commit.crystallization,
        crystals=(
            replace(crystal, provenance=("https://forged.example",)),
            *learning.stored_commit.commit.crystallization.crystals[1:],
        ),
    )
    forged_commit = replace(
        learning.stored_commit.commit,
        crystallization=forged_batch,
    )
    forged = replace(
        learning,
        stored_commit=replace(
            learning.stored_commit,
            commit=forged_commit,
        ),
    )

    with pytest.raises(ConceptRecognitionError, match="does not match"):
        ConceptRecognitionValidator(memory).validate(
            concept,
            prior_validation=prior,
            source_artifact=artifact,
            learning=forged,
        )


def test_recognition_archive_detects_tampering(tmp_path) -> None:
    concept, prior, artifact, memory, store, learning = learned(tmp_path)
    outcome = ConceptRecognitionService(
        memory,
        store,
        validator=ConceptRecognitionValidator(
            memory,
            id_factory=lambda: "recognition:tamper-test",
        ),
    ).validate_and_store(
        concept.concept_id,
        prior_validation=prior,
        source_artifact=artifact,
        learning=learning,
    )
    raw = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    raw["recognition_state"] = "CONTESTED"
    outcome.report_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ConceptRecognitionError, match="hash mismatch"):
        AtomicConceptRecognitionArchive(
            store.root / "recognition"
        ).load(outcome.report.recognition_id)
