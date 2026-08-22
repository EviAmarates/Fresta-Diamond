from __future__ import annotations

import json

import pytest

from fresta_diamond.chat import (
    AtomicChatStore,
    ChatRole,
    ChatStoreError,
)


def test_chat_store_seals_role_authority_and_message_order(tmp_path) -> None:
    store = AtomicChatStore(tmp_path / "chat")
    session = store.create(
        session_id="chat:test",
        context_id="context:test",
        transcript_sheet_id="chat-transcript:test",
        scope="scope:test",
        objective="Maintain one bounded conversation.",
    )

    user = store.append(
        session.session_id,
        role=ChatRole.USER,
        content="Olá.",
        provenance=("operator:user-supplied",),
    )
    assistant = store.append(
        session.session_id,
        role=ChatRole.ASSISTANT,
        content="Olá!",
        provenance=("attention:context:test@1",),
    )

    reloaded = AtomicChatStore(tmp_path / "chat")
    assert reloaded.session(session.session_id) == session
    assert reloaded.messages(session.session_id) == (user, assistant)
    assert user.authority == "USER_MESSAGE_ONLY"
    assert assistant.authority == "MODEL_RESPONSE_UNVALIDATED"


def test_chat_store_rejects_modified_history(tmp_path) -> None:
    store = AtomicChatStore(tmp_path / "chat")
    session = store.create(
        session_id="chat:tamper-test",
        context_id="context:tamper-test",
        transcript_sheet_id="chat-transcript:tamper-test",
        scope="scope:test",
        objective="Detect chat history modification.",
    )
    store.append(
        session.session_id,
        role=ChatRole.USER,
        content="Original text.",
        provenance=("operator:user-supplied",),
    )
    message_path = next((store.root / next(store.root.iterdir()).name).glob(
        "message-*.json"
    ))
    raw = json.loads(message_path.read_text(encoding="utf-8"))
    raw["payload"]["content"] = "Modified text."
    message_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ChatStoreError, match="verification failed"):
        store.messages(session.session_id)


def test_chat_store_rejects_duplicate_message_identity(tmp_path) -> None:
    store = AtomicChatStore(tmp_path / "chat")
    session = store.create(
        session_id="chat:duplicate-test",
        context_id="context:duplicate-test",
        transcript_sheet_id="chat-transcript:duplicate-test",
        scope="scope:test",
        objective="Reject duplicate message identity.",
    )
    store.append(
        session.session_id,
        role=ChatRole.USER,
        content="First message.",
        provenance=("operator:user-supplied",),
        message_id="chat-message:fixed",
    )

    with pytest.raises(ChatStoreError, match="already exists"):
        store.append(
            session.session_id,
            role=ChatRole.USER,
            content="Second message.",
            provenance=("operator:user-supplied",),
            message_id="chat-message:fixed",
        )
