"""Deterministic question-only benchmark runner contracts.

The runner compares a persistent Fresta path that can resume from checkpoints
with an isolated baseline that receives the same question and per-call budgets
but does not persist or resume anything.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fresta_diamond.contracts import Artifact, BlueprintSpec, CapabilityRequirement, ModuleManifest, OperationContract
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.journal import EventJournal, JsonlJournalArchive
from fresta_diamond.prompt_boundary import DATA_BOUNDARY_INSTRUCTION, render_inert_data
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.workspace import ExecutionBudget, JsonCheckpointStore


QUESTION_ONLY_REQUEST_SCHEMA = "artifact://question-only-request@1"
QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA = "artifact://question-only-query-proposal@1"
QUESTION_ONLY_EVIDENCE_BUNDLE_SCHEMA = "artifact://question-only-evidence-bundle@1"
QUESTION_ONLY_QUERY_CAPABILITY = "question.propose-queries@1"
QUESTION_ONLY_EVIDENCE_CAPABILITY = "question.collect-evidence@1"
QUESTION_ONLY_LLM_EFFECT = "llm.generate"
QUESTION_ONLY_SEARCH_EFFECT = "internet.search"


class QuestionOnlyArm(str, Enum):
    BASELINE = "BASELINE"
    FRESTA = "FRESTA"


@dataclass(frozen=True)
class QuestionOnlyBenchmarkCase:
    case_id: str
    question: str

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("Question-only benchmark case requires case_id and question")


@dataclass(frozen=True)
class QuestionOnlyBenchmarkConfig:
    per_call_operation_budget: int = 1
    max_queries: int = 3
    max_results_per_query: int = 2
    query_max_tokens: int = 512
    max_episodes: int = 2

    def __post_init__(self) -> None:
        if self.per_call_operation_budget < 1:
            raise ValueError("Per-call budget must be positive")
        if not 1 <= self.max_queries <= 6:
            raise ValueError("Question-only query budget must be between 1 and 6")
        if not 1 <= self.max_results_per_query <= 10:
            raise ValueError("Question-only result budget must be between 1 and 10")
        if self.query_max_tokens < 1:
            raise ValueError("Question-only token budget must be positive")
        if not 1 <= self.max_episodes <= 8:
            raise ValueError("Question-only episode budget must be between 1 and 8")


@dataclass(frozen=True)
class QuestionOnlyQuery:
    query_id: str
    text: str
    purpose: str
    preferred_source_types: tuple[str, ...]
    reveals_question_label: bool = False

    def __post_init__(self) -> None:
        if not all((self.query_id.strip(), self.text.strip(), self.purpose.strip())):
            raise ValueError("Question-only query fields are required")
        if not self.preferred_source_types:
            raise ValueError("Question-only query needs source preferences")
        if any(not item.strip() for item in self.preferred_source_types):
            raise ValueError("Question-only query source preferences are invalid")


@dataclass(frozen=True)
class QuestionOnlyQueryProposal:
    request_id: str
    question: str
    queries: tuple[QuestionOnlyQuery, ...]
    authority: str = "UNVALIDATED_QUESTION_ONLY_QUERY_PROPOSAL"
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.question.strip():
            raise ValueError("Question-only query proposal requires request_id and question")
        if not self.queries:
            raise ValueError("Question-only query proposal needs queries")
        if self.authority != "UNVALIDATED_QUESTION_ONLY_QUERY_PROPOSAL":
            raise PermissionError("Question-only query proposal cannot validate itself")
        if self.promotion_authority is not False:
            raise PermissionError("Question-only query proposal cannot promote itself")


@dataclass(frozen=True)
class QuestionOnlyEvidenceUnit:
    evidence_id: str
    query_id: str
    title: str
    content: str
    source_locator: str
    source_type: str
    retrieved_at: str
    content_hash: str
    authority: str = "UNVALIDATED_EXTERNAL_EVIDENCE"
    source_document_ref: str | None = None
    extracted_unit_ref: str | None = None
    provenance: tuple[str, ...] = ()
    source_lineage: str | None = None

    def __post_init__(self) -> None:
        if not all((
            self.evidence_id.strip(),
            self.query_id.strip(),
            self.title.strip(),
            self.content.strip(),
            self.source_locator.strip(),
            self.source_type.strip(),
            self.retrieved_at.strip(),
            self.content_hash.strip(),
        )):
            raise ValueError("Question-only evidence unit fields are required")
        if not self.source_locator.startswith(("http://", "https://")):
            raise ValueError("Question-only evidence locator must be HTTP(S)")
        if self.authority != "UNVALIDATED_EXTERNAL_EVIDENCE":
            raise PermissionError("Question-only evidence cannot validate itself")
        expected = sha256(self.content.encode("utf-8")).hexdigest()
        if expected != self.content_hash:
            raise ValueError("Question-only evidence hash mismatch")
        document_ref = self.source_document_ref or self.source_locator
        unit_ref = self.extracted_unit_ref or self.evidence_id
        if not document_ref.strip() or not unit_ref.strip():
            raise ValueError("Question-only evidence lineage references are required")
        provenance = tuple(self.provenance or (self.source_locator,))
        if any(not item.strip() for item in provenance):
            raise ValueError("Question-only evidence provenance is invalid")
        if (
            self.source_lineage is not None
            and not self.source_lineage.strip()
        ):
            raise ValueError("Question-only evidence source lineage is invalid")
        lineage = self.source_lineage or provenance[0]
        object.__setattr__(self, "source_document_ref", document_ref)
        object.__setattr__(self, "extracted_unit_ref", unit_ref)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "source_lineage", lineage)


@dataclass(frozen=True)
class QuestionOnlyEvidenceBundle:
    request_id: str
    question: str
    query_ids: tuple[str, ...]
    units: tuple[QuestionOnlyEvidenceUnit, ...]
    authority: str = "UNVALIDATED_QUESTION_ONLY_EVIDENCE"
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.question.strip():
            raise ValueError("Question-only evidence bundle requires request_id and question")
        if not self.query_ids:
            raise ValueError("Question-only evidence bundle needs query IDs")
        if not self.units:
            raise ValueError("Question-only evidence bundle needs units")
        if self.authority != "UNVALIDATED_QUESTION_ONLY_EVIDENCE":
            raise PermissionError("Question-only evidence bundle cannot validate itself")
        if self.promotion_authority is not False:
            raise PermissionError("Question-only evidence bundle cannot promote itself")


@dataclass(frozen=True)
class QuestionOnlyEpisodeResult:
    episode_index: int
    state: str
    checkpoint_id: str | None
    stored_checkpoint_id: str | None
    query_count: int
    evidence_unit_count: int
    model_call_count: int
    remainder_kinds: tuple[str, ...]


@dataclass(frozen=True)
class QuestionOnlyArmResult:
    arm: QuestionOnlyArm
    case_id: str
    question: str
    config: QuestionOnlyBenchmarkConfig
    episodes: tuple[QuestionOnlyEpisodeResult, ...]
    query_proposal: QuestionOnlyQueryProposal | None
    evidence_bundle: QuestionOnlyEvidenceBundle | None
    checkpoint_ids: tuple[str, ...]
    persistence_enabled: bool
    continuation_recorded: bool
    provenance_preserved: bool
    phi_closed: bool
    model_call_count: int


@dataclass(frozen=True)
class QuestionOnlyComparison:
    same_question: bool
    same_per_call_budget: bool
    same_token_budget: bool
    same_result_budget: bool
    baseline_completed: bool
    fresta_completed: bool
    baseline_episode_count: int
    fresta_episode_count: int
    baseline_checkpoint_count: int
    fresta_checkpoint_count: int
    baseline_continuation_recorded: bool
    fresta_continuation_recorded: bool
    baseline_provenance_preserved: bool
    fresta_provenance_preserved: bool
    baseline_phi_closed: bool
    fresta_phi_closed: bool
    model_call_delta: int


@dataclass(frozen=True)
class QuestionOnlyBenchmarkResult:
    case: QuestionOnlyBenchmarkCase
    config: QuestionOnlyBenchmarkConfig
    baseline: QuestionOnlyArmResult
    fresta: QuestionOnlyArmResult
    comparison: QuestionOnlyComparison


def question_only_request_artifact(
    case: QuestionOnlyBenchmarkCase,
    config: QuestionOnlyBenchmarkConfig,
) -> Artifact:
    return Artifact(
        schema=QUESTION_ONLY_REQUEST_SCHEMA,
        payload={
            "case_id": case.case_id,
            "question": case.question,
            "max_queries": config.max_queries,
            "max_results_per_query": config.max_results_per_query,
        },
    )


def question_only_blueprint() -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="benchmark.question-only-research",
        version=1,
        intent=(
            "Ask one question, propose neutral bounded queries, and collect "
            "provenance-preserving external evidence without validating it."
        ),
        requirements=(
            CapabilityRequirement(
                capability=QUESTION_ONLY_QUERY_CAPABILITY,
                input_name="request",
                input_schema=QUESTION_ONLY_REQUEST_SCHEMA,
                output_name="query_proposal",
                output_schema=QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
            CapabilityRequirement(
                capability=QUESTION_ONLY_EVIDENCE_CAPABILITY,
                input_name="query_proposal",
                input_schema=QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA,
                output_name="evidence_bundle",
                output_schema=QUESTION_ONLY_EVIDENCE_BUNDLE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
        ),
        allowed_effects=(QUESTION_ONLY_LLM_EFFECT, QUESTION_ONLY_SEARCH_EFFECT),
        granted_permissions=(),
    )


def question_only_manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="benchmark.question-only-research",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(
            OperationContract(
                operation_id="question-only.propose",
                version="1.0.0",
                capabilities=(QUESTION_ONLY_QUERY_CAPABILITY,),
                inputs={"request": QUESTION_ONLY_REQUEST_SCHEMA},
                outputs={"query_proposal": QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA},
                effects=(QUESTION_ONLY_LLM_EFFECT,),
                determinism="STOCHASTIC",
            ),
            OperationContract(
                operation_id="question-only.collect",
                version="1.0.0",
                capabilities=(QUESTION_ONLY_EVIDENCE_CAPABILITY,),
                inputs={"query_proposal": QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA},
                outputs={"evidence_bundle": QUESTION_ONLY_EVIDENCE_BUNDLE_SCHEMA},
                effects=(QUESTION_ONLY_SEARCH_EFFECT,),
                determinism="DETERMINISTIC",
            ),
        ),
    )


def register_question_only_provider(
    registry: ModuleRegistry,
    *,
    query_operation: "QuestionOnlyQueryOperation",
    evidence_operation: "QuestionOnlyEvidenceOperation",
) -> None:
    manifest = question_only_manifest()
    registry.discover(manifest)
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Question-only benchmark provider was rejected")
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: query_operation,
            manifest.operations[1].operation_id: evidence_operation,
        },
    )


@dataclass(frozen=True)
class QuestionOnlyQueryOperation:
    max_tokens: int = 512

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: Any,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Question-only request is required")
        question = _text(request, "question")
        max_queries = _int(request, "max_queries", default=3)
        if not 1 <= max_queries <= 6:
            raise ValueError("Question-only query budget is invalid")
        response = context.invoke(
            QUESTION_ONLY_LLM_EFFECT,
            messages=_question_messages(question, max_queries),
            temperature=0.1,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("Question-only query proposal missing content")
        payload = _extract_object(content)
        raw_queries = payload.get("queries")
        if not isinstance(raw_queries, list) or not raw_queries:
            raise ValueError("Question-only query proposal requires queries")
        if len(raw_queries) > max_queries:
            raise ValueError("Question-only query proposal exceeds its budget")
        queries: list[QuestionOnlyQuery] = []
        for item in raw_queries:
            if not isinstance(item, Mapping):
                raise ValueError("Question-only query must be an object")
            preferences = item.get("preferred_source_types")
            if not isinstance(preferences, list) or not preferences:
                raise ValueError("Question-only query requires source preferences")
            queries.append(QuestionOnlyQuery(
                query_id=_text(item, "query_id"),
                text=_text(item, "text"),
                purpose=_text(item, "purpose"),
                preferred_source_types=tuple(
                    _text({"value": value}, "value") for value in preferences
                ),
                reveals_question_label=False,
            ))
        if len({item.query_id for item in queries}) != len(queries):
            raise ValueError("Question-only query IDs must be unique")
        proposal = QuestionOnlyQueryProposal(
            request_id=str(payload.get("request_id") or f"question-only:{uuid4()}"),
            question=question,
            queries=tuple(queries),
        )
        return {
            "query_proposal": {
                "schema": QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA,
                "request_id": proposal.request_id,
                "question": proposal.question,
                "queries": [
                    {
                        "query_id": query.query_id,
                        "text": query.text,
                        "purpose": query.purpose,
                        "preferred_source_types": list(query.preferred_source_types),
                        "reveals_question_label": query.reveals_question_label,
                    }
                    for query in proposal.queries
                ],
                "authority": proposal.authority,
                "promotion_authority": proposal.promotion_authority,
            }
        }


@dataclass(frozen=True)
class QuestionOnlyEvidenceOperation:
    max_results_per_query: int = 2

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: Any,
    ) -> Mapping[str, Mapping[str, Any]]:
        query_proposal = inputs.get("query_proposal")
        if not isinstance(query_proposal, Mapping):
            raise ValueError("Question-only query proposal is required")
        question = _text(query_proposal, "question")
        raw_queries = query_proposal.get("queries")
        if not isinstance(raw_queries, (list, tuple)) or not raw_queries:
            raise ValueError("Question-only query proposal requires queries")
        queries = tuple(
            QuestionOnlyQuery(
                query_id=_text(item, "query_id"),
                text=_text(item, "text"),
                purpose=_text(item, "purpose"),
                preferred_source_types=tuple(
                    _text({"value": value}, "value")
                    for value in _list(item, "preferred_source_types")
                ),
                reveals_question_label=bool(item.get("reveals_question_label", False)),
            )
            for item in raw_queries
        )
        payload = context.invoke(
            QUESTION_ONLY_SEARCH_EFFECT,
            question=question,
            queries=[
                {
                    "query_id": query.query_id,
                    "text": query.text,
                    "purpose": query.purpose,
                    "preferred_source_types": list(query.preferred_source_types),
                }
                for query in queries
            ],
            max_results_per_query=self.max_results_per_query,
        )
        raw_units = payload.get("source_units")
        if not isinstance(raw_units, list) or not raw_units:
            raise ValueError("Question-only evidence bundle requires source units")
        units = tuple(_decode_evidence_unit(item) for item in raw_units)
        bundle = QuestionOnlyEvidenceBundle(
            request_id=str(query_proposal.get("request_id") or f"question-only:{uuid4()}"),
            question=question,
            query_ids=tuple(query.query_id for query in queries),
            units=units,
        )
        return {
            "evidence_bundle": {
                "schema": QUESTION_ONLY_EVIDENCE_BUNDLE_SCHEMA,
                "request_id": bundle.request_id,
                "question": bundle.question,
                "query_ids": list(bundle.query_ids),
                "source_units": [
                    _encode_evidence_unit(unit) for unit in bundle.units
                ],
                "authority": bundle.authority,
                "promotion_authority": bundle.promotion_authority,
            }
        }


def run_question_only_benchmark(
    case: QuestionOnlyBenchmarkCase,
    llm_adapter: Callable[..., Mapping[str, Any]],
    search_adapter: Callable[..., Mapping[str, Any]],
    *,
    config: QuestionOnlyBenchmarkConfig | None = None,
    fresta_root: str | Path | None = None,
) -> QuestionOnlyBenchmarkResult:
    config = config or QuestionOnlyBenchmarkConfig()
    blueprint = question_only_blueprint()
    request = question_only_request_artifact(case, config)

    baseline = _run_arm(
        arm=QuestionOnlyArm.BASELINE,
        case=case,
        config=config,
        blueprint=blueprint,
        request=request,
        llm_adapter=llm_adapter,
        search_adapter=search_adapter,
        checkpoint_root=None,
        journal_root=None,
        use_checkpoint_store=False,
    )
    fresta = _run_arm(
        arm=QuestionOnlyArm.FRESTA,
        case=case,
        config=config,
        blueprint=blueprint,
        request=request,
        llm_adapter=llm_adapter,
        search_adapter=search_adapter,
        checkpoint_root=fresta_root,
        journal_root=fresta_root,
        use_checkpoint_store=True,
    )
    comparison = QuestionOnlyComparison(
        same_question=baseline.question == fresta.question == case.question,
        same_per_call_budget=(
            baseline.config.per_call_operation_budget
            == fresta.config.per_call_operation_budget
            == config.per_call_operation_budget
        ),
        same_token_budget=(
            baseline.config.query_max_tokens
            == fresta.config.query_max_tokens
            == config.query_max_tokens
        ),
        same_result_budget=(
            baseline.config.max_results_per_query
            == fresta.config.max_results_per_query
            == config.max_results_per_query
        ),
        baseline_completed=_completed(baseline),
        fresta_completed=_completed(fresta),
        baseline_episode_count=len(baseline.episodes),
        fresta_episode_count=len(fresta.episodes),
        baseline_checkpoint_count=len(baseline.checkpoint_ids),
        fresta_checkpoint_count=len(fresta.checkpoint_ids),
        baseline_continuation_recorded=baseline.continuation_recorded,
        fresta_continuation_recorded=fresta.continuation_recorded,
        baseline_provenance_preserved=baseline.provenance_preserved,
        fresta_provenance_preserved=fresta.provenance_preserved,
        baseline_phi_closed=baseline.phi_closed,
        fresta_phi_closed=fresta.phi_closed,
        model_call_delta=fresta.model_call_count - baseline.model_call_count,
    )
    return QuestionOnlyBenchmarkResult(
        case=case,
        config=config,
        baseline=baseline,
        fresta=fresta,
        comparison=comparison,
    )


def _run_arm(
    *,
    arm: QuestionOnlyArm,
    case: QuestionOnlyBenchmarkCase,
    config: QuestionOnlyBenchmarkConfig,
    blueprint: BlueprintSpec,
    request: Artifact,
    llm_adapter: Callable[..., Mapping[str, Any]],
    search_adapter: Callable[..., Mapping[str, Any]],
    checkpoint_root: str | Path | None,
    journal_root: str | Path | None,
    use_checkpoint_store: bool,
) -> QuestionOnlyArmResult:
    registry = ModuleRegistry()
    counters = {"llm": 0, "search": 0}

    def counted_llm(grant: Any, **kwargs: Any) -> Mapping[str, Any]:
        counters["llm"] += 1
        return llm_adapter(grant, **kwargs)

    def counted_search(grant: Any, **kwargs: Any) -> Mapping[str, Any]:
        counters["search"] += 1
        return search_adapter(grant, **kwargs)

    register_question_only_provider(
        registry,
        query_operation=QuestionOnlyQueryOperation(max_tokens=config.query_max_tokens),
        evidence_operation=QuestionOnlyEvidenceOperation(
            max_results_per_query=config.max_results_per_query
        ),
    )
    controller_kwargs: dict[str, Any] = {
        "effect_broker": EffectBroker(
            {
                QUESTION_ONLY_LLM_EFFECT: counted_llm,
                QUESTION_ONLY_SEARCH_EFFECT: counted_search,
            }
        ),
    }
    if use_checkpoint_store:
        journal_root = Path(journal_root or Path.cwd() / "question-only-journal").resolve()
        checkpoint_root = Path(
            checkpoint_root or Path.cwd() / "question-only-checkpoints"
        ).resolve()
        journal = EventJournal()
        journal_archive = JsonlJournalArchive(journal_root)
        checkpoint_store = JsonCheckpointStore(checkpoint_root)
        controller_kwargs.update(
            journal=journal,
            journal_archive=journal_archive,
            checkpoint_store=checkpoint_store,
        )
    controller = DiamondController(registry, **controller_kwargs)
    budget = ExecutionBudget(config.per_call_operation_budget)
    episodes: list[QuestionOnlyEpisodeResult] = []
    result = controller.execute(blueprint, case.question, {"request": request}, budget=budget)
    previous_total_calls = 0
    current_total_calls = _current_calls(counters)
    episodes.append(_episode_result(0, result, counters, previous_total_calls))
    previous_total_calls = current_total_calls
    while (
        use_checkpoint_store
        and result.execution.state is not None
        and result.execution.state.value == "PAUSED"
        and len(episodes) < config.max_episodes
        and result.execution.checkpoint is not None
    ):
        result = controller.resume(
            result.execution.checkpoint,
            blueprint,
            budget=ExecutionBudget(config.per_call_operation_budget),
        )
        current_total_calls = _current_calls(counters)
        episodes.append(
            _episode_result(
                len(episodes),
                result,
                counters,
                previous_total_calls=previous_total_calls,
            )
        )
        previous_total_calls = current_total_calls
    query_proposal = _query_proposal_from_result(result)
    evidence_bundle = _evidence_bundle_from_result(result)
    checkpoint_ids = tuple(
        item.stored_checkpoint_id
        for item in episodes
        if item.stored_checkpoint_id is not None
    )
    provenance_preserved = _provenance_preserved(evidence_bundle)
    return QuestionOnlyArmResult(
        arm=arm,
        case_id=case.case_id,
        question=case.question,
        config=config,
        episodes=tuple(episodes),
        query_proposal=query_proposal,
        evidence_bundle=evidence_bundle,
        checkpoint_ids=checkpoint_ids,
        persistence_enabled=use_checkpoint_store,
        continuation_recorded=bool(checkpoint_ids),
        provenance_preserved=provenance_preserved,
        phi_closed=False,
        model_call_count=counters["llm"] + counters["search"],
    )


def _episode_result(
    episode_index: int,
    result: Any,
    counters: Mapping[str, int],
    previous_total_calls: int,
) -> QuestionOnlyEpisodeResult:
    query_proposal = _query_proposal_from_result(result)
    evidence_bundle = _evidence_bundle_from_result(result)
    return QuestionOnlyEpisodeResult(
        episode_index=episode_index,
        state=result.execution.state.value,
        checkpoint_id=(
            result.execution.checkpoint.checkpoint_id
            if result.execution.checkpoint is not None
            else None
        ),
        stored_checkpoint_id=(
            result.stored_checkpoint.checkpoint_id
            if result.stored_checkpoint is not None
            else None
        ),
        query_count=len(query_proposal.queries) if query_proposal is not None else 0,
        evidence_unit_count=(
            len(evidence_bundle.units) if evidence_bundle is not None else 0
        ),
        model_call_count=_current_calls(counters) - previous_total_calls,
        remainder_kinds=tuple(sorted({item.kind.value for item in result.execution.remainders})),
    )


def _query_proposal_from_result(result: Any) -> QuestionOnlyQueryProposal | None:
    artifact = result.execution.artifacts.get("query_proposal")
    if artifact is None:
        return None
    return decode_question_only_query_proposal(artifact)


def _evidence_bundle_from_result(result: Any) -> QuestionOnlyEvidenceBundle | None:
    artifact = result.execution.artifacts.get("evidence_bundle")
    if artifact is None:
        return None
    return decode_question_only_evidence_bundle(artifact)


def _completed(arm: QuestionOnlyArmResult) -> bool:
    return bool(arm.episodes and arm.episodes[-1].state == "COMPLETED")


def _provenance_preserved(bundle: QuestionOnlyEvidenceBundle | None) -> bool:
    if bundle is None:
        return True
    return all(
        unit.authority == "UNVALIDATED_EXTERNAL_EVIDENCE"
        and bool(unit.provenance)
        and unit.content_hash == sha256(unit.content.encode("utf-8")).hexdigest()
        for unit in bundle.units
    )


def _current_calls(counters: Mapping[str, int]) -> int:
    return counters["llm"] + counters["search"]


def decode_question_only_query_proposal(artifact: Artifact) -> QuestionOnlyQueryProposal:
    if artifact.schema != QUESTION_ONLY_QUERY_PROPOSAL_SCHEMA:
        raise ValueError("Unknown question-only query schema")
    payload = artifact.payload
    nested = payload.get("query_proposal")
    if isinstance(nested, Mapping):
        payload = nested
    if payload.get("authority") != "UNVALIDATED_QUESTION_ONLY_QUERY_PROPOSAL":
        raise PermissionError("Question-only query proposal authority is invalid")
    queries = payload.get("queries")
    if not isinstance(queries, (list, tuple)) or not queries:
        raise ValueError("Question-only query proposal contains no queries")
    return QuestionOnlyQueryProposal(
        request_id=_text(payload, "request_id"),
        question=_text(payload, "question"),
        queries=tuple(
            QuestionOnlyQuery(
                query_id=_text(item, "query_id"),
                text=_text(item, "text"),
                purpose=_text(item, "purpose"),
                preferred_source_types=tuple(
                    _text({"value": value}, "value")
                    for value in _list(item, "preferred_source_types")
                ),
                reveals_question_label=bool(item.get("reveals_question_label", False)),
            )
            for item in queries
        ),
        authority=_text(payload, "authority"),
        promotion_authority=bool(payload.get("promotion_authority", False)),
    )


def decode_question_only_evidence_bundle(
    artifact: Artifact,
) -> QuestionOnlyEvidenceBundle:
    if artifact.schema != QUESTION_ONLY_EVIDENCE_BUNDLE_SCHEMA:
        raise ValueError("Unknown question-only evidence schema")
    payload = artifact.payload
    nested = payload.get("evidence_bundle")
    if isinstance(nested, Mapping):
        payload = nested
    if payload.get("authority") != "UNVALIDATED_QUESTION_ONLY_EVIDENCE":
        raise PermissionError("Question-only evidence authority is invalid")
    units = payload.get("source_units")
    if not isinstance(units, (list, tuple)) or not units:
        raise ValueError("Question-only evidence bundle contains no units")
    return QuestionOnlyEvidenceBundle(
        request_id=_text(payload, "request_id"),
        question=_text(payload, "question"),
        query_ids=tuple(_list(payload, "query_ids")),
        units=tuple(_decode_evidence_unit(item) for item in units),
        authority=_text(payload, "authority"),
        promotion_authority=bool(payload.get("promotion_authority", False)),
    )


def _decode_evidence_unit(value: Mapping[str, Any]) -> QuestionOnlyEvidenceUnit:
    return QuestionOnlyEvidenceUnit(
        evidence_id=_text(value, "evidence_id"),
        query_id=_text(value, "query_id"),
        title=_text(value, "title"),
        content=_text(value, "content"),
        source_locator=_text(value, "source_locator"),
        source_type=_text(value, "source_type"),
        retrieved_at=_text(value, "retrieved_at"),
        content_hash=_text(value, "content_hash"),
        authority=_text(value, "authority"),
        source_document_ref=_optional_text(value, "source_document_ref"),
        extracted_unit_ref=_optional_text(value, "extracted_unit_ref"),
        provenance=tuple(_list(value, "provenance")),
        source_lineage=_optional_text(value, "source_lineage"),
    )


def _encode_evidence_unit(value: QuestionOnlyEvidenceUnit) -> dict[str, Any]:
    return {
        "evidence_id": value.evidence_id,
        "query_id": value.query_id,
        "title": value.title,
        "content": value.content,
        "source_locator": value.source_locator,
        "source_type": value.source_type,
        "retrieved_at": value.retrieved_at,
        "content_hash": value.content_hash,
        "authority": value.authority,
        "source_document_ref": value.source_document_ref,
        "extracted_unit_ref": value.extracted_unit_ref,
        "provenance": list(value.provenance),
        "source_lineage": value.source_lineage,
    }


def _question_messages(question: str, max_queries: int) -> tuple[Mapping[str, str], ...]:
    return (
        {
            "role": "system",
            "content": (
                "Propose neutral search queries for a single question. "
                "Return only one JSON object with a queries array. Each item "
                "must contain query_id, text, purpose, and "
                "preferred_source_types. Do not claim facts, authority, or "
                "promotion.\n\n"
                + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data(
                "question_only_request",
                {
                    "question": question,
                    "max_queries": max_queries,
                },
            ),
        },
    )


def _extract_object(content: str) -> Mapping[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        candidate = candidate.rsplit("```", 1)[0].strip()
    value = json.loads(candidate)
    if not isinstance(value, Mapping):
        raise ValueError("Question-only response must be a JSON object")
    return value


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _list(value: Mapping[str, Any], key: str) -> list[str]:
    item = value.get(key)
    if not isinstance(item, (list, tuple)) or any(
        not isinstance(entry, str) or not entry.strip() for entry in item
    ):
        raise ValueError(f"{key} must be a list of non-empty text")
    return [entry.strip() for entry in item]


def _int(value: Mapping[str, Any], key: str, *, default: int) -> int:
    item = value.get(key, default)
    if not isinstance(item, int) or isinstance(item, bool):
        raise ValueError(f"{key} must be an integer")
    return item
