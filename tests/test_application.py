from __future__ import annotations

import json
from pathlib import Path

import pytest

from fresta_diamond.application import DiamondApplication
from fresta_diamond.attention_memory import AttentionState, AttentionTransition
from fresta_diamond.attention_resolution import workspace_sheet_content
from fresta_diamond.cognitive_workspace import (
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.chat import ChatRole
from fresta_diamond.concepts import ConceptSignature, ConceptState
from fresta_diamond.crystallization import CrystalState
from fresta_diamond.sheet_decomposition import SheetDecompositionService
from fresta_diamond.prompt_boundary import read_inert_data
from fresta_diamond.reflection import ReflectionTrigger
from fresta_diamond.profiles import ProfileState, UserProfileClaim

from .test_concept_evidence import evidence_bundle


PERMISSIONS = ("llm.model:diamond-application-test",)
CATALOG_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "testdata"
    / "concept-catalog"
    / "notebooklm-ontology-index.json"
)


def response_bundle(element_id: str = "candidate:test-run") -> dict:
    return {
        "structural_evidence": {
            "analysis_id": "model:ignored",
            "object_ref": "model:ignored",
            "scope": "scope:cars",
            "analysis_depth": "CONTEXTUAL",
            "manifestations": [{
                "manifestation_id": "m1",
                "object_ref": "model:ignored",
                "description": "A bounded energy transformation claim.",
                "provenance": ["document:mechanics:p4"],
            }],
            "relations": [{
                "relation_id": "r1",
                "manifestation_id": "m1",
                "constraint_id": "c1",
                "forward_justification": "The source bounds the proposed claim.",
                "constraint_effect": "Only the attested transformation remains.",
                "return_witness": "The claim remains tied to its source.",
                "excluded_cost_id": "cost1",
                "scope": "scope:cars",
            }],
            "constraints": [{
                "constraint_id": "c1",
                "description": "Preserve source and bounded scope.",
                "scope": "scope:cars",
            }],
            "filters": [{
                "filter_id": "f1",
                "constraint_id": "c1",
                "manifestation_id": "m1",
                "excluded_cost_id": "cost1",
                "selection_justification": "Rejects claims beyond the source.",
            }],
            "excluded_costs": [{
                "cost_id": "cost1",
                "description": "Loss of source-bounded meaning.",
                "excluded_alternatives": ["unsupported generalization"],
            }],
            "groundings": [],
            "advisory_model_closed": True,
        },
        "candidate_assessments": [{
            "source_element_id": element_id,
            "claim_mode": "ATTESTATION",
            "premise_refs": [],
            "applied_constraints": [],
            "derivation_direction": None,
            "test_criterion": None,
            "horizon": None,
            "assumptions": [],
            "counterexample_searches": [],
        }],
    }


def test_persistent_learn_commits_and_reloads_memory(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs["messages"])
        return {
            "content": json.dumps(response_bundle()),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 100},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: "test-run",
    )
    outcome = app.learn_text(
        "Um motor transforma energia.",
        scope="scope:cars",
        provenance=("document:mechanics:p4",),
    )

    assert outcome.model_call_count == 1
    assert outcome.repair_attempts_used == 0
    assert outcome.result.execution.closure.structural_closed is True
    assert outcome.result.execution.closure.epistemic_closed is True
    assert outcome.stored_commit.path.exists()
    assert len(app.learning_commits()) == 1
    assert len(app.crystals(scope="scope:cars")) == 1
    assert app.crystals(scope="scope:cars")[0].state is CrystalState.PROVISIONAL
    assert app.concepts() == ()
    assert app.paths.journal.joinpath("journal-segments.jsonl").exists()
    assert len(app.journal_archive.segments()) >= 1

    restarted = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
    )
    assert restarted.learning_commits()[0].commit == outcome.stored_commit.commit
    assert restarted.crystals(scope="scope:cars")[0].content == (
        "Um motor transforma energia."
    )
    assert len(restarted.journal_archive.segments()) >= 1
    assert len(calls) == 1


def test_research_objective_proposes_queries_before_search(tmp_path) -> None:
    effects = []

    def adapter(_grant, **kwargs):
        effects.append(kwargs.get("messages"))
        return {
            "content": json.dumps({
                "queries": [{
                    "query_id": "q1",
                    "text": "Roman Empire administrative fragmentation",
                    "purpose": "find independent historical sources",
                    "preferred_source_types": ["ACADEMIC"],
                }],
            }),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 10},
        }

    def search_adapter(_grant, **kwargs):
        assert kwargs["queries"][0]["query_id"] == "q1"
        return {"results": []}

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
    )
    outcome = app.research_objective(
        objective="Analyse the fall of Rome",
        scope="scope:roman-history",
        search_adapter=search_adapter,
    )

    assert outcome.result.execution.state.value == "COMPLETED"
    assert outcome.source_artifact is not None
    assert outcome.learned == ()
    assert len(effects) == 1


def test_research_objective_normalizes_integer_model_query_ids(tmp_path) -> None:
    def adapter(_grant, **kwargs):
        return {
            "content": json.dumps({
                "queries": [{
                    "query_id": 1,
                    "text": "Roman Empire administrative fragmentation",
                    "purpose": "find independent historical sources",
                    "preferred_source_types": ["ACADEMIC"],
                }],
            }),
            "model": "diamond-application-test",
        }

    def search_adapter(_grant, *, queries, **_kwargs):
        assert queries[0]["query_id"] == "1"
        return {"results": []}

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
    )
    outcome = app.research_objective(
        objective="Analyse the fall of Rome",
        scope="scope:roman-history",
        search_adapter=search_adapter,
    )

    assert outcome.source_artifact is not None


def test_application_rejects_implicit_provenance(tmp_path) -> None:
    app = DiamondApplication(
        tmp_path,
        lambda *_args, **_kwargs: {},
        required_permissions=PERMISSIONS,
    )

    try:
        app.learn_text("candidate", provenance=())
    except ValueError as exc:
        assert "provenance" in str(exc)
    else:
        raise AssertionError("Missing provenance was accepted")


def test_application_stages_catalog_without_model_or_concept_write(
    tmp_path,
) -> None:
    calls = []

    def adapter(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Catalog staging must not invoke the model")

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
    )
    revision, = app.stage_concept_catalog(
        CATALOG_FIXTURE,
        ("notebooklm-concept-row-002",),
        scope="scope:ontology-catalog-review",
        objective_ref="objective:review-filter-nomination",
    )

    assert calls == []
    assert app.workspace.latest(revision.sheet_id) == revision
    assert app.concepts() == ()
    assert app.learning_commits() == ()


def test_concept_nomination_uses_persistent_active_crystals(tmp_path) -> None:
    run_ids = iter(("run-a", "run-b"))
    response_ids = iter(("candidate:run-a", "candidate:run-b"))

    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(response_bundle(next(response_ids))),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 100},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
    )
    for content in (
        "Um motor transforma energia.",
        "Componentes sustentam uma identidade funcional.",
    ):
        app.learn_text(
            content,
            scope="scope:cars",
            provenance=("document:mechanics:p4",),
        )
    crystals = app.crystals(scope="scope:cars")

    concept = app.propose_concept(
        canonical_name="Automóvel funcional",
        aliases=("Carro",),
        scope="scope:cars",
        crystal_ids=tuple(item.crystal_id for item in crystals),
        signature=ConceptSignature(
            characteristics=("identidade funcional delimitada",),
            relations=("componentes participam numa função coerente",),
            constraints=("a transformação preserva a função",),
            exclusions=("agregados sem função coerente",),
        ),
    )

    assert concept.state is ConceptState.CANDIDATE
    assert len(concept.memberships) == 2
    assert app.latest_concepts() == (concept,)
    restarted = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
    )
    assert restarted.latest_concepts() == (concept,)


def test_application_evaluates_candidate_without_giving_llm_authority(
    tmp_path,
) -> None:
    run_ids = iter(("run-a", "run-b"))
    response_ids = iter(("candidate:run-a", "candidate:run-b"))

    def adapter(_grant, **kwargs):
        messages = kwargs["messages"]
        if "Propose evidence for a concept candidate" in messages[0]["content"]:
            content = messages[1]["content"]
            return {
                "content": json.dumps(evidence_bundle(
                    read_inert_data(content, "concept_candidate")
                )),
                "model": "diamond-application-test",
            }
        return {
            "content": json.dumps(response_bundle(next(response_ids))),
            "model": "diamond-application-test",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
    )
    for content in (
        "Um motor transforma energia.",
        "Componentes sustentam uma identidade funcional.",
    ):
        app.learn_text(
            content,
            scope="scope:cars",
            provenance=("document:mechanics:p4",),
        )
    proposed = app.propose_concept(
        canonical_name="AutomÃ³vel funcional",
        aliases=("Carro",),
        scope="scope:cars",
        crystal_ids=tuple(
            item.crystal_id for item in app.crystals(scope="scope:cars")
        ),
        signature=ConceptSignature(
            characteristics=("identidade funcional delimitada",),
            relations=("componentes participam numa funÃ§Ã£o coerente",),
            constraints=("a transformaÃ§Ã£o preserva a funÃ§Ã£o",),
            exclusions=("agregados sem funÃ§Ã£o coerente",),
        ),
    )

    outcome = app.evaluate_concept(proposed.concept_id)

    assert outcome.model_call_count == 1
    assert outcome.validation is not None
    assert outcome.validation.report.recommended_state is ConceptState.VALIDATED
    assert outcome.validation.record.state is ConceptState.VALIDATED
    assert outcome.validation.record.version == 2
    assert app.concept_store.latest(proposed.concept_id).state is (
        ConceptState.VALIDATED
    )


def test_targeted_concept_gap_research_reenters_learn_before_evaluation(
    tmp_path,
) -> None:
    run_ids = iter(("run-a", "run-b"))
    concept_calls = 0

    def dynamic_learning_bundle(messages):
        data = read_inert_data(messages[1]["content"], "learning_candidates")
        candidates = data["candidates"]
        provenance = list(dict.fromkeys(
            source
            for candidate in candidates
            for source in candidate["provenance"]
        ))
        return {
            "structural_evidence": {
                "assembly_id": "SINGLE_WITNESS_CHAIN",
                "source_authority_id": "ORDINARY_ATTRIBUTED_SOURCE",
                "witness": {
                    "manifestation_description": (
                        "The supplied sources report bounded concept evidence."
                    ),
                    "manifestation_provenance": provenance,
                    "forward_justification": (
                        "The reports remain bounded by their explicit sources."
                    ),
                    "constraint_effect": (
                        "Only source-attributed content remains admissible."
                    ),
                    "return_witness": (
                        "The source reports survive without promotion authority."
                    ),
                    "constraint_description": (
                        "Preserve source, scope, and report status."
                    ),
                    "selection_justification": (
                        "Rejects unsupported generalization beyond the sources."
                    ),
                    "excluded_cost_description": "Loss of source boundaries.",
                    "excluded_alternatives": ["unattributed generalization"],
                },
                "advisory_model_closed": True,
            },
            "candidate_assessments": [{
                "source_element_id": candidate["source_element_id"],
                "classification_id": "ATTESTATION",
                "premise_refs": [],
                "applied_constraints": [],
                "derivation_direction": None,
                "test_criterion": None,
                "horizon": None,
                "assumptions": [],
                "counterexample_searches": [],
            } for candidate in candidates],
        }

    def adapter(_grant, **kwargs):
        nonlocal concept_calls
        messages = kwargs["messages"]
        if "Propose evidence for a concept candidate" in messages[0]["content"]:
            concept_calls += 1
            request = read_inert_data(messages[1]["content"], "concept_candidate")
            bundle = evidence_bundle(request, canonical_structure=True)
            if concept_calls == 1:
                bundle["derivation_seals"] = [
                    seal for seal in bundle["derivation_seals"]
                    if not seal["target_ref"].startswith("signature:exclusions:")
                ]
            return {"content": json.dumps(bundle), "model": "concept-test"}
        return {
            "content": json.dumps(dynamic_learning_bundle(messages)),
            "model": "learning-test",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
    )
    for content in (
        "Um motor transforma energia.",
        "Componentes sustentam uma identidade funcional.",
    ):
        app.learn_text(
            content,
            scope="scope:cars",
            provenance=("document:mechanics:p4",),
        )
    proposed = app.propose_concept(
        canonical_name="Automóvel funcional",
        scope="scope:cars",
        crystal_ids=tuple(
            item.crystal_id for item in app.crystals(scope="scope:cars")
        ),
        signature=ConceptSignature(
            characteristics=("identidade funcional delimitada",),
            relations=("componentes participam numa função coerente",),
            functions=("transformar energia em movimento",),
            constraints=("a transformação preserva a função",),
            exclusions=("agregados sem função coerente",),
        ),
    )
    search_calls = []

    def search_adapter(_grant, *, queries, **_kwargs):
        search_calls.append(queries)
        return {"results": [{
            "query_id": queries[0]["query_id"],
            "title": "Functional boundary",
            "snippet": (
                "A functional system excludes component aggregates that do "
                "not preserve the organized function."
            ),
            "url": "https://evidence.example/functional-boundary",
            "source_type": "ACADEMIC",
        }]}

    outcome = app.evaluate_and_resolve_concept(
        proposed.concept_id,
        search_adapter=search_adapter,
        max_queries=1,
        max_results_per_query=1,
    )
    assert outcome.initial_evaluation.validation is not None
    assert outcome.initial_evaluation.validation.report.recommended_state is (
        ConceptState.CANDIDATE
    )
    assert outcome.gap_resolution is not None
    resolved = outcome.gap_resolution

    assert len(search_calls) == 1
    assert [item["query_id"] for item in search_calls[0]] == [
        "query:boundaries"
    ]
    assert resolved.learning is not None
    assert resolved.revised_concept is not None
    assert len(resolved.revised_concept.memberships) == 3
    assert resolved.evaluation is not None
    assert resolved.evaluation.validation is not None
    assert resolved.evaluation.validation.record.state is ConceptState.VALIDATED
    assert resolved.evaluation.validation.record.version == 3


def test_attention_turn_materializes_committed_memory_from_same_app(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs["messages"])
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="bounded_attention"' in joined:
            return {
                "content": "A memória sustenta apenas uma atestação provisória.",
                "model": "diamond-application-test",
                "usage": {"total_tokens": 50},
            }
        return {
            "content": json.dumps(response_bundle()),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 100},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: "test-run",
        max_attention_tokens=2_000,
        max_response_tokens=300,
    )
    learned = app.learn_text(
        "Um motor transforma energia.",
        scope="scope:cars",
        provenance=("document:mechanics:p4",),
    )
    crystal = learned.stored_commit.commit.crystallization.crystals[0]
    context = app.create_attention_context(
        objective="Explicar o que a memória permite afirmar.",
        scope="scope:cars",
        summary="Uma aprendizagem provisória está disponível.",
        selected_refs=(crystal.crystal_id,),
    )

    turn = app.attention_turn(
        context.context_id,
        instruction="Responde sem promover a memória.",
        token_budget=1_000,
    )

    prompt = turn.result.execution.artifacts["prompt"].payload
    response = turn.result.execution.artifacts["response"].payload
    assert turn.model_call_count == 1
    assert prompt["projection_state"] == "READY"
    assert prompt["authority_manifest"] == ({
        "item_ref": crystal.crystal_id,
        "kind": "CRYSTAL",
        "evidence_state": "PROVISIONAL",
        "authority": "LEARNING_MEMORY:PROVISIONAL",
    },)
    assert response["authority"] == "MODEL_RESPONSE_UNVALIDATED"
    assert "provisória" in response["content"]
    assert len(calls) == 2


def test_llm_nomination_persists_only_a_concept_candidate(tmp_path) -> None:
    run_ids = iter(("concept-a", "concept-b"))
    learn_elements = iter(("candidate:concept-a", "candidate:concept-b"))

    def adapter(_grant, **kwargs):
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="concept_inputs"' in joined:
            trusted = read_inert_data(joined, "concept_inputs")
            ids = [item["crystal_id"] for item in trusted["crystals"]]
            nomination = {
                "decision": "PROPOSE",
                "canonical_name": "Automóvel funcional",
                "aliases": ["Carro"],
                "crystal_ids": ids,
                "parent_concept_ids": [],
                "signature": {
                    "characteristics": ["identidade funcional delimitada"],
                    "relations": ["componentes participam numa função"],
                    "functions": ["transformar energia"],
                    "constraints": ["preservar coerência funcional"],
                    "exclusions": ["agregados sem função"],
                    "examples": [],
                    "counterexamples": [],
                },
                "rationale": "Os cristais convergem num conceito limitado.",
            }
            return {
                "content": json.dumps(nomination),
                "model": "diamond-application-test",
                "usage": {"total_tokens": 80},
            }
        return {
            "content": json.dumps(response_bundle(next(learn_elements))),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 100},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
        max_response_tokens=500,
    )
    for content in (
        "Um motor transforma energia.",
        "Componentes preservam uma identidade funcional.",
    ):
        app.learn_text(
            content,
            scope="scope:cars",
            provenance=("document:mechanics:p4",),
        )

    outcome = app.nominate_concept(
        scope="scope:cars",
        objective="Verificar se os cristais sustentam um conceito comum.",
    )

    assert outcome.model_call_count == 1
    assert outcome.nomination is not None
    assert outcome.concept is not None
    assert outcome.concept.state is ConceptState.CANDIDATE
    assert outcome.concept.validation_refs == ()
    assert outcome.concept.promotion_authority is False
    assert app.latest_concepts() == (outcome.concept,)


def test_objective_retrieval_materializes_exact_memory_and_workspace_roots(
    tmp_path,
) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        messages = kwargs["messages"]
        joined = "\n".join(item["content"] for item in messages)
        calls.append(joined)
        if 'label="objective_retrieval_request"' in joined:
            request = read_inert_data(joined, "objective_retrieval_request")
            crystal = next(
                item for item in request["candidates"]
                if item["kind"] == "CRYSTAL"
            )
            workspace = next(
                item for item in request["candidates"]
                if item["kind"] == "WORKSPACE"
                and item["item_ref"].startswith("sheet:catalog:")
            )
            return {
                "content": json.dumps({
                    "decision": "SELECT",
                    "items": [
                        {
                            "item_ref": crystal["item_ref"],
                            "relevance": 0.9,
                            "contextual_roles": [1],
                            "rationale": "Atesta a manifestação pedida.",
                        },
                        {
                            "item_ref": workspace["item_ref"],
                            "relevance": 0.7,
                            "contextual_roles": [3],
                            "rationale": "Propõe uma moldura conceptual a rever.",
                        },
                    ],
                    "rationale": "As duas raízes são suficientes para o objetivo.",
                }),
                "model": "diamond-application-test",
                "usage": {"total_tokens": 80},
            }
        return {
            "content": json.dumps(response_bundle()),
            "model": "diamond-application-test",
            "usage": {"total_tokens": 100},
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: "test-run",
        max_attention_tokens=2_000,
        max_response_tokens=500,
    )
    learned = app.learn_text(
        "Um motor transforma energia.",
        scope="scope:cars",
        provenance=("document:mechanics:p4",),
    )
    crystal = learned.stored_commit.commit.crystallization.crystals[0]
    revision, = app.stage_concept_catalog(
        CATALOG_FIXTURE,
        ("notebooklm-concept-row-002",),
        scope="scope:cars",
        objective_ref="objective:explain-car",
    )

    outcome = app.retrieve_for_objective(
        scope="scope:cars",
        objective="Explicar a transformação funcional do automóvel.",
    )

    assert outcome.model_call_count == 1
    assert outcome.nomination is not None, (
        outcome.result.execution.state,
        tuple(
            item.description for item in outcome.result.execution.remainders
        ),
    )
    assert outcome.context is not None
    assert outcome.materialized is not None
    assert outcome.context.selected_refs == (crystal.crystal_id,)
    assert outcome.context.workspace_sheet_refs == (
        f"sheet:{revision.sheet_id}",
    )
    projection = outcome.materialized.projection
    assert projection.injection_ready is True
    selected = {item.item_ref: item for item in projection.selected}
    assert selected[crystal.crystal_id].contextual_roles == (1,)
    workspace_ref = f"sheet:{revision.sheet_id}"
    assert selected[workspace_ref].contextual_roles == (3,)
    assert selected[workspace_ref].authority == (
        "UNVALIDATED_WORKSPACE_PROPOSAL"
    )
    assert len(calls) == 2


def test_objective_retrieval_batches_sequentially_and_unions_nominations(
    tmp_path,
) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        joined = "\n".join(
            item["content"] for item in kwargs["messages"]
        )
        calls.append(joined)
        request = read_inert_data(joined, "objective_retrieval_request")
        target = next((
            item for item in request["candidates"]
            if "notebooklm-concept-row-008" in item["item_ref"]
        ), None)
        if target is None:
            proposal = {
                "decision": "NO_SELECTION",
                "items": [],
                "rationale": "This batch does not contain the requested method.",
            }
        else:
            proposal = {
                "decision": "SELECT",
                "items": [{
                    "item_ref": target["item_ref"],
                    "relevance": 1.0,
                    "contextual_roles": [1, 2, 3],
                    "rationale": "This sheet names the three-order method.",
                }],
                "rationale": "One exact sheet satisfies the objective.",
            }
        return {
            "content": json.dumps(proposal),
            "model": "diamond-application-test",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        max_attention_tokens=3_000,
        max_response_tokens=500,
    )
    app.stage_concept_catalog(
        CATALOG_FIXTURE,
        (
            "notebooklm-concept-row-002",
            "notebooklm-concept-row-003",
            "notebooklm-concept-row-008",
        ),
        scope="scope:ontology-method",
        objective_ref="objective:identify-three-orders",
    )

    outcome = app.retrieve_for_objective(
        scope="scope:ontology-method",
        objective="Selecionar o método explícito de análise em três ordens.",
        candidate_batch_tokens=800,
    )

    assert outcome.model_call_count == len(outcome.batch_results)
    assert outcome.model_call_count > 1
    assert len(calls) == outcome.model_call_count
    assert outcome.nomination is not None
    assert len(outcome.nomination.items) == 1
    selected = outcome.nomination.items[0]
    assert "notebooklm-concept-row-008" in selected.item_ref
    assert selected.source_authority == "UNVALIDATED_WORKSPACE_PROPOSAL"
    assert outcome.materialized is not None
    assert outcome.materialized.projection.injection_ready is True


def test_attention_turn_sleeps_and_atomically_resumes_pending_refs(
    tmp_path,
) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs["messages"])
        return {
            "content": "Resposta limitada ao batch atual.",
            "model": "diamond-application-test",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_attention_tokens=400,
        max_response_tokens=100,
    )
    for name, content in (("a", "A" * 500), ("b", "B" * 500)):
        app.workspace.save(SheetRevision(
            sheet_id=f"large-{name}",
            revision_number=1,
            title=f"Large sheet {name}",
            state=SheetState.DRAFT,
            elements=(SheetElement(
                element_id=f"note:{name}",
                kind=SheetElementKind.NOTE,
                content=content,
                scope="scope:sleep-test",
                provenance=(f"operator:{name}",),
            ),),
        ))
    context = app.create_attention_context(
        objective="Processar duas folhas sem exceder o budget.",
        scope="scope:sleep-test",
        summary="Duas folhas independentes aguardam processamento.",
        workspace_sheet_refs=("sheet:large-a", "sheet:large-b"),
    )

    first = app.attention_turn(
        context.context_id,
        instruction="Processa apenas o batch disponível.",
        token_budget=260,
    )

    assert first.continuation is not None
    assert first.continuation.reasons == ("TOKEN_BUDGET",)
    assert first.continuation.completed_refs
    assert first.continuation.pending_refs
    assert first.sleep_revision is not None
    assert first.sleep_revision.state is AttentionState.SUSPENDED
    assert app.attention_memory.active() is None

    resumed = app.resume_attention(first.continuation.checkpoint_id)

    assert resumed.state is AttentionState.ACTIVE
    assert resumed.transition is AttentionTransition.REACTIVATED
    assert resumed.workspace_sheet_refs == first.continuation.pending_refs
    assert resumed.selected_refs == ()
    assert resumed.previous_revision_id == first.sleep_revision.revision_id
    with pytest.raises(ValueError, match="latest safe sleep"):
        app.resume_attention(first.continuation.checkpoint_id)

    second = app.attention_turn(
        context.context_id,
        instruction="Processa o batch restante.",
        token_budget=260,
    )

    assert second.result.execution.artifacts["prompt"].payload[
        "projection_state"
    ] == "READY"
    assert second.continuation is None
    assert second.sleep_revision is None
    assert len(calls) == 2


def test_attention_zero_progress_decomposes_and_processes_first_batch(tmp_path) -> None:
    calls = []

    def adapter(_grant, **_kwargs):
        calls.append("called")
        return {"content": "processed bounded leaf", "model": "test"}

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_attention_tokens=300,
        max_response_tokens=100,
    )
    oversized = SheetRevision(
        sheet_id="oversized",
        revision_number=1,
        title="One oversized required sheet",
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="note:oversized",
            kind=SheetElementKind.NOTE,
            content="X" * 2_000,
            scope="scope:oversized",
            provenance=("operator:oversized",),
        ),),
    )
    app.workspace.save(oversized)
    context = app.create_attention_context(
        objective="Processar uma folha obrigatória demasiado grande.",
        scope="scope:oversized",
        summary="A folha ainda não foi decomposta.",
        selected_refs=("sheet:oversized",),
    )

    outcome = app.attention_turn(
        context.context_id,
        instruction="Não responder sem a evidência obrigatória.",
        token_budget=200,
    )

    assert calls == ["called"]
    assert outcome.model_call_count == 1
    assert outcome.result.execution.artifacts["prompt"].payload[
        "authority_manifest"
    ]
    assert outcome.decomposition is not None
    assert SheetDecompositionService(app.workspace).reconstruct(
        outcome.decomposition
    ) == workspace_sheet_content(oversized)
    assert outcome.continuation is not None
    assert outcome.continuation.completed_refs
    assert "sheet:oversized" not in outcome.continuation.pending_refs
    assert outcome.sleep_revision is not None
    assert outcome.sleep_revision.state is AttentionState.SUSPENDED
    assert app.attention_memory.active() is None

    resumed = app.resume_attention(outcome.continuation.checkpoint_id)
    assert resumed.workspace_sheet_refs == outcome.continuation.pending_refs
    processed = {
        item["item_ref"]
        for item in outcome.result.execution.artifacts["prompt"].payload[
            "authority_manifest"
        ]
    }
    for _batch in range(100):
        next_outcome = app.attention_turn(
            context.context_id,
            instruction="Continue with the next exact leaves.",
            token_budget=200,
        )
        batch_refs = {
            item["item_ref"]
            for item in next_outcome.result.execution.artifacts["prompt"].payload[
                "authority_manifest"
            ]
        }
        assert batch_refs
        assert processed.isdisjoint(batch_refs)
        processed.update(batch_refs)
        if next_outcome.continuation is None:
            break
        app.resume_attention(next_outcome.continuation.checkpoint_id)
    else:
        pytest.fail("Decomposed attention did not converge within 100 batches")

    assert processed == {
        item.target_ref for item in outcome.decomposition.leaf_refs
    }


def test_attention_can_leave_zero_progress_decomposition_explicit(tmp_path) -> None:
    calls = []

    def adapter(_grant, **_kwargs):
        calls.append("called")
        return {"content": "must not run", "model": "test"}

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_attention_tokens=300,
        max_response_tokens=100,
    )
    app.workspace.save(SheetRevision(
        sheet_id="oversized",
        revision_number=1,
        title="One oversized required sheet",
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="note:oversized",
            kind=SheetElementKind.NOTE,
            content="X" * 2_000,
            scope="scope:oversized",
            provenance=("operator:oversized",),
        ),),
    ))
    context = app.create_attention_context(
        objective="Process oversized evidence.",
        scope="scope:oversized",
        summary="Awaiting explicit decomposition.",
        selected_refs=("sheet:oversized",),
    )

    outcome = app.attention_turn(
        context.context_id,
        instruction="Do not answer without required evidence.",
        token_budget=200,
        auto_decompose=False,
    )

    assert calls == []
    assert outcome.decomposition is None
    assert outcome.continuation is not None
    assert outcome.continuation.completed_refs == ()
    with pytest.raises(ValueError, match="repair or decomposition"):
        app.resume_attention(outcome.continuation.checkpoint_id)


def test_active_scratch_sheet_can_start_blank_and_evolve_exactly(tmp_path) -> None:
    def adapter(*_args, **_kwargs):
        raise AssertionError("Scratch-sheet lifecycle must not call the model")

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
    )
    blank = SheetRevision(
        sheet_id="scratch:task",
        revision_id="scratch:revision:1",
        revision_number=1,
        title="Active task scratchpad",
        state=SheetState.DRAFT,
        elements=(),
    )
    created = app.create_attention_with_active_sheet(
        objective="Organizar temporariamente uma tarefa.",
        scope="scope:scratch-task",
        summary="A folha ativa começa vazia.",
        sheet=blank,
    )
    original_ref = created.context.active_sheet_ref
    assert original_ref is not None
    revised_sheet = SheetRevision(
        sheet_id=blank.sheet_id,
        revision_id="scratch:revision:2",
        revision_number=2,
        parent_revision_id=blank.revision_id,
        title=blank.title,
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="note:first",
            kind=SheetElementKind.NOTE,
            content="Primeiro detalhe temporário da tarefa.",
            scope="scope:scratch-task",
            provenance=(original_ref,),
        ),),
    )

    evolved = app.revise_active_sheet(
        created.context.context_id,
        revised_sheet,
        summary="A folha ativa contém agora um detalhe.",
    )

    assert evolved.context.active_sheet_ref != original_ref
    assert evolved.context.active_sheet_ref in (
        evolved.context.workspace_sheet_refs
    )
    assert original_ref not in evolved.context.workspace_sheet_refs
    assert app.workspace.resolve_reference(original_ref) == blank
    assert app.workspace.resolve_reference(
        evolved.context.active_sheet_ref
    ) == revised_sheet
    assert app.workspace.history(blank.sheet_id) == (blank, revised_sheet)
    assert len(app.attention_memory.history(created.context.context_id)) == 2


def test_chat_uses_attention_and_preserves_unvalidated_transcript(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="objective_retrieval_request"' in joined:
            request = read_inert_data(joined, "objective_retrieval_request")
            target = request["candidates"][0]
            return {
                "content": json.dumps({
                    "decision": "SELECT",
                    "items": [{
                        "item_ref": target["item_ref"],
                        "relevance": 0.8,
                        "contextual_roles": [2],
                        "rationale": "Exact context for the chat objective.",
                    }],
                    "rationale": "One bounded root is enough.",
                }),
                "model": "chat-test",
            }
        return {
            "content": "Resposta limitada ao contexto disponível.",
            "model": "chat-test",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_attention_tokens=1_000,
        max_response_tokens=200,
    )
    app.workspace.save(SheetRevision(
        sheet_id="chat-context",
        revision_number=1,
        title="Chat context",
        state=SheetState.STAGED,
        elements=(SheetElement(
            element_id="chat-context:note",
            kind=SheetElementKind.NOTE,
            content="Contexto delimitado para a conversa.",
            scope="scope:chat",
            provenance=("test:chat",),
        ),),
    ))

    started = app.start_chat(
        scope="scope:chat",
        objective="Conversar usando apenas o contexto delimitado.",
    )
    assert started.session is not None
    assert started.context is not None
    assert started.context.active_sheet_ref is not None
    assert started.model_call_count == 1

    turn = app.chat_turn(started.session.session_id, "O que podes afirmar?")

    assert turn.model_call_count == 1
    assert turn.assistant_message is not None
    assert turn.assistant_message.authority == "MODEL_RESPONSE_UNVALIDATED"
    assert [item.role.value for item in app.chat_messages(
        started.session.session_id
    )] == ["USER", "ASSISTANT"]
    assert [item.kind.value for item in turn.transcript.elements[-2:]] == [
        "USER_MESSAGE",
        "ASSISTANT_MESSAGE",
    ]
    assert app.learning_commits() == ()
    assert len(calls) == 2


def test_chat_can_start_without_candidates_or_inventing_memory(
    tmp_path,
) -> None:
    def adapter(_grant, **_kwargs):
        raise AssertionError("Empty retrieval must not call the model")

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.start_chat(
        scope="scope:new-chat",
        objective="Start without pretending prior memory is relevant.",
    )

    assert outcome.session is not None
    assert outcome.context is not None
    assert outcome.context.selected_refs == ()
    assert outcome.context.validated_refs == ()
    assert outcome.transcript is not None
    assert outcome.transcript.elements == ()
    assert outcome.retrieval is None
    assert outcome.model_call_count == 0


def test_chat_reflection_routes_through_controller_and_stores_proposal(
    tmp_path,
) -> None:
    def adapter(_grant, **kwargs):
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="reflection_request"' in joined:
            return {
                "content": json.dumps({
                    "target": "USER_PROFILE",
                    "category": "style",
                    "content": "Prefers bounded answers.",
                    "rationale": "Explicit collaboration signal.",
                }),
                "model": "reflection-test",
            }
        return {"content": "Resposta limitada.", "model": "reflection-test"}

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    started = app.start_chat(
        scope="scope:chat",
        objective="Preserve a bounded collaboration.",
    )
    app.chat_store.append(
        started.session.session_id,
        role=ChatRole.USER,
        content="Please keep answers bounded.",
        provenance=("operator:user-supplied",),
    )
    outcome = app.propose_chat_reflection(
        started.session.session_id,
        trigger=ReflectionTrigger.NEW_PREFERENCE,
    )

    assert outcome.proposal is not None
    assert outcome.proposal["authority"] == "REFLECTION_PROPOSAL_ONLY"
    assert isinstance(outcome.stored, UserProfileClaim)
    assert outcome.stored.state is ProfileState.PROPOSED
    assert app.user_profile_store.latest(outcome.stored.claim_id) == outcome.stored
