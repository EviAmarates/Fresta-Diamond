from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fresta_diamond.question_only_benchmark import (
    QuestionOnlyArm,
    QuestionOnlyBenchmarkCase,
    QuestionOnlyBenchmarkConfig,
    QuestionOnlyBenchmarkResult,
    run_question_only_benchmark,
)


QUESTION = "Analyse the fall of the Western Roman Empire."


def _adapters():
    calls: list[tuple[str, dict]] = []

    def llm_adapter(_grant, **kwargs):
        calls.append(("llm", kwargs))
        messages = kwargs["messages"]
        assert len(messages) == 2
        assert QUESTION in messages[1]["content"]
        return {
            "content": json.dumps({
                "queries": [{
                    "query_id": "q1",
                    "text": "Western Roman Empire decline factors",
                    "purpose": "Find bounded historical sources for the question.",
                    "preferred_source_types": ["ACADEMIC"],
                }],
            }),
            "model": "question-only-test",
            "usage": {"total_tokens": 11},
        }

    def search_adapter(_grant, **kwargs):
        calls.append(("search", kwargs))
        assert kwargs["question"] == QUESTION
        assert kwargs["max_results_per_query"] == 1
        assert kwargs["queries"][0]["query_id"] == "q1"
        locator = "https://example.test/roman-empire"
        content = "The Western Roman Empire fell through multiple pressures."
        return {
            "source_units": [{
                "evidence_id": "evidence:q1",
                "query_id": "q1",
                "title": "Western Roman Empire overview",
                "content": content,
                "source_locator": locator,
                "source_type": "ACADEMIC",
                "retrieved_at": "2026-09-03T22:44:00Z",
                "content_hash": sha256(content.encode("utf-8")).hexdigest(),
                "authority": "UNVALIDATED_EXTERNAL_EVIDENCE",
                "source_document_ref": locator,
                "extracted_unit_ref": "unit:q1",
                "provenance": [locator],
                "source_lineage": "library:roman-history",
            }],
        }

    return calls, llm_adapter, search_adapter


def _run(tmp_path: Path) -> tuple[QuestionOnlyBenchmarkResult, list[tuple[str, dict]]]:
    calls, llm_adapter, search_adapter = _adapters()
    case = QuestionOnlyBenchmarkCase("roman-fall", QUESTION)
    config = QuestionOnlyBenchmarkConfig(
        per_call_operation_budget=1,
        max_queries=1,
        max_results_per_query=1,
        query_max_tokens=128,
        max_episodes=2,
    )
    result = run_question_only_benchmark(
        case,
        llm_adapter,
        search_adapter,
        config=config,
        fresta_root=tmp_path / "fresta",
    )
    return result, calls


def test_question_only_runner_keeps_baseline_isolated(tmp_path: Path) -> None:
    result, calls = _run(tmp_path)

    assert result.baseline.arm is QuestionOnlyArm.BASELINE
    assert result.baseline.persistence_enabled is False
    assert result.baseline.continuation_recorded is False
    assert result.baseline.checkpoint_ids == ()
    assert result.baseline.evidence_bundle is None
    assert result.baseline.provenance_preserved is True
    assert result.baseline.phi_closed is False
    assert result.baseline.episodes[-1].state == "PAUSED"
    assert result.baseline.episodes[0].stored_checkpoint_id is None

    assert result.fresta.arm is QuestionOnlyArm.FRESTA
    assert result.fresta.persistence_enabled is True
    assert result.fresta.continuation_recorded is True
    assert len(result.fresta.checkpoint_ids) == 1
    assert result.fresta.evidence_bundle is not None
    assert result.fresta.provenance_preserved is True
    assert result.fresta.phi_closed is False
    assert [episode.state for episode in result.fresta.episodes] == [
        "PAUSED",
        "COMPLETED",
    ]
    assert result.fresta.episodes[0].stored_checkpoint_id is not None
    assert result.fresta.episodes[1].stored_checkpoint_id is None

    assert [kind for kind, _ in calls] == ["llm", "llm", "search"]


def test_question_only_runner_continues_through_bounded_episodes(
    tmp_path: Path,
) -> None:
    result, _calls = _run(tmp_path)

    assert result.fresta.episodes[0].query_count == 1
    assert result.fresta.episodes[0].evidence_unit_count == 0
    assert result.fresta.episodes[0].model_call_count == 1
    assert result.fresta.episodes[1].query_count == 1
    assert result.fresta.episodes[1].evidence_unit_count == 1
    assert result.fresta.episodes[1].model_call_count == 1
    assert result.fresta.model_call_count == 2
    assert result.comparison.baseline_completed is False
    assert result.comparison.fresta_completed is True
    assert result.comparison.model_call_delta == 1


def test_question_only_runner_metric_shape(tmp_path: Path) -> None:
    result, _calls = _run(tmp_path)

    assert result.comparison.same_question is True
    assert result.comparison.same_per_call_budget is True
    assert result.comparison.same_token_budget is True
    assert result.comparison.same_result_budget is True
    assert result.comparison.baseline_episode_count == 1
    assert result.comparison.fresta_episode_count == 2
    assert result.comparison.baseline_checkpoint_count == 0
    assert result.comparison.fresta_checkpoint_count == 1
    assert result.comparison.baseline_continuation_recorded is False
    assert result.comparison.fresta_continuation_recorded is True
    assert result.comparison.baseline_provenance_preserved is True
    assert result.comparison.fresta_provenance_preserved is True
    assert result.comparison.baseline_phi_closed is False
    assert result.comparison.fresta_phi_closed is False
