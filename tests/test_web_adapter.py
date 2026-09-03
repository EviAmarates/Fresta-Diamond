import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from fresta_diamond.command_service import (
    CommandResult,
    CommandState,
    DiamondCommandService,
)
from fresta_diamond.web_adapter import create_web_server


class StubApplication:
    pass


def _service() -> DiamondCommandService:
    return DiamondCommandService(StubApplication())


class InvestigativeService:
    def __init__(self) -> None:
        self.calls = []

    def invoke(self, command: str, **arguments: str) -> CommandResult:
        self.calls.append((command, arguments))
        return CommandResult(
            invocation_id="command:test",
            command=command,
            state=CommandState.COMPLETED,
            message="Investigation accepted.",
            payload={"question": arguments.get("question", "")},
        )

    def execute_line(self, _line: str) -> CommandResult:
        return CommandResult(
            invocation_id="command:test",
            command="help",
            state=CommandState.COMPLETED,
            message="Help.",
        )


def test_web_adapter_exposes_health_and_shared_commands() -> None:
    server = create_web_server(_service(), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{base}/health") as response:
            assert json.load(response)["state"] == "OK"
        request = Request(
            f"{base}/command",
            data=json.dumps({"command": "/help"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {server.auth_token}",
            },
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        assert result["command"] == "help"
        assert result["authority"] == "COMMAND_RESULT_ONLY"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_serves_local_ui() -> None:
    server = create_web_server(_service(), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
            body = response.read().decode("utf-8")
        assert "Fresta Diamond" in body
        assert "/command" in body
        assert "/investigate" in body
        assert "Sources &amp; provenance" in body
        assert "Φ is open" in body
        assert "Analysis" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_forwards_direct_question_to_research_command() -> None:
    service = InvestigativeService()
    server = create_web_server(
        service,
        port=0,
        auth_token="test-transport-token",
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/investigate",
            data=json.dumps({"question": "Why did Rome fall?"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-transport-token",
            },
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        assert result["command"] == "research"
        assert result["payload"]["question"] == "Why did Rome fall?"
        assert service.calls == [(
            "research",
            {
                "question": "Why did Rome fall?",
                "scope": "scope:diamond-web",
                "response_mode": "conversation",
            },
        )]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_continues_a_suspended_investigation() -> None:
    service = InvestigativeService()
    server = create_web_server(
        service,
        port=0,
        auth_token="test-transport-token",
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/continue",
            data=json.dumps({
                "session_id": "chat:one",
                "checkpoint_id": "checkpoint:one",
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-transport-token",
            },
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        assert result["command"] == "chat.say"
        assert [item[0] for item in service.calls] == ["chat.resume", "chat.say"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_rejects_invalid_command_requests() -> None:
    server = create_web_server(_service(), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/command",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {server.auth_token}",
            },
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 400
        assert json.load(error.value)["error_type"] == "CommandError"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_rejects_missing_transport_token() -> None:
    server = create_web_server(_service(), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/command",
            data=json.dumps({"command": "/help"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_rejects_invalid_transport_token() -> None:
    server = create_web_server(_service(), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/command",
            data=json.dumps({"command": "/help"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid",
            },
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_adapter_only_binds_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        create_web_server(_service(), host="0.0.0.0")
