"""Minimal loopback HTTP adapter over the shared command service."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import secrets
from typing import Any

from fresta_diamond.command_service import (
    CommandError,
    DiamondCommandService,
    encode_command_result,
)


MAX_REQUEST_BYTES = 64 * 1024

WEB_UI = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fresta Diamond</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #101318; color: #e8edf2; }
    h1 { margin-bottom: .25rem; } p { color: #aeb8c2; }
    textarea, input { width: 100%; box-sizing: border-box; margin: .4rem 0 1rem; padding: .7rem; border: 1px solid #46515d; border-radius: 6px; background: #1a2028; color: inherit; }
    textarea { min-height: 5rem; font-family: ui-monospace, monospace; }
    button { padding: .65rem 1rem; border: 0; border-radius: 6px; background: #2f81f7; color: white; cursor: pointer; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 1rem; border-radius: 6px; background: #080a0d; min-height: 8rem; }
    code { color: #79c0ff; }
  </style>
</head>
<body>
  <h1>Fresta Diamond</h1>
  <p>
    Fresta is a Jarvis-like research companion: it remembers your work,
    investigates bounded questions, and keeps going across limited context
    windows. It does not invent facts or sources: it proposes questions and
    hypotheses, then the system checks provenance, risk, and authority before
    anything is retained.
  </p>
  <label for="question">Question</label>
  <textarea id="question" placeholder="Write what you want to investigate"></textarea>
  <label for="mode">Response mode</label>
  <select id="mode">
    <option value="conversation">Conversation</option>
    <option value="analysis">Analysis</option>
  </select>
  <button id="investigate">Investigate</button>
  <button id="continue" hidden>Continue investigation</button>
  <p><small>Advanced command surface</small></p>
  <label for="token">Transport token</label>
  <input id="token" type="password" autocomplete="off" placeholder="Paste the token printed by run_web.py">
  <label for="command">Command</label>
  <textarea id="command">/help</textarea>
  <button id="run">Run command</button>
  <pre id="result">Ready.</pre>
  <script>
    const token = document.getElementById("token");
    const question = document.getElementById("question");
    const mode = document.getElementById("mode");
    const command = document.getElementById("command");
    const result = document.getElementById("result");
    const continueButton = document.getElementById("continue");
    let continuation = null;
    function showResult(body) {
      const payload = body.payload || {};
      const chat = payload.chat || payload;
      const session = chat && chat.session;
      const lines = [
        body.message || "No result message.",
        `State: ${body.state || "UNKNOWN"}`
      ];
      const answer = chat && chat.assistant_message;
      if (answer && answer.content) {
        lines.push(`\nResponse:\n${answer.content}`);
      }
      if (Array.isArray(payload.sources)) {
        lines.push("\nSource provenance:");
        if (payload.sources.length === 0) {
          lines.push("No external source units were produced.");
        } else {
          payload.sources.forEach((source) => {
            lines.push(
              `- ${source.title}\n  ${source.source_locator}\n  ` +
              `authority=${source.authority}; lineage=${source.source_lineage || "unspecified"}`
            );
          });
        }
      }
      if (Array.isArray(payload.remainders) && payload.remainders.length > 0) {
        lines.push(
          `\nOpen remainders (${payload.remainders.length}):\n` +
          payload.remainders.map((item) => `- ${item.description}`).join("\n")
        );
      }
      if (payload.phi_open === true) {
        lines.push("\nPhi remains open; this result is not an oracle conclusion.");
      }
      if (body.continuation_checkpoint_id) {
        lines.push(
          `\nContinuation checkpoint: ${body.continuation_checkpoint_id}`
        );
      }
      lines.push(`\nTechnical detail:\n${JSON.stringify(body, null, 2)}`);
      result.textContent = lines.join("\n");
      continuation = body.continuation_checkpoint_id && session
        ? {session_id: session.session_id, checkpoint_id: body.continuation_checkpoint_id}
        : null;
      continueButton.hidden = continuation === null;
    }
    async function post(path, payload) {
      result.textContent = "Running...";
      try {
        const response = await fetch(path, {
          method: "POST",
          headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token.value}`},
          body: JSON.stringify(payload)
        });
        const body = await response.json();
        showResult(body);
      } catch (error) {
        result.textContent = String(error);
      }
    }
    document.getElementById("investigate").addEventListener("click", () => {
      post("/investigate", {question: question.value, mode: mode.value});
    });
    continueButton.addEventListener("click", () => {
      if (continuation !== null) {
        post("/continue", {
          ...continuation,
          mode: mode.value,
          message: "Continue the bounded investigation from the checkpoint."
        });
      }
    });
    document.getElementById("run").addEventListener("click", () => {
      post("/command", {command: command.value});
    });
  </script>
</body>
</html>
"""


def create_web_server(
    service: DiamondCommandService,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    auth_token: str | None = None,
) -> ThreadingHTTPServer:
    """Create a loopback-only server; the caller owns its lifecycle.

    The token is an ephemeral transport capability and is never persisted.
    """
    _require_loopback(host)
    token = auth_token or secrets.token_urlsafe(32)
    if not token.strip():
        raise ValueError("Web adapter auth token cannot be empty")

    class Handler(BaseHTTPRequestHandler):
        server_version = "FrestaDiamondHTTP/0.1"

        def do_GET(self) -> None:
            if self.path == "/":
                self._send_html(WEB_UI)
                return
            if self.path != "/health":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            self._send_json(HTTPStatus.OK, {"state": "OK", "service": "fresta-diamond"})

        def do_POST(self) -> None:
            if self.path not in {"/command", "/investigate", "/continue"}:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            supplied_token = self.headers.get("Authorization", "")
            if not secrets.compare_digest(supplied_token, f"Bearer {token}"):
                self._send_json(HTTPStatus.UNAUTHORIZED, {
                    "state": "ERROR",
                    "error_type": "PermissionError",
                    "message": "A valid local transport token is required",
                })
                return
            try:
                payload = self._read_json()
                if self.path == "/command":
                    command = payload.get("command")
                    if not isinstance(command, str) or not command.strip():
                        raise CommandError("Request field 'command' must be non-empty text")
                    result = encode_command_result(service.execute_line(command))
                else:
                    if self.path == "/continue":
                        session_id = payload.get("session_id")
                        checkpoint_id = payload.get("checkpoint_id")
                        message = payload.get(
                            "message",
                            "Continue the bounded investigation from the checkpoint.",
                        )
                        mode = payload.get("mode", "conversation")
                        if not all(isinstance(item, str) and item.strip() for item in (
                            session_id,
                            checkpoint_id,
                            message,
                        )):
                            raise CommandError(
                                "Continuation requires session_id, checkpoint_id, "
                                "and non-empty message text"
                            )
                        if mode not in {"conversation", "analysis"}:
                            raise CommandError(
                                "Continuation mode must be 'conversation' or 'analysis'"
                            )
                        service.invoke(
                            "chat.resume",
                            session_id=session_id,
                            checkpoint_id=checkpoint_id,
                        )
                        result = encode_command_result(
                            service.invoke(
                                "chat.say",
                                session_id=session_id,
                                message=message,
                                response_mode=mode,
                            )
                        )
                    else:
                        question = payload.get("question")
                        if not isinstance(question, str) or not question.strip():
                            raise CommandError(
                                "Request field 'question' must be non-empty text"
                            )
                        scope = payload.get("scope", "scope:diamond-web")
                        mode = payload.get("mode", "conversation")
                        if not isinstance(scope, str) or not scope.strip():
                            raise CommandError("Request field 'scope' must be non-empty text")
                        if mode not in {"conversation", "analysis"}:
                            raise CommandError(
                                "Investigation mode must be 'conversation' or 'analysis'"
                            )
                        result = encode_command_result(
                            service.invoke(
                                "research",
                                question=question,
                                scope=scope,
                                response_mode=mode,
                            )
                        )
            except (CommandError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {
                    "state": "ERROR",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })
                return
            self._send_json(HTTPStatus.OK, result)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = self.headers.get("Content-Length")
            if length is None:
                raise ValueError("Content-Length is required")
            try:
                size = int(length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if size < 0 or size > MAX_REQUEST_BYTES:
                raise ValueError("Request body exceeds the byte limit")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Request body is incomplete")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object")
            return value

        def _send_json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer((host, port), Handler)
    server.auth_token = token
    return server


def _require_loopback(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Web adapter host must be a loopback IP address") from exc
    if not address.is_loopback:
        raise ValueError("Web adapter host must be loopback-only")
