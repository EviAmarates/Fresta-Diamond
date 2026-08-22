"""Bounded local OpenAI-compatible adapter behavior."""

import pytest

from fresta_diamond.adapters import OpenAICompatibleChatAdapter
from fresta_diamond.contracts import EffectGrant


def grant(*, permissions: tuple[str, ...]) -> EffectGrant:
    return EffectGrant(
        plan_id="plan",
        node_id="node",
        module_id="provider",
        operation_id="chat",
        effects=("llm.generate",),
        permissions=permissions,
    )


def test_adapter_pins_model_host_and_token_ceiling() -> None:
    observed = {}

    def transport(endpoint, payload, timeout):
        observed.update(endpoint=endpoint, payload=payload, timeout=timeout)
        return {
            "model": "qwen/qwen3-14b",
            "choices": [{"message": {"content": "{\"ok\": true}"}}],
            "usage": {"total_tokens": 42},
        }

    adapter = OpenAICompatibleChatAdapter(
        "http://127.0.0.1:1234",
        "qwen/qwen3-14b",
        timeout_seconds=17,
        max_tokens=100,
        transport=transport,
    )
    result = adapter(
        grant(permissions=adapter.required_permissions),
        messages=({"role": "user", "content": "bounded"},),
        max_tokens=999,
    )

    assert observed["endpoint"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert observed["payload"]["model"] == "qwen/qwen3-14b"
    assert observed["payload"]["max_tokens"] == 100
    assert observed["timeout"] == 17
    assert result["content"] == "{\"ok\": true}"


def test_adapter_refuses_grant_for_another_model_or_host() -> None:
    adapter = OpenAICompatibleChatAdapter(
        "http://127.0.0.1:1234",
        "qwen/qwen3-14b",
        transport=lambda *_: {},
    )

    with pytest.raises(PermissionError, match="missing adapter permissions"):
        adapter(
            grant(permissions=("llm.model:another-model",)),
            messages=({"role": "user", "content": "bounded"},),
        )


def test_adapter_rejects_response_without_assistant_content() -> None:
    adapter = OpenAICompatibleChatAdapter(
        "http://127.0.0.1:1234",
        "qwen/qwen3-14b",
        transport=lambda *_: {"choices": []},
    )

    with pytest.raises(RuntimeError, match="no assistant message"):
        adapter(
            grant(permissions=adapter.required_permissions),
            messages=({"role": "user", "content": "bounded"},),
        )
