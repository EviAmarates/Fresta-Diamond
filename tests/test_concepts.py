from __future__ import annotations

from dataclasses import replace
import json

import pytest

from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptCandidateBuilder,
    ConceptParentLink,
    ConceptSignature,
    ConceptState,
    ConceptStoreError,
    DerivationContribution,
    DerivationSeal,
    DerivationSource,
    DerivationSourceKind,
    decode_concept_record,
    encode_concept_record,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)
from .test_learning_crystal_gate import evaluated


def committed_memory(tmp_path, *, claim_mode: str = "ATTESTATION"):
    proposal, result = evaluated(claim_mode=claim_mode)
    memory = AtomicDiamondLearningMemory(tmp_path / "memory")
    memory.commit(proposal, result)
    return memory


def signature() -> ConceptSignature:
    return ConceptSignature(
        characteristics=("bounded functional identity",),
        relations=("components participate in a coherent function",),
        constraints=("the function must survive admissible transformation",),
        exclusions=("arrangements with no coherent function",),
    )


def candidate(memory, *, concept_id: str = "concept:automobile"):
    crystals = memory.crystals(policy=CrystalRetrievalPolicy.FALLBACK)
    return ConceptCandidateBuilder(
        memory,
        id_factory=lambda: concept_id,
        clock=lambda: "2026-07-26T00:00:00+00:00",
    ).propose(
        canonical_name="Automóvel",
        aliases=("Carro",),
        scope="scope:cars",
        crystal_ids=tuple(item.crystal_id for item in crystals),
        signature=signature(),
    )


def test_candidate_uses_committed_crystals_without_intrinsic_orders(
    tmp_path,
) -> None:
    memory = committed_memory(tmp_path)

    concept = candidate(memory)
    encoded = encode_concept_record(concept)

    assert concept.state is ConceptState.CANDIDATE
    assert len(concept.memberships) == 2
    assert concept.validation_refs == ()
    assert concept.promotion_authority is False
    assert "order" not in encoded
    assert "order_profile" not in encoded


def test_deferred_crystal_requires_explicit_fallback_policy(tmp_path) -> None:
    memory = committed_memory(tmp_path, claim_mode="OBSERVATION")
    all_crystals = memory.crystals(policy=CrystalRetrievalPolicy.AUDIT)
    builder = ConceptCandidateBuilder(memory)
    kwargs = {
        "canonical_name": "Functional system",
        "scope": "scope:cars",
        "crystal_ids": tuple(item.crystal_id for item in all_crystals),
        "signature": signature(),
    }

    with pytest.raises(ConceptStoreError, match="unavailable crystals"):
        builder.propose(**kwargs)

    proposed = builder.propose(
        **kwargs,
        retrieval_policy=CrystalRetrievalPolicy.FALLBACK,
    )
    assert len(proposed.memberships) == 2


def test_store_preserves_versioned_name_and_alias_history(tmp_path) -> None:
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    first = candidate(memory)
    store.save(first)

    second = store.revise(
        first.concept_id,
        canonical_name="Automóvel funcional",
        aliases=("Automóvel", "Carro"),
        reason="narrower name after review",
    )

    assert second.version == 2
    assert second.previous_version_ref == first.version_ref
    assert second.canonical_name == "Automóvel funcional"
    assert second.aliases == ("Automóvel", "Carro")
    assert store.history(first.concept_id) == (first, second)


def test_parent_links_require_known_concepts_and_remain_candidates(
    tmp_path,
) -> None:
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    child = replace(
        candidate(memory),
        parent_links=(ConceptParentLink("concept:vehicle"),),
    )

    with pytest.raises(ConceptStoreError, match="Unknown parent"):
        store.save(child)


def test_candidate_hierarchy_rejects_cycles(tmp_path) -> None:
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    vehicle = candidate(memory, concept_id="concept:vehicle")
    store.save(vehicle)
    automobile = replace(
        candidate(memory, concept_id="concept:automobile"),
        parent_links=(ConceptParentLink("concept:vehicle"),),
    )
    store.save(automobile)

    with pytest.raises(ConceptStoreError, match="cycle"):
        store.revise(
            "concept:vehicle",
            parent_links=(ConceptParentLink("concept:automobile"),),
            reason="invalid reciprocal parent",
        )


def test_store_refuses_validation_without_concept_validation_operation(
    tmp_path,
) -> None:
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    proposed = candidate(memory)
    forged = replace(
        proposed,
        state=ConceptState.VALIDATED,
        derivation_seals=(DerivationSeal(
            seal_id="seal:invented",
            target_ref="signature:characteristics:invented",
            contribution=DerivationContribution.DIRECT,
            sources=(DerivationSource(
                "document:invented",
                DerivationSourceKind.DOCUMENT,
            ),),
            analysis_id="analysis:invented",
            scope=proposed.scope,
        ),),
        validation_refs=("analysis:invented",),
    )

    with pytest.raises(PermissionError, match="not installed"):
        store.save(forged)


def test_codec_rejects_legacy_intrinsic_order_fields(tmp_path) -> None:
    memory = committed_memory(tmp_path)
    encoded = encode_concept_record(candidate(memory))
    encoded["order"] = 3

    with pytest.raises(ValueError, match="intrinsic orders"):
        decode_concept_record(encoded)


def test_concept_requires_two_distinct_members(tmp_path) -> None:
    memory = committed_memory(tmp_path)
    one = memory.crystals()[0]

    with pytest.raises(ValueError, match="two distinct"):
        ConceptCandidateBuilder(memory).propose(
            canonical_name="Micro-topic",
            scope="scope:cars",
            crystal_ids=(one.crystal_id,),
            signature=signature(),
        )


def test_store_detects_historical_tampering(tmp_path) -> None:
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    path = store.save(candidate(memory))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["canonical_name"] = "Rewritten silently"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ConceptStoreError, match="hash mismatch"):
        store.records()
