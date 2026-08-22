"""Isolated, invariant-based regression laboratory for Diamond learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping
from uuid import uuid4

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.concepts import (
    AtomicConceptStore,
    ConceptCandidateBuilder,
    ConceptSignature,
    DerivationContribution,
    DerivationSeal,
    DerivationSource,
    DerivationSourceKind,
    concept_targets,
)
from fresta_diamond.concept_validation import (
    ConceptValidationService,
    ConceptValidator,
)
from fresta_diamond.concept_research import (
    build_concept_research_request,
    concept_research_blueprint,
    decode_source_units,
    register_concept_research_provider,
    research_request_artifact,
    stage_source_units,
)
from fresta_diamond.concept_integration import (
    ConceptRecognitionService,
    ConceptRecognitionValidator,
    ConceptSourceLearner,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.crystallization import CrystallizationGate
from fresta_diamond.effects import EffectBroker
from fresta_diamond.epistemology import decode_epistemic_evidence_graph
from fresta_diamond.learning import (
    build_workspace_learn_request,
    register_workspace_learn_provider,
)
from fresta_diamond.learning_memory import (
    AtomicDiamondLearningMemory,
    CrystalRetrievalPolicy,
)
from fresta_diamond.llm_learning import (
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    learning_evaluation_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.phi_minus import PhiMinusDeriver
from fresta_diamond.ontology import decode_structural_evidence_graph
from fresta_diamond.registry import ModuleRegistry


BENCHMARK_MANIFEST_SCHEMA = "fresta://diamond-benchmark-manifest@1"
BENCHMARK_RUN_SCHEMA = "fresta://diamond-benchmark-run@1"
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_REPLAY_PERMISSIONS = ("llm.model:diamond-replay",)


class BenchmarkLabError(RuntimeError):
    """Raised when isolated benchmark data violates its contract."""


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    fixture_path: Path
    fixture_hash: str
    fixture: Mapping[str, Any]


@dataclass(frozen=True)
class BenchmarkComparison:
    matches: bool
    differences: tuple[str, ...]


class DiamondBenchmarkLab:
    """Read immutable cases and archive comparable runs under one data root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.manifest_path = self.root / "manifest.json"
        self._manifest = self._read_json(self.manifest_path)
        if self._manifest.get("schema") != BENCHMARK_MANIFEST_SCHEMA:
            raise BenchmarkLabError("Unsupported Diamond benchmark manifest")
        self.suite_id = self._safe_id(self._manifest.get("suite_id"), "suite_id")
        self.baseline_id = self._safe_id(
            self._manifest.get("baseline_id"), "baseline_id"
        )

    def list_cases(self) -> tuple[str, ...]:
        return tuple(self._case_index())

    def load_case(self, case_id: str) -> BenchmarkCase:
        return self._load_case(case_id, seen=frozenset())

    def _load_case(
        self,
        case_id: str,
        *,
        seen: frozenset[str],
    ) -> BenchmarkCase:
        case_id = self._safe_id(case_id, "case_id")
        if case_id in seen:
            raise BenchmarkLabError(
                f"Cyclic benchmark fixture inheritance: {case_id}"
            )
        descriptor = self._case_index().get(case_id)
        if descriptor is None:
            raise BenchmarkLabError(f"Unknown benchmark case: {case_id}")
        relative = descriptor.get("fixture")
        if not isinstance(relative, str):
            raise BenchmarkLabError(f"Case {case_id} has no fixture path")
        path = self._contained_path(relative, expected_parent="fixtures")
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        expected = descriptor.get("sha256")
        if expected != digest:
            raise BenchmarkLabError(
                f"Fixture digest mismatch for {case_id}: expected {expected}, got {digest}"
            )
        fixture = json.loads(raw.decode("utf-8"))
        if fixture.get("case_id") != case_id:
            raise BenchmarkLabError(f"Fixture identity mismatch for {case_id}")
        base_id = fixture.get("extends_case")
        if base_id is None:
            return BenchmarkCase(case_id, path, digest, fixture)
        base_id = self._safe_id(base_id, "extends_case")
        base = self._load_case(base_id, seen=seen | {case_id})
        merged = {
            **base.fixture,
            **fixture,
            "case_id": case_id,
        }
        composite = sha256(
            f"{base.fixture_hash}:{digest}".encode("utf-8")
        ).hexdigest()
        return BenchmarkCase(case_id, path, composite, merged)

    def load_baseline(self) -> Mapping[str, Any]:
        return self._load_baseline(self.baseline_id, seen=frozenset())

    def _load_baseline(
        self,
        baseline_id: str,
        *,
        seen: frozenset[str],
    ) -> Mapping[str, Any]:
        baseline_id = self._safe_id(baseline_id, "baseline_id")
        if baseline_id in seen:
            raise BenchmarkLabError(
                f"Cyclic benchmark baseline inheritance: {baseline_id}"
            )
        path = self._contained_path(
            f"baselines/{baseline_id}.json", expected_parent="baselines"
        )
        baseline = self._read_json(path)
        if baseline.get("suite_id") != self.suite_id:
            raise BenchmarkLabError("Baseline belongs to another suite")
        if baseline.get("baseline_id") != baseline_id:
            raise BenchmarkLabError("Baseline identity mismatch")
        own_cases = baseline.get("cases")
        if not isinstance(own_cases, Mapping):
            raise BenchmarkLabError("Baseline cases must be an object")
        parent_id = baseline.get("extends")
        if parent_id is None:
            return baseline
        parent_id = self._safe_id(parent_id, "extends")
        parent = self._load_baseline(
            parent_id,
            seen=seen | {baseline_id},
        )
        parent_cases = parent.get("cases")
        if not isinstance(parent_cases, Mapping):
            raise BenchmarkLabError("Inherited baseline cases must be an object")
        return {
            **baseline,
            "cases": {**parent_cases, **own_cases},
        }

    def expected_projection(self, case_id: str) -> Mapping[str, Any]:
        cases = self.load_baseline().get("cases")
        if not isinstance(cases, Mapping) or not isinstance(cases.get(case_id), Mapping):
            raise BenchmarkLabError(f"Baseline has no projection for {case_id}")
        return cases[case_id]

    def compare(
        self, case_id: str, projection: Mapping[str, Any]
    ) -> BenchmarkComparison:
        differences: list[str] = []
        _compare_values(
            self.expected_projection(case_id),
            projection,
            path="$",
            differences=differences,
        )
        return BenchmarkComparison(not differences, tuple(differences))

    def archive_run(
        self,
        *,
        case: BenchmarkCase,
        mode: str,
        projection: Mapping[str, Any],
        comparison: BenchmarkComparison,
        model: str,
    ) -> Path:
        run_id = (
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-"
            f"{case.case_id}-{uuid4().hex[:8]}"
        )
        path = self._contained_path(f"runs/{run_id}.json", expected_parent="runs")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": BENCHMARK_RUN_SCHEMA,
            "run_id": run_id,
            "suite_id": self.suite_id,
            "case_id": case.case_id,
            "fixture_sha256": case.fixture_hash,
            "baseline_id": self.baseline_id,
            "mode": mode,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "matches_baseline": comparison.matches,
            "differences": list(comparison.differences),
            "projection": projection,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def _case_index(self) -> dict[str, Mapping[str, Any]]:
        raw = self._manifest.get("cases")
        if not isinstance(raw, list) or not raw:
            raise BenchmarkLabError("Benchmark manifest contains no cases")
        result: dict[str, Mapping[str, Any]] = {}
        for descriptor in raw:
            if not isinstance(descriptor, Mapping):
                raise BenchmarkLabError("Invalid benchmark case descriptor")
            case_id = self._safe_id(descriptor.get("case_id"), "case_id")
            if case_id in result:
                raise BenchmarkLabError(f"Duplicate benchmark case: {case_id}")
            result[case_id] = descriptor
        return result

    def _contained_path(self, relative: str, *, expected_parent: str) -> Path:
        candidate = (self.root / relative).resolve()
        expected = (self.root / expected_parent).resolve()
        if candidate == expected or expected not in candidate.parents:
            raise BenchmarkLabError(f"Path escapes {expected_parent}: {relative}")
        return candidate

    @staticmethod
    def _safe_id(value: Any, field: str) -> str:
        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
            raise BenchmarkLabError(f"Invalid {field}: {value!r}")
        return value

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BenchmarkLabError(f"Cannot read benchmark JSON: {path}") from exc
        if not isinstance(value, Mapping):
            raise BenchmarkLabError(f"Benchmark JSON must be an object: {path}")
        return value


def run_learning_benchmark(
    case: BenchmarkCase,
    adapter: Callable[..., Mapping[str, Any]],
    *,
    permissions: tuple[str, ...],
    max_tokens: int = 4_000,
) -> dict[str, Any]:
    """Execute one case through the real intake, validators, and Gatekeeper."""

    fixture = case.fixture
    candidates = _fixture_candidates(fixture)
    objective = _text(fixture, "objective")
    scopes = {_text(item, "scope") for item in candidates}
    if len(scopes) != 1:
        raise BenchmarkLabError("Benchmark candidates require one shared scope")
    scope = next(iter(scopes))
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)

    with TemporaryDirectory(prefix="fresta-diamond-benchmark-") as temporary:
        workspace = JsonlCognitiveWorkspace(temporary)
        workspace.save(SheetRevision(
            sheet_id=case.case_id,
            revision_number=1,
            title=f"Benchmark: {case.case_id}",
            state=SheetState.STAGED,
            elements=tuple(
                SheetElement(
                    element_id=_text(candidate, "element_id"),
                    kind=SheetElementKind(_text(candidate, "kind")),
                    content=_text(candidate, "content"),
                    scope=scope,
                    provenance=tuple(_text_list(candidate, "provenance")),
                )
                for candidate in candidates
            ),
        ))
        selection, artifact = workspace.select(
            case.case_id,
            tuple(_text(item, "element_id") for item in candidates),
            objective=objective,
        )
        request = build_workspace_learn_request(selection, artifact)
        intake = DiamondController(registry).execute(
            request.blueprint, request.objective, request.inputs
        )

    proposal = intake.execution.artifacts["learning_proposal"]
    manifest = llm_learning_manifest(permissions)
    registry.discover(manifest)
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise BenchmarkLabError("Benchmark learning provider was rejected")
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: LlmLearningStructuralOperation(
                max_tokens=max_tokens
            ),
            manifest.operations[1].operation_id: LlmLearningEpistemicOperation(),
            manifest.operations[2].operation_id: LlmLearningRepairOperation(
                max_tokens=max_tokens
            ),
        },
    )
    calls = 0

    def counted_adapter(grant: Any, **kwargs: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return adapter(grant, **kwargs)

    result = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": counted_adapter}),
    ).execute(
        learning_evaluation_blueprint(permissions),
        objective,
        {"learning_proposal": proposal},
    )
    batch = CrystallizationGate().evaluate(proposal, result)
    negative_boundary = PhiMinusDeriver().derive(batch, result)
    with TemporaryDirectory(prefix="fresta-diamond-memory-benchmark-") as memory_root:
        memory = AtomicDiamondLearningMemory(memory_root)
        stored_commit = memory.commit_batch(batch, result)
        committed_crystals = memory.crystals(
            policy=CrystalRetrievalPolicy.AUDIT
        )
        committed_boundary = memory.negative_boundary()
        memory_projection = {
            "commit_schema": "fresta://diamond-learning-commit@1",
            "committed": stored_commit.path.exists(),
            "crystals_committed": len(committed_crystals),
            "positive_crystals": sum(
                item.state.value in {"ACCEPTED", "PROVISIONAL"}
                for item in committed_crystals
            ),
            "indeterminate_crystals": sum(
                item.state.value == "DEFERRED"
                for item in committed_crystals
            ),
            "excluded_crystals": sum(
                item.state.value in {"QUARANTINED", "PHI_MINUS"}
                for item in committed_crystals
            ),
            "negative_observations": len(committed_boundary),
            "justified_phi_minus": sum(
                item.phi_minus_justified for item in committed_boundary
            ),
            "pending_commits": len(memory.pending()),
            "promotion_authority": stored_commit.commit.promotion_authority,
        }
        concept_projection = None
        concept_validation_projection = None
        concept_research_projection = None
        concept_integration_projection = None
        raw_concept = fixture.get("concept_proposal")
        if raw_concept is not None:
            if not isinstance(raw_concept, Mapping):
                raise BenchmarkLabError("concept_proposal must be an object")
            raw_signature = _mapping(raw_concept, "signature")
            signature_fields = (
                "characteristics",
                "relations",
                "functions",
                "constraints",
                "exclusions",
                "examples",
                "counterexamples",
            )
            signature = ConceptSignature(**{
                field_name: tuple(
                    _optional_text_list(raw_signature, field_name)
                )
                for field_name in signature_fields
            })
            concept_id = _text(raw_concept, "concept_id")
            concept = ConceptCandidateBuilder(
                memory,
                id_factory=lambda: concept_id,
            ).propose(
                canonical_name=_text(raw_concept, "canonical_name"),
                aliases=tuple(
                    _optional_text_list(raw_concept, "aliases")
                ),
                scope=scope,
                crystal_ids=tuple(
                    item.crystal_id for item in committed_crystals
                    if item.state.value in {"ACCEPTED", "PROVISIONAL"}
                ),
                signature=signature,
            )
            concept_store = AtomicConceptStore(
                Path(memory_root) / "concepts"
            )
            concept_store.save(concept)
            reloaded = concept_store.latest(concept.concept_id)
            concept_projection = {
                "concept_id": reloaded.concept_id,
                "version": reloaded.version,
                "state": reloaded.state.value,
                "membership_count": len(reloaded.memberships),
                "validation_refs": len(reloaded.validation_refs),
                "parent_link_count": len(reloaded.parent_links),
                "promotion_authority": reloaded.promotion_authority,
                "intrinsic_order_present": False,
            }
            raw_validation = fixture.get("concept_validation")
            if raw_validation is not None:
                if not isinstance(raw_validation, Mapping):
                    raise BenchmarkLabError(
                        "concept_validation must be an object"
                    )
                structural_graph = decode_structural_evidence_graph(
                    _mapping(raw_validation, "structural_graph")
                )
                epistemic_graph = decode_epistemic_evidence_graph(
                    _mapping(raw_validation, "epistemic_graph")
                )
                created_at = _text(raw_validation, "created_at")
                sources = tuple(
                    DerivationSource(
                        item.crystal_id,
                        DerivationSourceKind.MEMORY_CRYSTAL,
                    )
                    for item in committed_crystals
                    if item.state.value in {"ACCEPTED", "PROVISIONAL"}
                )
                seals = tuple(
                    DerivationSeal(
                        seal_id=f"seal:{case.case_id}:{index}",
                        target_ref=target,
                        contribution=(
                            DerivationContribution.DIRECT
                            if target.startswith("membership:")
                            else DerivationContribution.SYNTHESIS
                        ),
                        sources=sources,
                        analysis_id=structural_graph.analysis_id,
                        scope=scope,
                        created_at=created_at,
                    )
                    for index, target in enumerate(
                        concept_targets(reloaded), start=1
                    )
                )
                validation = ConceptValidationService(
                    memory,
                    concept_store,
                    validator=ConceptValidator(
                        memory,
                        id_factory=lambda: (
                            f"validation:{case.case_id}"
                        ),
                        clock=lambda: created_at,
                    ),
                    clock=lambda: created_at,
                ).validate_and_store(
                    concept.concept_id,
                    seals=seals,
                    structural_graph=structural_graph,
                    epistemic_graph=epistemic_graph,
                )
                concept_validation_projection = {
                    "validation_id": validation.report.validation_id,
                    "recommended_state": (
                        validation.report.recommended_state.value
                    ),
                    "local_fit": validation.report.local_fit.value,
                    "structural_state": (
                        validation.report.structural_state.value
                    ),
                    "recognition_state": (
                        validation.report.recognition_state.value
                    ),
                    "definition_state": (
                        validation.report.definition_state.value
                    ),
                    "remainder_kinds": sorted({
                        item.kind.value
                        for item in validation.report.active_remainders
                    }),
                    "result_version": validation.record.version,
                    "membership_states": sorted(
                        item.state.value
                        for item in validation.record.memberships
                    ),
                    "derivation_seals": len(
                        validation.record.derivation_seals
                    ),
                    "report_archived": validation.report_path.exists(),
                    "concept_version_archived": (
                        validation.concept_path is not None
                        and validation.concept_path.exists()
                    ),
                    "promotion_authority": (
                        validation.report.promotion_authority
                    ),
                }
                raw_research = fixture.get("concept_research")
                if raw_research is not None:
                    if not isinstance(raw_research, Mapping):
                        raise BenchmarkLabError(
                            "concept_research must be an object"
                        )
                    research_request = build_concept_research_request(
                        validation.record,
                        validation.report,
                        max_queries=_integer(
                            raw_research, "max_queries"
                        ),
                        max_results_per_query=_integer(
                            raw_research, "max_results_per_query"
                        ),
                        request_id=f"concept-research:{case.case_id}",
                    )
                    effect_calls = 0

                    def replay_search(
                        _grant: Any,
                        **_kwargs: Any,
                    ) -> Mapping[str, Any]:
                        nonlocal effect_calls
                        effect_calls += 1
                        results = raw_research.get("results")
                        if not isinstance(results, (list, tuple)):
                            raise BenchmarkLabError(
                                "concept research results must be an array"
                            )
                        return {"results": results}

                    register_concept_research_provider(registry)
                    research_result = DiamondController(
                        registry,
                        effect_broker=EffectBroker({
                            "internet.search": replay_search
                        }),
                    ).execute(
                        concept_research_blueprint(),
                        "Research the validated concept externally",
                        {
                            "research_request": research_request_artifact(
                                research_request
                            )
                        },
                    )
                    source_artifact = research_result.execution.artifacts[
                        "source_units"
                    ]
                    units = decode_source_units(source_artifact)
                    research_workspace = JsonlCognitiveWorkspace(
                        Path(memory_root) / "research-workspace"
                    )
                    research_sheet = stage_source_units(
                        research_workspace,
                        source_artifact,
                        sheet_id=f"{case.case_id}-research",
                        concept_ref=validation.record.version_ref,
                    )
                    research_selection, research_selection_artifact = (
                        research_workspace.select(
                            research_sheet.sheet_id,
                            tuple(
                                item.element_id
                                for item in research_sheet.elements
                            ),
                            objective=(
                                "Learn externally reported concept material"
                            ),
                        )
                    )
                    learn_handoff = build_workspace_learn_request(
                        research_selection,
                        research_selection_artifact,
                    )
                    concept_research_projection = {
                        "technical_completed": (
                            research_result.execution.closure.technical_completed
                        ),
                        "effect_calls": effect_calls,
                        "query_ids": [
                            item.query_id
                            for item in research_request.queries
                        ],
                        "neutral_query_first": (
                            not research_request.queries[
                                0
                            ].reveals_candidate_label
                        ),
                        "label_query_last": (
                            research_request.queries[
                                -1
                            ].reveals_candidate_label
                        ),
                        "source_units": len(units),
                        "source_types": sorted({
                            item.source_type for item in units
                        }),
                        "staged_elements": len(research_sheet.elements),
                        "selection_authority": (
                            research_selection.authority
                        ),
                        "learn_handoff_schema": (
                            learn_handoff.inputs["selection"].schema
                        ),
                        "required_next_step": source_artifact.payload[
                            "required_next_step"
                        ],
                        "promotion_authority": source_artifact.payload[
                            "promotion_authority"
                        ],
                    }
                    raw_integration = fixture.get("concept_integration")
                    if raw_integration is not None:
                        if not isinstance(raw_integration, Mapping):
                            raise BenchmarkLabError(
                                "concept_integration must be an object"
                            )
                        integration_created_at = _text(
                            raw_integration, "created_at"
                        )
                        source_locators = [
                            item.source_locator for item in units
                        ]
                        external_bundle = {
                            "structural_evidence": {
                                "analysis_id": (
                                    f"analysis:external:{case.case_id}"
                                ),
                                "object_ref": (
                                    "object:external-concept-sources"
                                ),
                                "scope": scope,
                                "analysis_depth": "CONTEXTUAL",
                                "manifestations": [{
                                    "manifestation_id": (
                                        "manifestation:external-sources"
                                    ),
                                    "object_ref": (
                                        "object:external-concept-sources"
                                    ),
                                    "description": (
                                        "Independent sources report a "
                                        "bounded recognized concept."
                                    ),
                                    "provenance": source_locators,
                                }],
                                "relations": [{
                                    "relation_id": (
                                        "relation:external-convergence"
                                    ),
                                    "manifestation_id": (
                                        "manifestation:external-sources"
                                    ),
                                    "constraint_id": (
                                        "constraint:source-comparison"
                                    ),
                                    "forward_justification": (
                                        "Independent reports preserve "
                                        "comparable functional relations."
                                    ),
                                    "constraint_effect": (
                                        "Only bounded comparable reports "
                                        "remain admissible."
                                    ),
                                    "return_witness": (
                                        "The sources still describe the "
                                        "selected concept."
                                    ),
                                    "excluded_cost_id": (
                                        "cost:definition-divergence"
                                    ),
                                    "scope": scope,
                                }],
                                "constraints": [{
                                    "constraint_id": (
                                        "constraint:source-comparison"
                                    ),
                                    "description": (
                                        "External reports preserve source "
                                        "and scope."
                                    ),
                                    "scope": scope,
                                }],
                                "filters": [{
                                    "filter_id": (
                                        "filter:external-reports"
                                    ),
                                    "constraint_id": (
                                        "constraint:source-comparison"
                                    ),
                                    "manifestation_id": (
                                        "manifestation:external-sources"
                                    ),
                                    "excluded_cost_id": (
                                        "cost:definition-divergence"
                                    ),
                                    "selection_justification": (
                                        "Selects mutually comparable "
                                        "external reports."
                                    ),
                                }],
                                "excluded_costs": [{
                                    "cost_id": (
                                        "cost:definition-divergence"
                                    ),
                                    "description": (
                                        "Loss of comparable conceptual "
                                        "content."
                                    ),
                                    "excluded_alternatives": [
                                        "unrelated uses of the same label"
                                    ],
                                }],
                                "groundings": [],
                                "advisory_model_closed": True,
                            },
                            "candidate_assessments": [{
                                "source_element_id": (
                                    f"source-unit:{item.source_unit_id}"
                                ),
                                "claim_mode": _text(
                                    raw_integration, "claim_mode"
                                ),
                                "premise_refs": [],
                                "applied_constraints": [],
                                "derivation_direction": None,
                                "test_criterion": None,
                                "horizon": None,
                                "assumptions": [],
                                "counterexample_searches": [],
                            } for item in units],
                        }
                        external_calls = 0

                        def external_replay(
                            _grant: Any,
                            **_kwargs: Any,
                        ) -> Mapping[str, Any]:
                            nonlocal external_calls
                            external_calls += 1
                            return {
                                "content": json.dumps(
                                    external_bundle,
                                    ensure_ascii=False,
                                ),
                                "model": "diamond-external-replay",
                                "usage": {"total_tokens": 0},
                            }

                        external_learning = ConceptSourceLearner(
                            external_replay,
                            required_permissions=permissions,
                            max_tokens=max_tokens,
                            sheet_id_factory=lambda: (
                                f"{case.case_id}-external-learning"
                            ),
                        ).learn(
                            concept=validation.record,
                            source_artifact=source_artifact,
                            workspace=JsonlCognitiveWorkspace(
                                Path(memory_root)
                                / "external-learning-workspace"
                            ),
                            memory=memory,
                        )
                        recognition = ConceptRecognitionService(
                            memory,
                            concept_store,
                            validator=ConceptRecognitionValidator(
                                memory,
                                id_factory=lambda: (
                                    f"recognition:{case.case_id}"
                                ),
                                clock=lambda: integration_created_at,
                            ),
                            clock=lambda: integration_created_at,
                        ).validate_and_store(
                            validation.record.concept_id,
                            prior_validation=validation.report,
                            source_artifact=source_artifact,
                            learning=external_learning,
                        )
                        external_crystals = (
                            external_learning.stored_commit.commit
                            .crystallization.crystals
                        )
                        external_seals = recognition.record.derivation_seals[
                            len(validation.record.derivation_seals):
                        ]
                        concept_integration_projection = {
                            "model_call_count": external_calls,
                            "external_commit": (
                                external_learning.stored_commit.path.exists()
                            ),
                            "external_crystals": len(external_crystals),
                            "external_states": sorted(
                                item.state.value
                                for item in external_crystals
                            ),
                            "recognition_state": (
                                recognition.report.recognition_state.value
                            ),
                            "external_definition_state": (
                                recognition.report
                                .external_definition_state.value
                            ),
                            "result_version": recognition.record.version,
                            "concept_state": (
                                recognition.record.state.value
                            ),
                            "concept_recognition_state": (
                                recognition.record.recognition_state.value
                            ),
                            "concept_definition_state": (
                                recognition.record.definition_state.value
                            ),
                            "web_seals": len(external_seals),
                            "source_locators": len(
                                recognition.report.source_locators
                            ),
                            "source_families": list(
                                recognition.report.source_families
                            ),
                            "source_types": list(
                                recognition.report.source_types
                            ),
                            "evidence_coverage_state": (
                                recognition.report
                                .evidence_coverage_state.value
                            ),
                            "research_stop_decision": (
                                recognition.report
                                .research_stop_decision.value
                            ),
                            "unmet_requirements": list(
                                recognition.report.unmet_requirements
                            ),
                            "report_archived": (
                                recognition.report_path.exists()
                            ),
                            "concept_version_archived": (
                                recognition.concept_path is not None
                                and recognition.concept_path.exists()
                            ),
                            "promotion_authority": (
                                recognition.report.promotion_authority
                            ),
                        }
    epistemic = result.execution.artifacts.get("epistemic_evidence")
    events = (
        epistemic.payload.get("evidence_events", ())
        if epistemic is not None else ()
    )
    actors = sorted({
        item.get("source_actor")
        for item in events
        if isinstance(item, Mapping) and isinstance(item.get("source_actor"), str)
    })
    locators = sorted({
        item.get("source_locator")
        for item in events
        if isinstance(item, Mapping) and isinstance(item.get("source_locator"), str)
    })
    document_input = any(item.startswith("document:") for item in locators)
    return {
        "technical_completed": result.execution.closure.technical_completed,
        "structural_closed": result.execution.closure.structural_closed,
        "constitutional_closed": result.execution.closure.constitutional_closed,
        "epistemic_closed": result.execution.closure.epistemic_closed,
        "remainder_kinds": sorted({
            item.kind.value for item in result.execution.remainders
        }),
        "crystals": [
            {
                "source_element_id": item.source_element_id,
                "state": item.state.value,
                "claim_mode": (
                    item.claim_mode.value if item.claim_mode is not None else None
                ),
                "reason_codes": list(item.reason_codes),
            }
            for item in batch.crystals
        ],
        "evidence_source_actors": actors,
        "evidence_source_locators": locators,
        "document_identity_boundary_preserved": (
            not document_input or "source:user" not in actors
        ),
        "negative_boundary": [
            {
                "source_element_id": item.source_element_id,
                "disposition": item.disposition.value,
                "phi_minus_justified": item.phi_minus_justified,
                "reason_codes": list(item.reason_codes),
                "remainder_kinds": list(item.remainder_kinds),
                "promotion_authority": item.promotion_authority,
            }
            for item in negative_boundary
        ],
        "learning_memory": memory_projection,
        **(
            {"concept_candidate": concept_projection}
            if concept_projection is not None else {}
        ),
        **(
            {"concept_validation": concept_validation_projection}
            if concept_validation_projection is not None else {}
        ),
        **(
            {"concept_research": concept_research_projection}
            if concept_research_projection is not None else {}
        ),
        **(
            {"concept_integration": concept_integration_projection}
            if concept_integration_projection is not None else {}
        ),
        "model_call_count": calls,
    }


def replay_adapter(case: BenchmarkCase) -> Callable[..., Mapping[str, Any]]:
    """Return the fixture bundle as an OpenAI-compatible deterministic response."""

    bundle = _mapping(case.fixture, "provider_bundle")

    def adapter(_grant: Any, **_kwargs: Any) -> Mapping[str, Any]:
        return {
            "content": json.dumps(bundle, ensure_ascii=False),
            "model": "diamond-replay",
            "usage": {"total_tokens": 0},
        }

    return adapter


def replay_permissions() -> tuple[str, ...]:
    return _REPLAY_PERMISSIONS


def _compare_values(
    expected: Any,
    actual: Any,
    *,
    path: str,
    differences: list[str],
) -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected:
                differences.append(f"{child}: unexpected")
            elif key not in actual:
                differences.append(f"{child}: missing")
            else:
                _compare_values(
                    expected[key], actual[key], path=child, differences=differences
                )
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if expected != actual:
            differences.append(f"{path}: expected {expected!r}, got {actual!r}")
        return
    if expected != actual:
        differences.append(f"{path}: expected {expected!r}, got {actual!r}")


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise BenchmarkLabError(f"{key} must be an object")
    return item


def _fixture_candidates(
    fixture: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    single = fixture.get("candidate")
    multiple = fixture.get("candidates")
    if isinstance(single, Mapping) and multiple is None:
        return (single,)
    if isinstance(multiple, list) and multiple and all(
        isinstance(item, Mapping) for item in multiple
    ):
        return tuple(multiple)
    raise BenchmarkLabError(
        "Fixture requires candidate or a non-empty candidates array"
    )


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise BenchmarkLabError(f"{key} must be non-empty text")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise BenchmarkLabError(f"{key} must be an integer")
    return item


def _text_list(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, list) or not item or any(
        not isinstance(entry, str) or not entry.strip() for entry in item
    ):
        raise BenchmarkLabError(f"{key} must be a non-empty text list")
    return tuple(item)


def _optional_text_list(
    value: Mapping[str, Any],
    key: str,
) -> tuple[str, ...]:
    item = value.get(key, [])
    if not isinstance(item, list) or any(
        not isinstance(entry, str) or not entry.strip() for entry in item
    ):
        raise BenchmarkLabError(f"{key} must be a text list")
    return tuple(item)
