from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fresta_diamond.command_runner import (
    CommandRuntimeConfig,
    execute_configured_command,
)


ROOT = Path(__file__).resolve().parents[1]


def test_configured_help_is_offline_and_json_ready(tmp_path) -> None:
    result = execute_configured_command(
        CommandRuntimeConfig(
            data_root=tmp_path / "data",
            base_url="http://127.0.0.1:1",
            timeout_seconds=0.01,
        ),
        "/help",
    )

    assert result["state"] == "COMPLETED"
    assert result["model_call_count"] == 0
    assert json.loads(json.dumps(result))["command"] == "help"
    assert not (tmp_path / "data").exists()


def test_runner_script_uses_explicit_data_root_and_shared_codec(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_commands.py"),
            "--data-root",
            str(tmp_path / "runtime"),
            "--base-url",
            "http://127.0.0.1:1",
            "--command",
            "/help",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["command"] == "help"
    assert payload["authority"] == "COMMAND_RESULT_ONLY"
    assert completed.stderr == ""


def test_runtime_config_rejects_unsafe_limits(tmp_path) -> None:
    with pytest.raises(ValueError, match="attention budget"):
        CommandRuntimeConfig(data_root=tmp_path, max_attention_tokens=31)
    with pytest.raises(ValueError, match="repair attempts"):
        CommandRuntimeConfig(data_root=tmp_path, repair_attempts=4)
