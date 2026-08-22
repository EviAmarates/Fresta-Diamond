"""Isolated one-call smoke for objective-relative attention retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.application import DiamondApplication  # noqa: E402


CATALOG = (
    DIAMOND_ROOT
    / "testdata"
    / "concept-catalog"
    / "notebooklm-ontology-index.json"
)
ENTRY_IDS = (
    "notebooklm-concept-row-002",
    "notebooklm-concept-row-003",
    "notebooklm-concept-row-008",
)
SCOPE = "scope:objective-retrieval-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage three unvalidated catalog sheets, then make exactly one "
            "local-model call to nominate objective-relative attention roots."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=1_200)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Optional isolated root; omitted uses a temporary directory.",
    )
    return parser.parse_args()


def run(root: Path, args: argparse.Namespace) -> int:
    adapter = OpenAICompatibleChatAdapter(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )
    app = DiamondApplication(
        root,
        adapter,
        required_permissions=adapter.required_permissions,
        max_response_tokens=args.max_tokens,
        repair_attempts=0,
    )
    revisions = app.stage_concept_catalog(
        CATALOG,
        ENTRY_IDS,
        scope=SCOPE,
        objective_ref="objective:identify-three-order-method",
    )
    print(
        f"[Diamond objective retrieval smoke] model={args.model} calls=1",
        flush=True,
    )
    outcome = app.retrieve_for_objective(
        scope=SCOPE,
        objective=(
            "Select only the sheet that explicitly describes the method of "
            "first-, second-, and third-order analysis."
        ),
        summary="Three unvalidated external proposals await selection.",
    )
    projection = (
        outcome.materialized.projection
        if outcome.materialized is not None else None
    )
    supplied = {f"sheet:{item.sheet_id}" for item in revisions}
    selected = (
        tuple(item.item_ref for item in projection.selected)
        if projection is not None else ()
    )
    print(json.dumps({
        "model_calls": outcome.model_call_count,
        "execution_state": outcome.result.execution.state.value,
        "decision": (
            outcome.nomination.decision.value if outcome.nomination else None
        ),
        "selected_refs": selected,
        "selected_refs_were_supplied": set(selected).issubset(supplied),
        "projection_state": projection.state.value if projection else None,
        "injection_ready": projection.injection_ready if projection else None,
        "authorities": (
            {item.item_ref: item.authority for item in projection.selected}
            if projection else {}
        ),
        "contextual_roles": (
            {
                item.item_ref: list(item.contextual_roles)
                for item in projection.selected
            }
            if projection else {}
        ),
        "remainders": [
            item.description for item in outcome.result.execution.remainders
        ],
    }, ensure_ascii=False, indent=2), flush=True)
    return 0 if (
        outcome.model_call_count == 1
        and outcome.nomination is not None
        and set(selected).issubset(supplied)
    ) else 2


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    if args.data_root is not None:
        args.data_root.mkdir(parents=True, exist_ok=True)
        return run(args.data_root, args)
    with TemporaryDirectory(prefix="fresta-diamond-objective-retrieval-") as root:
        return run(Path(root), args)


if __name__ == "__main__":
    raise SystemExit(main())
