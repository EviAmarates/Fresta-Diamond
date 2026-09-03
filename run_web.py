"""Start the local Fresta Diamond Web interface."""

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
from fresta_diamond.web_adapter import create_web_server  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the local loopback Fresta Diamond Web interface."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Dedicated Diamond data directory; production data is never inferred.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--attention-tokens", type=int, default=7_000)
    parser.add_argument("--response-tokens", type=int, default=2_000)
    parser.add_argument("--repair-attempts", type=int, choices=range(0, 4), default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
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
    server = create_web_server(
        build_command_service(config),
        host=args.host,
        port=args.port,
    )
    print(f"Fresta Diamond Web: http://{args.host}:{server.server_port}/")
    print(f"Transport token: {server.auth_token}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
