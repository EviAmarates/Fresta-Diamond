from __future__ import annotations

from dataclasses import replace
import json

import pytest

from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptState,
    DerivationContribution,
    DerivationSeal,
    DerivationSource,
    DerivationSourceKind,
    MembershipState,
    concept_targets,
    decode_concept_record,
    encode_concept_record,
    membership_target,
)
from fresta_diamond.concept_validation import (
    AtomicConceptValidationArchive,
    ConceptAxisState,
    ConceptValidationError,
    ConceptValidationService,
    ConceptValidator,
)
from fresta_diamond.epistemology import (
    ClaimMode,
    EpistemicClaim,
    EpistemicEvidenceGraph,
    EvidenceEvent,
    EvidenceKind,
    EvidenceStance,
)
from fresta_diamond.ontology import (
    AnalysisDepth,
    ConstraintEvidence,
    ExcludedCostEvidence,
    FilterEvidence,
    ManifestationEvidence,
    StrongRelationEvidence,
    StructuralEvidenceGraph,
)
from .test_concepts import candidate, committed_memory


ANALYSIS_ID = "analysis:concept-automobile"
NOW = "2026-07-26T12:00:00+00:00"


def evidence_graphs(concept, memory, *, provenance: str | None = None):
    crystals = memory.crystals()
    source = provenance or crystals[0].provenance[0]
    structural = StructuralEvidenceGraph(
        analysis_id=ANALYSIS_ID,
        object_ref=concept.version_ref,
        scope=concept.scope,
        manifestations=(ManifestationEvidence(
            manifestation_id="manifestation:automobile",
            object_ref=concept.version_ref,
            description="The selected crystals manifest a bounded functional system.",
            provenance=(source,),
        ),),
        relations=(StrongRelationEvidence(
            relation_id="relation:functional-membership",
            manifestation_id="manifestation:automobile",
            constraint_id="constraint:functional-coherence",
            forward_justification=(
                "The members jointly participate in energy transformation "
                "and functional identity."
            ),
            constraint_effect=(
                "Only arrangements preserving the bounded function remain."
            ),
            return_witness=(
                "The selected members still witness the proposed concept."
            ),
            excluded_cost_id="cost:no-coherent-function",
            scope=concept.scope,
        ),),
        constraints=(ConstraintEvidence(
            constraint_id="constraint:functional-coherence",
            description="Membership must preserve coherent function.",
            scope=concept.scope,
        ),),
        filters=(FilterEvidence(
            filter_id="filter:functional-system",
            constraint_id="constraint:functional-coherence",
            manifestation_id="manifestation:automobile",
            excluded_cost_id="cost:no-coherent-function",
            selection_justification=(
                "Selects members that jointly sustain the proposed function."
            ),
        ),),
        excluded_costs=(ExcludedCostEvidence(
            cost_id="cost:no-coherent-function",
            description="Loss of coherent function.",
            excluded_alternatives=("unrelated component collections",),
        ),),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
    )
    epistemic = EpistemicEvidenceGraph(
        analysis_id=ANALYSIS_ID,
        object_ref=concept.version_ref,
        scope=concept.scope,
        claims=(EpistemicClaim(
            claim_id="claim:concept-fit",
            content="The committed members instantiate the proposed concept.",
            subject_ref=concept.version_ref,
            owner_ref="owner:diamond-analysis",
            scope=concept.scope,
            claim_mode=ClaimMode.DERIVATION,
            evidence_ids=("evidence:concept-premise",),
            premise_refs=tuple(item.crystal_id for item in crystals),
            applied_constraints=("constraint:functional-coherence",),
            derivation_direction="committed members -> relation -> concept",
        ),),
        evidence_events=(EvidenceEvent(
            evidence_id="evidence:concept-premise",
            claim_id="claim:concept-fit",
            evidence_kind=EvidenceKind.PREMISE,
            stance=EvidenceStance.SUPPORTS,
            source_actor="source:document",
            source_locator=source,
            source_lineage=source,
            context_id=concept.version_ref,
            method="bounded concept derivation",
            observed_at=NOW,
            scope=concept.scope,
        ),),
    )
    return structural, epistemic


def complete_seals(concept, memory):
    crystals = memory.crystals()
    sources = tuple(
        DerivationSource(
            item.crystal_id,
            DerivationSourceKind.MEMORY_CRYSTAL,
        )
        for item in crystals
    )
    seals = []
    for index, target in enumerate(concept_targets(concept), start=1):
        seals.append(DerivationSeal(
            seal_id=f"seal:concept:{index}",
            target_ref=target,
            contribution=(
                DerivationContribution.DIRECT
                if target.startswith("membership:")
                else DerivationContribution.SYNTHESIS
            ),
            sources=sources,
            analysis_id=ANALYSIS_ID,
            scope=concept.scope,
            created_at=NOW,
        ))
    return tuple(seals)


def service(tmp_path):
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    proposed = candidate(memory)
    store.save(proposed)
    validator = ConceptValidator(
        memory,
        id_factory=lambda: "validation:automobile:v1",
        clock=lambda: NOW,
    )
    runner = ConceptValidationService(
        memory,
        store,
        validator=validator,
        clock=lambda: NOW,
    )
    return memory, store, proposed, runner


def test_closed_internal_evidence_versions_candidate_as_validated(
    tmp_path,
) -> None:
    memory, store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.report.recommended_state is ConceptState.VALIDATED
    assert outcome.report.local_fit is ConceptAxisState.SUPPORTED
    assert outcome.report.structural_state is ConceptAxisState.SUPPORTED
    assert outcome.report.definition_state is ConceptAxisState.SUPPORTED
    assert (
        outcome.report.recognition_state
        is ConceptAxisState.NOT_EVALUATED
    )
    assert outcome.record.version == 2
    assert outcome.record.state is ConceptState.VALIDATED
    assert {item.state for item in outcome.record.memberships} == {
        MembershipState.SUPPORTED
    }
    assert len(outcome.record.derivation_seals) == len(
        concept_targets(proposed)
    )
    assert store.latest(proposed.concept_id) == outcome.record
    archived = AtomicConceptValidationArchive(
        store.root / "validations"
    ).load(outcome.report.validation_id)
    assert archived == outcome.report


def test_missing_field_seal_keeps_candidate_and_archives_remainder(
    tmp_path,
) -> None:
    memory, store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    seals = complete_seals(proposed, memory)[1:]

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=seals,
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert outcome.report.definition_state is ConceptAxisState.INDETERMINATE
    assert outcome.concept_path is None
    assert store.latest(proposed.concept_id) == proposed
    assert outcome.report_path.exists()


def test_counterevidence_versions_concept_as_contested(tmp_path) -> None:
    memory, store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    target = membership_target(proposed.memberships[0].crystal_id)
    counter = DerivationSeal(
        seal_id="seal:counterexample",
        target_ref=target,
        contribution=DerivationContribution.COUNTEREVIDENCE,
        sources=(DerivationSource(
            proposed.memberships[0].crystal_id,
            DerivationSourceKind.MEMORY_CRYSTAL,
        ),),
        analysis_id=ANALYSIS_ID,
        scope=proposed.scope,
        created_at=NOW,
    )

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory) + (counter,),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.record.state is ConceptState.CONTESTED
    assert outcome.report.local_fit is ConceptAxisState.CONTESTED
    contested = next(
        item for item in outcome.record.memberships
        if item.crystal_id == proposed.memberships[0].crystal_id
    )
    assert contested.state is MembershipState.CONTESTED


def test_uncommitted_graph_provenance_cannot_validate(tmp_path) -> None:
    memory, _store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(
        proposed,
        memory,
        provenance="web:https://invented.invalid",
    )

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert any(
        "uncommitted provenance" in item.description
        for item in outcome.report.active_remainders
    )


def test_web_source_cannot_enter_internal_validation_directly(tmp_path) -> None:
    memory, _store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    seals = list(complete_seals(proposed, memory))
    seals[0] = replace(
        seals[0],
        sources=(DerivationSource(
            "https://example.invalid/concept",
            DerivationSourceKind.WEB_SOURCE,
        ),),
    )

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=tuple(seals),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert any(
        "unlearned" in item.description
        for item in outcome.report.active_remainders
    )


def test_wrong_analysis_object_cannot_validate(tmp_path) -> None:
    memory, _store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    structural = replace(structural, object_ref="concept:another@1")

    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )

    assert outcome.report.recommended_state is ConceptState.CANDIDATE
    assert any(
        item.kind.value == "INVALID_SCOPE"
        for item in outcome.report.active_remainders
    )


def test_concept_codec_rejects_tampered_derivation_seal(tmp_path) -> None:
    memory, _store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )
    encoded = encode_concept_record(outcome.record)
    encoded["derivation_seals"][0]["target_ref"] = "membership:rewritten"

    with pytest.raises(ValueError, match="digest mismatch"):
        decode_concept_record(encoded)


def test_validation_archive_detects_tampering(tmp_path) -> None:
    memory, store, proposed, runner = service(tmp_path)
    structural, epistemic = evidence_graphs(proposed, memory)
    outcome = runner.validate_and_store(
        proposed.concept_id,
        seals=complete_seals(proposed, memory),
        structural_graph=structural,
        epistemic_graph=epistemic,
    )
    raw = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    raw["recommended_state"] = "CANDIDATE"
    outcome.report_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ConceptValidationError, match="hash mismatch"):
        AtomicConceptValidationArchive(
            store.root / "validations"
        ).load(outcome.report.validation_id)
