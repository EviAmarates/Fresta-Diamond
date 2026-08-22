"""Bounded adapter for local OpenAI-compatible chat-completion servers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fresta_diamond.contracts import EffectGrant


Transport = Callable[[str, Mapping[str, Any], float], Mapping[str, Any]]


@dataclass(frozen=True)
class OpenAICompatibleChatAdapter:
    """Call one configured model; callers cannot replace its host or model."""

    base_url: str
    model: str
    timeout_seconds: float = 300.0
    max_tokens: int = 4_000
    transport: Transport | None = None

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if not self.model.strip():
            raise ValueError("model is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

    @property
    def endpoint(self) -> str:
        root = self.base_url.rstrip("/")
        if root.endswith("/v1"):
            return root + "/chat/completions"
        return root + "/v1/chat/completions"

    @property
    def required_permissions(self) -> tuple[str, str]:
        host = urlparse(self.base_url).netloc
        return (f"llm.model:{self.model}", f"network.host:{host}")

    def __call__(
        self,
        grant: EffectGrant,
        *,
        messages: Sequence[Mapping[str, str]],
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> Mapping[str, Any]:
        if "llm.generate" not in grant.effects:
            raise PermissionError("Grant does not include llm.generate")
        missing = set(self.required_permissions) - set(grant.permissions)
        if missing:
            raise PermissionError(
                "Grant is missing adapter permissions: " + ", ".join(sorted(missing))
            )
        normalized_messages = self._validate_messages(messages)
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        requested_tokens = self.max_tokens if max_tokens is None else max_tokens
        if requested_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        request_payload = {
            "model": self.model,
            "messages": normalized_messages,
            "temperature": temperature,
            "max_tokens": min(requested_tokens, self.max_tokens),
            "stream": False,
        }
        transport = self.transport or _http_json_transport
        response = transport(self.endpoint, request_payload, self.timeout_seconds)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "OpenAI-compatible response has no assistant message content"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenAI-compatible response content is empty")
        return {
            "content": content,
            "model": response.get("model", self.model),
            "usage": response.get("usage", {}),
        }

    @staticmethod
    def _validate_messages(
        messages: Sequence[Mapping[str, str]],
    ) -> tuple[Mapping[str, str], ...]:
        if not messages:
            raise ValueError("At least one chat message is required")
        normalized = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise ValueError(f"Unsupported chat role: {role}")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Chat message content must be non-empty text")
            normalized.append({"role": role, "content": content})
        return tuple(normalized)


def _http_json_transport(
    endpoint: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> Mapping[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM server returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"LLM server is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM server returned invalid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise RuntimeError("LLM server response must be a JSON object")
    return decoded
