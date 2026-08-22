"""Isolated live smoke: learn -> nomination -> concept evidence validation."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two isolated learns, concept nomination, and deterministic "
            "concept validation over bounded model evidence."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--repair-attempts", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Optional explicit isolated root; omitted uses a temporary root.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    adapter = OpenAICompatibleChatAdapter(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )
    if args.data_root is not None:
        args.data_root.mkdir(parents=True, exist_ok=True)
        return run(args.data_root, adapter, args)
    with TemporaryDirectory(prefix="fresta-diamond-application-smoke-") as root:
        return run(Path(root), adapter, args)


def run(root: Path, adapter, args: argparse.Namespace) -> int:
    app = DiamondApplication(
        root,
        adapter,
        required_permissions=adapter.required_permissions,
        max_tokens=args.max_tokens,
        repair_attempts=args.repair_attempts,
        max_response_tokens=2_000,
    )
    candidates = (
        "Um automóvel transforma energia em movimento através dos seus componentes.",
        "A organização dos componentes sustenta a identidade funcional do automóvel.",
    )
    print(f"[Diamond application smoke] model={args.model}", flush=True)
    for index, content in enumerate(candidates, start=1):
        print(f"\n[/learn {index}/{len(candidates)}]", flush=True)
        outcome = app.learn_text(
            content,
            scope="scope:diamond-smoke:cars",
            provenance=("document:synthetic-diamond-smoke",),
            objective=(
                "Evaluate this synthetic smoke-test candidate without "
                "assuming it is true."
            ),
        )
        closure = outcome.result.execution.closure
        print(json.dumps({
            "model_calls": outcome.model_call_count,
            "repairs": outcome.repair_attempts_used,
            "structural_closed": closure.structural_closed,
            "epistemic_closed": closure.epistemic_closed,
            "crystals": [
                {
                    "state": item.state.value,
                    "reason_codes": list(item.reason_codes),
                }
                for item in outcome.stored_commit.commit.crystallization.crystals
            ],
        }, ensure_ascii=False, indent=2), flush=True)

    active = app.crystals(scope="scope:diamond-smoke:cars")
    if len(active) < 2:
        print("\n[concept] fewer than two ACTIVE crystals; nomination skipped.")
        return 2
    print("\n[concept nomination]", flush=True)
    nominated = app.nominate_concept(
        scope="scope:diamond-smoke:cars",
        objective=(
            "Determine whether the active crystals support one bounded, "
            "order-free concept. Refuse if they do not."
        ),
        crystal_ids=tuple(item.crystal_id for item in active),
    )
    payload = {
        "execution_state": nominated.result.execution.state.value,
        "model_calls": nominated.model_call_count,
        "decision": (
            nominated.nomination.decision.value
            if nominated.nomination is not None else None
        ),
        "rationale": (
            nominated.nomination.rationale
            if nominated.nomination is not None else None
        ),
        "stored_concept": (
            {
                "version_ref": nominated.concept.version_ref,
                "name": nominated.concept.canonical_name,
                "state": nominated.concept.state.value,
                "memberships": len(nominated.concept.memberships),
            }
            if nominated.concept is not None else None
        ),
        "remainders": [
            item.description for item in nominated.result.execution.remainders
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    if nominated.concept is None:
        return 0 if nominated.nomination is not None else 2

    print("\n[concept evidence + deterministic validation]", flush=True)
    evaluated = app.evaluate_concept(
        nominated.concept.concept_id,
        objective=(
            "Evaluate whether the committed crystals justify every bounded "
            "part of this candidate concept. Omit unsupported seals."
        ),
    )
    validation_payload = {
        "execution_state": evaluated.result.execution.state.value,
        "model_calls": evaluated.model_call_count,
        "structural_closed": (
            evaluated.result.execution.closure.structural_closed
        ),
        "epistemic_closed": (
            evaluated.result.execution.closure.epistemic_closed
        ),
        "recommended_state": (
            evaluated.validation.report.recommended_state.value
            if evaluated.validation is not None else None
        ),
        "stored_state": (
            evaluated.validation.record.state.value
            if evaluated.validation is not None else None
        ),
        "validation_remainders": (
            [
                item.description
                for item in evaluated.validation.report.active_remainders
            ]
            if evaluated.validation is not None else []
        ),
        "controller_remainders": [
            item.description for item in evaluated.result.execution.remainders
        ],
    }
    print(json.dumps(
        validation_payload, ensure_ascii=False, indent=2
    ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
