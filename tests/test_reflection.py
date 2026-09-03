from __future__ import annotations

import pytest

from fresta_diamond.reflection import (
    LlmReflectionOperation,
    ReflectionDecision,
    ReflectionRequest,
    ReflectionTrigger,
    decide_reflection,
    build_reflection_request,
)


def request(trigger=None) -> ReflectionRequest:
    return ReflectionRequest(
        session_id="chat:reflection",
        trigger=trigger,
        objective="Preserve a bounded collaboration.",
        scope="scope:collaboration",
        transcript_refs=("chat-message:1",),
    )


def test_reflection_is_disabled_without_a_declared_trigger() -> None:
    result = decide_reflection(request())

    assert result.decision is ReflectionDecision.NO_REFLECTION
    assert result.authority == "REFLECTION_PROPOSAL_ONLY"


@pytest.mark.parametrize("trigger", tuple(ReflectionTrigger))
def test_declared_trigger_only_opens_a_non_authoritative_proposal(trigger) -> None:
    result = decide_reflection(request(trigger))

    assert result.decision is ReflectionDecision.PROPOSE
    assert result.authority == "REFLECTION_PROPOSAL_ONLY"


def test_reflection_requires_transcript_provenance() -> None:
    with pytest.raises(ValueError, match="transcript references"):
        ReflectionRequest(
            session_id="chat:reflection",
            trigger=ReflectionTrigger.EXPLICIT_REQUEST,
            objective="Bounded objective.",
            scope="scope:test",
            transcript_refs=(),
        )


def test_llm_reflection_is_anchored_as_unvalidated_proposal() -> None:
    class Context:
        def invoke(self, _effect, **_kwargs):
            return {
                "content": (
                    '{"target":"USER_PROFILE","category":"style",'
                    '"content":"Prefers concise answers.",'
                    '"rationale":"Explicit collaboration signal."}'
                )
            }

    artifact = build_reflection_request(
        request(ReflectionTrigger.NEW_PREFERENCE)
    )
    result = LlmReflectionOperation()(
        {"request": artifact.payload},
        Context(),
    )["proposal"]

    assert result["target"] == "USER_PROFILE"
    assert result["authority"] == "REFLECTION_PROPOSAL_ONLY"
    assert result["transcript_refs"] == ("chat-message:1",)
