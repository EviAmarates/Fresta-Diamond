"""Persistent application facade for user-facing Diamond adapters.

The controller remains provider-agnostic.  This module composes the existing
workspace, learning, validation, crystallization, and memory contracts into a
small durable use case that REPL and Web adapters can share.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.attention_continuation import JsonAttentionContinuationStore
from fresta_diamond.attention_memory import (
    AttentionContextRevision,
    AttentionMemory,
    AttentionState,
)
from fresta_diamond.attention_prompt import (
    AttentionPromptPreparationOperation,
    AttentionResponseOperation,
    build_attention_turn_request,
    register_attention_prompt_provider,
    attention_prompt_manifest,
)
from fresta_diamond.attention_resolution import (
    AttentionMaterializationService,
    AttentionMaterializedProjection,
    CompositeAttentionResolver,
    ConceptAttentionResolver,
    LearningMemoryAttentionResolver,
    WorkspaceAttentionResolver,
    workspace_sheet_content,
)
from fresta_diamond.attention_projection import (
    AttentionEvidenceState,
    AttentionItemKind,
    AttentionProjectionCheckpoint,
)
from fresta_diamond.cognitive_workspace import (
    CognitiveWorkspaceError,
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.sheet_decomposition import (
    SheetDecompositionOutcome,
    SheetDecompositionService,
)
from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptCandidateBuilder,
    ConceptMembership,
    ConceptRecord,
    ConceptState,
    ConceptSignature,
)
from fresta_diamond.concept_nomination import (
    ConceptNomination,
    ConceptNominationDecision,
    LlmConceptNominationOperation,
    build_concept_nomination_request,
    concept_nomination_blueprint,
    decode_concept_nomination,
    register_concept_nomination_provider,
    concept_nomination_manifest,
)
from fresta_diamond.concept_catalog import (
    ConceptCatalogIntake,
    load_concept_catalog,
)
from fresta_diamond.concept_evidence import (
    LlmConceptStructuralOperation,
    build_concept_evidence_request,
    concept_evidence_blueprint,
    decode_concept_seals,
    register_concept_evidence_provider,
    concept_evidence_manifest,
)
from fresta_diamond.objective_retrieval import (
    LlmObjectiveRetrievalOperation,
    ObjectiveRetrievalDecision,
    ObjectiveRetrievalEmpty,
    ObjectiveRetrievalNomination,
    batch_objective_retrieval_request,
    build_objective_retrieval_request,
    decode_objective_retrieval_nomination,
    merge_objective_retrieval_nominations,
    objective_retrieval_blueprint,
    register_objective_retrieval_provider,
    objective_retrieval_manifest,
)
from fresta_diamond.concept_validation import (
    ConceptValidationOutcome,
    ConceptValidationReport,
    ConceptValidationService,
)
from fresta_diamond.contracts import (
    Artifact,
    ControllerResult,
    ModuleManifest,
    Remainder,
    RemainderKind,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.constitutional_firewall import ConstitutionalFirewall
from fresta_diamond.firewall_semantic import ControllerFirewallSemanticAnalyzer
from fresta_diamond.effects import EffectBroker
from fresta_diamond.learning import (
    build_workspace_learn_request,
    register_workspace_learn_provider,
    workspace_learn_manifest,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
    StoredLearningCommit,
)
from fresta_diamond.llm_learning import (
    LEARNING_REPAIR_REQUEST_SCHEMA,
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    learning_evaluation_blueprint,
    learning_repair_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.concept_research import (
    ConceptResearchRequest,
    WikipediaConceptSearchAdapter,
    build_concept_research_request,
    concept_research_blueprint,
    concept_research_manifest,
    decode_source_units,
    register_concept_research_provider,
    research_request_artifact,
)
from fresta_diamond.concept_integration import (
    ConceptSourceLearner,
    ExternalConceptLearningOutcome,
)
from fresta_diamond.module_design import (
    AtomicModuleSuggestionArchive,
    LlmModuleSuggestionOperation,
    ModuleSuggestion,
    StoredModuleSuggestion,
    build_module_suggestion_request,
    decode_module_suggestion_artifact,
    deterministic_existing_provider_suggestion,
    module_suggestion_blueprint,
    module_suggestion_manifest,
    register_module_suggestion_provider,
)
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.epistemology import (
    EpistemicEvidenceGraph,
    decode_epistemic_evidence_graph,
)
from fresta_diamond.ontology import (
    StructuralEvidenceGraph,
    decode_structural_evidence_graph,
)
from fresta_diamond.concepts import DerivationSeal
from fresta_diamond.prompt_boundary import validate_model_messages
from fresta_diamond.chat import (
    AtomicChatStore,
    ChatMessage,
    ChatRole,
    ChatSession,
)


@dataclass(frozen=True)
class DiamondDataPaths:
    root: Path
    workspace: Path
    learning_memory: Path
    concepts: Path
    attention: Path
    continuations: Path
    module_suggestions: Path
    chat: Path

    @classmethod
    def under(cls, root: str | Path) -> "DiamondDataPaths":
        resolved = Path(root).resolve()
        return cls(
            root=resolved,
            workspace=resolved / "workspace",
            learning_memory=resolved / "learning-memory",
            concepts=resolved / "concepts",
            attention=resolved / "attention",
            continuations=resolved / "attention-continuations",
            module_suggestions=resolved / "module-suggestions",
            chat=resolved / "chat",
        )


@dataclass(frozen=True)
class DiamondLearnOutcome:
    sheet_id: str
    element_id: str
    proposal: Artifact
    result: ControllerResult
    stored_commit: StoredLearningCommit
    model_call_count: int
    repair_attempts_used: int


@dataclass(frozen=True)
class DiamondAttentionOutcome:
    context: AttentionContextRevision
    result: ControllerResult
    model_call_count: int
    continuation: AttentionProjectionCheckpoint | None = None
    sleep_revision: AttentionContextRevision | None = None
    decomposition: SheetDecompositionOutcome | None = None


@dataclass(frozen=True)
class DiamondAttentionDecompositionOutcome:
    source_context: AttentionContextRevision
    resumed_context: AttentionContextRevision
    continuation: AttentionProjectionCheckpoint
    decomposition: SheetDecompositionOutcome


@dataclass(frozen=True)
class DiamondActiveSheetOutcome:
    sheet: SheetRevision
    context: AttentionContextRevision
    content_hash: str


@dataclass(frozen=True)
class DiamondChatStartOutcome:
    retrieval: DiamondObjectiveRetrievalOutcome | None
    session: ChatSession | None
    context: AttentionContextRevision | None
    transcript: SheetRevision | None
    model_call_count: int


@dataclass(frozen=True)
class DiamondChatTurnOutcome:
    session: ChatSession
    user_message: ChatMessage
    assistant_message: ChatMessage | None
    attention: DiamondAttentionOutcome
    context: AttentionContextRevision
    transcript: SheetRevision
    model_call_count: int


@dataclass(frozen=True)
class DiamondConceptNominationOutcome:
    result: ControllerResult
    nomination: ConceptNomination | None
    concept: ConceptRecord | None
    model_call_count: int


@dataclass(frozen=True)
class DiamondConceptEvaluationOutcome:
    result: ControllerResult
    validation: ConceptValidationOutcome | None
    model_call_count: int


@dataclass(frozen=True)
class DiamondConceptGapResolutionOutcome:
    research_request: ConceptResearchRequest
    research_result: ControllerResult
    source_artifact: Artifact | None
    learning: ExternalConceptLearningOutcome | None
    revised_concept: ConceptRecord | None
    evaluation: DiamondConceptEvaluationOutcome | None
    model_call_count: int


@dataclass(frozen=True)
class DiamondConceptResolutionOutcome:
    initial_evaluation: DiamondConceptEvaluationOutcome
    gap_resolution: DiamondConceptGapResolutionOutcome | None
    model_call_count: int


@dataclass(frozen=True)
class DiamondObjectiveRetrievalOutcome:
    result: ControllerResult
    nomination: ObjectiveRetrievalNomination | None
    context: AttentionContextRevision | None
    materialized: AttentionMaterializedProjection | None
    model_call_count: int
    batch_results: tuple[ControllerResult, ...] = ()


@dataclass(frozen=True)
class DiamondModuleSuggestionOutcome:
    result: ControllerResult | None
    suggestion: ModuleSuggestion | None
    stored: StoredModuleSuggestion | None
    model_call_count: int
    deterministic_reuse: bool = False


class DiamondApplication:
    """One persistent Diamond instance, independent from Frankenstein data."""

    def __init__(
        self,
        data_root: str | Path,
        llm_adapter: Callable[..., Mapping[str, Any]],
        *,
        required_permissions: tuple[str, ...],
        max_tokens: int = 4_000,
        repair_attempts: int = 1,
        max_attention_tokens: int = 7_000,
        max_response_tokens: int = 2_000,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not required_permissions:
            raise ValueError("Diamond application requires model permission")
        if max_tokens < 1:
            raise ValueError("Diamond application max_tokens must be positive")
        if not 0 <= repair_attempts <= 3:
            raise ValueError("Diamond repair attempts must be between 0 and 3")
        if max_attention_tokens < 32 or max_response_tokens < 1:
            raise ValueError("Diamond attention token limits are invalid")
        self.paths = DiamondDataPaths.under(data_root)
        self.workspace = JsonlCognitiveWorkspace(self.paths.workspace)
        self.memory = AtomicDiamondLearningMemory(self.paths.learning_memory)
        self.concept_store = AtomicConceptStore(self.paths.concepts)
        self.attention_memory = AttentionMemory(self.paths.attention)
        self.attention_continuations = JsonAttentionContinuationStore(
            self.paths.continuations
        )
        self.module_suggestion_archive = AtomicModuleSuggestionArchive(
            self.paths.module_suggestions
        )
        self.chat_store = AtomicChatStore(self.paths.chat)
        self._adapter = llm_adapter
        self._permissions = tuple(required_permissions)
        self._max_tokens = max_tokens
        self._repair_attempts = repair_attempts
        self._max_attention_tokens = max_attention_tokens
        self._max_response_tokens = max_response_tokens
        self._run_id_factory = run_id_factory or (lambda: uuid4().hex)
        self._model_calls = 0
        self._model_call_lock = Lock()
        self._firewall_semantic_analyzer = ControllerFirewallSemanticAnalyzer(
            self._invoke_model,
            self._permissions,
        )
        self._firewall = ConstitutionalFirewall(
            semantic_analyzer=self._firewall_semantic_analyzer
        )

    def _controller(self, registry: ModuleRegistry, **kwargs: Any) -> DiamondController:
        return DiamondController(registry, firewall=self._firewall, **kwargs)

    def _invoke_model(self, grant: Any, **kwargs: Any) -> Mapping[str, Any]:
        messages = kwargs.get("messages")
        if not isinstance(messages, (list, tuple)):
            raise ValueError("Model call requires bounded messages")
        kwargs["messages"] = validate_model_messages(messages)
        with self._model_call_lock:
            self._model_calls += 1
        return self._adapter(grant, **kwargs)

    def _model_position(self) -> int:
        with self._model_call_lock:
            return self._model_calls

    def _model_calls_since(self, position: int) -> int:
        with self._model_call_lock:
            return self._model_calls - position

    def learn_text(
        self,
        text: str,
        *,
        scope: str = "scope:diamond-default",
        provenance: tuple[str, ...] = ("operator:user-supplied",),
        objective: str = "Evaluate this candidate without assuming it is true.",
        kind: SheetElementKind = SheetElementKind.CLAIM,
    ) -> DiamondLearnOutcome:
        model_position = self._model_position()
        content = text.strip()
        if not content:
            raise ValueError("Learning text cannot be empty")
        if not scope.strip() or not objective.strip():
            raise ValueError("Learning scope and objective are required")
        if not provenance or any(not item.strip() for item in provenance):
            raise ValueError("Learning provenance must be explicit")

        run_id = self._run_id_factory()
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Learning run ID must be non-empty text")
        sheet_id = f"learn-{run_id}"
        element_id = f"candidate:{run_id}"
        self.workspace.save(SheetRevision(
            sheet_id=sheet_id,
            revision_number=1,
            title="Diamond learning candidate",
            state=SheetState.STAGED,
            elements=(SheetElement(
                element_id=element_id,
                kind=SheetElementKind(kind),
                content=content,
                scope=scope,
                provenance=tuple(provenance),
            ),),
            objective_ref=f"objective:{run_id}",
        ))
        selection, selection_artifact = self.workspace.select(
            sheet_id,
            (element_id,),
            objective=objective,
        )

        registry = ModuleRegistry()
        register_workspace_learn_provider(registry)
        request = build_workspace_learn_request(selection, selection_artifact)
        intake = self._controller(registry).execute(
            request.blueprint,
            request.objective,
            request.inputs,
        )
        proposal = intake.execution.artifacts["learning_proposal"]
        self._register_learning_provider(registry)

        controller = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        )
        result = controller.execute(
            learning_evaluation_blueprint(self._permissions),
            objective,
            {"learning_proposal": proposal},
        )
        attempts_used = 0
        for attempt in range(1, self._repair_attempts + 1):
            closure = result.execution.closure
            if closure.structural_closed is True and closure.epistemic_closed is True:
                break
            structural = result.execution.artifacts.get("structural_evidence")
            if structural is None or not result.execution.remainders:
                break
            repair_request = Artifact(
                schema=LEARNING_REPAIR_REQUEST_SCHEMA,
                payload={
                    "learning_proposal": proposal.payload,
                    "original_bundle": structural.payload["_provider_bundle"],
                    "parent_artifact_id": structural.artifact_id,
                    "repair_attempt": attempt,
                    "validator_remainders": [
                        {
                            "kind": item.kind.value,
                            "required_for": item.required_for,
                            "description": item.description,
                        }
                        for item in result.execution.remainders
                    ],
                },
                provenance=(structural.artifact_id,),
            )
            result = controller.execute(
                learning_repair_blueprint(self._permissions),
                f"Repair learning evidence, attempt {attempt}",
                {"repair_request": repair_request},
            )
            attempts_used = attempt

        stored = self.memory.commit(proposal, result)
        return DiamondLearnOutcome(
            sheet_id=sheet_id,
            element_id=element_id,
            proposal=proposal,
            result=result,
            stored_commit=stored,
            model_call_count=self._model_calls_since(model_position),
            repair_attempts_used=attempts_used,
        )

    def learning_commits(self) -> tuple[StoredLearningCommit, ...]:
        return self.memory.commits()

    def suggest_module(
        self,
        *,
        objective: str,
        required_capability: str,
        output_schema: str,
        input_schemas: Mapping[str, str] | None = None,
        remainders: tuple[Remainder, ...] | None = None,
        occurrence_count: int = 1,
        allowed_effects: tuple[str, ...] = (),
        allowed_permissions: tuple[str, ...] = (),
    ) -> DiamondModuleSuggestionOutcome:
        """Refuse or archive one non-executable below-controller design."""

        model_position = self._model_position()

        observed = remainders or (Remainder(
            kind=RemainderKind.MISSING_CAPABILITY,
            description=(
                "The bounded objective requested a capability absent from its "
                "current execution path."
            ),
            required_for=objective,
            resolvable=True,
            suggested_capability=required_capability,
        ),)
        request = build_module_suggestion_request(
            self._native_module_manifests(),
            objective=objective,
            required_capability=required_capability,
            input_schemas=dict(input_schemas or {}),
            output_schema=output_schema,
            remainders=observed,
            occurrence_count=occurrence_count,
            allowed_effects=allowed_effects,
            allowed_permissions=allowed_permissions,
        )
        deterministic = deterministic_existing_provider_suggestion(request)
        if deterministic is not None:
            stored = self.module_suggestion_archive.save(deterministic)
            return DiamondModuleSuggestionOutcome(
                None,
                deterministic,
                stored,
                self._model_calls_since(model_position),
                True,
            )

        registry = ModuleRegistry()
        register_module_suggestion_provider(
            registry,
            permissions=self._permissions,
            operation=LlmModuleSuggestionOperation(
                max_tokens=self._max_response_tokens
            ),
        )
        result = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        ).execute(
            module_suggestion_blueprint(self._permissions),
            objective,
            {"request": request},
        )
        artifact = result.execution.artifacts.get("suggestion")
        if artifact is None:
            return DiamondModuleSuggestionOutcome(
                result,
                None,
                None,
                self._model_calls_since(model_position),
            )
        suggestion = decode_module_suggestion_artifact(artifact)
        stored = self.module_suggestion_archive.save(suggestion)
        return DiamondModuleSuggestionOutcome(
            result,
            suggestion,
            stored,
            self._model_calls_since(model_position),
        )

    def module_suggestions(self) -> tuple[StoredModuleSuggestion, ...]:
        return self.module_suggestion_archive.suggestions()

    def module_suggestion(self, suggestion_id: str) -> StoredModuleSuggestion:
        return self.module_suggestion_archive.load(suggestion_id)

    def _native_module_manifests(self) -> tuple[ModuleManifest, ...]:
        """Observable native inventory until Diamond owns one persistent registry."""

        return (
            workspace_learn_manifest(),
            llm_learning_manifest(self._permissions),
            concept_nomination_manifest(self._permissions),
            concept_evidence_manifest(self._permissions),
            concept_research_manifest(),
            objective_retrieval_manifest(self._permissions),
            attention_prompt_manifest(self._permissions),
            module_suggestion_manifest(self._permissions),
        )

    def crystals(
        self,
        *,
        scope: str | None = None,
        policy: CrystalRetrievalPolicy = CrystalRetrievalPolicy.ACTIVE,
    ):
        return self.memory.crystals(scope=scope, policy=policy)

    def concepts(self) -> tuple[ConceptRecord, ...]:
        return self.concept_store.records()

    def latest_concepts(self) -> tuple[ConceptRecord, ...]:
        return self.concept_store.latest_records()

    def concept_history(self, concept_id: str) -> tuple[ConceptRecord, ...]:
        """Return the verified version history for one exact concept."""

        # latest() verifies gaps and lineage and supplies the canonical unknown
        # concept diagnostic before the history is exposed to an interface.
        self.concept_store.latest(concept_id)
        return self.concept_store.history(concept_id)

    def concept(
        self,
        concept_id: str,
        *,
        version: int | None = None,
    ) -> ConceptRecord:
        """Read one latest or exact concept version without mutation."""

        if version is None:
            return self.concept_store.latest(concept_id)
        if version < 1:
            raise ValueError("Concept version must be positive")
        for record in self.concept_history(concept_id):
            if record.version == version:
                return record
        raise ValueError(f"Unknown concept version: {concept_id}@{version}")

    def stage_concept_catalog(
        self,
        catalog_path: str | Path,
        entry_ids: tuple[str, ...],
        *,
        scope: str,
        objective_ref: str,
    ) -> tuple[SheetRevision, ...]:
        """Stage external concept heuristics without learning or validating."""

        return ConceptCatalogIntake(self.workspace).stage(
            load_concept_catalog(catalog_path),
            entry_ids,
            scope=scope,
            objective_ref=objective_ref,
        )

    def propose_concept(
        self,
        *,
        canonical_name: str,
        scope: str,
        crystal_ids: tuple[str, ...],
        signature: ConceptSignature,
        aliases: tuple[str, ...] = (),
        parent_concept_ids: tuple[str, ...] = (),
        retrieval_policy: CrystalRetrievalPolicy = CrystalRetrievalPolicy.ACTIVE,
    ) -> ConceptRecord:
        """Persist a nomination without granting it validation authority."""

        proposed = ConceptCandidateBuilder(self.memory).propose(
            canonical_name=canonical_name,
            aliases=aliases,
            scope=scope,
            crystal_ids=crystal_ids,
            signature=signature,
            parent_concept_ids=parent_concept_ids,
            retrieval_policy=retrieval_policy,
        )
        self.concept_store.save(proposed)
        return proposed

    def nominate_concept(
        self,
        *,
        scope: str,
        objective: str,
        crystal_ids: tuple[str, ...] | None = None,
    ) -> DiamondConceptNominationOutcome:
        """Ask the LLM to nominate or refuse; persist only a candidate."""

        model_position = self._model_position()

        request = build_concept_nomination_request(
            self.memory,
            self.concept_store,
            scope=scope,
            objective=objective,
            crystal_ids=crystal_ids,
        )
        registry = ModuleRegistry()
        register_concept_nomination_provider(
            registry,
            required_permissions=self._permissions,
            operation=LlmConceptNominationOperation(
                max_tokens=self._max_response_tokens
            ),
        )
        result = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        ).execute(
            concept_nomination_blueprint(self._permissions),
            objective,
            {"request": request},
        )
        artifact = result.execution.artifacts.get("nomination")
        if artifact is None:
            return DiamondConceptNominationOutcome(
                result,
                None,
                None,
                self._model_calls_since(model_position),
            )
        nomination = decode_concept_nomination(artifact)
        if nomination.decision is ConceptNominationDecision.NO_CONCEPT:
            return DiamondConceptNominationOutcome(
                result,
                nomination,
                None,
                self._model_calls_since(model_position),
            )
        signature = ConceptSignature(**dict(nomination.signature))
        concept = self.propose_concept(
            canonical_name=nomination.canonical_name or "",
            aliases=nomination.aliases,
            scope=nomination.scope,
            crystal_ids=nomination.crystal_ids,
            signature=signature,
            parent_concept_ids=nomination.parent_concept_ids,
        )
        return DiamondConceptNominationOutcome(
            result,
            nomination,
            concept,
            self._model_calls_since(model_position),
        )

    def validate_concept(
        self,
        concept_id: str,
        *,
        seals: tuple[DerivationSeal, ...],
        structural_graph: StructuralEvidenceGraph,
        epistemic_graph: EpistemicEvidenceGraph,
    ) -> ConceptValidationOutcome:
        """Apply deterministic concept validation and preserve its report."""

        return ConceptValidationService(
            self.memory,
            self.concept_store,
        ).validate_and_store(
            concept_id,
            seals=seals,
            structural_graph=structural_graph,
            epistemic_graph=epistemic_graph,
        )

    def evaluate_concept(
        self,
        concept_id: str,
        *,
        objective: str | None = None,
    ) -> DiamondConceptEvaluationOutcome:
        """Propose bounded evidence, then validate it deterministically."""

        model_position = self._model_position()

        request = build_concept_evidence_request(
            self.memory,
            self.concept_store,
            concept_id,
            objective=objective,
        )
        registry = ModuleRegistry()
        register_concept_evidence_provider(
            registry,
            required_permissions=self._permissions,
            structural=LlmConceptStructuralOperation(
                max_tokens=self._max_tokens
            ),
        )
        result = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        ).execute(
            concept_evidence_blueprint(self._permissions),
            objective or "Evaluate one bounded concept candidate",
            {"request": request},
        )
        artifacts = result.execution.artifacts
        required = (
            "structural_evidence",
            "epistemic_evidence",
            "concept_seals",
        )
        if any(name not in artifacts for name in required):
            return DiamondConceptEvaluationOutcome(
                result,
                None,
                self._model_calls_since(model_position),
            )
        structural = decode_structural_evidence_graph(
            artifacts["structural_evidence"].payload
        )
        epistemic = decode_epistemic_evidence_graph(
            artifacts["epistemic_evidence"].payload
        )
        validation = self.validate_concept(
            concept_id,
            seals=decode_concept_seals(artifacts["concept_seals"]),
            structural_graph=structural,
            epistemic_graph=epistemic,
        )
        return DiamondConceptEvaluationOutcome(
            result,
            validation,
            self._model_calls_since(model_position),
        )

    def resolve_concept_gaps(
        self,
        concept_id: str,
        report: ConceptValidationReport,
        *,
        search_adapter: Callable[..., Mapping[str, Any]] | None = None,
        max_queries: int = 2,
        max_results_per_query: int = 2,
    ) -> DiamondConceptGapResolutionOutcome:
        """Research exact unsatisfied parts, learn sources, then re-evaluate.

        External results never seal or promote a concept directly. Only active
        crystals produced by the ordinary learning path become candidate
        memberships in a new version before deterministic concept evaluation.
        """
        model_position = self._model_position()
        concept = self.concept_store.latest(concept_id)
        if concept.state is not ConceptState.CANDIDATE:
            raise ValueError("Targeted gap resolution requires a concept candidate")
        if report.concept_ref != concept.version_ref:
            raise ValueError("Concept gap report does not match the current version")
        targets = tuple(dict.fromkeys(
            item.required_for
            for item in report.active_remainders
            if "concept part has no positive derivation seal" in (
                item.description.casefold()
            )
        ))
        if not targets:
            raise ValueError("Concept report exposes no targetable seal gap")
        research_request = build_concept_research_request(
            concept,
            report,
            max_queries=max_queries,
            max_results_per_query=max_results_per_query,
            target_refs=targets,
        )
        registry = ModuleRegistry()
        register_concept_research_provider(registry)
        research_result = self._controller(
            registry,
            effect_broker=EffectBroker({
                "internet.search": (
                    search_adapter or WikipediaConceptSearchAdapter()
                )
            }),
        ).execute(
            concept_research_blueprint(),
            "Research exact unresolved concept parts",
            {"research_request": research_request_artifact(research_request)},
        )
        source_artifact = research_result.execution.artifacts.get("source_units")
        if source_artifact is None:
            return DiamondConceptGapResolutionOutcome(
                research_request,
                research_result,
                None,
                None,
                None,
                None,
                self._model_calls_since(model_position),
            )
        if not decode_source_units(source_artifact):
            return DiamondConceptGapResolutionOutcome(
                research_request,
                research_result,
                source_artifact,
                None,
                None,
                None,
                self._model_calls_since(model_position),
            )
        learning = ConceptSourceLearner(
            self._invoke_model,
            required_permissions=self._permissions,
            max_tokens=self._max_tokens,
        ).learn(
            concept=concept,
            source_artifact=source_artifact,
            workspace=self.workspace,
            memory=self.memory,
        )
        active_ids = {
            item.crystal_id
            for item in self.memory.crystals(
                scope=concept.scope,
                policy=CrystalRetrievalPolicy.ACTIVE,
            )
        }
        learned_ids = tuple(
            item.crystal_id
            for item in learning.stored_commit.commit.crystallization.crystals
            if item.crystal_id in active_ids
        )
        if not learned_ids:
            return DiamondConceptGapResolutionOutcome(
                research_request,
                research_result,
                source_artifact,
                learning,
                None,
                None,
                self._model_calls_since(model_position),
            )
        existing = {item.crystal_id for item in concept.memberships}
        memberships = concept.memberships + tuple(
            ConceptMembership(crystal_id=crystal_id)
            for crystal_id in learned_ids
            if crystal_id not in existing
        )
        if len(memberships) == len(concept.memberships):
            return DiamondConceptGapResolutionOutcome(
                research_request,
                research_result,
                source_artifact,
                learning,
                None,
                None,
                self._model_calls_since(model_position),
            )
        revised = self.concept_store.revise(
            concept_id,
            memberships=memberships,
            state=ConceptState.CANDIDATE,
            reason=(
                "targeted external gap research learned through ordinary "
                f"memory intake ({research_request.request_id})"
            ),
        )
        evaluation = self.evaluate_concept(
            concept_id,
            objective=(
                "Re-evaluate the revised candidate using its original and "
                "newly learned source-bounded memberships."
            ),
        )
        return DiamondConceptGapResolutionOutcome(
            research_request,
            research_result,
            source_artifact,
            learning,
            revised,
            evaluation,
            self._model_calls_since(model_position),
        )

    def evaluate_and_resolve_concept(
        self,
        concept_id: str,
        *,
        objective: str | None = None,
        search_adapter: Callable[..., Mapping[str, Any]] | None = None,
        max_queries: int = 2,
        max_results_per_query: int = 2,
    ) -> DiamondConceptResolutionOutcome:
        """Evaluate once and research only an exact remaining seal gap.

        Interfaces call this application orchestration instead of embedding a
        command chain. Existing evaluation, research, learning and validation
        boundaries remain authoritative.
        """

        model_position = self._model_position()
        initial = self.evaluate_concept(concept_id, objective=objective)
        resolution = None
        if initial.validation is not None:
            report = initial.validation.report
            has_targetable_gap = any(
                "concept part has no positive derivation seal"
                in item.description.casefold()
                for item in report.active_remainders
            )
            if (
                initial.validation.record.state is ConceptState.CANDIDATE
                and has_targetable_gap
            ):
                resolution = self.resolve_concept_gaps(
                    concept_id,
                    report,
                    search_adapter=search_adapter,
                    max_queries=max_queries,
                    max_results_per_query=max_results_per_query,
                )
        return DiamondConceptResolutionOutcome(
            initial,
            resolution,
            self._model_calls_since(model_position),
        )

    def create_attention_context(
        self,
        *,
        objective: str,
        scope: str,
        summary: str,
        selected_refs: tuple[str, ...] = (),
        validated_refs: tuple[str, ...] = (),
        workspace_sheet_refs: tuple[str, ...] = (),
        active_sheet_ref: str | None = None,
        source_refs: tuple[str, ...] = (),
        remainder_refs: tuple[str, ...] = (),
    ) -> AttentionContextRevision:
        return self.attention_memory.create(
            objective=objective,
            scope=scope,
            summary=summary,
            selected_refs=selected_refs,
            validated_refs=validated_refs,
            workspace_sheet_refs=workspace_sheet_refs,
            active_sheet_ref=active_sheet_ref,
            source_refs=source_refs,
            remainder_refs=remainder_refs,
        )

    def create_attention_with_active_sheet(
        self,
        *,
        objective: str,
        scope: str,
        summary: str,
        sheet: SheetRevision,
    ) -> DiamondActiveSheetOutcome:
        """Persist one scratch sheet and bind its exact revision to attention."""

        sheet_scopes = {item.scope for item in sheet.elements}
        if sheet_scopes and sheet_scopes != {scope}:
            raise ValueError("Active sheet elements must match attention scope")
        content_hash = self.workspace.save(sheet)
        reference = self.workspace.reference(
            sheet.sheet_id,
            sheet.revision_id,
        )
        context = self.create_attention_context(
            objective=objective,
            scope=scope,
            summary=summary,
            workspace_sheet_refs=(reference.target_ref,),
            active_sheet_ref=reference.target_ref,
        )
        return DiamondActiveSheetOutcome(sheet, context, content_hash)

    def bind_active_sheet(
        self,
        context_id: str,
        sheet: SheetRevision,
        *,
        summary: str | None = None,
    ) -> DiamondActiveSheetOutcome:
        """Bind a first exact active sheet to an existing active context."""

        current = self.attention_memory.latest(context_id)
        if current.state is not AttentionState.ACTIVE:
            raise ValueError("Only active attention can bind a scratch sheet")
        if current.active_sheet_ref is not None:
            raise ValueError("Attention context already has an active scratch sheet")
        sheet_scopes = {item.scope for item in sheet.elements}
        if sheet_scopes and sheet_scopes != {current.scope}:
            raise ValueError("Active sheet elements must match attention scope")
        content_hash = self.workspace.save(sheet)
        reference = self.workspace.reference(sheet.sheet_id, sheet.revision_id)
        context = self.attention_memory.update(
            context_id,
            summary=summary or current.summary,
            workspace_sheet_refs=tuple(dict.fromkeys((
                *current.workspace_sheet_refs,
                reference.target_ref,
            ))),
            active_sheet_ref=reference.target_ref,
        )
        return DiamondActiveSheetOutcome(sheet, context, content_hash)

    def start_active_sheet(
        self,
        *,
        objective: str,
        scope: str,
        summary: str | None = None,
        title: str = "Active task sheet",
        content: str | None = None,
        kind: SheetElementKind = SheetElementKind.NOTE,
    ) -> DiamondActiveSheetOutcome:
        """Create a command-friendly scratch sheet and bind it to attention."""

        if not objective.strip() or not scope.strip() or not title.strip():
            raise ValueError("Active sheet objective, scope, and title are required")
        if content is not None and not content.strip():
            raise ValueError("Initial active sheet content cannot be blank")
        sheet_id = f"scratch:{uuid4()}"
        elements = () if content is None else (SheetElement(
            element_id=f"sheet-element:{uuid4()}",
            kind=kind,
            content=content.strip(),
            scope=scope.strip(),
            provenance=("operator:active-sheet",),
        ),)
        return self.create_attention_with_active_sheet(
            objective=objective.strip(),
            scope=scope.strip(),
            summary=(summary or objective).strip(),
            sheet=SheetRevision(
                sheet_id=sheet_id,
                revision_number=1,
                title=title.strip(),
                state=SheetState.DRAFT,
                elements=elements,
            ),
        )

    def active_sheet(self, context_id: str) -> SheetRevision:
        """Resolve the exact active sheet revision bound to one context."""

        context = self.attention_memory.latest(context_id)
        if context.active_sheet_ref is None:
            raise ValueError("Attention context has no active scratch sheet")
        return self.workspace.resolve_reference(context.active_sheet_ref)

    def append_active_sheet(
        self,
        context_id: str,
        content: str,
        *,
        kind: SheetElementKind = SheetElementKind.NOTE,
        summary: str | None = None,
        provenance: tuple[str, ...] = (),
    ) -> DiamondActiveSheetOutcome:
        """Append one element while preserving the immutable prior revision."""

        if not content.strip():
            raise ValueError("Active sheet content cannot be blank")
        context = self.attention_memory.latest(context_id)
        previous = self.active_sheet(context_id)
        prior_ref = context.active_sheet_ref
        assert prior_ref is not None
        revised = SheetRevision(
            sheet_id=previous.sheet_id,
            revision_number=previous.revision_number + 1,
            title=previous.title,
            state=SheetState.DRAFT,
            elements=previous.elements + (SheetElement(
                element_id=f"sheet-element:{uuid4()}",
                kind=kind,
                content=content.strip(),
                scope=context.scope,
                provenance=tuple(dict.fromkeys((prior_ref, *provenance))),
            ),),
            links=previous.links,
            parent_revision_id=previous.revision_id,
            objective_ref=previous.objective_ref,
            author_ref=previous.author_ref,
        )
        return self.revise_active_sheet(
            context_id,
            revised,
            summary=summary,
        )

    def revise_active_sheet(
        self,
        context_id: str,
        sheet: SheetRevision,
        *,
        summary: str | None = None,
    ) -> DiamondActiveSheetOutcome:
        """Advance the exact active sheet and attention through new revisions."""

        current = self.attention_memory.latest(context_id)
        if current.state is not AttentionState.ACTIVE:
            raise ValueError("Only active attention can revise its scratch sheet")
        if current.active_sheet_ref is None:
            raise ValueError("Attention context has no active scratch sheet")
        previous = self.workspace.resolve_reference(current.active_sheet_ref)
        if sheet.sheet_id != previous.sheet_id:
            raise ValueError("Active sheet revision changed sheet identity")
        if sheet.parent_revision_id != previous.revision_id:
            raise ValueError("Active sheet revision does not extend the bound head")
        sheet_scopes = {item.scope for item in sheet.elements}
        if sheet_scopes and sheet_scopes != {current.scope}:
            raise ValueError("Active sheet elements must match attention scope")
        content_hash = self.workspace.save(sheet)
        reference = self.workspace.reference(
            sheet.sheet_id,
            sheet.revision_id,
        )
        workspace_refs = tuple(
            reference.target_ref if item == current.active_sheet_ref else item
            for item in current.workspace_sheet_refs
        )
        revised_context = self.attention_memory.update(
            context_id,
            summary=summary or current.summary,
            workspace_sheet_refs=workspace_refs,
            active_sheet_ref=reference.target_ref,
        )
        return DiamondActiveSheetOutcome(
            sheet,
            revised_context,
            content_hash,
        )

    def retrieve_for_objective(
        self,
        *,
        scope: str,
        objective: str,
        summary: str | None = None,
        token_budget: int | None = None,
        candidate_batch_tokens: int | None = None,
    ) -> DiamondObjectiveRetrievalOutcome:
        """Nominate exact roots, create attention, and close dependencies."""

        model_position = self._model_position()

        request = build_objective_retrieval_request(
            self.memory,
            self.concept_store,
            self.workspace,
            scope=scope,
            objective=objective,
        )
        requests = batch_objective_retrieval_request(
            request,
            max_request_tokens=(
                candidate_batch_tokens
                if candidate_batch_tokens is not None
                else self._max_attention_tokens
            ),
        )
        registry = ModuleRegistry()
        register_objective_retrieval_provider(
            registry,
            required_permissions=self._permissions,
            operation=LlmObjectiveRetrievalOperation(
                max_tokens=self._max_response_tokens
            ),
        )
        controller = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        )
        batch_results = []
        nominations = []
        for batch in requests:
            result = controller.execute(
                objective_retrieval_blueprint(self._permissions),
                objective,
                {"request": batch},
            )
            batch_results.append(result)
            artifact = result.execution.artifacts.get("nomination")
            if artifact is None:
                return DiamondObjectiveRetrievalOutcome(
                    result,
                    None,
                    None,
                    None,
                    self._model_calls_since(model_position),
                    tuple(batch_results),
                )
            nominations.append(decode_objective_retrieval_nomination(artifact))
        nomination = merge_objective_retrieval_nominations(tuple(nominations))
        result = batch_results[-1]
        if nomination.decision is ObjectiveRetrievalDecision.NO_SELECTION:
            return DiamondObjectiveRetrievalOutcome(
                result,
                nomination,
                None,
                None,
                self._model_calls_since(model_position),
                tuple(batch_results),
            )
        selected: list[str] = []
        validated: list[str] = []
        workspace_refs: list[str] = []
        remainders: list[str] = []
        for item in nomination.items:
            if item.kind == "WORKSPACE":
                workspace_refs.append(item.item_ref)
            elif item.kind == "PHI_MINUS":
                remainders.append(item.item_ref)
            elif (
                item.kind == "CONCEPT"
                and item.source_authority in {
                    "CONCEPT_STORE:VALIDATED",
                    "CONCEPT_STORE:CRYSTALLIZED",
                }
            ):
                validated.append(item.item_ref)
            else:
                selected.append(item.item_ref)
        context = self.create_attention_context(
            objective=objective,
            scope=scope,
            summary=summary or nomination.rationale,
            selected_refs=tuple(selected),
            validated_refs=tuple(validated),
            workspace_sheet_refs=tuple(workspace_refs),
            remainder_refs=tuple(remainders),
        )
        materialized = AttentionMaterializationService(
            CompositeAttentionResolver((
                LearningMemoryAttentionResolver(self.memory),
                ConceptAttentionResolver(self.concept_store),
                WorkspaceAttentionResolver(self.workspace),
            )),
            continuation_store=self.attention_continuations,
        ).materialize_and_project(
            context,
            token_budget=token_budget or self._max_attention_tokens,
            nominations=nomination.attention_nominations,
        )
        return DiamondObjectiveRetrievalOutcome(
            result,
            nomination,
            context,
            materialized,
            self._model_calls_since(model_position),
            tuple(batch_results),
        )

    def start_chat(
        self,
        *,
        scope: str,
        objective: str,
        summary: str | None = None,
        token_budget: int | None = None,
        candidate_batch_tokens: int | None = None,
    ) -> DiamondChatStartOutcome:
        """Create objective-relative attention and a persistent chat transcript."""

        model_position = self._model_position()
        try:
            retrieval = self.retrieve_for_objective(
                scope=scope,
                objective=objective,
                summary=summary,
                token_budget=token_budget,
                candidate_batch_tokens=candidate_batch_tokens,
            )
        except ObjectiveRetrievalEmpty:
            retrieval = None
        if retrieval is not None and retrieval.nomination is None:
            return DiamondChatStartOutcome(
                retrieval,
                None,
                None,
                None,
                self._model_calls_since(model_position),
            )
        context = (
            retrieval.context if retrieval is not None else None
        ) or self.create_attention_context(
            objective=objective,
            scope=scope,
            summary=(
                summary
                or (
                    retrieval.nomination.rationale
                    if retrieval is not None else objective
                )
            ),
        )
        transcript = SheetRevision(
            sheet_id=f"chat-transcript:{uuid4()}",
            revision_number=1,
            title="Chat transcript",
            state=SheetState.DRAFT,
            elements=(),
            author_ref="actor:chat-coordinator",
        )
        bound = self.bind_active_sheet(
            context.context_id,
            transcript,
            summary=summary or context.summary,
        )
        session = self.chat_store.create(
            context_id=context.context_id,
            transcript_sheet_id=transcript.sheet_id,
            scope=scope,
            objective=objective,
        )
        return DiamondChatStartOutcome(
            retrieval,
            session,
            bound.context,
            transcript,
            self._model_calls_since(model_position),
        )

    def chat_turn(
        self,
        session_id: str,
        message: str,
        *,
        token_budget: int | None = None,
    ) -> DiamondChatTurnOutcome:
        """Persist a user turn, run bounded attention, and preserve any response."""

        if not message.strip():
            raise ValueError("Chat message cannot be blank")
        model_position = self._model_position()
        session = self.chat_store.session(session_id)
        user_message = self.chat_store.append(
            session_id,
            role=ChatRole.USER,
            content=message,
            provenance=("operator:user-supplied",),
        )
        user_projection = self.append_active_sheet(
            session.context_id,
            message,
            kind=SheetElementKind.USER_MESSAGE,
            provenance=(user_message.message_id,),
        )
        attention = self.attention_turn(
            session.context_id,
            instruction=message,
            token_budget=token_budget,
        )
        response = attention.result.execution.artifacts.get("response")
        assistant_message = None
        transcript = user_projection.sheet
        if response is not None:
            content = response.payload.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Chat response artifact contains no text")
            assistant_message = self.chat_store.append(
                session_id,
                role=ChatRole.ASSISTANT,
                content=content,
                provenance=tuple(response.provenance) or (
                    attention.context.context_ref,
                ),
            )
            if attention.sleep_revision is None:
                assistant_projection = self.append_active_sheet(
                    session.context_id,
                    content,
                    kind=SheetElementKind.ASSISTANT_MESSAGE,
                    provenance=(assistant_message.message_id,),
                )
                transcript = assistant_projection.sheet
        context = self.attention_memory.latest(session.context_id)
        return DiamondChatTurnOutcome(
            session,
            user_message,
            assistant_message,
            attention,
            context,
            transcript,
            self._model_calls_since(model_position),
        )

    def chat_session(self, session_id: str) -> ChatSession:
        return self.chat_store.session(session_id)

    def chat_sessions(self) -> tuple[ChatSession, ...]:
        return self.chat_store.sessions()

    def chat_messages(self, session_id: str) -> tuple[ChatMessage, ...]:
        return self.chat_store.messages(session_id)

    def attention_turn(
        self,
        context_id: str,
        *,
        instruction: str,
        token_budget: int | None = None,
        auto_sleep: bool = True,
        auto_decompose: bool = True,
    ) -> DiamondAttentionOutcome:
        """Generate one unvalidated response over exact persistent references."""

        model_position = self._model_position()

        context = self.attention_memory.latest(context_id)
        budget = token_budget or self._max_attention_tokens
        materializer = AttentionMaterializationService(
            self._attention_resolver(),
            continuation_store=self.attention_continuations,
        )
        known_continuations = {
            item.checkpoint_id
            for item in self.attention_continuations.for_context(
                context.context_ref
            )
        }
        registry = ModuleRegistry()
        register_attention_prompt_provider(
            registry,
            preparation=AttentionPromptPreparationOperation(
                self.attention_memory,
                materializer,
                max_attention_tokens=self._max_attention_tokens,
            ),
            response=AttentionResponseOperation(
                max_tokens=self._max_response_tokens
            ),
            granted_permissions=self._permissions,
        )
        request = build_attention_turn_request(
            context_id=context.context_id,
            context_ref=context.context_ref,
            objective=context.objective,
            instruction=instruction,
            token_budget=budget,
            granted_permissions=self._permissions,
        )
        result = self._controller(
            registry,
            effect_broker=EffectBroker({"llm.generate": self._invoke_model}),
        ).execute(
            request.blueprint,
            request.objective,
            request.inputs,
        )
        created = tuple(
            item
            for item in self.attention_continuations.for_context(
                context.context_ref
            )
            if item.checkpoint_id not in known_continuations
        )
        if len(created) > 1:
            raise RuntimeError("One attention turn created multiple continuations")
        prompt = result.execution.artifacts.get("prompt")
        continuation_id = (
            prompt.payload.get("continuation_checkpoint_id")
            if prompt is not None else None
        )
        continuation = (
            self.attention_continuations.load(continuation_id)
            if isinstance(continuation_id, str) and continuation_id
            else (created[0] if created else None)
        )
        sleep_revision = None
        if (
            auto_sleep
            and continuation is not None
            and self._is_token_budget_sleep(continuation)
        ):
            sleep_revision = self.attention_memory.suspend(
                context.context_id,
                reason=f"TOKEN_BUDGET:{continuation.checkpoint_id}",
                summary=(
                    f"Sleeping after revision {context.revision_number}; "
                    f"{len(continuation.pending_refs)} attention refs remain."
                ),
            )
        if (
            auto_decompose
            and sleep_revision is not None
            and continuation is not None
            and self._requires_decomposition(continuation)
            and self._has_decomposable_workspace_ref(continuation)
        ):
            repaired = self.decompose_attention(continuation.checkpoint_id)
            resumed = self.attention_turn(
                context.context_id,
                instruction=instruction,
                token_budget=budget,
                auto_sleep=auto_sleep,
                auto_decompose=False,
            )
            return DiamondAttentionOutcome(
                resumed.context,
                resumed.result,
                self._model_calls_since(model_position),
                resumed.continuation,
                resumed.sleep_revision,
                repaired.decomposition,
            )
        return DiamondAttentionOutcome(
            context,
            result,
            self._model_calls_since(model_position),
            continuation,
            sleep_revision,
        )

    def decompose_attention(
        self,
        checkpoint_id: str,
        *,
        max_child_content_tokens: int | None = None,
        max_children_per_index: int = 32,
    ) -> DiamondAttentionDecompositionOutcome:
        """Replace one zero-progress oversized sheet with exact bounded leaves."""

        continuation = self.attention_continuations.load(checkpoint_id)
        if not self._requires_decomposition(continuation):
            raise ValueError(
                "Attention decomposition requires one zero-progress oversized ref"
            )
        source, latest = self._safe_sleep_context(continuation)
        item_ref = continuation.pending_refs[0]
        try:
            sheet = (
                self.workspace.resolve_reference(item_ref)
                if item_ref.startswith("sheet-revision:")
                else self.workspace.latest(item_ref.removeprefix("sheet:"))
            )
        except CognitiveWorkspaceError as exc:
            raise ValueError(
                "Oversized attention ref is not a resolvable workspace sheet"
            ) from exc
        if not (
            item_ref.startswith("sheet:")
            or item_ref.startswith("sheet-revision:")
        ):
            raise ValueError(
                "Only workspace sheets support deterministic decomposition"
            )
        exact_source = self.workspace.reference(
            sheet.sheet_id,
            sheet.revision_id,
        ).target_ref
        run_id = self._run_id_factory()
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Decomposition run ID must be non-empty text")
        content_budget = (
            max_child_content_tokens
            if max_child_content_tokens is not None
            else max(1, continuation.token_budget // 8)
        )
        decomposition = SheetDecompositionService(self.workspace).decompose(
            content=workspace_sheet_content(sheet),
            source_ref=exact_source,
            mother_sheet_id=f"attn-dec:{run_id}",
            mother_revision_id=f"attn-dec:{run_id}:r1",
            title=f"Attention decomposition of {sheet.title}",
            scope=source.scope,
            max_child_content_tokens=content_budget,
            max_children_per_index=max_children_per_index,
            objective_ref=source.context_ref,
            decomposition_id=run_id,
        )
        leaf_refs = tuple(item.target_ref for item in decomposition.leaf_refs)
        resumed = self.attention_memory.reactivate(
            source.context_id,
            summary=(
                f"Decomposed oversized workspace object into "
                f"{len(leaf_refs)} exact attention leaves."
            ),
            source_refs=(),
            validated_refs=(),
            selected_refs=(),
            workspace_sheet_refs=leaf_refs,
            active_sheet_ref=None,
            remainder_refs=(),
        )
        if latest.revision_id != resumed.previous_revision_id:
            raise RuntimeError("Attention decomposition resumed an unexpected head")
        return DiamondAttentionDecompositionOutcome(
            source,
            resumed,
            continuation,
            decomposition,
        )

    def resume_attention(
        self,
        checkpoint_id: str,
        *,
        summary: str | None = None,
    ) -> AttentionContextRevision:
        """Atomically reactivate only the pending refs of one safe sleep."""

        continuation = self.attention_continuations.load(checkpoint_id)
        if not self._automatically_resumable(continuation):
            raise ValueError(
                "Attention continuation needs repair or decomposition, not resume"
            )
        source, _latest = self._safe_sleep_context(continuation)
        context_id = source.context_id
        resolution = self._attention_resolver().resolve(source)
        by_ref = {item.item_ref: item for item in resolution.candidates}
        missing = set(continuation.pending_refs) - set(by_ref)
        if missing:
            raise ValueError(
                f"Pending attention refs cannot be resolved: {sorted(missing)}"
            )
        categorized = {
            "source": [],
            "validated": [],
            "selected": [],
            "workspace": [],
            "remainder": [],
        }
        for item_ref in continuation.pending_refs:
            candidate = by_ref[item_ref]
            if candidate.kind is AttentionItemKind.SOURCE:
                categorized["source"].append(item_ref)
            elif candidate.kind is AttentionItemKind.WORKSPACE:
                categorized["workspace"].append(item_ref)
            elif candidate.kind in {
                AttentionItemKind.REMAINDER,
                AttentionItemKind.PHI_MINUS,
            }:
                categorized["remainder"].append(item_ref)
            elif candidate.evidence_state is AttentionEvidenceState.VALIDATED:
                categorized["validated"].append(item_ref)
            else:
                categorized["selected"].append(item_ref)
        return self.attention_memory.reactivate(
            context_id,
            summary=(
                summary
                or f"Resumed {len(continuation.pending_refs)} pending refs."
            ),
            source_refs=tuple(categorized["source"]),
            validated_refs=tuple(categorized["validated"]),
            selected_refs=tuple(categorized["selected"]),
            workspace_sheet_refs=tuple(categorized["workspace"]),
            active_sheet_ref=(
                source.active_sheet_ref
                if source.active_sheet_ref in continuation.pending_refs
                else None
            ),
            remainder_refs=tuple(categorized["remainder"]),
        )

    def _attention_resolver(self) -> CompositeAttentionResolver:
        return CompositeAttentionResolver((
            LearningMemoryAttentionResolver(self.memory),
            ConceptAttentionResolver(self.concept_store),
            WorkspaceAttentionResolver(self.workspace),
        ))

    @staticmethod
    def _automatically_resumable(
        continuation: AttentionProjectionCheckpoint,
    ) -> bool:
        return bool(
            continuation.completed_refs
            and DiamondApplication._is_token_budget_sleep(continuation)
        )

    @staticmethod
    def _requires_decomposition(
        continuation: AttentionProjectionCheckpoint,
    ) -> bool:
        return bool(
            not continuation.completed_refs
            and len(continuation.pending_refs) == 1
            and DiamondApplication._is_token_budget_sleep(continuation)
        )

    @staticmethod
    def _has_decomposable_workspace_ref(
        continuation: AttentionProjectionCheckpoint,
    ) -> bool:
        return bool(
            len(continuation.pending_refs) == 1
            and continuation.pending_refs[0].startswith((
                "sheet:",
                "sheet-revision:",
            ))
        )

    def _safe_sleep_context(
        self,
        continuation: AttentionProjectionCheckpoint,
    ) -> tuple[AttentionContextRevision, AttentionContextRevision]:
        context_id = self._context_id_from_ref(continuation.context_ref)
        history = self.attention_memory.history(context_id)
        source = next((
            item for item in history
            if item.context_ref == continuation.context_ref
        ), None)
        if source is None:
            raise ValueError("Attention continuation source revision is missing")
        latest = self.attention_memory.latest(context_id)
        expected_reason = f"TOKEN_BUDGET:{continuation.checkpoint_id}"
        if (
            latest.state is not AttentionState.SUSPENDED
            or latest.suspension_reason != expected_reason
            or latest.previous_revision_id != source.revision_id
        ):
            raise ValueError(
                "Attention continuation does not match the latest safe sleep"
            )
        return source, latest

    @staticmethod
    def _is_token_budget_sleep(
        continuation: AttentionProjectionCheckpoint,
    ) -> bool:
        return bool(
            continuation.pending_refs
            and not continuation.blocked_refs
            and set(continuation.reasons) == {"TOKEN_BUDGET"}
        )

    @staticmethod
    def _context_id_from_ref(context_ref: str) -> str:
        if not context_ref.startswith("attention:") or "@" not in context_ref:
            raise ValueError("Attention continuation context ref is invalid")
        context_id, revision = context_ref.removeprefix("attention:").rsplit(
            "@", 1
        )
        if not context_id.strip() or not revision.isdigit():
            raise ValueError("Attention continuation context ref is invalid")
        return context_id

    def _register_learning_provider(self, registry: ModuleRegistry) -> None:
        manifest = llm_learning_manifest(self._permissions)
        registry.discover(
            manifest,
            ModuleDiscoveryEvidence(
                source=ModuleSource.LOCAL,
                provenance=("runtime:diamond-application-llm",),
            ),
        )
        admission = registry.verify(manifest.module_id)
        if not admission.admitted:
            raise RuntimeError("Diamond learning provider was rejected")
        registry.enable(
            manifest.module_id,
            {
                manifest.operations[0].operation_id: (
                    LlmLearningStructuralOperation(max_tokens=self._max_tokens)
                ),
                manifest.operations[1].operation_id: (
                    LlmLearningEpistemicOperation()
                ),
                manifest.operations[2].operation_id: (
                    LlmLearningRepairOperation(max_tokens=self._max_tokens)
                ),
            },
        )
