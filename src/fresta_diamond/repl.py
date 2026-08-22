"""Thin persistent REPL over the shared Diamond command service."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, TextIO

from fresta_diamond.command_service import (
    CommandError,
    DiamondCommandService,
    encode_command_result,
)


REPL_ERROR_AUTHORITY = "REPL_PRESENTATION_ERROR_ONLY"
_EXIT_LINES = frozenset({"exit", "quit", "/exit", "/quit"})


@dataclass(frozen=True)
class ReplSummary:
    commands_executed: int
    command_errors: int
    exit_reason: str


class DiamondRepl:
    """Keep one service alive; parse no cognitive command locally."""

    def __init__(
        self,
        service: DiamondCommandService,
        *,
        input_stream: TextIO,
        output_stream: TextIO,
        prompt: str = "diamond> ",
        pretty: bool = True,
        show_banner: bool = True,
        show_prompt: bool | None = None,
    ) -> None:
        if not prompt:
            raise ValueError("REPL prompt cannot be empty")
        self._service = service
        self._input = input_stream
        self._output = output_stream
        self._prompt = prompt
        self._pretty = pretty
        self._show_banner = show_banner
        self._show_prompt = (
            bool(input_stream.isatty() and output_stream.isatty())
            if show_prompt is None
            else show_prompt
        )

    @property
    def service(self) -> DiamondCommandService:
        return self._service

    def run(self) -> ReplSummary:
        commands = 0
        errors = 0
        if self._show_banner:
            self._write(
                "Fresta Diamond REPL — /help lists shared commands; /exit leaves."
            )
        while True:
            if self._show_prompt:
                self._output.write(self._prompt)
                self._output.flush()
            try:
                raw = self._input.readline()
            except KeyboardInterrupt:
                self._write("")
                return ReplSummary(commands, errors, "INTERRUPTED")
            if raw == "":
                self._write("")
                return ReplSummary(commands, errors, "EOF")
            line = raw.strip()
            if not line:
                continue
            if line.casefold() in _EXIT_LINES:
                return ReplSummary(commands, errors, "EXIT_COMMAND")
            try:
                result = self._service.execute_line(line)
            except KeyboardInterrupt:
                errors += 1
                self._write_json({
                    "state": "INTERRUPTED",
                    "error_type": "KeyboardInterrupt",
                    "message": "Command interrupted; the REPL session remains active.",
                    "authority": REPL_ERROR_AUTHORITY,
                })
                continue
            except CommandError as exc:
                errors += 1
                self._write_json({
                    "state": "ERROR",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "authority": REPL_ERROR_AUTHORITY,
                })
                continue
            except Exception as exc:
                # Runtime/adapters remain typed internally; the REPL only translates
                # their presentation and keeps the persistent service available.
                errors += 1
                self._write_json({
                    "state": "ERROR",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "authority": REPL_ERROR_AUTHORITY,
                })
                continue
            commands += 1
            self._write_json(encode_command_result(result))

    def _write_json(self, value: dict[str, Any]) -> None:
        self._write(json.dumps(
            value,
            ensure_ascii=False,
            indent=2 if self._pretty else None,
            separators=None if self._pretty else (",", ":"),
        ))

    def _write(self, value: str) -> None:
        self._output.write(value + "\n")
        self._output.flush()
