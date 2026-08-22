"""Execute one shared Diamond command without starting a REPL or Web server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DIAMOND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.command_runner import (  # noqa: E402
    CommandRuntimeConfig,
    execute_configured_command,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute one command through the shared Diamond command service."
    )
    parser.add_argument("--command", required=True, help="Full slash command line.")
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
    try:
        result = execute_configured_command(config, args.command)
    except Exception as exc:  # CLI translates; domain APIs retain typed errors.
        print(json.dumps({
            "state": "ERROR",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result.get("state") == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
