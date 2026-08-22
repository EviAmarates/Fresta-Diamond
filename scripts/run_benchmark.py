"""Run isolated Diamond regression cases in deterministic replay or live mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.benchmarking import (  # noqa: E402
    DiamondBenchmarkLab,
    replay_adapter,
    replay_permissions,
    run_learning_benchmark,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Diamond /learn invariants against a named baseline."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", help="Run one case ID.")
    group.add_argument("--all", action="store_true", help="Run every case.")
    group.add_argument("--list", action="store_true", help="List case IDs.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the local LLM instead of the deterministic recorded bundle.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Compare without writing a run record.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    lab = DiamondBenchmarkLab(ROOT / "testdata")
    if args.list:
        print("\n".join(lab.list_cases()))
        return 0
    case_ids = lab.list_cases() if args.all else (args.case or lab.list_cases()[0],)
    adapter = None
    permissions = replay_permissions()
    model = "diamond-replay"
    if args.live:
        adapter = OpenAICompatibleChatAdapter(
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
            max_tokens=args.max_tokens,
        )
        permissions = adapter.required_permissions
        model = args.model

    failed = False
    for case_id in case_ids:
        case = lab.load_case(case_id)
        projection = run_learning_benchmark(
            case,
            adapter or replay_adapter(case),
            permissions=permissions,
            max_tokens=args.max_tokens,
        )
        comparison = lab.compare(case.case_id, projection)
        path = None
        if not args.no_archive:
            path = lab.archive_run(
                case=case,
                mode="LIVE" if args.live else "REPLAY",
                projection=projection,
                comparison=comparison,
                model=model,
            )
        print(f"\n--- {case.case_id} ---")
        print(json.dumps({
            "matches_baseline": comparison.matches,
            "differences": list(comparison.differences),
            "projection": projection,
            "archived_at": str(path) if path is not None else None,
        }, ensure_ascii=False, indent=2))
        failed = failed or not comparison.matches
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
