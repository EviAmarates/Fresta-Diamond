from __future__ import annotations

import json

from fresta_diamond.concept_nomination import (
    ConceptNominationDecision,
    LlmConceptNominationOperation,
    build_concept_nomination_request,
    concept_nomination_blueprint,
    decode_concept_nomination,
    register_concept_nomination_provider,
)
from fresta_diamond.concepts import AtomicConceptStore
from fresta_diamond.contracts import ExecutionState
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.registry import ModuleRegistry

from .test_concepts import committed_memory


PERMISSIONS = ("llm.model:concept-nomination-test",)


def proposal(crystal_ids, **overrides):
    value = {
        "decision": "PROPOSE",
        "canonical_name": "Automóvel funcional",
        "aliases": ["Carro"],
        "crystal_ids": list(crystal_ids),
        "parent_concept_ids": [],
        "signature": {
            "characteristics": ["identidade funcional delimitada"],
            "relations": ["componentes participam numa função"],
            "functions": ["transformar energia em movimento"],
            "constraints": ["a função deve permanecer coerente"],
            "exclusions": ["agregados sem função"],
            "examples": [],
            "counterexamples": [],
        },
        "rationale": "Os dois cristais sustentam uma unidade intensional.",
    }
    value.update(overrides)
    return value


def run(tmp_path, response):
    memory = committed_memory(tmp_path)
    store = AtomicConceptStore(tmp_path / "concepts")
    crystals = memory.crystals()
    request = build_concept_nomination_request(
        memory,
        store,
        scope="scope:cars",
        objective="Procurar um conceito funcional delimitado.",
        crystal_ids=tuple(item.crystal_id for item in crystals),
    )
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(response(tuple(item.crystal_id for item in crystals))),
            "model": "concept-nomination-test",
            "usage": {"total_tokens": 100},
        }

    registry = ModuleRegistry()
    register_concept_nomination_provider(
        registry,
        required_permissions=PERMISSIONS,
        operation=LlmConceptNominationOperation(max_tokens=500),
    )
    result = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": adapter}),
    ).execute(
        concept_nomination_blueprint(PERMISSIONS),
        "Nominate without validation",
        {"request": request},
    )
    return result, calls, crystals


def test_llm_can_nominate_only_supplied_crystals(tmp_path) -> None:
    result, calls, crystals = run(tmp_path, proposal)

    assert result.execution.state is ExecutionState.COMPLETED
    assert len(calls) == 1
    nomination = decode_concept_nomination(
        result.execution.artifacts["nomination"]
    )
    assert nomination.decision is ConceptNominationDecision.PROPOSE
    assert nomination.crystal_ids == tuple(item.crystal_id for item in crystals)
    assert nomination.scope == "scope:cars"
    assert nomination.authority == "UNVALIDATED_CONCEPT_NOMINATION"


def test_llm_can_refuse_to_fabricate_a_concept(tmp_path) -> None:
    def no_concept(_ids):
        return {
            "decision": "NO_CONCEPT",
            "rationale": "Os cristais ainda não formam uma unidade intensional.",
        }

    result, calls, _ = run(tmp_path, no_concept)
    nomination = decode_concept_nomination(
        result.execution.artifacts["nomination"]
    )

    assert result.execution.state is ExecutionState.COMPLETED
    assert len(calls) == 1
    assert nomination.decision is ConceptNominationDecision.NO_CONCEPT
    assert nomination.canonical_name is None
    assert nomination.crystal_ids == ()


def test_invented_crystal_fails_before_a_nomination_exists(tmp_path) -> None:
    def invented(ids):
        return proposal((*ids, "crystal:invented"))

    result, calls, _ = run(tmp_path, invented)

    assert len(calls) == 1
    assert result.execution.state is ExecutionState.FAILED
    assert "nomination" not in result.execution.artifacts
    assert any(
        "invented crystal" in item.description.lower()
        for item in result.execution.remainders
    )
