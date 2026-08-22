from __future__ import annotations

from io import StringIO
import json
import subprocess
import sys
from pathlib import Path

from fresta_diamond.application import DiamondApplication
from fresta_diamond.command_service import DiamondCommandService
from fresta_diamond.repl import DiamondRepl

from .test_application import PERMISSIONS


ROOT = Path(__file__).resolve().parents[1]


def offline_service(tmp_path) -> DiamondCommandService:
    def unavailable(*_args, **_kwargs):
        raise AssertionError("Offline REPL command unexpectedly called the model")

    return DiamondCommandService(DiamondApplication(
        tmp_path,
        unavailable,
        required_permissions=PERMISSIONS,
    ))


def compact_repl(service, source: str, output: StringIO | None = None):
    target = output or StringIO()
    repl = DiamondRepl(
        service,
        input_stream=StringIO(source),
        output_stream=target,
        prompt="> ",
        pretty=False,
        show_banner=False,
    )
    return repl.run(), target


def json_lines(output: StringIO) -> list[dict]:
    return [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.startswith("{")
    ]


def test_repl_keeps_one_service_and_application_state(tmp_path) -> None:
    service = offline_service(tmp_path)
    summary, output = compact_repl(
        service,
        "/attention create Remember the current bounded task\n"
        "/attention status\n"
        "/exit\n",
    )

    payloads = json_lines(output)
    assert summary.commands_executed == 2
    assert summary.command_errors == 0
    assert summary.exit_reason == "EXIT_COMMAND"
    created = payloads[0]["payload"]["context"]
    current = payloads[1]["payload"]["context"]
    assert current["context_id"] == created["context_id"]
    assert (
        service.application.attention_memory.active().context_id
        == created["context_id"]
    )


def test_repl_error_does_not_destroy_session(tmp_path) -> None:
    summary, output = compact_repl(
        offline_service(tmp_path),
        "/does-not-exist\n/help\n/quit\n",
    )

    payloads = json_lines(output)
    assert summary.commands_executed == 1
    assert summary.command_errors == 1
    assert payloads[0]["state"] == "ERROR"
    assert payloads[0]["authority"] == "REPL_PRESENTATION_ERROR_ONLY"
    assert payloads[1]["command"] == "help"


def test_repl_ignores_blank_lines_and_exits_cleanly_on_eof(tmp_path) -> None:
    summary, output = compact_repl(offline_service(tmp_path), "\n/help\n")

    assert summary.commands_executed == 1
    assert summary.exit_reason == "EOF"
    assert json_lines(output)[0]["command"] == "help"


def test_interrupted_command_does_not_destroy_session(tmp_path) -> None:
    real = offline_service(tmp_path)

    class InterruptOnce:
        def __init__(self):
            self.calls = 0

        def execute_line(self, line):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt
            return real.execute_line(line)

    summary, output = compact_repl(InterruptOnce(), "/help\n/help\n/exit\n")
    payloads = json_lines(output)

    assert summary.commands_executed == 1
    assert summary.command_errors == 1
    assert payloads[0]["state"] == "INTERRUPTED"
    assert payloads[1]["command"] == "help"


def test_repl_script_builds_once_and_runs_offline_commands(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_repl.py"),
            "--data-root",
            str(tmp_path / "runtime"),
            "--base-url",
            "http://127.0.0.1:1",
            "--compact",
            "--no-banner",
        ],
        cwd=ROOT,
        input="/help\n/module proposals\n/exit\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    payloads = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.startswith("{")
    ]
    assert [item["command"] for item in payloads] == [
        "help",
        "module.proposals",
    ]
    assert all(item["model_call_count"] == 0 for item in payloads)
    assert completed.stderr == ""
