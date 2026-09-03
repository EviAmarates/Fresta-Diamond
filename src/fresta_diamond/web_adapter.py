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
 <meta name="theme-color" content="#0b1119">
 <title>Fresta Diamond · Research</title>
 <style>
   :root {
     color-scheme: dark;
     font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
     --bg: #081018;
     --panel: rgba(17, 29, 42, .88);
     --panel-strong: #121f2e;
     --line: #26394c;
     --text: #edf5fb;
     --muted: #91a6b8;
     --cyan: #53d8e8;
     --gold: #e6b566;
     --green: #7cdbad;
     --red: #ff8e8e;
   }
   * { box-sizing: border-box; }
   body {
     min-height: 100vh; margin: 0; color: var(--text);
     background: radial-gradient(circle at 15% 0%, #15344b 0, transparent 36rem),
                 radial-gradient(circle at 100% 30%, #20253b 0, transparent 32rem),
                 var(--bg);
   }
   main { width: min(980px, 100%); margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
   header { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; margin-bottom: 2rem; }
   .brand { display: flex; gap: .85rem; align-items: center; }
   .mark {
     display: grid; place-items: center; width: 2.8rem; height: 2.8rem;
     border: 1px solid rgba(83, 216, 232, .55); border-radius: 14px;
     color: var(--cyan); font-size: 1.45rem; box-shadow: 0 0 28px rgba(83, 216, 232, .16);
   }
   h1, h2, p { margin-top: 0; }
   h1 { margin-bottom: .2rem; font-size: clamp(1.35rem, 3vw, 1.8rem); letter-spacing: -.03em; }
   h2 { margin-bottom: .55rem; font-size: 1.05rem; }
   .tagline { margin: 0; color: var(--muted); font-size: .92rem; }
   .badge {
     padding: .38rem .65rem; border: 1px solid rgba(124, 219, 173, .35);
     border-radius: 999px; color: var(--green); font-size: .72rem;
     letter-spacing: .08em; white-space: nowrap;
   }
   .hero, .result-card, details {
     background: var(--panel); border: 1px solid var(--line);
     border-radius: 18px; box-shadow: 0 18px 60px rgba(0, 0, 0, .18);
   }
   .hero { padding: clamp(1.15rem, 4vw, 2rem); }
   .hero-copy { max-width: 680px; margin-bottom: 1.5rem; color: var(--muted); line-height: 1.6; }
   label { display: block; margin: 0 0 .5rem; color: #c7d8e5; font-size: .84rem; font-weight: 650; }
   textarea, input, select {
     width: 100%; border: 1px solid var(--line); border-radius: 11px;
     background: rgba(5, 13, 21, .72); color: var(--text); font: inherit;
     outline: none; transition: border-color .18s, box-shadow .18s;
   }
   textarea { min-height: 8rem; padding: 1rem; resize: vertical; line-height: 1.5; }
   input, select { padding: .72rem .8rem; }
   textarea:focus, input:focus, select:focus { border-color: var(--cyan); box-shadow: 0 0 0 3px rgba(83, 216, 232, .12); }
   .controls { display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: end; margin-top: 1rem; }
   .mode { display: flex; padding: .2rem; border: 1px solid var(--line); border-radius: 11px; background: rgba(5, 13, 21, .5); }
   .mode button { flex: 1; padding: .62rem .8rem; border: 0; border-radius: 8px; background: transparent; color: var(--muted); cursor: pointer; font: inherit; }
   .mode button.active { background: #1b3b4d; color: var(--text); }
   .actions { display: flex; gap: .6rem; flex-wrap: wrap; }
   button.primary, button.secondary {
     border: 0; border-radius: 10px; padding: .75rem 1.1rem; color: #061019;
     cursor: pointer; font: inherit; font-weight: 750; transition: transform .18s, filter .18s;
   }
   button.primary { background: linear-gradient(135deg, var(--cyan), #91f0d1); }
   button.secondary { background: #263c4d; color: var(--text); }
   button:hover { filter: brightness(1.1); transform: translateY(-1px); }
   button:disabled { cursor: wait; opacity: .6; transform: none; }
   .hint { margin: .7rem 0 0; color: var(--muted); font-size: .78rem; }
   details { margin-top: 1rem; padding: 1rem 1.1rem; }
   summary { cursor: pointer; color: #c7d8e5; font-size: .84rem; font-weight: 650; }
   .advanced-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; }
   .advanced-grid textarea { min-height: 5rem; font-family: ui-monospace, monospace; font-size: .82rem; }
   .result-card { margin-top: 1.25rem; padding: clamp(1.15rem, 4vw, 1.7rem); }
   .result-top { display: flex; justify-content: space-between; gap: 1rem; align-items: center; border-bottom: 1px solid var(--line); padding-bottom: .9rem; }
   .status { color: var(--gold); font-size: .76rem; font-weight: 750; letter-spacing: .08em; }
   .status.completed { color: var(--green); }
   .status.error { color: var(--red); }
   .status.running { color: var(--cyan); }
   .message { margin: 1rem 0; color: var(--muted); line-height: 1.55; }
   .response { margin: 1rem 0; padding: 1rem; border-left: 3px solid var(--cyan); border-radius: 0 11px 11px 0; background: rgba(83, 216, 232, .06); white-space: pre-wrap; line-height: 1.62; }
   .section-label { margin: 1.35rem 0 .65rem; color: #c7d8e5; font-size: .78rem; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
   .source-list { display: grid; gap: .65rem; }
   .source { padding: .8rem; border: 1px solid var(--line); border-radius: 11px; background: rgba(5, 13, 21, .38); }
   .source a { color: var(--cyan); overflow-wrap: anywhere; }
   .source small { display: block; margin-top: .35rem; color: var(--muted); }
   .empty, .remainder { color: var(--muted); font-size: .88rem; }
   .remainder { padding: .65rem .8rem; border-left: 2px solid var(--gold); background: rgba(230, 181, 102, .06); }
   .phi { margin-top: 1rem; padding: .75rem .85rem; border: 1px solid rgba(230, 181, 102, .28); border-radius: 10px; color: #efd5a6; background: rgba(230, 181, 102, .06); font-size: .88rem; }
   .technical { margin-top: 1rem; box-shadow: none; background: rgba(5, 13, 21, .28); }
   .technical pre { max-height: 22rem; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: #a9c4d5; font: .76rem/1.45 ui-monospace, monospace; }
   @media (max-width: 680px) {
     main { padding-top: 1.4rem; } header { margin-bottom: 1.3rem; }
     .badge { display: none; } .controls, .advanced-grid { grid-template-columns: 1fr; }
     .actions button { flex: 1; } .result-top { align-items: flex-start; flex-direction: column; }
   }
 </style>
</head>
<body>
 <main>
   <header>
     <div class="brand">
       <div class="mark" aria-hidden="true">Φ</div>
       <div>
         <h1>Fresta Diamond</h1>
         <p class="tagline">It does not invent — it investigates.</p>
       </div>
     </div>
     <div class="badge">LOOPBACK · Φ OPEN</div>
   </header>

   <section class="hero" aria-labelledby="investigation-title">
     <h2 id="investigation-title">What do you want to investigate?</h2>
     <p class="hero-copy">
       Ask a question. Fresta proposes a bounded path, looks for sources,
       preserves provenance, and continues the investigation without pretending
       to conclude.
     </p>
     <label for="question">Question</label>
     <textarea id="question" placeholder="e.g. What are the main explanations for the fall of the Western Roman Empire?"></textarea>
     <div class="controls">
       <div>
         <label>Response mode</label>
         <div class="mode" role="group" aria-label="Response mode">
           <button type="button" class="active" data-mode="conversation">Conversation</button>
           <button type="button" data-mode="analysis">Analysis</button>
         </div>
       </div>
       <div class="actions">
         <button type="button" class="secondary" id="continue" hidden>Continue</button>
         <button type="button" class="primary" id="investigate">Investigate</button>
       </div>
     </div>
     <p class="hint">Tip: <kbd>Ctrl</kbd> + <kbd>Enter</kbd> submits the question.</p>
   </section>

   <details>
     <summary>Local connection and advanced commands</summary>
     <div class="advanced-grid">
       <div>
         <label for="token">Transport token</label>
         <input id="token" type="password" autocomplete="off" placeholder="Paste the token shown by run_web.py">
       </div>
       <div>
         <label for="command">Diamond command</label>
         <textarea id="command">/help</textarea>
         <button type="button" class="secondary" id="run">Run command</button>
       </div>
     </div>
   </details>

   <section class="result-card" id="result-card" aria-live="polite">
     <div class="result-top">
       <h2>Investigation status</h2>
       <div class="status" id="status">READY</div>
     </div>
     <p class="message" id="message">The next response will appear here.</p>
     <div id="response-section" hidden>
       <div class="section-label">Resposta</div>
       <div class="response" id="response"></div>
     </div>
     <div>
       <div class="section-label">Sources &amp; provenance</div>
       <div class="source-list" id="sources"><div class="empty">No sources have been produced for this investigation yet.</div></div>
     </div>
     <div id="remainders-section" hidden>
       <div class="section-label">Open items</div>
       <div class="source-list" id="remainders"></div>
     </div>
     <div class="phi" id="phi">Φ is open. Fresta is not an oracle.</div>
     <details class="technical">
       <summary>Technical detail</summary>
       <pre id="technical">No execution yet.</pre>
     </details>
   </section>
 </main>
 <script>
   const token = document.getElementById("token");
   const question = document.getElementById("question");
   const command = document.getElementById("command");
   const status = document.getElementById("status");
   const message = document.getElementById("message");
   const responseSection = document.getElementById("response-section");
   const responseText = document.getElementById("response");
   const sources = document.getElementById("sources");
   const remaindersSection = document.getElementById("remainders-section");
   const remainders = document.getElementById("remainders");
   const technical = document.getElementById("technical");
   const continueButton = document.getElementById("continue");
   const investigateButton = document.getElementById("investigate");
   const runButton = document.getElementById("run");
   let responseMode = "conversation";
   let continuation = null;

   function setStatus(value) {
     status.textContent = value || "UNKNOWN";
     status.className = "status " + String(value || "").toLowerCase();
   }
   function clearChildren(node) {
     while (node.firstChild) node.removeChild(node.firstChild);
   }
   function showList(node, values, emptyText, render) {
     clearChildren(node);
     if (!values.length) {
       const empty = document.createElement("div");
       empty.className = "empty";
       empty.textContent = emptyText;
       node.appendChild(empty);
       return;
     }
     values.forEach((value) => node.appendChild(render(value)));
   }
   function sourceCard(source) {
     const card = document.createElement("div");
     card.className = "source";
     const title = document.createElement("strong");
     title.textContent = source.title || "Untitled source";
     card.appendChild(title);
     const link = document.createElement("a");
     link.href = source.source_locator || "#";
     link.target = "_blank";
     link.rel = "noreferrer";
     link.textContent = source.source_locator || "Locator unavailable";
     card.appendChild(link);
     const meta = document.createElement("small");
     meta.textContent = `authority=${source.authority || "unknown"} · lineage=${source.source_lineage || "unspecified"}`;
     card.appendChild(meta);
     return card;
   }
   function remainderCard(item) {
     const card = document.createElement("div");
     card.className = "remainder";
     card.textContent = item.description || "Open item without a description.";
     return card;
   }
   function showResult(body) {
     const payload = body.payload || {};
     const chat = payload.chat || {};
     const answer = chat.assistant_message || {};
     setStatus(body.state || "UNKNOWN");
     message.textContent = body.message || "No result message.";
     responseSection.hidden = !answer.content;
     responseText.textContent = answer.content || "";
     showList(sources, Array.isArray(payload.sources) ? payload.sources : [], "No external source units were produced.", sourceCard);
     const openRemainders = Array.isArray(payload.remainders) ? payload.remainders : [];
     remaindersSection.hidden = openRemainders.length === 0;
     showList(remainders, openRemainders, "", remainderCard);
     document.getElementById("phi").hidden = payload.phi_open !== true;
     technical.textContent = JSON.stringify(body, null, 2);
     const session = chat.session;
     continuation = body.continuation_checkpoint_id && session
       ? {session_id: session.session_id, checkpoint_id: body.continuation_checkpoint_id}
       : null;
     continueButton.hidden = continuation === null;
   }
   function setBusy(isBusy) {
     investigateButton.disabled = isBusy;
     runButton.disabled = isBusy;
     continueButton.disabled = isBusy;
     if (isBusy) setStatus("RUNNING");
   }
   async function post(path, payload) {
     if (!token.value.trim()) {
       setStatus("ERROR");
       message.textContent = "Paste the transport token shown by run_web.py first.";
       return;
     }
     setBusy(true);
     try {
       const result = await fetch(path, {
         method: "POST",
         headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token.value.trim()}`},
         body: JSON.stringify(payload)
       });
       const body = await result.json();
       showResult(body);
     } catch (error) {
       setStatus("ERROR");
       message.textContent = String(error);
     } finally {
       setBusy(false);
     }
   }
   document.querySelectorAll("[data-mode]").forEach((button) => {
     button.addEventListener("click", () => {
       responseMode = button.dataset.mode;
       document.querySelectorAll("[data-mode]").forEach((item) => item.classList.toggle("active", item === button));
     });
   });
   investigateButton.addEventListener("click", () => post("/investigate", {question: question.value, mode: responseMode}));
   question.addEventListener("keydown", (event) => {
     if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
       event.preventDefault();
       investigateButton.click();
     }
   });
   continueButton.addEventListener("click", () => {
     if (continuation) {
       post("/continue", {...continuation, mode: responseMode, message: "Continue the bounded investigation from this checkpoint."});
     }
   });
   runButton.addEventListener("click", () => post("/command", {command: command.value}));
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
