"""Configurable one-command runtime over the shared Diamond command service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fresta_diamond.adapters import OpenAICompatibleChatAdapter
from fresta_diamond.application import DiamondApplication
from fresta_diamond.command_service import (
    DiamondCommandService,
    encode_command_result,
)


@dataclass(frozen=True)
class CommandRuntimeConfig:
    data_root: Path
    base_url: str = "http://127.0.0.1:1234"
    model: str = "qwen/qwen3-14b"
    timeout_seconds: float = 300.0
    max_model_tokens: int = 4_000
    repair_attempts: int = 1
    max_attention_tokens: int = 7_000
    max_response_tokens: int = 2_000

    def __post_init__(self) -> None:
        if not isinstance(self.data_root, Path):
            object.__setattr__(self, "data_root", Path(self.data_root))
        if not self.model.strip():
            raise ValueError("Command runtime model is required")
        if self.timeout_seconds <= 0:
            raise ValueError("Command runtime timeout must be positive")
        if self.max_model_tokens < 1 or self.max_response_tokens < 1:
            raise ValueError("Command runtime model token limits are invalid")
        if self.max_attention_tokens < 32:
            raise ValueError("Command runtime attention budget must be >= 32")
        if not 0 <= self.repair_attempts <= 3:
            raise ValueError("Command runtime repair attempts must be 0-3")


def build_command_service(config: CommandRuntimeConfig) -> DiamondCommandService:
    adapter = OpenAICompatibleChatAdapter(
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        max_tokens=config.max_model_tokens,
    )
    application = DiamondApplication(
        config.data_root,
        adapter,
        required_permissions=adapter.required_permissions,
        max_tokens=config.max_model_tokens,
        repair_attempts=config.repair_attempts,
        max_attention_tokens=config.max_attention_tokens,
        max_response_tokens=config.max_response_tokens,
    )
    return DiamondCommandService(application)


def execute_configured_command(
    config: CommandRuntimeConfig,
    line: str,
) -> dict[str, Any]:
    """Execute one line; network is used only if that command needs the model."""

    return encode_command_result(build_command_service(config).execute_line(line))
