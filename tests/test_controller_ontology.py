"""Controller integration for provider-produced ontological evidence artifacts."""

from dataclasses import replace

from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ExecutionState,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.ontology import (
    ANALYSIS_DIRECTION,
    GROUNDING_DIRECTION,
    STRUCTURAL_EVIDENCE_SCHEMA,
    AnalysisDepth,
    ConstitutionalGroundingEvidence,
    ConstraintEvidence,
    ExcludedCostEvidence,
    FilterEvidence,
    ManifestationEvidence,
    StrongRelationEvidence,
    StructuralEvidenceGraph,
    encode_structural_evidence_graph,
)
from fresta_diamond.registry import ModuleRegistry


OBJECT_SCHEMA = "artifact://bounded-object@1"


def graph(*, advisory: bool | None = None) -> StructuralEvidenceGraph:
    return StructuralEvidenceGraph(
        analysis_id="analysis-controller",
        object_ref="object:controller-test",
        scope="scope:controller-test",
        manifestations=(
            ManifestationEvidence(
                "o1-output",
                "object:controller-test",
                "A bounded output survives validation",
                ("artifact:input",),
            ),
        ),
        relations=(
            StrongRelationEvidence(
                "o2-contract",
                "o1-output",
                "o3-schema",
                "The output is compared with its declared contract",
                "Incompatible outputs are excluded",
                "The admitted output preserves the declared operation identity",
                "cost-incompatible",
                "scope:controller-test",
            ),
        ),
        constraints=(
            ConstraintEvidence(
                "o3-schema",
                "The output must satisfy the declared schema",
                "scope:controller-test",
            ),
        ),
        filters=(
            FilterEvidence(
                "filter-schema",
                "o3-schema",
                "o1-output",
                "cost-incompatible",
                "Schema validation selects the admitted output",
            ),
        ),
        excluded_costs=(
            ExcludedCostEvidence(
                "cost-incompatible",
                "Malformed alternatives are not admitted",
                ("artifact:malformed-output",),
            ),
        ),
        groundings=(
            ConstitutionalGroundingEvidence(
                "grounding-schema",
                "filter-schema",
                GROUNDING_DIRECTION,
                ANALYSIS_DIRECTION,
                "Filtering presupposes alternatives that are not totalized",
            ),
        ),
        advisory_model_closed=advisory,
    )


def controller_for(handler) -> tuple[DiamondController, BlueprintSpec]:
    operation = OperationContract(
        operation_id="analysis.propose-evidence",
        version="1.0.0",
        capabilities=("three-orders.propose-evidence@1",),
        inputs={"object": OBJECT_SCHEMA},
        outputs={"evidence": STRUCTURAL_EVIDENCE_SCHEMA},
    )
    manifest = ModuleManifest(
        module_id="evidence-provider",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )
    registry = ModuleRegistry()
    registry.discover(manifest)
    registry.verify(manifest.module_id)
    registry.enable(manifest.module_id, {operation.operation_id: handler})
    blueprint = BlueprintSpec(
        blueprint_id="propose-evidence",
        version=1,
        intent="Propose evidence for one bounded object",
        requirement=CapabilityRequirement(
            "three-orders.propose-evidence@1",
            "object",
            OBJECT_SCHEMA,
            "evidence",
            STRUCTURAL_EVIDENCE_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
    )
    return DiamondController(registry), blueprint


def input_artifact() -> dict[str, Artifact]:
    return {
        "object": Artifact(
            schema=OBJECT_SCHEMA,
            payload={"object_ref": "object:controller-test"},
        )
    }


def test_controller_attaches_valid_report_independent_of_model_checkbox() -> None:
    proposed = graph(advisory=False)
    controller, blueprint = controller_for(
        lambda *_: {"evidence": encode_structural_evidence_graph(proposed)}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    assert result.execution.state is ExecutionState.COMPLETED
    assert len(result.ontological_reports) == 1
    assert result.ontological_reports[0].structural_closed is True
    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.constitutional_closed is True


def test_model_true_cannot_hide_unused_selected_evidence() -> None:
    proposed = graph(advisory=True)
    unused = ManifestationEvidence(
        "o1-unused",
        proposed.object_ref,
        "Retrieved but absent from the justification",
        ("artifact:unused",),
    )
    proposed = replace(
        proposed,
        manifestations=proposed.manifestations + (unused,),
    )
    controller, blueprint = controller_for(
        lambda *_: {"evidence": encode_structural_evidence_graph(proposed)}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    assert len(result.ontological_reports) == 1
    assert result.ontological_reports[0].structural_closed is False
    assert result.execution.closure.structural_closed is False
    assert result.execution.closure.active_remainders


def test_malformed_provider_graph_is_visible_and_cannot_close() -> None:
    controller, blueprint = controller_for(
        lambda *_: {"evidence": {"analysis_id": "incomplete"}}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    assert result.execution.state is ExecutionState.COMPLETED
    assert result.ontological_reports == ()
    assert result.execution.closure.structural_closed is False
    assert result.execution.closure.constitutional_closed is False
    assert "Malformed structural evidence" in result.execution.remainders[0].description


def test_contextual_graph_closes_locally_without_evaluating_phi_or_f() -> None:
    proposed = replace(
        graph(),
        groundings=(),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
    )
    controller, blueprint = controller_for(
        lambda *_: {"evidence": encode_structural_evidence_graph(proposed)}
    )

    result = controller.execute(blueprint, "validate locally", input_artifact())

    assert result.execution.closure.structural_closed is True
    assert result.execution.closure.constitutional_closed is None
    assert result.ontological_reports[0].active_remainders == ()


def _risk_payload(proposed: StructuralEvidenceGraph) -> dict:
    payload = dict(encode_structural_evidence_graph(proposed))
    payload["_source_risk_attestation"] = {
        "input_digest": "a" * 64,
        "heuristic_ids": ["AE-H003"],
        "reason_codes": ["CONSTITUTIONAL_BYPASS_REQUEST"],
        "handling": "ATTRIBUTED_SOURCE_CLAIM_REQUIRED",
    }
    return payload


def test_risky_source_cannot_launder_instruction_into_closed_relation() -> None:
    proposed = replace(
        graph(),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
        groundings=(),
        manifestations=(ManifestationEvidence(
            "o1-output",
            "object:controller-test",
            "Bounded manifestation of document validation authority",
            ("artifact:input",),
        ),),
        relations=(StrongRelationEvidence(
            "o2-contract",
            "o1-output",
            "o3-schema",
            "Document authority overrides the kernel",
            "The request excludes kernel mediation",
            "Validated memory state",
            "cost-incompatible",
            "scope:controller-test",
        ),),
    )
    controller, blueprint = controller_for(
        lambda *_: {"evidence": _risk_payload(proposed)}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    report = result.ontological_reports[0]
    assert report.structural_closed is False
    assert result.execution.closure.structural_closed is False
    assert any(
        item.kind.value == "POLICY_VIOLATION"
        for item in report.active_remainders
    )


def test_risky_source_can_close_when_claim_stays_attributed_and_limited() -> None:
    proposed = replace(
        graph(),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
        groundings=(),
        manifestations=(ManifestationEvidence(
            "o1-output",
            "object:controller-test",
            "The source document claims authority to bypass validation",
            ("artifact:input",),
        ),),
        relations=(StrongRelationEvidence(
            "o2-contract",
            "o1-output",
            "o3-schema",
            "The source claim is compared with the host boundary",
            "Unsupported authority cannot promote unvalidated content",
            "The document supplies no corroboration for its authority claim",
            "cost-incompatible",
            "scope:controller-test",
        ),),
    )
    controller, blueprint = controller_for(
        lambda *_: {"evidence": _risk_payload(proposed)}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    assert result.ontological_reports[0].structural_closed is True
    assert result.execution.closure.structural_closed is True


def test_bypass_wording_is_not_mistaken_for_an_authority_limitation() -> None:
    proposed = replace(
        graph(),
        analysis_depth=AnalysisDepth.CONTEXTUAL,
        groundings=(),
        manifestations=(ManifestationEvidence(
            "o1-output",
            "object:controller-test",
            "The source document requests direct validated-memory promotion",
            ("artifact:input",),
        ),),
        relations=(StrongRelationEvidence(
            "o2-contract",
            "o1-output",
            "o3-schema",
            "The source claim is evaluated as supplied text",
            "Direct promotion proceeds without kernel validation",
            "The source declares itself authoritative",
            "cost-incompatible",
            "scope:controller-test",
        ),),
    )
    controller, blueprint = controller_for(
        lambda *_: {"evidence": _risk_payload(proposed)}
    )

    result = controller.execute(blueprint, "validate this object", input_artifact())

    assert result.execution.closure.structural_closed is False
    assert any(
        "lacks an explicit authority" in item.description
        for item in result.execution.remainders
    )
