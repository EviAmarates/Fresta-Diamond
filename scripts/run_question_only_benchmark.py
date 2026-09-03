"""Run one local question-only benchmark case with explicit adapters."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.concept_research import (  # noqa: E402
    AcademicLibrarySearchAdapter,
    CONCEPT_SEARCH_PERMISSION,
)
from fresta_diamond.contracts import EffectGrant  # noqa: E402
from fresta_diamond.question_only_benchmark import (  # noqa: E402
    QuestionOnlyBenchmarkCase,
    QuestionOnlyBenchmarkConfig,
    QuestionOnlyBenchmarkResult,
    run_question_only_benchmark,
)


DEFAULT_BASE_URL = "http://127.0.0.1:1234"
DEFAULT_MODEL = "qwen/qwen3-14b"
DEFAULT_CASE_ID = "western-roman-empire-fall"
DEFAULT_QUESTION = "Analyse the fall of the Western Roman Empire."


@dataclass(frozen=True)
class QuestionOnlyLocalLlmAdapter:
    adapter: OpenAICompatibleChatAdapter

    def __call__(self, grant: EffectGrant, **kwargs: Any) -> Mapping[str, Any]:
        return self.adapter(
            _grant_with_permissions(grant, self.adapter.required_permissions),
            **kwargs,
        )


@dataclass(frozen=True)
class QuestionOnlyAcademicSearchAdapter:
    adapter: AcademicLibrarySearchAdapter

    def __call__(
        self,
        grant: EffectGrant,
        *,
        question: str,
        queries: tuple[Mapping[str, Any], ...],
        max_results_per_query: int,
    ) -> Mapping[str, Any]:
        del question
        response = self.adapter(
            _grant_with_permissions(grant, (CONCEPT_SEARCH_PERMISSION,)),
            queries=queries,
            max_results_per_query=max_results_per_query,
        )
        raw_results = response.get("results")
        if not isinstance(raw_results, (list, tuple)):
            raise ValueError("Academic search adapter returned malformed results")
        query_ids = {
            _text(query, "query_id")
            for query in queries
        }
        per_query: dict[str, int] = {query_id: 0 for query_id in query_ids}
        source_units: list[dict[str, Any]] = []
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for index, item in enumerate(raw_results):
            if not isinstance(item, Mapping):
                raise TypeError("Academic search adapter result must be an object")
            query_id = _text(item, "query_id")
            if query_id not in query_ids:
                raise ValueError("Academic search adapter returned an unknown query")
            if per_query[query_id] >= max_results_per_query:
                continue
            title = _text(item, "title")
            content = _optional_text(item, "snippet") or title
            url = _text(item, "url")
            source_type = _text(item, "source_type")
            source_lineage = _optional_text(item, "source_lineage")
            unit_id = f"{query_id}:{index}"
            source_units.append({
                "evidence_id": unit_id,
                "query_id": query_id,
                "title": title,
                "content": content,
                "source_locator": url,
                "source_type": source_type,
                "retrieved_at": retrieved_at,
                "content_hash": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
                "authority": "UNVALIDATED_EXTERNAL_EVIDENCE",
                "source_document_ref": url,
                "extracted_unit_ref": unit_id,
                "provenance": [url],
                "source_lineage": source_lineage or "library:academic",
            })
            per_query[query_id] += 1
        return {"source_units": source_units}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one question-only benchmark case with an explicit local "
            "OpenAI-compatible model and academic search adapter."
        )
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--search-timeout", type=float, default=20.0)
    parser.add_argument(
        "--search-user-agent",
        default="Fresta-Diamond/0.1 question-only-benchmark",
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--per-call-operation-budget", type=int, default=1)
    parser.add_argument("--max-queries", type=int, default=3)
    parser.add_argument("--max-results-per-query", type=int, default=2)
    parser.add_argument("--query-max-tokens", type=int, default=512)
    parser.add_argument("--max-episodes", type=int, default=2)
    return parser.parse_args(argv)


def build_case(args: argparse.Namespace) -> QuestionOnlyBenchmarkCase:
    return QuestionOnlyBenchmarkCase(args.case_id, args.question)


def build_config(args: argparse.Namespace) -> QuestionOnlyBenchmarkConfig:
    return QuestionOnlyBenchmarkConfig(
        per_call_operation_budget=args.per_call_operation_budget,
        max_queries=args.max_queries,
        max_results_per_query=args.max_results_per_query,
        query_max_tokens=args.query_max_tokens,
        max_episodes=args.max_episodes,
    )


def build_llm_adapter(
    args: argparse.Namespace,
    *,
    transport: Callable[[str, Mapping[str, Any], float], Mapping[str, Any]] | None = None,
) -> QuestionOnlyLocalLlmAdapter:
    return QuestionOnlyLocalLlmAdapter(
        OpenAICompatibleChatAdapter(
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
            max_tokens=args.max_tokens,
            transport=transport,
        )
    )


def build_search_adapter(
    args: argparse.Namespace,
    *,
    library_adapter: AcademicLibrarySearchAdapter | None = None,
) -> QuestionOnlyAcademicSearchAdapter:
    return QuestionOnlyAcademicSearchAdapter(
        library_adapter
        or AcademicLibrarySearchAdapter(
            timeout_seconds=args.search_timeout,
            user_agent=args.search_user_agent,
        )
    )


def run(
    args: argparse.Namespace,
    *,
    transport: Callable[[str, Mapping[str, Any], float], Mapping[str, Any]] | None = None,
    library_adapter: AcademicLibrarySearchAdapter | None = None,
) -> QuestionOnlyBenchmarkResult:
    data_root = args.data_root.resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    case = build_case(args)
    config = build_config(args)
    llm_adapter = build_llm_adapter(args, transport=transport)
    search_adapter = build_search_adapter(args, library_adapter=library_adapter)
    fresta_root = data_root / "fresta" / case.case_id
    result = run_question_only_benchmark(
        case,
        llm_adapter,
        search_adapter,
        config=config,
        fresta_root=fresta_root,
    )
    print(
        json.dumps(
            summarize_result(
                result,
                data_root=data_root,
                fresta_root=fresta_root,
                llm_adapter=llm_adapter,
                search_adapter=search_adapter,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return result


def summarize_result(
    result: QuestionOnlyBenchmarkResult,
    *,
    data_root: Path,
    fresta_root: Path,
    llm_adapter: QuestionOnlyLocalLlmAdapter,
    search_adapter: QuestionOnlyAcademicSearchAdapter,
) -> Mapping[str, Any]:
    return {
        "case_id": result.case.case_id,
        "question": result.case.question,
        "data_root": str(data_root),
        "fresta_root": str(fresta_root),
        "llm": {
            "base_url": llm_adapter.adapter.base_url,
            "model": llm_adapter.adapter.model,
            "timeout_seconds": llm_adapter.adapter.timeout_seconds,
            "max_tokens": llm_adapter.adapter.max_tokens,
        },
        "search": {
            "timeout_seconds": search_adapter.adapter.timeout_seconds,
            "user_agent": search_adapter.adapter.user_agent,
        },
        "comparison": {
            "same_question": result.comparison.same_question,
            "same_per_call_budget": result.comparison.same_per_call_budget,
            "same_token_budget": result.comparison.same_token_budget,
            "same_result_budget": result.comparison.same_result_budget,
            "baseline_completed": result.comparison.baseline_completed,
            "fresta_completed": result.comparison.fresta_completed,
            "baseline_episode_count": result.comparison.baseline_episode_count,
            "fresta_episode_count": result.comparison.fresta_episode_count,
            "baseline_checkpoint_count": result.comparison.baseline_checkpoint_count,
            "fresta_checkpoint_count": result.comparison.fresta_checkpoint_count,
            "baseline_continuation_recorded": (
                result.comparison.baseline_continuation_recorded
            ),
            "fresta_continuation_recorded": (
                result.comparison.fresta_continuation_recorded
            ),
            "baseline_provenance_preserved": (
                result.comparison.baseline_provenance_preserved
            ),
            "fresta_provenance_preserved": (
                result.comparison.fresta_provenance_preserved
            ),
            "baseline_phi_closed": result.comparison.baseline_phi_closed,
            "fresta_phi_closed": result.comparison.fresta_phi_closed,
            "model_call_delta": result.comparison.model_call_delta,
        },
        "baseline": _summarize_arm(result.baseline),
        "fresta": _summarize_arm(result.fresta),
    }


def _summarize_arm(arm) -> Mapping[str, Any]:
    return {
        "arm": arm.arm.value,
        "episodes": [
            {
                "episode_index": episode.episode_index,
                "state": episode.state,
                "checkpoint_id": episode.checkpoint_id,
                "stored_checkpoint_id": episode.stored_checkpoint_id,
                "query_count": episode.query_count,
                "evidence_unit_count": episode.evidence_unit_count,
                "model_call_count": episode.model_call_count,
                "remainder_kinds": list(episode.remainder_kinds),
            }
            for episode in arm.episodes
        ],
        "checkpoint_ids": list(arm.checkpoint_ids),
        "persistence_enabled": arm.persistence_enabled,
        "continuation_recorded": arm.continuation_recorded,
        "provenance_preserved": arm.provenance_preserved,
        "phi_closed": arm.phi_closed,
        "model_call_count": arm.model_call_count,
    }


def _benchmark_contract_holds(result: QuestionOnlyBenchmarkResult) -> bool:
    return all((
        result.comparison.same_question,
        result.comparison.same_per_call_budget,
        result.comparison.same_token_budget,
        result.comparison.same_result_budget,
        not result.baseline.persistence_enabled,
        not result.baseline.continuation_recorded,
        result.fresta.persistence_enabled,
        result.fresta.continuation_recorded,
        result.baseline.provenance_preserved,
        result.fresta.provenance_preserved,
        not result.baseline.phi_closed,
        not result.fresta.phi_closed,
        result.comparison.baseline_completed is False,
        result.comparison.fresta_completed is True,
    ))


def _grant_with_permissions(
    grant: EffectGrant,
    permissions: tuple[str, ...],
) -> EffectGrant:
    return EffectGrant(
        plan_id=grant.plan_id,
        node_id=grant.node_id,
        module_id=grant.module_id,
        operation_id=grant.operation_id,
        effects=grant.effects,
        permissions=permissions,
        grant_id=grant.grant_id,
    )


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    result = run(args)
    return 0 if _benchmark_contract_holds(result) else 2


if __name__ == "__main__":
    raise SystemExit(main())
