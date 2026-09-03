"""Shared headless command boundary for future REPL and Web adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any
import shlex
from uuid import uuid4

from fresta_diamond.application import CHAT_RESPONSE_MODES, DiamondApplication
from fresta_diamond.attention_memory import AttentionContextRevision
from fresta_diamond.cognitive_workspace import (
    SheetElementKind,
    encode_sheet_revision,
)
from fresta_diamond.concepts import (
    ConceptRecord,
    ConceptState,
    encode_concept_record,
)
from fresta_diamond.concept_research import decode_source_units
from fresta_diamond.concept_nomination import ConceptNomination
from fresta_diamond.concept_validation import encode_concept_validation_report
from fresta_diamond.module_design import ModuleSuggestion
from fresta_diamond.chat import (
    ChatMessage,
    ChatSession,
    encode_chat_message,
    encode_chat_session,
)
from fresta_diamond.brain_analysis import encode_brain_analysis


COMMAND_INVOCATION_AUTHORITY = "COMMAND_INVOCATION_ONLY"
COMMAND_RESULT_AUTHORITY = "COMMAND_RESULT_ONLY"


class CommandState(str, Enum):
    COMPLETED = "COMPLETED"
    SUSPENDED = "SUSPENDED"
    IDLE = "IDLE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    usage: str
    aliases: tuple[str, ...] = ()
    may_call_model: bool = False

    def __post_init__(self) -> None:
        names = (self.name, *self.aliases)
        if any(not item.strip() or item.startswith("/") for item in names):
            raise ValueError("Command names must be non-empty and omit slash")
        if len(names) != len(set(names)):
            raise ValueError("Command names and aliases must be unique")
        if not self.description.strip() or not self.usage.strip():
            raise ValueError("Command description and usage are required")


@dataclass(frozen=True)
class CommandInvocation:
    command: str
    arguments: Mapping[str, Any]
    invocation_id: str = field(default_factory=lambda: f"command:{uuid4()}")
    authority: str = COMMAND_INVOCATION_AUTHORITY

    def __post_init__(self) -> None:
        if not self.command.strip() or not self.invocation_id.strip():
            raise ValueError("Command invocation identifiers are required")
        if self.authority != COMMAND_INVOCATION_AUTHORITY:
            raise PermissionError("A command invocation cannot grant authority")
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class CommandResult:
    invocation_id: str
    command: str
    state: CommandState
    message: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    model_call_count: int = 0
    continuation_checkpoint_id: str | None = None
    authority: str = COMMAND_RESULT_AUTHORITY

    def __post_init__(self) -> None:
        if not self.invocation_id.strip() or not self.command.strip():
            raise ValueError("Command result identifiers are required")
        if not self.message.strip():
            raise ValueError("Command result message is required")
        if self.model_call_count < 0:
            raise ValueError("Model call count cannot be negative")
        if self.authority != COMMAND_RESULT_AUTHORITY:
            raise PermissionError("A command result cannot grant authority")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class CommandError(RuntimeError):
    """A command could not be resolved or validated."""


CommandHandler = Callable[[CommandInvocation], CommandResult]
CommandLineParser = Callable[[tuple[str, ...]], Mapping[str, Any]]


class CommandRegistry:
    """Resolve command names without coupling interface code to handlers."""

    def __init__(self) -> None:
        self._specs: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}
        self._handlers: dict[str, CommandHandler] = {}
        self._parsers: dict[str, CommandLineParser] = {}

    def register(
        self,
        spec: CommandSpec,
        handler: CommandHandler,
        *,
        line_parser: CommandLineParser | None = None,
    ) -> None:
        names = (spec.name, *spec.aliases)
        collisions = set(names).intersection(self._aliases)
        if collisions:
            raise CommandError(f"Command name already registered: {sorted(collisions)[0]}")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler
        if line_parser is not None:
            self._parsers[spec.name] = line_parser
        for name in names:
            self._aliases[name] = spec.name

    def resolve(self, name: str) -> tuple[CommandSpec, CommandHandler]:
        canonical = self._aliases.get(_normalize_name(name))
        if canonical is None:
            raise CommandError(f"Unknown command: {name}")
        return self._specs[canonical], self._handlers[canonical]

    def parser(self, name: str) -> CommandLineParser | None:
        canonical = self._aliases.get(_normalize_name(name))
        return self._parsers.get(canonical) if canonical is not None else None

    def specs(self) -> tuple[CommandSpec, ...]:
        return tuple(self._specs[name] for name in sorted(self._specs))


class DiamondCommandService:
    """One shared command surface over an injected persistent application."""

    def __init__(
        self,
        application: DiamondApplication,
        *,
        invocation_id_factory: Callable[[], str] | None = None,
        concept_search_adapter: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        self.application = application
        self.registry = CommandRegistry()
        self._invocation_id_factory = invocation_id_factory or (
            lambda: f"command:{uuid4()}"
        )
        self._concept_search_adapter = concept_search_adapter
        self._register_builtins()

    def invoke(self, command: str, **arguments: Any) -> CommandResult:
        spec, handler = self.registry.resolve(command)
        invocation_id = self._invocation_id_factory()
        invocation = CommandInvocation(
            command=spec.name,
            arguments=arguments,
            invocation_id=invocation_id,
        )
        result = handler(invocation)
        if result.invocation_id != invocation_id or result.command != spec.name:
            raise CommandError("Command handler returned a result for another invocation")
        return result

    def execute_line(self, line: str) -> CommandResult:
        try:
            tokens = tuple(shlex.split(line, posix=True))
        except ValueError as exc:
            raise CommandError(f"Invalid command quoting: {exc}") from exc
        if not tokens:
            raise CommandError("Command line cannot be empty")
        name, arguments = self._line_target(tokens)
        spec, _handler = self.registry.resolve(name)
        parser = self.registry.parser(spec.name)
        if parser is None:
            if arguments:
                raise CommandError(f"{spec.name} does not accept line arguments")
            parsed: Mapping[str, Any] = {}
        else:
            parsed = parser(arguments)
        return self.invoke(spec.name, **dict(parsed))

    def _line_target(self, tokens: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
        first = _normalize_name(tokens[0])
        if len(tokens) >= 2:
            compound = f"{first}.{_normalize_name(tokens[1])}"
            try:
                self.registry.resolve(compound)
            except CommandError:
                pass
            else:
                return compound, tokens[2:]
        return first, tokens[1:]

    def _register_builtins(self) -> None:
        self.registry.register(
            CommandSpec(
                "help",
                "List the canonical shared command surface.",
                "/help",
            ),
            self._help,
        )
        self.registry.register(
            CommandSpec(
                "learn",
                "Evaluate and commit one bounded candidate through /learn.",
                "/learn [--scope SCOPE] [--objective OBJECTIVE] TEXT",
                may_call_model=True,
            ),
            self._learn,
            line_parser=_parse_learn,
        )
        self.registry.register(
            CommandSpec(
                "research",
                "Investigate one question through objective-relative retrieval and bounded Web research.",
                "/research [--scope SCOPE] [--mode conversation|analysis] "
                "[--queries N] [--results N] QUESTION",
                aliases=("investigate",),
                may_call_model=True,
            ),
            self._research,
            line_parser=_parse_research,
        )
        self.registry.register(
            CommandSpec(
                "chat.start",
                "Start persistent objective-relative chat attention.",
                "/chat start [--scope SCOPE] [--summary TEXT] [--budget N] "
                "[--batch-budget N] OBJECTIVE",
                aliases=("chat-start",),
                may_call_model=True,
            ),
            self._chat_start,
            line_parser=_parse_chat_start,
        )
        self.registry.register(
            CommandSpec(
                "chat.say",
                "Persist one user message and run a bounded attention response.",
                "/chat say [--budget N] [--mode conversation|analysis] "
                "SESSION_ID MESSAGE",
                aliases=("chat-say",),
                may_call_model=True,
            ),
            self._chat_say,
            line_parser=_parse_chat_say,
        )
        self.registry.register(
            CommandSpec(
                "chat.status",
                "Inspect one chat binding and its sealed canonical history.",
                "/chat status SESSION_ID",
                aliases=("chat-status",),
            ),
            self._chat_status,
            line_parser=_parse_chat_status,
        )
        self.registry.register(
            CommandSpec(
                "chat.archive",
                "Archive a chat without deleting its sealed history.",
                "/chat archive SESSION_ID REASON",
                aliases=("chat-archive",),
            ),
            self._chat_archive,
            line_parser=_parse_chat_lifecycle,
        )
        self.registry.register(
            CommandSpec(
                "chat.abandon",
                "Abandon a chat without deleting its sealed history.",
                "/chat abandon SESSION_ID REASON",
                aliases=("chat-abandon",),
            ),
            self._chat_abandon,
            line_parser=_parse_chat_lifecycle,
        )
        self.registry.register(
            CommandSpec(
                "chat.resume",
                "Resume chat attention and return the exact transcript head.",
                "/chat resume SESSION_ID CHECKPOINT_ID [SUMMARY]",
                aliases=("chat-resume",),
            ),
            self._chat_resume,
            line_parser=_parse_chat_resume,
        )
        self.registry.register(
            CommandSpec(
                "chat.list",
                "List persistent chat bindings without reading message content.",
                "/chat list",
                aliases=("chat-list",),
            ),
            self._chat_list,
        )
        self.registry.register(
            CommandSpec(
                "attention.create",
                "Create one persistent foreground attention context.",
                "/attention create [--scope SCOPE] [--summary TEXT] OBJECTIVE",
                aliases=("attention-create",),
            ),
            self._attention_create,
            line_parser=_parse_attention_create,
        )
        self.registry.register(
            CommandSpec(
                "attention.turn",
                "Run one bounded attention turn with automatic sleep/decomposition.",
                "/attention turn [--budget N] CONTEXT_ID INSTRUCTION",
                aliases=("attention-turn",),
                may_call_model=True,
            ),
            self._attention_turn,
            line_parser=_parse_attention_turn,
        )
        self.registry.register(
            CommandSpec(
                "attention.resume",
                "Reactivate only pending refs from one continuation checkpoint.",
                "/attention resume CHECKPOINT_ID [SUMMARY]",
                aliases=("attention-resume",),
            ),
            self._attention_resume,
            line_parser=_parse_attention_resume,
        )
        self.registry.register(
            CommandSpec(
                "attention.status",
                "Inspect one context or the current foreground context.",
                "/attention status [CONTEXT_ID]",
                aliases=("attention-status",),
            ),
            self._attention_status,
            line_parser=_parse_attention_status,
        )
        self.registry.register(
            CommandSpec(
                "attention.retrieve",
                "Select exact objective-relative refs and create bounded attention.",
                "/attention retrieve [--scope SCOPE] [--budget N] "
                "[--batch-budget N] OBJECTIVE",
                aliases=("retrieve", "attention-retrieve"),
                may_call_model=True,
            ),
            self._attention_retrieve,
            line_parser=_parse_attention_retrieve,
        )
        self.registry.register(
            CommandSpec(
                "workspace.create",
                "Create a versioned active sheet bound to a new attention context.",
                "/workspace create [--scope SCOPE] [--summary TEXT] "
                "[--title TEXT] [--content TEXT] OBJECTIVE",
                aliases=("workspace-create",),
            ),
            self._workspace_create,
            line_parser=_parse_workspace_create,
        )
        self.registry.register(
            CommandSpec(
                "workspace.show",
                "Read the exact active sheet revision for one attention context.",
                "/workspace show CONTEXT_ID",
                aliases=("workspace-show",),
            ),
            self._workspace_show,
            line_parser=_parse_workspace_show,
        )
        self.registry.register(
            CommandSpec(
                "workspace.append",
                "Append one element as a new immutable active-sheet revision.",
                "/workspace append [--kind KIND] [--summary TEXT] "
                "CONTEXT_ID CONTENT",
                aliases=("workspace-append",),
            ),
            self._workspace_append,
            line_parser=_parse_workspace_append,
        )
        self.registry.register(
            CommandSpec(
                "concept.list",
                "List latest or historical concept records without model use.",
                "/concept list [--scope SCOPE] [--state STATE] [--all-versions]",
                aliases=("concept-list",),
            ),
            self._concept_list,
            line_parser=_parse_concept_list,
        )
        self.registry.register(
            CommandSpec(
                "concept.inspect",
                "Inspect one exact concept version and its authority boundary.",
                "/concept inspect [--version N] CONCEPT_ID",
                aliases=("concept-inspect",),
            ),
            self._concept_inspect,
            line_parser=_parse_concept_inspect,
        )
        self.registry.register(
            CommandSpec(
                "concept.nominate",
                "Ask the model to nominate or refuse one bounded concept.",
                "/concept nominate [--scope SCOPE] [--crystals ID,ID] OBJECTIVE",
                aliases=("concept-nominate",),
                may_call_model=True,
            ),
            self._concept_nominate,
            line_parser=_parse_concept_nominate,
        )
        self.registry.register(
            CommandSpec(
                "concept.evaluate",
                "Propose evidence and deterministically evaluate one candidate.",
                "/concept evaluate [--objective TEXT] CONCEPT_ID",
                aliases=("concept-evaluate",),
                may_call_model=True,
            ),
            self._concept_evaluate,
            line_parser=_parse_concept_evaluate,
        )
        self.registry.register(
            CommandSpec(
                "concept.resolve",
                "Evaluate a candidate and resolve only exact researchable gaps.",
                "/concept resolve [--objective TEXT] [--queries N] "
                "[--results N] CONCEPT_ID",
                aliases=("concept-resolve",),
                may_call_model=True,
            ),
            self._concept_resolve,
            line_parser=_parse_concept_resolve,
        )
        self.registry.register(
            CommandSpec(
                "module.suggest",
                "Refuse or archive one non-executable below-controller design.",
                "/module suggest --output-schema SCHEMA CAPABILITY OBJECTIVE",
                aliases=("module-suggest",),
                may_call_model=True,
            ),
            self._module_suggest,
            line_parser=_parse_module_suggest,
        )
        self.registry.register(
            CommandSpec(
                "module.proposals",
                "List archived module design decisions without loading code.",
                "/module proposals",
                aliases=("module-proposals",),
            ),
            self._module_proposals,
        )
        self.registry.register(
            CommandSpec(
                "module.inspect",
                "Inspect one exact archived module design decision.",
                "/module inspect SUGGESTION_ID",
                aliases=("module-inspect",),
            ),
            self._module_inspect,
            line_parser=_parse_module_inspect,
        )
        self.registry.register(
            CommandSpec(
                "profile.inspect",
                "Audit user-profile proposal and adoption lineage without mutation.",
                "/profile inspect [CLAIM_ID]",
                aliases=("profile-inspect",),
            ),
            self._profile_inspect,
            line_parser=_parse_profile_inspect,
        )
        self.registry.register(
            CommandSpec(
                "personality.inspect",
                "Audit assistant-personality proposal and adoption lineage without mutation.",
                "/personality inspect [TRAIT_ID]",
                aliases=("personality-inspect",),
            ),
            self._personality_inspect,
            line_parser=_parse_personality_inspect,
        )
        self.registry.register(
            CommandSpec(
                "brain.analyze",
                "Create an immutable deterministic inventory and bounded diagnosis.",
                "/brain analyze",
            ),
            self._brain_analyze,
        )
        self.registry.register(
            CommandSpec(
                "document.checkpoints",
                "List durable document-learning cursors without mutation.",
                "/document checkpoints",
            ),
            self._document_checkpoints,
        )
        self.registry.register(
            CommandSpec(
                "document.checkpoint",
                "Inspect one durable document-learning cursor.",
                "/document checkpoint CHECKPOINT_ID",
                aliases=("document-checkpoint",),
            ),
            self._document_checkpoint,
            line_parser=_parse_document_checkpoint,
        )
        self.registry.register(
            CommandSpec(
                "document.resume",
                "Resume pending document-learning leaves through the normal pipeline.",
                "/document resume CHECKPOINT_ID [--max-leaves N]",
                aliases=("document-resume",),
                may_call_model=True,
            ),
            self._document_resume,
            line_parser=_parse_document_resume,
        )

    def _help(self, invocation: CommandInvocation) -> CommandResult:
        commands = tuple(
            {
                "name": item.name,
                "aliases": item.aliases,
                "description": item.description,
                "usage": item.usage,
                "may_call_model": item.may_call_model,
            }
            for item in self.registry.specs()
        )
        return self._result(invocation, "Canonical commands listed.", {"commands": commands})

    def _learn(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        text = _required_text(args, "text")
        outcome = self.application.learn_text(
            text,
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            objective=_optional_text(
                args,
                "objective",
                "Evaluate this candidate without assuming it is true.",
            ),
            provenance=_text_tuple(
                args.get("provenance", ("operator:user-supplied",)),
                "provenance",
            ),
            kind=SheetElementKind(args.get("kind", SheetElementKind.CLAIM)),
        )
        commit = outcome.stored_commit.commit
        crystals = commit.crystallization.crystals
        payload = {
            "sheet_id": outcome.sheet_id,
            "element_id": outcome.element_id,
            "proposal_id": commit.proposal_id,
            "commit_id": commit.commit_id,
            "commit_hash": outcome.stored_commit.content_hash,
            "crystal_states": tuple(item.state.value for item in crystals),
            "negative_boundary_count": len(commit.negative_boundary),
            "repair_attempts_used": outcome.repair_attempts_used,
            "execution_state": outcome.result.execution.state.value,
            "technical_completed": (
                outcome.result.execution.closure.technical_completed
            ),
        }
        return self._result(
            invocation,
            f"Learn committed {len(crystals)} crystal candidate(s).",
            payload,
            model_call_count=outcome.model_call_count,
        )

    def _research(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        objective = _required_text(args, "question")
        scope = _optional_text(args, "scope", "scope:diamond-web")
        max_queries = _bounded_integer(args, "max_queries", default=2, maximum=6)
        max_results = _bounded_integer(
            args,
            "max_results_per_query",
            default=2,
            maximum=10,
        )
        response_mode = _optional_text(args, "response_mode", "conversation")
        if response_mode not in CHAT_RESPONSE_MODES:
            raise CommandError(
                "Response mode must be 'conversation' or 'analysis'"
            )
        research = self.application.research_objective(
            objective=objective,
            scope=scope,
            search_adapter=self._concept_search_adapter,
            max_queries=max_queries,
            max_results_per_query=max_results,
        )
        payload = _research_payload(research, objective, response_mode)
        model_calls = research.model_call_count
        if not payload["sources"]:
            return self._result(
                invocation,
                "Investigation stopped before external evidence was produced; "
                "no source-grounded response was generated.",
                payload,
                state=CommandState.INCOMPLETE,
                model_call_count=model_calls,
            )

        started = self.application.start_chat(
            scope=scope,
            objective=objective,
            summary="Continue the bounded investigation without closing Phi.",
        )
        model_calls += started.model_call_count
        if started.session is None or started.context is None:
            payload["chat"] = None
            return self._result(
                invocation,
                "Investigation produced evidence, but objective-relative attention "
                "did not produce a chat context.",
                payload,
                state=CommandState.INCOMPLETE,
                model_call_count=model_calls,
            )

        turn = self.application.chat_turn(
            started.session.session_id,
            objective,
            response_mode=response_mode,
        )
        model_calls += turn.model_call_count
        checkpoint_id = (
            turn.attention.continuation.checkpoint_id
            if turn.attention.continuation is not None
            else None
        )
        state = (
            CommandState.SUSPENDED
            if turn.attention.sleep_revision is not None
            else (
                CommandState.COMPLETED
                if turn.assistant_message is not None
                else CommandState.INCOMPLETE
            )
        )
        payload["chat"] = {
            "session": encode_chat_session(turn.session),
            "user_message": encode_chat_message(turn.user_message),
            "assistant_message": (
                encode_chat_message(turn.assistant_message)
                if turn.assistant_message is not None
                else None
            ),
            "context": _context_payload(turn.context),
            "transcript_revision": turn.transcript.revision_number,
            "execution_state": turn.attention.result.execution.state.value,
            "remainders": _execution_remainders(turn.attention.result),
        }
        return self._result(
            invocation,
            (
                "Investigation completed with an open, source-grounded response."
                if state is CommandState.COMPLETED
                else "Investigation is bounded and can continue from its checkpoint."
            ),
            payload,
            state=state,
            model_call_count=model_calls,
            continuation_checkpoint_id=checkpoint_id,
        )

    def _chat_start(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        token_budget = args.get("token_budget")
        if token_budget is not None:
            token_budget = _minimum_integer(args, "token_budget", minimum=32)
        batch_budget = args.get("candidate_batch_tokens")
        if batch_budget is not None:
            batch_budget = _minimum_integer(
                args,
                "candidate_batch_tokens",
                minimum=128,
            )
        outcome = self.application.start_chat(
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            objective=_required_text(args, "objective"),
            summary=args.get("summary"),
            token_budget=token_budget,
            candidate_batch_tokens=batch_budget,
        )
        if outcome.session is None or outcome.context is None:
            assert outcome.retrieval is not None
            return self._result(
                invocation,
                "Chat start stopped because retrieval did not produce a decision.",
                {
                    "session": None,
                    "context": None,
                    "retrieval_state": outcome.retrieval.result.execution.state.value,
                    "remainders": _execution_remainders(outcome.retrieval.result),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )
        return self._result(
            invocation,
            "Persistent chat started over objective-relative attention.",
            {
                "session": encode_chat_session(outcome.session),
                "context": _context_payload(outcome.context),
                "transcript": encode_sheet_revision(outcome.transcript),
                "retrieval_decision": (
                    outcome.retrieval.nomination.decision.value
                    if outcome.retrieval is not None else "NO_CANDIDATES"
                ),
            },
            model_call_count=outcome.model_call_count,
        )

    def _chat_say(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        token_budget = args.get("token_budget")
        if token_budget is not None:
            token_budget = _minimum_integer(args, "token_budget", minimum=32)
        response_mode = _optional_text(
            args,
            "response_mode",
            "conversation",
        )
        if response_mode not in CHAT_RESPONSE_MODES:
            raise CommandError(
                "Response mode must be 'conversation' or 'analysis'"
            )
        outcome = self.application.chat_turn(
            _required_text(args, "session_id"),
            _required_text(args, "message"),
            token_budget=token_budget,
            response_mode=response_mode,
        )
        checkpoint_id = (
            outcome.attention.continuation.checkpoint_id
            if outcome.attention.continuation is not None else None
        )
        state = (
            CommandState.SUSPENDED
            if outcome.attention.sleep_revision is not None
            else (
                CommandState.COMPLETED
                if outcome.assistant_message is not None
                else CommandState.INCOMPLETE
            )
        )
        return self._result(
            invocation,
            (
                "Chat turn persisted and attention suspended."
                if state is CommandState.SUSPENDED
                else (
                    "Chat turn persisted."
                    if state is CommandState.COMPLETED
                    else "User message persisted without a model response."
                )
            ),
            {
                "session": encode_chat_session(outcome.session),
                "user_message": encode_chat_message(outcome.user_message),
                "assistant_message": (
                    encode_chat_message(outcome.assistant_message)
                    if outcome.assistant_message is not None else None
                ),
                "context": _context_payload(outcome.context),
                "transcript_revision": outcome.transcript.revision_number,
                "execution_state": outcome.attention.result.execution.state.value,
                "remainders": _execution_remainders(outcome.attention.result),
            },
            state=state,
            model_call_count=outcome.model_call_count,
            continuation_checkpoint_id=checkpoint_id,
        )

    def _chat_status(self, invocation: CommandInvocation) -> CommandResult:
        session_id = _required_text(invocation.arguments, "session_id")
        session = self.application.chat_session(session_id)
        messages = self.application.chat_messages(session_id)
        context = self.application.attention_memory.latest(session.context_id)
        return self._result(
            invocation,
            f"Chat contains {len(messages)} sealed message(s).",
            {
                "session": encode_chat_session(session),
                "context": _context_payload(context),
                "messages": tuple(encode_chat_message(item) for item in messages),
            },
            state=(
                CommandState.SUSPENDED
                if context.state.value == "SUSPENDED"
                else CommandState.COMPLETED
            ),
        )

    def _chat_archive(self, invocation: CommandInvocation) -> CommandResult:
        return self._close_chat(invocation, archive=True)

    def _chat_abandon(self, invocation: CommandInvocation) -> CommandResult:
        return self._close_chat(invocation, archive=False)

    def _close_chat(
        self,
        invocation: CommandInvocation,
        *,
        archive: bool,
    ) -> CommandResult:
        args = invocation.arguments
        session_id = _required_text(args, "session_id")
        reason = _required_text(args, "reason")
        session = (
            self.application.archive_chat(session_id, reason=reason)
            if archive
            else self.application.abandon_chat(session_id, reason=reason)
        )
        return self._result(
            invocation,
            f"Chat session {session.state.value.lower()}.",
            {"session": encode_chat_session(session)},
        )

    def _chat_resume(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        context, transcript = self.application.resume_chat(
            _required_text(args, "session_id"),
            _required_text(args, "checkpoint_id"),
            summary=args.get("summary"),
        )
        return self._result(
            invocation,
            "Chat attention resumed with the current transcript head.",
            {
                "context": _context_payload(context),
                "transcript": encode_sheet_revision(transcript),
            },
        )

    def _chat_list(self, invocation: CommandInvocation) -> CommandResult:
        sessions = self.application.chat_sessions()
        return self._result(
            invocation,
            f"Listed {len(sessions)} persistent chat session(s).",
            {"sessions": tuple(encode_chat_session(item) for item in sessions)},
            state=CommandState.IDLE if not sessions else CommandState.COMPLETED,
        )

    def _attention_create(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        objective = _required_text(args, "objective")
        context = self.application.create_attention_context(
            objective=objective,
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            summary=_optional_text(args, "summary", objective),
            selected_refs=_text_tuple(args.get("selected_refs", ()), "selected_refs"),
            validated_refs=_text_tuple(args.get("validated_refs", ()), "validated_refs"),
            workspace_sheet_refs=_text_tuple(
                args.get("workspace_sheet_refs", ()),
                "workspace_sheet_refs",
            ),
            active_sheet_ref=args.get("active_sheet_ref"),
            source_refs=_text_tuple(args.get("source_refs", ()), "source_refs"),
            remainder_refs=_text_tuple(args.get("remainder_refs", ()), "remainder_refs"),
        )
        return self._result(
            invocation,
            "Attention context created.",
            {"context": _context_payload(context)},
        )

    def _attention_turn(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        context_id = _required_text(args, "context_id")
        token_budget = args.get("token_budget")
        if token_budget is not None and (
            not isinstance(token_budget, int)
            or isinstance(token_budget, bool)
            or token_budget < 32
        ):
            raise CommandError("token_budget must be an integer >= 32")
        auto_decompose = args.get("auto_decompose", True)
        if not isinstance(auto_decompose, bool):
            raise CommandError("auto_decompose must be boolean")
        outcome = self.application.attention_turn(
            context_id,
            instruction=_required_text(args, "instruction"),
            token_budget=token_budget,
            auto_decompose=auto_decompose,
        )
        response = outcome.result.execution.artifacts.get("response")
        checkpoint_id = (
            outcome.continuation.checkpoint_id
            if outcome.continuation is not None else None
        )
        state = (
            CommandState.SUSPENDED
            if outcome.sleep_revision is not None
            else (
                CommandState.COMPLETED
                if response is not None else CommandState.INCOMPLETE
            )
        )
        payload = {
            "context": _context_payload(outcome.context),
            "response": response.payload.get("content") if response else None,
            "projection_state": (
                response.payload.get("projection_state") if response else None
            ),
            "pending_refs": (
                outcome.continuation.pending_refs
                if outcome.continuation is not None else ()
            ),
            "decomposition_root_ref": (
                outcome.decomposition.root.reference.target_ref
                if outcome.decomposition is not None else None
            ),
            "execution_state": outcome.result.execution.state.value,
            "remainders": tuple({
                "kind": item.kind.value,
                "required_for": item.required_for,
                "description": item.description,
            } for item in outcome.result.execution.remainders),
        }
        if response is None:
            message = (
                "Attention suspended without a model response; inspect remainders."
                if checkpoint_id
                else "Attention turn did not produce a model response."
            )
        else:
            message = (
                "Attention turn suspended with pending refs."
                if checkpoint_id else "Attention turn completed."
            )
        return self._result(
            invocation,
            message,
            payload,
            state=state,
            model_call_count=outcome.model_call_count,
            continuation_checkpoint_id=checkpoint_id,
        )

    def _attention_resume(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        context = self.application.resume_attention(
            _required_text(args, "checkpoint_id"),
            summary=args.get("summary"),
        )
        return self._result(
            invocation,
            "Attention resumed with pending refs only.",
            {"context": _context_payload(context)},
        )

    def _attention_status(self, invocation: CommandInvocation) -> CommandResult:
        context_id = invocation.arguments.get("context_id")
        context = (
            self.application.attention_memory.latest(_required_text(
                invocation.arguments,
                "context_id",
            ))
            if context_id is not None
            else self.application.attention_memory.active()
        )
        if context is None:
            return self._result(
                invocation,
                "No foreground attention context is active.",
                {"context": None},
                state=CommandState.IDLE,
            )
        return self._result(
            invocation,
            f"Attention context is {context.state.value}.",
            {"context": _context_payload(context)},
            state=(
                CommandState.SUSPENDED
                if context.state.value == "SUSPENDED"
                else CommandState.COMPLETED
            ),
        )

    def _attention_retrieve(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        token_budget = args.get("token_budget")
        if token_budget is not None:
            token_budget = _minimum_integer(args, "token_budget", minimum=32)
        batch_budget = args.get("candidate_batch_tokens")
        if batch_budget is not None:
            batch_budget = _minimum_integer(
                args,
                "candidate_batch_tokens",
                minimum=128,
            )
        outcome = self.application.retrieve_for_objective(
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            objective=_required_text(args, "objective"),
            summary=args.get("summary"),
            token_budget=token_budget,
            candidate_batch_tokens=batch_budget,
        )
        if outcome.nomination is None:
            return self._result(
                invocation,
                "Objective retrieval did not produce a nomination.",
                {
                    "nomination": None,
                    "execution_state": outcome.result.execution.state.value,
                    "remainders": _execution_remainders(outcome.result),
                    "batch_count": len(outcome.batch_results),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )
        nomination = outcome.nomination
        nomination_payload = {
            "decision": nomination.decision.value,
            "scope": nomination.scope,
            "objective": nomination.objective,
            "rationale": nomination.rationale,
            "authority": nomination.authority,
            "items": tuple({
                "item_ref": item.item_ref,
                "kind": item.kind,
                "source_authority": item.source_authority,
                "relevance": item.relevance,
                "contextual_roles": item.contextual_roles,
                "rationale": item.rationale,
            } for item in nomination.items),
        }
        if outcome.context is None or outcome.materialized is None:
            return self._result(
                invocation,
                "Objective retrieval selected no attention roots.",
                {
                    "nomination": nomination_payload,
                    "context": None,
                    "projection": None,
                    "batch_count": len(outcome.batch_results),
                },
                state=CommandState.IDLE,
                model_call_count=outcome.model_call_count,
            )
        projection = outcome.materialized.projection
        checkpoint = projection.continuation_checkpoint
        state = (
            CommandState.SUSPENDED
            if checkpoint is not None
            else (
                CommandState.COMPLETED
                if projection.injection_ready else CommandState.INCOMPLETE
            )
        )
        return self._result(
            invocation,
            "Objective-relative attention materialized.",
            {
                "nomination": nomination_payload,
                "context": _context_payload(outcome.context),
                "projection": {
                    "state": projection.state.value,
                    "token_budget": projection.token_budget,
                    "used_tokens": projection.used_tokens,
                    "selected": tuple({
                        "item_ref": item.item_ref,
                        "kind": item.kind.value,
                        "authority": item.authority,
                        "evidence_state": item.evidence_state.value,
                        "contextual_roles": item.contextual_roles,
                        "dependency_refs": item.dependency_refs,
                        "estimated_tokens": item.estimated_tokens,
                    } for item in projection.selected),
                    "missing_required_refs": projection.missing_required_refs,
                    "overflow_refs": projection.overflow_refs,
                    "injection_ready": projection.injection_ready,
                    "continuation_required": projection.continuation_required,
                },
                "batch_count": len(outcome.batch_results),
            },
            state=state,
            model_call_count=outcome.model_call_count,
            continuation_checkpoint_id=(
                checkpoint.checkpoint_id if checkpoint is not None else None
            ),
        )

    def _workspace_create(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        content = args.get("content")
        if content is not None:
            content = _required_text(args, "content")
        outcome = self.application.start_active_sheet(
            objective=_required_text(args, "objective"),
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            summary=args.get("summary"),
            title=_optional_text(args, "title", "Active task sheet"),
            content=content,
        )
        return self._result(
            invocation,
            "Active workspace created without model use.",
            {
                "sheet": encode_sheet_revision(outcome.sheet),
                "context": _context_payload(outcome.context),
                "content_hash": outcome.content_hash,
            },
        )

    def _workspace_show(self, invocation: CommandInvocation) -> CommandResult:
        sheet = self.application.active_sheet(
            _required_text(invocation.arguments, "context_id")
        )
        return self._result(
            invocation,
            f"Read active sheet revision {sheet.revision_number}.",
            {"sheet": encode_sheet_revision(sheet)},
        )

    def _workspace_append(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        raw_kind = args.get("kind", SheetElementKind.NOTE)
        try:
            kind = (
                raw_kind
                if isinstance(raw_kind, SheetElementKind)
                else SheetElementKind(_required_text(args, "kind").upper())
            )
        except ValueError as exc:
            raise CommandError(f"Unknown sheet element kind: {raw_kind}") from exc
        outcome = self.application.append_active_sheet(
            _required_text(args, "context_id"),
            _required_text(args, "content"),
            kind=kind,
            summary=args.get("summary"),
        )
        return self._result(
            invocation,
            f"Active sheet advanced to revision {outcome.sheet.revision_number}.",
            {
                "sheet": encode_sheet_revision(outcome.sheet),
                "context": _context_payload(outcome.context),
                "content_hash": outcome.content_hash,
            },
        )

    def _module_suggest(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        input_schemas = args.get("input_schemas", {})
        if not isinstance(input_schemas, Mapping) or any(
            not isinstance(name, str) or not name.strip()
            or not isinstance(schema, str) or not schema.strip()
            for name, schema in input_schemas.items()
        ):
            raise CommandError("input_schemas must be a text mapping")
        occurrences = args.get("occurrence_count", 1)
        if not isinstance(occurrences, int) or isinstance(occurrences, bool) or occurrences < 1:
            raise CommandError("occurrence_count must be a positive integer")
        outcome = self.application.suggest_module(
            objective=_required_text(args, "objective"),
            required_capability=_required_text(args, "required_capability"),
            output_schema=_required_text(args, "output_schema"),
            input_schemas=dict(input_schemas),
            occurrence_count=occurrences,
            allowed_effects=_text_tuple(args.get("allowed_effects", ()), "allowed_effects"),
            allowed_permissions=_text_tuple(
                args.get("allowed_permissions", ()),
                "allowed_permissions",
            ),
        )
        if outcome.suggestion is None:
            execution = outcome.result.execution if outcome.result is not None else None
            return self._result(
                invocation,
                "Module suggestion did not produce a design decision.",
                {
                    "suggestion": None,
                    "execution_state": execution.state.value if execution else None,
                    "remainders": tuple({
                        "kind": item.kind.value,
                        "description": item.description,
                    } for item in (execution.remainders if execution else ())),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )
        suggestion = outcome.suggestion
        return self._result(
            invocation,
            (
                "Existing capability must be reused; no module proposed."
                if outcome.deterministic_reuse
                else f"Module design decision: {suggestion.decision.value}."
            ),
            {
                "suggestion": _module_suggestion_payload(suggestion),
                "content_hash": outcome.stored.content_hash if outcome.stored else None,
                "deterministic_reuse": outcome.deterministic_reuse,
                "executable_code_created": False,
                "module_enabled": False,
            },
            model_call_count=outcome.model_call_count,
        )

    def _module_proposals(self, invocation: CommandInvocation) -> CommandResult:
        values = self.application.module_suggestions()
        return self._result(
            invocation,
            f"Listed {len(values)} archived module decision(s).",
            {"suggestions": tuple(
                _module_suggestion_payload(item.suggestion) for item in values
            )},
        )

    def _module_inspect(self, invocation: CommandInvocation) -> CommandResult:
        stored = self.application.module_suggestion(
            _required_text(invocation.arguments, "suggestion_id")
        )
        return self._result(
            invocation,
            "Archived module decision verified.",
            {
                "suggestion": _module_suggestion_payload(stored.suggestion),
                "content_hash": stored.content_hash,
                "executable_code_created": False,
                "module_enabled": False,
            },
        )

    def _profile_inspect(self, invocation: CommandInvocation) -> CommandResult:
        claim_id = invocation.arguments.get("claim_id")
        if claim_id is not None:
            claim_id = _required_text(invocation.arguments, "claim_id")
        reports = self.application.inspect_user_profiles(claim_id)
        return self._result(
            invocation,
            f"Inspected {len(reports)} user-profile record(s).",
            {"records": tuple(_profile_inspection_payload(item) for item in reports)},
        )

    def _personality_inspect(self, invocation: CommandInvocation) -> CommandResult:
        trait_id = invocation.arguments.get("trait_id")
        if trait_id is not None:
            trait_id = _required_text(invocation.arguments, "trait_id")
        reports = self.application.inspect_assistant_personality(trait_id)
        return self._result(
            invocation,
            f"Inspected {len(reports)} assistant-personality record(s).",
            {"records": tuple(_profile_inspection_payload(item) for item in reports)},
        )

    def _brain_analyze(self, invocation: CommandInvocation) -> CommandResult:
        report = self.application.brain_analyze()
        return self._result(
            invocation,
            "Immutable brain analysis report created.",
            encode_brain_analysis(report),
        )

    def _document_checkpoints(self, invocation: CommandInvocation) -> CommandResult:
        values = self.application.document_learning_checkpoints()
        return self._result(
            invocation,
            f"Listed {len(values)} document-learning checkpoint(s).",
            {"checkpoints": tuple(_document_checkpoint_payload(item) for item in values)},
        )

    def _document_checkpoint(self, invocation: CommandInvocation) -> CommandResult:
        checkpoint = self.application.document_learning_checkpoint(
            _required_text(invocation.arguments, "checkpoint_id")
        )
        return self._result(
            invocation,
            "Document-learning checkpoint verified.",
            {"checkpoint": _document_checkpoint_payload(checkpoint)},
        )

    def _document_resume(self, invocation: CommandInvocation) -> CommandResult:
        checkpoint_id = _required_text(invocation.arguments, "checkpoint_id")
        args = dict(invocation.arguments)
        args.setdefault("max_leaves", 1)
        max_leaves = _minimum_integer(
            args,
            "max_leaves",
            minimum=1,
        )
        decomposition = self.application.load_document_decomposition(checkpoint_id)
        outcome = self.application.resume_document_learning(
            checkpoint_id,
            decomposition,
            max_leaves=max_leaves,
        )
        return self._result(
            invocation,
            f"Resumed {len(outcome.outcomes)} document leaf batch item(s).",
            {
                "checkpoint": _document_checkpoint_payload(outcome.checkpoint),
                "processed_leaf_refs": outcome.processed_leaf_refs,
                "pending_leaf_refs": outcome.pending_leaf_refs,
                "model_calls": sum(
                    item.model_call_count for item in outcome.outcomes
                ),
            },
            model_call_count=sum(item.model_call_count for item in outcome.outcomes),
        )

    def _concept_list(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        all_versions = args.get("all_versions", False)
        if not isinstance(all_versions, bool):
            raise CommandError("all_versions must be boolean")
        values = (
            self.application.concepts()
            if all_versions else self.application.latest_concepts()
        )
        scope = args.get("scope")
        if scope is not None:
            scope = _required_text(args, "scope")
            values = tuple(item for item in values if item.scope == scope)
        state = args.get("state")
        if state is not None:
            try:
                expected = state if isinstance(state, ConceptState) else ConceptState(
                    _required_text(args, "state").upper()
                )
            except ValueError as exc:
                raise CommandError(f"Unknown concept state: {state}") from exc
            values = tuple(item for item in values if item.state is expected)
        return self._result(
            invocation,
            f"Listed {len(values)} concept record(s).",
            {"concepts": tuple(_concept_summary(item) for item in values)},
            state=CommandState.IDLE if not values else CommandState.COMPLETED,
        )

    def _concept_inspect(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        version = args.get("version")
        if version is not None and (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            raise CommandError("version must be a positive integer")
        concept_id = _required_text(args, "concept_id")
        record = self.application.concept(concept_id, version=version)
        history = self.application.concept_history(concept_id)
        return self._result(
            invocation,
            f"Inspected {record.version_ref}.",
            {
                "concept": encode_concept_record(record),
                "history_refs": tuple(item.version_ref for item in history),
            },
        )

    def _concept_nominate(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        raw_ids = args.get("crystal_ids")
        crystal_ids = (
            None if raw_ids is None else _text_tuple(raw_ids, "crystal_ids")
        )
        outcome = self.application.nominate_concept(
            scope=_optional_text(args, "scope", "scope:diamond-default"),
            objective=_required_text(args, "objective"),
            crystal_ids=crystal_ids,
        )
        if outcome.nomination is None:
            return self._result(
                invocation,
                "Concept nomination did not produce a bounded decision.",
                {
                    "nomination": None,
                    "concept": None,
                    "execution_state": outcome.result.execution.state.value,
                    "remainders": _execution_remainders(outcome.result),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )
        return self._result(
            invocation,
            (
                "Concept candidate persisted without validation authority."
                if outcome.concept is not None
                else "Model returned NO_CONCEPT; no concept was persisted."
            ),
            {
                "nomination": _concept_nomination_payload(outcome.nomination),
                "concept": (
                    encode_concept_record(outcome.concept)
                    if outcome.concept is not None else None
                ),
                "execution_state": outcome.result.execution.state.value,
            },
            model_call_count=outcome.model_call_count,
        )

    def _concept_evaluate(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        objective = args.get("objective")
        if objective is not None:
            objective = _required_text(args, "objective")
        outcome = self.application.evaluate_concept(
            _required_text(args, "concept_id"),
            objective=objective,
        )
        if outcome.validation is None:
            return self._result(
                invocation,
                "Concept evaluation did not produce complete validation inputs.",
                {
                    "validation": None,
                    "execution_state": outcome.result.execution.state.value,
                    "remainders": _execution_remainders(outcome.result),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )
        validation = outcome.validation
        return self._result(
            invocation,
            (
                "Concept evaluation archived; deterministic state is "
                f"{validation.record.state.value}."
            ),
            {
                "validation": encode_concept_validation_report(validation.report),
                "concept": encode_concept_record(validation.record),
                "execution_state": outcome.result.execution.state.value,
            },
            model_call_count=outcome.model_call_count,
        )

    def _concept_resolve(self, invocation: CommandInvocation) -> CommandResult:
        args = invocation.arguments
        objective = args.get("objective")
        if objective is not None:
            objective = _required_text(args, "objective")
        max_queries = _bounded_integer(args, "max_queries", default=2, maximum=6)
        max_results = _bounded_integer(
            args,
            "max_results_per_query",
            default=2,
            maximum=10,
        )
        outcome = self.application.evaluate_and_resolve_concept(
            _required_text(args, "concept_id"),
            objective=objective,
            search_adapter=self._concept_search_adapter,
            max_queries=max_queries,
            max_results_per_query=max_results,
        )
        initial = outcome.initial_evaluation
        if initial.validation is None:
            return self._result(
                invocation,
                "Initial concept evaluation did not produce validation inputs.",
                {
                    "initial_validation": None,
                    "resolution_attempted": False,
                    "execution_state": initial.result.execution.state.value,
                    "remainders": _execution_remainders(initial.result),
                },
                state=CommandState.INCOMPLETE,
                model_call_count=outcome.model_call_count,
            )

        gap = outcome.gap_resolution
        reevaluation = gap.evaluation if gap is not None else None
        final_validation = (
            reevaluation.validation
            if reevaluation is not None and reevaluation.validation is not None
            else None
        )
        final_record = (
            final_validation.record
            if final_validation is not None
            else (
                gap.revised_concept
                if gap is not None and gap.revised_concept is not None
                else initial.validation.record
            )
        )
        unresolved = final_record.state is ConceptState.CANDIDATE
        research = None
        if gap is not None:
            research = {
                "request_id": gap.research_request.request_id,
                "query_ids": tuple(
                    item.query_id for item in gap.research_request.queries
                ),
                "source_units_produced": gap.source_artifact is not None,
                "learning_commit_id": (
                    gap.learning.stored_commit.commit.commit_id
                    if gap.learning is not None else None
                ),
                "revised_concept_ref": (
                    gap.revised_concept.version_ref
                    if gap.revised_concept is not None else None
                ),
            }
        if gap is None:
            message = (
                f"Concept resolved without research as {final_record.state.value}."
                if not unresolved
                else "Concept remains open with no targetable research gap."
            )
        elif final_validation is not None:
            message = (
                "Targeted research re-entered /learn; deterministic state is "
                f"{final_record.state.value}."
            )
        else:
            message = "Targeted research stopped safely before re-evaluation."
        return self._result(
            invocation,
            message,
            {
                "initial_validation": encode_concept_validation_report(
                    initial.validation.report
                ),
                "resolution_attempted": gap is not None,
                "research": research,
                "reevaluation": (
                    encode_concept_validation_report(final_validation.report)
                    if final_validation is not None else None
                ),
                "concept": encode_concept_record(final_record),
            },
            state=(CommandState.INCOMPLETE if unresolved else CommandState.COMPLETED),
            model_call_count=outcome.model_call_count,
        )

    @staticmethod
    def _result(
        invocation: CommandInvocation,
        message: str,
        payload: Mapping[str, Any],
        *,
        state: CommandState = CommandState.COMPLETED,
        model_call_count: int = 0,
        continuation_checkpoint_id: str | None = None,
    ) -> CommandResult:
        return CommandResult(
            invocation.invocation_id,
            invocation.command,
            state,
            message,
            payload,
            model_call_count,
            continuation_checkpoint_id,
        )


def _context_payload(context: AttentionContextRevision) -> dict[str, Any]:
    return {
        "context_id": context.context_id,
        "context_ref": context.context_ref,
        "revision_number": context.revision_number,
        "state": context.state.value,
        "transition": context.transition.value,
        "objective": context.objective,
        "scope": context.scope,
        "summary": context.summary,
        "source_refs": context.source_refs,
        "validated_refs": context.validated_refs,
        "selected_refs": context.selected_refs,
        "workspace_sheet_refs": context.workspace_sheet_refs,
        "active_sheet_ref": context.active_sheet_ref,
        "remainder_refs": context.remainder_refs,
        "checkpoint_ref": context.checkpoint_ref,
        "suspension_reason": context.suspension_reason,
    }


def _research_payload(
    value: Any,
    objective: str,
    response_mode: str,
) -> dict[str, Any]:
    units = (
        decode_source_units(value.source_artifact)
        if value.source_artifact is not None
        else ()
    )
    retrieval = value.retrieval
    nomination = (
        None
        if retrieval is None or retrieval.nomination is None
        else _nomination_payload(retrieval.nomination)
    )
    return {
        "request_id": value.request.request_id,
        "objective": objective,
        "response_mode": response_mode,
        "scope": value.request.scope,
        "queries": tuple({
            "query_id": item.query_id,
            "text": item.text,
            "purpose": item.purpose,
            "preferred_source_types": item.preferred_source_types,
            "intent": item.search_intent.value,
        } for item in value.request.queries),
        "execution_state": value.result.execution.state.value,
        "remainders": _execution_remainders(value.result),
        "retrieval": nomination,
        "sources": tuple({
            "source_unit_id": item.source_unit_id,
            "query_id": item.query_id,
            "title": item.title,
            "source_locator": item.source_locator,
            "source_type": item.source_type,
            "retrieved_at": item.retrieved_at,
            "content_hash": item.content_hash,
            "authority": item.authority,
            "source_document_ref": item.source_document_ref,
            "extracted_unit_ref": item.extracted_unit_ref,
            "source_lineage": item.source_lineage,
        } for item in units),
        "learning": tuple({
            "commit_id": item.stored_commit.commit.commit_id,
            "commit_hash": item.stored_commit.content_hash,
            "crystal_states": tuple(
                crystal.state.value
                for crystal in item.stored_commit.commit.crystallization.crystals
            ),
        } for item in value.learned),
        "authority": "UNVALIDATED_EXTERNAL_SOURCE_BUNDLE",
        "phi_open": True,
    }


def _nomination_payload(value: Any) -> dict[str, Any]:
    return {
        "decision": value.decision.value,
        "scope": value.scope,
        "objective": value.objective,
        "rationale": value.rationale,
        "authority": value.authority,
        "items": tuple({
            "item_ref": item.item_ref,
            "kind": item.kind,
            "source_authority": item.source_authority,
            "relevance": item.relevance,
            "contextual_roles": item.contextual_roles,
            "rationale": item.rationale,
        } for item in value.items),
    }


def _profile_inspection_payload(value: Any) -> dict[str, Any]:
    return {
        "record_id": value.record_id,
        "version_refs": value.version_refs,
        "states": tuple(item.value for item in value.states),
        "latest_version": value.latest_version,
        "latest_state": value.latest_state.value,
    }


def _document_checkpoint_payload(value: Any) -> dict[str, Any]:
    return {
        "checkpoint_id": value.checkpoint_id,
        "decomposition_id": value.decomposition_id,
        "objective": value.objective,
        "processed_leaf_refs": value.processed_leaf_refs,
        "pending_leaf_refs": value.pending_leaf_refs,
        "content_hash": value.content_hash,
    }


def _module_suggestion_payload(value: ModuleSuggestion) -> dict[str, Any]:
    operation = value.operation
    return {
        "suggestion_id": value.suggestion_id,
        "decision": value.decision.value,
        "objective": value.objective,
        "required_capability": value.required_capability,
        "layer": value.layer,
        "rationale": value.rationale,
        "exact_provider_refs": value.exact_provider_refs,
        "reuse_candidate_refs": value.reuse_candidate_refs,
        "remainder_refs": value.remainder_refs,
        "allowed_effects": value.allowed_effects,
        "allowed_permissions": value.allowed_permissions,
        "o1_required_outcomes": value.o1_required_outcomes,
        "o2_composition_analysis": value.o2_composition_analysis,
        "o2_dependencies": value.o2_dependencies,
        "o3_constraints": value.o3_constraints,
        "o3_completion_conditions": value.o3_completion_conditions,
        "operation": None if operation is None else {
            "module_id": operation.module_id,
            "operation_id": operation.operation_id,
            "capability": operation.capability,
            "inputs": dict(operation.inputs),
            "outputs": dict(operation.outputs),
            "effects": operation.effects,
            "permissions": operation.permissions,
            "failure_modes": operation.failure_modes,
            "determinism": operation.determinism,
        },
        "admission_precheck_passed": value.admission_precheck_passed,
        "policy_remainders": tuple({
            "kind": item.kind.value,
            "description": item.description,
        } for item in value.policy_remainders),
        "created_at": value.created_at,
        "authority": value.authority,
    }


def _concept_summary(value: ConceptRecord) -> dict[str, Any]:
    return {
        "concept_id": value.concept_id,
        "version_ref": value.version_ref,
        "version": value.version,
        "canonical_name": value.canonical_name,
        "aliases": value.aliases,
        "scope": value.scope,
        "state": value.state.value,
        "memberships": len(value.memberships),
        "parent_links": len(value.parent_links),
        "validation_refs": len(value.validation_refs),
        "recognition_state": value.recognition_state.value,
        "definition_state": value.definition_state.value,
        "promotion_authority": value.promotion_authority,
    }


def _concept_nomination_payload(value: ConceptNomination) -> dict[str, Any]:
    return {
        "decision": value.decision.value,
        "scope": value.scope,
        "objective": value.objective,
        "canonical_name": value.canonical_name,
        "aliases": value.aliases,
        "crystal_ids": value.crystal_ids,
        "parent_concept_ids": value.parent_concept_ids,
        "signature": dict(value.signature),
        "rationale": value.rationale,
        "authority": value.authority,
    }


def _execution_remainders(value: Any) -> tuple[dict[str, Any], ...]:
    return tuple({
        "kind": item.kind.value,
        "required_for": item.required_for,
        "description": item.description,
    } for item in value.execution.remainders)


def encode_command_result(value: CommandResult) -> dict[str, Any]:
    """Return the stable JSON-ready boundary consumed by interface adapters."""

    return {
        "invocation_id": value.invocation_id,
        "command": value.command,
        "state": value.state.value,
        "message": value.message,
        "payload": _json_value(dict(value.payload)),
        "model_call_count": value.model_call_count,
        "continuation_checkpoint_id": value.continuation_checkpoint_id,
        "authority": value.authority,
    }


def _parse_learn(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"scope", "objective", "kind"})
    if not positional:
        raise CommandError("/learn requires candidate text")
    return {**options, "text": " ".join(positional)}


def _parse_research(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"scope", "queries", "results", "mode"},
    )
    if not positional:
        raise CommandError("/research requires a question")
    result: dict[str, Any] = {
        "question": " ".join(positional),
        **({"scope": options["scope"]} if "scope" in options else {}),
    }
    if "mode" in options:
        result["response_mode"] = options["mode"]
    for option, argument in (
        ("queries", "max_queries"),
        ("results", "max_results_per_query"),
    ):
        if option in options:
            try:
                result[argument] = int(options[option])
            except ValueError as exc:
                raise CommandError(f"--{option} must be an integer") from exc
    return result


def _parse_chat_start(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"scope", "summary", "budget", "batch-budget"},
    )
    if not positional:
        raise CommandError("/chat start requires an objective")
    result: dict[str, Any] = {
        "objective": " ".join(positional),
        **{
            key: value for key, value in options.items()
            if key in {"scope", "summary"}
        },
    }
    for option, argument in (
        ("budget", "token_budget"),
        ("batch-budget", "candidate_batch_tokens"),
    ):
        if option in options:
            try:
                result[argument] = int(options[option])
            except ValueError as exc:
                raise CommandError(f"--{option} must be an integer") from exc
    return result


def _parse_chat_say(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"budget", "mode"})
    if len(positional) < 2:
        raise CommandError("/chat say requires SESSION_ID and MESSAGE")
    result: dict[str, Any] = {
        "session_id": positional[0],
        "message": " ".join(positional[1:]),
    }
    if "budget" in options:
        try:
            result["token_budget"] = int(options["budget"])
        except ValueError as exc:
            raise CommandError("--budget must be an integer") from exc
    if "mode" in options:
        result["response_mode"] = options["mode"]
    return result


def _parse_chat_status(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) != 1:
        raise CommandError("/chat status requires one SESSION_ID")
    return {"session_id": tokens[0]}


def _parse_chat_lifecycle(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) < 2:
        raise CommandError("Chat lifecycle commands require SESSION_ID and REASON")
    return {"session_id": tokens[0], "reason": " ".join(tokens[1:])}


def _parse_chat_resume(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) < 2:
        raise CommandError(
            "/chat resume requires SESSION_ID and CHECKPOINT_ID"
        )
    result: dict[str, Any] = {
        "session_id": tokens[0],
        "checkpoint_id": tokens[1],
    }
    if len(tokens) > 2:
        result["summary"] = " ".join(tokens[2:])
    return result


def _parse_attention_create(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"scope", "summary"})
    if not positional:
        raise CommandError("/attention create requires an objective")
    return {**options, "objective": " ".join(positional)}


def _parse_attention_turn(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"budget"},
        boolean_options={"no-auto-decompose"},
    )
    if len(positional) < 2:
        raise CommandError("/attention turn requires CONTEXT_ID and INSTRUCTION")
    result: dict[str, Any] = {
        "context_id": positional[0],
        "instruction": " ".join(positional[1:]),
    }
    if "budget" in options:
        try:
            result["token_budget"] = int(options["budget"])
        except ValueError as exc:
            raise CommandError("--budget must be an integer") from exc
    if options.get("no-auto-decompose") is True:
        result["auto_decompose"] = False
    return result


def _parse_attention_resume(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if not tokens:
        raise CommandError("/attention resume requires CHECKPOINT_ID")
    return {
        "checkpoint_id": tokens[0],
        **({"summary": " ".join(tokens[1:])} if len(tokens) > 1 else {}),
    }


def _parse_attention_status(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) > 1:
        raise CommandError("/attention status accepts at most one CONTEXT_ID")
    return {"context_id": tokens[0]} if tokens else {}


def _parse_attention_retrieve(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"scope", "summary", "budget", "batch-budget"},
    )
    if not positional:
        raise CommandError("/attention retrieve requires an objective")
    result: dict[str, Any] = {
        "objective": " ".join(positional),
        **{
            key: value
            for key, value in options.items()
            if key in {"scope", "summary"}
        },
    }
    for option, argument in (
        ("budget", "token_budget"),
        ("batch-budget", "candidate_batch_tokens"),
    ):
        if option in options:
            try:
                result[argument] = int(options[option])
            except ValueError as exc:
                raise CommandError(f"--{option} must be an integer") from exc
    return result


def _parse_workspace_create(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"scope", "summary", "title", "content"},
    )
    if not positional:
        raise CommandError("/workspace create requires an objective")
    return {**options, "objective": " ".join(positional)}


def _parse_workspace_show(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) != 1:
        raise CommandError("/workspace show requires one CONTEXT_ID")
    return {"context_id": tokens[0]}


def _parse_workspace_append(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"kind", "summary"})
    if len(positional) < 2:
        raise CommandError("/workspace append requires CONTEXT_ID and CONTENT")
    return {
        **options,
        "context_id": positional[0],
        "content": " ".join(positional[1:]),
    }


def _parse_module_suggest(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"output-schema", "occurrences"})
    if len(positional) < 2:
        raise CommandError("/module suggest requires CAPABILITY and OBJECTIVE")
    if "output-schema" not in options:
        raise CommandError("/module suggest requires --output-schema")
    result: dict[str, Any] = {
        "required_capability": positional[0],
        "objective": " ".join(positional[1:]),
        "output_schema": options["output-schema"],
    }
    if "occurrences" in options:
        try:
            result["occurrence_count"] = int(options["occurrences"])
        except ValueError as exc:
            raise CommandError("--occurrences must be an integer") from exc
    return result


def _parse_concept_list(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(
        tokens,
        {"scope", "state"},
        boolean_options={"all-versions"},
    )
    if positional:
        raise CommandError("/concept list accepts options only")
    return {
        **{key: value for key, value in options.items() if key != "all-versions"},
        "all_versions": bool(options.get("all-versions", False)),
    }


def _parse_concept_inspect(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"version"})
    if len(positional) != 1:
        raise CommandError("/concept inspect requires one CONCEPT_ID")
    result: dict[str, Any] = {"concept_id": positional[0]}
    if "version" in options:
        try:
            result["version"] = int(options["version"])
        except ValueError as exc:
            raise CommandError("--version must be an integer") from exc
    return result


def _parse_concept_nominate(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"scope", "crystals"})
    if not positional:
        raise CommandError("/concept nominate requires an objective")
    result: dict[str, Any] = {
        **{key: value for key, value in options.items() if key != "crystals"},
        "objective": " ".join(positional),
    }
    if "crystals" in options:
        ids = tuple(
            item.strip() for item in options["crystals"].split(",")
            if item.strip()
        )
        if not ids:
            raise CommandError("--crystals requires comma-separated IDs")
        result["crystal_ids"] = ids
    return result


def _parse_concept_evaluate(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"objective"})
    if len(positional) != 1:
        raise CommandError("/concept evaluate requires one CONCEPT_ID")
    return {**options, "concept_id": positional[0]}


def _parse_concept_resolve(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"objective", "queries", "results"})
    if len(positional) != 1:
        raise CommandError("/concept resolve requires one CONCEPT_ID")
    result: dict[str, Any] = {"concept_id": positional[0]}
    if "objective" in options:
        result["objective"] = options["objective"]
    for option, argument in (
        ("queries", "max_queries"),
        ("results", "max_results_per_query"),
    ):
        if option in options:
            try:
                result[argument] = int(options[option])
            except ValueError as exc:
                raise CommandError(f"--{option} must be an integer") from exc
    return result


def _parse_module_inspect(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) != 1:
        raise CommandError("/module inspect requires one SUGGESTION_ID")
    return {"suggestion_id": tokens[0]}


def _parse_profile_inspect(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) > 1:
        raise CommandError("Profile inspection accepts at most one record ID")
    return {"claim_id": tokens[0]} if tokens else {}


def _parse_personality_inspect(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) > 1:
        raise CommandError("Personality inspection accepts at most one record ID")
    return {"trait_id": tokens[0]} if tokens else {}


def _parse_document_checkpoint(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    if len(tokens) != 1:
        raise CommandError("/document checkpoint requires CHECKPOINT_ID")
    return {"checkpoint_id": tokens[0]}


def _parse_document_resume(tokens: tuple[str, ...]) -> Mapping[str, Any]:
    options, positional = _options(tokens, {"max-leaves"})
    if len(positional) != 1:
        raise CommandError("/document resume requires CHECKPOINT_ID")
    result: dict[str, Any] = {"checkpoint_id": positional[0]}
    if "max-leaves" in options:
        try:
            result["max_leaves"] = int(options["max-leaves"])
        except ValueError as exc:
            raise CommandError("--max-leaves must be an integer") from exc
    return result


def _options(
    tokens: tuple[str, ...],
    valued_options: set[str],
    *,
    boolean_options: set[str] | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    booleans = boolean_options or set()
    options: dict[str, Any] = {}
    positional: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            positional.append(token)
            index += 1
            continue
        key = token[2:]
        if key in booleans:
            options[key] = True
            index += 1
            continue
        if key not in valued_options:
            raise CommandError(f"Unknown option: --{key}")
        if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
            raise CommandError(f"Option --{key} requires a value")
        options[key] = tokens[index + 1]
        index += 2
    return options, tuple(positional)


def _required_text(
    values: Mapping[str, Any],
    key: str,
) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"{key} must be non-empty text")
    return value.strip()


def _optional_text(values: Mapping[str, Any], key: str, default: str) -> str:
    value = values.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"{key} must be non-empty text")
    return value.strip()


def _bounded_integer(
    values: Mapping[str, Any],
    key: str,
    *,
    default: int,
    maximum: int,
) -> int:
    value = values.get(key, default)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= maximum
    ):
        raise CommandError(f"{key} must be an integer between 1 and {maximum}")
    return value


def _minimum_integer(
    values: Mapping[str, Any],
    key: str,
    *,
    minimum: int,
) -> int:
    value = values.get(key)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
    ):
        raise CommandError(f"{key} must be an integer >= {minimum}")
    return value


def _text_tuple(value: Any, key: str) -> tuple[str, ...]:
    if isinstance(value, list):
        value = tuple(value)
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CommandError(f"{key} must be a sequence of non-empty text")
    return value


def _normalize_name(name: str) -> str:
    return name.strip().removeprefix("/").lower()


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Command result contains non-JSON value: {type(value).__name__}")
