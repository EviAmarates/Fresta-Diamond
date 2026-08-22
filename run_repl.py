"""Start one persistent REPL over the shared Diamond command service."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


DIAMOND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.command_runner import (  # noqa: E402
    CommandRuntimeConfig,
    build_command_service,
)
from fresta_diamond.repl import DiamondRepl  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a persistent REPL over Diamond's shared command service."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Dedicated Diamond data directory; production data is never inferred.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--attention-tokens", type=int, default=7_000)
    parser.add_argument("--response-tokens", type=int, default=2_000)
    parser.add_argument("--repair-attempts", type=int, choices=range(0, 4), default=1)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Render each command result as one compact JSON line.",
    )
    parser.add_argument("--no-banner", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    config = CommandRuntimeConfig(
        data_root=args.data_root,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_model_tokens=args.max_tokens,
        repair_attempts=args.repair_attempts,
        max_attention_tokens=args.attention_tokens,
        max_response_tokens=args.response_tokens,
    )
    repl = DiamondRepl(
        build_command_service(config),
        input_stream=sys.stdin,
        output_stream=sys.stdout,
        pretty=not args.compact,
        show_banner=not args.no_banner,
    )
    repl.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
