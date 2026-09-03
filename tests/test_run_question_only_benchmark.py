from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from fresta_diamond.concept_research import CONCEPT_SEARCH_PERMISSION
from fresta_diamond.contracts import EffectGrant
from fresta_diamond.question_only_benchmark import (
    QuestionOnlyArm,
    QuestionOnlyArmResult,
    QuestionOnlyBenchmarkCase,
    QuestionOnlyBenchmarkConfig,
    QuestionOnlyBenchmarkResult,
    QuestionOnlyComparison,
    QuestionOnlyEpisodeResult,
)
from scripts import run_question_only_benchmark as script


def test_parse_args_requires_an_explicit_data_root() -> None:
    with pytest.raises(SystemExit):
        script.parse_args([])


def test_build_config_rejects_invalid_episode_budget(tmp_path: Path) -> None:
    args = script.parse_args([
        "--data-root",
        str(tmp_path / "runs"),
        "--max-episodes",
        "0",
    ])

    with pytest.raises(ValueError, match="episode budget"):
        script.build_config(args)


def test_llm_adapter_wires_endpoint_model_and_permissions(tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def transport(endpoint, payload, timeout):
        observed.update(endpoint=endpoint, payload=payload, timeout=timeout)
        return {
            "model": "qwen/qwen3-14b",
            "choices": [{"message": {"content": "{\"ok\": true}"}}],
            "usage": {"total_tokens": 7},
        }

    args = script.parse_args([
        "--data-root",
        str(tmp_path / "question-only"),
        "--base-url",
        "http://127.0.0.1:1234",
        "--model",
        "qwen/qwen3-14b",
        "--timeout",
        "17",
        "--max-tokens",
        "100",
    ])
    adapter = script.build_llm_adapter(args, transport=transport)
    result = adapter(
        _grant(),
        messages=({"role": "user", "content": "bounded"},),
        max_tokens=999,
    )

    assert observed["endpoint"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert observed["payload"]["model"] == "qwen/qwen3-14b"
    assert observed["payload"]["max_tokens"] == 100
    assert observed["timeout"] == 17
    assert result["content"] == "{\"ok\": true}"


def test_search_adapter_converts_academic_results_to_source_units(
    tmp_path: Path,
) -> None:
    calls: list[tuple[EffectGrant, tuple, int]] = []

    class FakeAcademicSearchAdapter:
        timeout_seconds = 11.0
        user_agent = "fake-agent"

        def __call__(self, grant, *, queries, max_results_per_query):
            calls.append((grant, queries, max_results_per_query))
            return {
                "results": [
                    {
                        "query_id": queries[0]["query_id"],
                        "title": "Western Roman Empire overview",
                        "snippet": "The empire fell through multiple pressures.",
                        "url": "https://example.test/roman",
                        "source_type": "ACADEMIC",
                        "source_lineage": "library:openalex",
                    }
                ]
            }

    args = script.parse_args([
        "--data-root",
        str(tmp_path / "question-only"),
        "--case-id",
        "roman-fall",
    ])
    adapter = script.build_search_adapter(args, library_adapter=FakeAcademicSearchAdapter())
    result = adapter(
        _grant(),
        question="Analyse the fall of the Western Roman Empire.",
        queries=(
            {
                "query_id": "q1",
                "text": "Western Roman Empire decline factors",
                "purpose": "Find bounded historical sources for the question.",
                "preferred_source_types": ["ACADEMIC"],
            },
        ),
        max_results_per_query=1,
    )

    assert calls[0][0].permissions == (CONCEPT_SEARCH_PERMISSION,)
    assert calls[0][2] == 1
    assert len(result["source_units"]) == 1
    unit = result["source_units"][0]
    assert unit["source_locator"] == "https://example.test/roman"
    assert unit["content_hash"] == sha256(
        "The empire fell through multiple pressures.".encode("utf-8")
    ).hexdigest()
    assert unit["authority"] == "UNVALIDATED_EXTERNAL_EVIDENCE"


def test_run_wires_data_root_and_benchmark_config(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}
    case = QuestionOnlyBenchmarkCase("roman-fall", "Analyse the fall of the Western Roman Empire.")
    config = QuestionOnlyBenchmarkConfig()
    result = _benchmark_result(case, config)

    class FakeLibraryAdapter:
        timeout_seconds = 5.0
        user_agent = "fake-library"

        def __call__(self, grant, *, queries, max_results_per_query):
            return {"results": []}

    def fake_run_question_only_benchmark(
        received_case,
        llm_adapter,
        search_adapter,
        *,
        config,
        fresta_root,
    ):
        observed.update(
            case=received_case,
            llm_adapter=llm_adapter,
            search_adapter=search_adapter,
            config=config,
            fresta_root=fresta_root,
        )
        return result

    monkeypatch.setattr(script, "run_question_only_benchmark", fake_run_question_only_benchmark)

    args = script.parse_args([
        "--data-root",
        str(tmp_path / "question-only"),
        "--case-id",
        "roman-fall",
    ])
    returned = script.run(
        args,
        transport=lambda *_args, **_kwargs: {
            "model": "qwen/qwen3-14b",
            "choices": [{"message": {"content": "{\"queries\": []}"}}],
            "usage": {},
        },
        library_adapter=FakeLibraryAdapter(),
    )

    assert returned is result
    assert observed["case"] == case
    assert observed["config"] == config
    assert observed["fresta_root"] == (tmp_path / "question-only" / "fresta" / "roman-fall").resolve()
    assert isinstance(observed["llm_adapter"], script.QuestionOnlyLocalLlmAdapter)
    assert isinstance(observed["search_adapter"], script.QuestionOnlyAcademicSearchAdapter)


def _grant() -> EffectGrant:
    return EffectGrant(
        plan_id="plan",
        node_id="node",
        module_id="provider",
        operation_id="operation",
        effects=("llm.generate", "internet.search"),
        permissions=(),
    )


def _benchmark_result(
    case: QuestionOnlyBenchmarkCase,
    config: QuestionOnlyBenchmarkConfig,
) -> QuestionOnlyBenchmarkResult:
    baseline_episode = QuestionOnlyEpisodeResult(
        episode_index=0,
        state="PAUSED",
        checkpoint_id="checkpoint:baseline",
        stored_checkpoint_id=None,
        query_count=1,
        evidence_unit_count=0,
        model_call_count=1,
        remainder_kinds=(),
    )
    fresta_episodes = (
        QuestionOnlyEpisodeResult(
            episode_index=0,
            state="PAUSED",
            checkpoint_id="checkpoint:fresta:0",
            stored_checkpoint_id="stored:fresta:0",
            query_count=1,
            evidence_unit_count=0,
            model_call_count=1,
            remainder_kinds=(),
        ),
        QuestionOnlyEpisodeResult(
            episode_index=1,
            state="COMPLETED",
            checkpoint_id=None,
            stored_checkpoint_id=None,
            query_count=1,
            evidence_unit_count=1,
            model_call_count=1,
            remainder_kinds=(),
        ),
    )
    baseline = QuestionOnlyArmResult(
        arm=QuestionOnlyArm.BASELINE,
        case_id=case.case_id,
        question=case.question,
        config=config,
        episodes=(baseline_episode,),
        query_proposal=None,
        evidence_bundle=None,
        checkpoint_ids=(),
        persistence_enabled=False,
        continuation_recorded=False,
        provenance_preserved=True,
        phi_closed=False,
        model_call_count=1,
    )
    fresta = QuestionOnlyArmResult(
        arm=QuestionOnlyArm.FRESTA,
        case_id=case.case_id,
        question=case.question,
        config=config,
        episodes=fresta_episodes,
        query_proposal=None,
        evidence_bundle=None,
        checkpoint_ids=("stored:fresta:0",),
        persistence_enabled=True,
        continuation_recorded=True,
        provenance_preserved=True,
        phi_closed=False,
        model_call_count=2,
    )
    comparison = QuestionOnlyComparison(
        same_question=True,
        same_per_call_budget=True,
        same_token_budget=True,
        same_result_budget=True,
        baseline_completed=False,
        fresta_completed=True,
        baseline_episode_count=1,
        fresta_episode_count=2,
        baseline_checkpoint_count=0,
        fresta_checkpoint_count=1,
        baseline_continuation_recorded=False,
        fresta_continuation_recorded=True,
        baseline_provenance_preserved=True,
        fresta_provenance_preserved=True,
        baseline_phi_closed=False,
        fresta_phi_closed=False,
        model_call_delta=1,
    )
    return QuestionOnlyBenchmarkResult(
        case=case,
        config=config,
        baseline=baseline,
        fresta=fresta,
        comparison=comparison,
    )
