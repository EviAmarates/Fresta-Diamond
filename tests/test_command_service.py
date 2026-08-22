from __future__ import annotations

import json

import pytest

from fresta_diamond.application import DiamondApplication
from fresta_diamond.cognitive_workspace import (
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.command_service import (
    COMMAND_RESULT_AUTHORITY,
    CommandError,
    CommandResult,
    CommandSpec,
    CommandState,
    DiamondCommandService,
    encode_command_result,
)
from fresta_diamond.concepts import (
    ConceptMembership,
    ConceptRecord,
    ConceptSignature,
    ConceptState,
)
from fresta_diamond.prompt_boundary import read_inert_data
from fresta_diamond.learning import LEARN_PREPARE_CAPABILITY

from .test_application import PERMISSIONS, response_bundle
from .test_concept_evidence import evidence_bundle


def service(tmp_path, adapter, *, run_id="command-run"):
    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_attention_tokens=300,
        max_response_tokens=100,
        run_id_factory=lambda: run_id,
    )
    commands = DiamondCommandService(
        app,
        invocation_id_factory=lambda: "command:test",
    )
    return app, commands


def test_help_exposes_one_canonical_surface_with_model_metadata(tmp_path) -> None:
    _app, commands = service(
        tmp_path,
        lambda *_args, **_kwargs: pytest.fail("help must not call the model"),
    )

    result = commands.execute_line("/help")

    by_name = {item["name"]: item for item in result.payload["commands"]}
    assert set(by_name) == {
        "attention.create",
        "attention.resume",
        "attention.retrieve",
        "attention.status",
        "attention.turn",
        "chat.list",
        "chat.say",
        "chat.start",
        "chat.status",
        "concept.evaluate",
        "concept.inspect",
        "concept.list",
        "concept.nominate",
        "concept.resolve",
        "help",
        "learn",
        "module.inspect",
        "module.proposals",
        "module.suggest",
        "workspace.append",
        "workspace.create",
        "workspace.show",
    }
    assert by_name["learn"]["may_call_model"] is True
    assert by_name["attention.status"]["may_call_model"] is False
    assert by_name["attention.retrieve"]["may_call_model"] is True
    assert by_name["chat.start"]["may_call_model"] is True
    assert by_name["chat.status"]["may_call_model"] is False
    assert by_name["workspace.append"]["may_call_model"] is False
    assert by_name["module.suggest"]["may_call_model"] is True
    assert by_name["concept.list"]["may_call_model"] is False
    assert by_name["concept.nominate"]["may_call_model"] is True
    assert by_name["concept.resolve"]["may_call_model"] is True
    assert result.authority == COMMAND_RESULT_AUTHORITY
    encoded = encode_command_result(result)
    assert json.loads(json.dumps(encoded, ensure_ascii=False))["command"] == "help"


def test_learn_command_uses_application_pipeline_and_reports_commit(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(response_bundle("candidate:command-run")),
            "model": "command-replay",
        }

    app, commands = service(tmp_path, adapter)

    result = commands.execute_line(
        '/learn --scope scope:cars "An engine transforms energy."'
    )

    assert result.command == "learn"
    assert result.state is CommandState.COMPLETED
    assert 1 <= result.model_call_count <= 2
    assert result.payload["commit_id"]
    assert result.payload["sheet_id"] == "learn-command-run"
    assert result.payload["technical_completed"] is True
    assert len(app.learning_commits()) == 1
    assert len(calls) == result.model_call_count


def test_attention_commands_create_turn_status_and_use_same_context(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        return {"content": "Bounded command response.", "model": "command-test"}

    _app, commands = service(tmp_path, adapter)
    created = commands.execute_line(
        '/attention create --scope scope:chat --summary "Fresh task" '
        '"Discuss one bounded object"'
    )
    context_id = created.payload["context"]["context_id"]

    status = commands.execute_line(f"/attention status {context_id}")
    turn = commands.execute_line(
        f'/attention turn {context_id} "Answer from bounded attention"'
    )

    assert status.payload["context"]["context_ref"] == (
        created.payload["context"]["context_ref"]
    )
    assert turn.payload["response"] == "Bounded command response."
    assert turn.state is CommandState.COMPLETED
    assert turn.continuation_checkpoint_id is None
    assert turn.model_call_count == 1
    assert len(calls) == 1


def test_workspace_commands_create_append_and_show_exact_revisions(tmp_path) -> None:
    app, commands = service(
        tmp_path,
        lambda *_args, **_kwargs: pytest.fail("workspace must remain offline"),
    )

    created = commands.execute_line(
        '/workspace create --scope scope:task --title "Task sheet" '
        '--content "Initial bounded note" "Organize the active task"'
    )
    context_id = created.payload["context"]["context_id"]
    original_ref = created.payload["context"]["active_sheet_ref"]
    appended = commands.execute_line(
        f'/workspace append --kind hypothesis {context_id} '
        '"A provisional relation to inspect"'
    )
    shown = commands.execute_line(f"/workspace show {context_id}")

    assert created.model_call_count == appended.model_call_count == 0
    assert created.payload["sheet"]["revision_number"] == 1
    assert appended.payload["sheet"]["revision_number"] == 2
    assert appended.payload["sheet"]["parent_revision_id"] == (
        created.payload["sheet"]["revision_id"]
    )
    assert appended.payload["sheet"]["elements"][-1]["kind"] == "HYPOTHESIS"
    assert shown.payload["sheet"] == appended.payload["sheet"]
    assert appended.payload["context"]["active_sheet_ref"] != original_ref
    assert len(app.workspace.history(created.payload["sheet"]["sheet_id"])) == 2


def test_attention_retrieve_command_materializes_exact_selected_ref(tmp_path) -> None:
    def adapter(_grant, **kwargs):
        request = read_inert_data(
            kwargs["messages"][1]["content"],
            "objective_retrieval_request",
        )
        target = request["candidates"][0]
        return {
            "content": json.dumps({
                "decision": "SELECT",
                "items": [{
                    "item_ref": target["item_ref"],
                    "relevance": 0.9,
                    "contextual_roles": [2],
                    "rationale": "The exact sheet relates to the objective.",
                }],
                "rationale": "One exact bounded root is sufficient.",
            }),
            "model": "command-retrieval-test",
        }

    app, commands = service(tmp_path, adapter)
    app.workspace.save(SheetRevision(
        sheet_id="retrieval-command-sheet",
        revision_number=1,
        title="Retrieval command evidence",
        state=SheetState.STAGED,
        elements=(SheetElement(
            element_id="retrieval:note",
            kind=SheetElementKind.NOTE,
            content="An exact bounded relation for command retrieval.",
            scope="scope:retrieval",
            provenance=("test:command",),
        ),),
    ))

    result = commands.execute_line(
        '/attention retrieve --scope scope:retrieval --budget 300 '
        '"Relate the available exact sheet"'
    )

    assert result.state is CommandState.COMPLETED
    assert result.model_call_count == 1
    assert result.payload["projection"]["injection_ready"] is True
    assert result.payload["projection"]["selected"][0]["item_ref"] == (
        "sheet:retrieval-command-sheet"
    )
    assert result.payload["projection"]["selected"][0]["contextual_roles"] == (2,)


def test_chat_commands_share_persistent_attention_and_history(tmp_path) -> None:
    def adapter(_grant, **kwargs):
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="objective_retrieval_request"' in joined:
            request = read_inert_data(joined, "objective_retrieval_request")
            target = request["candidates"][0]
            return {
                "content": json.dumps({
                    "decision": "SELECT",
                    "items": [{
                        "item_ref": target["item_ref"],
                        "relevance": 0.8,
                        "contextual_roles": [1],
                        "rationale": "Exact chat context.",
                    }],
                    "rationale": "Bounded chat context selected.",
                }),
                "model": "command-chat-test",
            }
        return {
            "content": "Resposta persistente e não validada.",
            "model": "command-chat-test",
        }

    app, commands = service(tmp_path, adapter)
    app.workspace.save(SheetRevision(
        sheet_id="command-chat-context",
        revision_number=1,
        title="Command chat context",
        state=SheetState.STAGED,
        elements=(SheetElement(
            element_id="command-chat:note",
            kind=SheetElementKind.NOTE,
            content="Contexto exato para o chat por comandos.",
            scope="scope:chat-command",
            provenance=("test:chat-command",),
        ),),
    ))

    started = commands.execute_line(
        '/chat start --scope scope:chat-command "Manter uma conversa limitada"'
    )
    session_id = started.payload["session"]["session_id"]
    said = commands.execute_line(
        f'/chat say {session_id} "Responde usando o contexto"'
    )
    status = commands.execute_line(f"/chat status {session_id}")
    listed = commands.execute_line("/chat list")

    assert started.model_call_count == said.model_call_count == 1
    assert said.payload["assistant_message"]["authority"] == (
        "MODEL_RESPONSE_UNVALIDATED"
    )
    assert [item["role"] for item in status.payload["messages"]] == [
        "USER",
        "ASSISTANT",
    ]
    assert listed.payload["sessions"][0]["session_id"] == session_id
    assert status.model_call_count == listed.model_call_count == 0


def test_attention_command_does_not_report_completion_without_response(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        raise RuntimeError("model stopped before producing content")

    _app, commands = service(tmp_path, adapter)
    created = commands.invoke(
        "attention.create",
        objective="Test an interrupted model response.",
    )

    result = commands.invoke(
        "attention.turn",
        context_id=created.payload["context"]["context_id"],
        instruction="Attempt one bounded response.",
    )

    assert result.state is CommandState.INCOMPLETE
    assert result.payload["response"] is None
    assert result.payload["execution_state"] != "COMPLETED"
    assert result.payload["remainders"]
    assert result.model_call_count == 1


def test_attention_command_auto_decomposes_and_returns_continuation(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        return {"content": "Processed one bounded batch.", "model": "command-test"}

    app, commands = service(tmp_path, adapter, run_id="attention-command-run")
    app.workspace.save(SheetRevision(
        sheet_id="large-command-sheet",
        revision_number=1,
        title="Large command sheet",
        state=SheetState.DRAFT,
        elements=(SheetElement(
            element_id="large:content",
            kind=SheetElementKind.NOTE,
            content="X" * 2_000,
            scope="scope:commands",
            provenance=("test:commands",),
        ),),
    ))
    created = commands.invoke(
        "attention.create",
        objective="Process one oversized command object.",
        scope="scope:commands",
        summary="Oversized object awaiting attention.",
        selected_refs=("sheet:large-command-sheet",),
    )
    context_id = created.payload["context"]["context_id"]

    turn = commands.invoke(
        "attention.turn",
        context_id=context_id,
        instruction="Process the available exact batch.",
        token_budget=200,
    )

    assert turn.state is CommandState.SUSPENDED
    assert turn.continuation_checkpoint_id
    assert turn.payload["decomposition_root_ref"].startswith("sheet-revision:")
    assert turn.payload["pending_refs"]

    resumed = commands.invoke(
        "attention.resume",
        checkpoint_id=turn.continuation_checkpoint_id,
    )
    assert resumed.payload["context"]["state"] == "ACTIVE"
    assert tuple(resumed.payload["context"]["workspace_sheet_refs"]) == tuple(
        turn.payload["pending_refs"]
    )


def test_registry_can_add_a_command_without_editing_service_or_interface(tmp_path) -> None:
    _app, commands = service(
        tmp_path,
        lambda *_args, **_kwargs: pytest.fail("custom command must not call model"),
    )

    def handler(invocation):
        return CommandResult(
            invocation.invocation_id,
            invocation.command,
            CommandState.COMPLETED,
            "Custom capability reached.",
            {"value": 42},
        )

    commands.registry.register(
        CommandSpec(
            "custom.inspect",
            "Inspect one custom capability.",
            "/custom-inspect",
            aliases=("custom-inspect",),
        ),
        handler,
    )

    result = commands.execute_line("/custom-inspect")
    assert result.payload == {"value": 42}


def test_module_commands_refuse_duplicate_list_and_inspect_without_llm(tmp_path) -> None:
    calls = []
    _app, commands = service(
        tmp_path,
        lambda *_args, **_kwargs: calls.append(True),
    )

    suggestion = commands.execute_line(
        "/module suggest --output-schema artifact://learning-proposal@1 "
        f"{LEARN_PREPARE_CAPABILITY} prepare-an-existing-learning-proposal"
    )
    suggestion_id = suggestion.payload["suggestion"]["suggestion_id"]
    listed = commands.execute_line("/module proposals")
    inspected = commands.execute_line(f"/module inspect {suggestion_id}")

    assert calls == []
    assert suggestion.model_call_count == 0
    assert suggestion.payload["deterministic_reuse"] is True
    assert suggestion.payload["executable_code_created"] is False
    assert suggestion.payload["module_enabled"] is False
    assert listed.payload["suggestions"][0]["suggestion_id"] == suggestion_id
    assert inspected.payload["suggestion"]["decision"] == "NO_NEW_MODULE"
    assert inspected.payload["content_hash"]


def test_concept_list_and_inspect_share_text_and_structured_boundary(tmp_path) -> None:
    app, commands = service(
        tmp_path,
        lambda *_args, **_kwargs: pytest.fail("inspection must remain offline"),
    )
    record = ConceptRecord(
        concept_id="concept:bounded-vehicle",
        version=1,
        canonical_name="Bounded vehicle",
        aliases=("Vehicle",),
        scope="scope:cars",
        state=ConceptState.CANDIDATE,
        signature=ConceptSignature(
            characteristics=("bounded functional identity",),
            constraints=("requires coherent component relations",),
        ),
        memberships=(
            ConceptMembership("crystal:vehicle-a"),
            ConceptMembership("crystal:vehicle-b"),
        ),
    )
    app.concept_store.save(record)

    textual = commands.execute_line("/concept list --scope scope:cars")
    structured = commands.invoke("concept.list", scope="scope:cars")
    inspected = commands.execute_line(
        "/concept inspect --version 1 concept:bounded-vehicle"
    )

    assert textual.model_call_count == structured.model_call_count == 0
    assert textual.payload["concepts"] == structured.payload["concepts"]
    assert textual.payload["concepts"][0]["version_ref"] == record.version_ref
    assert inspected.payload["concept"]["concept_id"] == record.concept_id
    assert inspected.payload["history_refs"] == (record.version_ref,)
    assert inspected.payload["concept"]["promotion_authority"] is False


def test_concept_nominate_then_resolve_uses_existing_application_pipelines(
    tmp_path,
) -> None:
    run_ids = iter(("command-concept-a", "command-concept-b"))
    learn_elements = iter((
        "candidate:command-concept-a",
        "candidate:command-concept-b",
    ))
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        joined = "\n".join(item["content"] for item in kwargs["messages"])
        if 'label="concept_inputs"' in joined:
            trusted = read_inert_data(joined, "concept_inputs")
            return {
                "content": json.dumps({
                    "decision": "PROPOSE",
                    "canonical_name": "Functional vehicle",
                    "aliases": ["Vehicle"],
                    "crystal_ids": [
                        item["crystal_id"] for item in trusted["crystals"]
                    ],
                    "parent_concept_ids": [],
                    "signature": {
                        "characteristics": ["bounded functional identity"],
                        "relations": ["components sustain operation"],
                        "functions": ["transform energy into movement"],
                        "constraints": ["preserve source scope"],
                        "exclusions": ["unrelated aggregates"],
                        "examples": [],
                        "counterexamples": [],
                    },
                    "rationale": "Two crystals support one bounded candidate.",
                }),
                "model": "command-concept-replay",
            }
        if 'label="concept_candidate"' in joined:
            raw = read_inert_data(joined, "concept_candidate")
            return {
                "content": json.dumps(evidence_bundle(raw)),
                "model": "command-concept-replay",
            }
        return {
            "content": json.dumps(response_bundle(next(learn_elements))),
            "model": "command-concept-replay",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
    )
    commands = DiamondCommandService(
        app,
        invocation_id_factory=lambda: "command:concept-test",
    )
    for text in (
        "An engine transforms energy.",
        "Components sustain a functional identity.",
    ):
        app.learn_text(
            text,
            scope="scope:cars",
            provenance=("document:mechanics:p4",),
        )

    nominated = commands.execute_line(
        "/concept nominate --scope scope:cars "
        '"Nominate one bounded functional concept"'
    )
    concept_id = nominated.payload["concept"]["concept_id"]
    resolved = commands.execute_line(
        "/concept resolve --objective \"Evaluate the bounded candidate only.\" "
        f"--queries 1 --results 1 {concept_id}"
    )

    assert nominated.model_call_count == 1
    assert nominated.payload["nomination"]["authority"] == (
        "UNVALIDATED_CONCEPT_NOMINATION"
    )
    assert nominated.payload["concept"]["state"] == "CANDIDATE"
    assert resolved.model_call_count == 1
    assert resolved.payload["initial_validation"]["recommended_state"] == (
        "VALIDATED"
    )
    assert resolved.payload["resolution_attempted"] is False
    assert resolved.payload["research"] is None
    assert resolved.payload["concept"]["state"] == "VALIDATED"
    assert resolved.payload["concept"]["version"] == 2
    assert resolved.payload["concept"]["promotion_authority"] is False
    assert len(calls) == 4


def test_command_parser_rejects_unknowns_and_bad_options(tmp_path) -> None:
    _app, commands = service(tmp_path, lambda *_args, **_kwargs: {})

    with pytest.raises(CommandError, match="Unknown command"):
        commands.execute_line("/invented")
    with pytest.raises(CommandError, match="Unknown option"):
        commands.execute_line("/learn --invent-authority yes text")
    with pytest.raises(CommandError, match="integer"):
        commands.execute_line("/attention turn --budget many context:x do work")
    with pytest.raises(CommandError, match="between 1 and 6"):
        commands.execute_line("/concept resolve --queries 0 concept:any")
