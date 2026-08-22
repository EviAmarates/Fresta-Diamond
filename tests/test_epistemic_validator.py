"""Claim-mode burdens and the independent epistemic closure axis."""

from dataclasses import replace

from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
    RemainderKind,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.epistemology import (
    EPISTEMIC_EVIDENCE_SCHEMA,
    ClaimMode,
    EpistemicClaim,
    EpistemicEvidenceGraph,
    EpistemicValidator,
    EvidenceEvent,
    EvidenceKind,
    EvidenceStance,
    claim_mode_classification_catalog,
    decode_epistemic_evidence_graph,
    encode_epistemic_evidence_graph,
)
from fresta_diamond.registry import ModuleRegistry


SCOPE = "scope:epistemic-test"
OBJECT_SCHEMA = "artifact://bounded-object@1"


def test_kernel_classification_catalog_covers_modes_and_explicit_defer() -> None:
    catalog = claim_mode_classification_catalog(
        available_modes=(ClaimMode.ATTESTATION, ClaimMode.HYPOTHESIS),
    )
    by_id = {item["classification_id"]: item for item in catalog}

    assert set(ClaimMode).issubset({ClaimMode(item) for item in by_id if item != "DEFER"})
    assert by_id["ATTESTATION"]["available_in_this_intake"] is True
    assert by_id["OBSERVATION"]["available_in_this_intake"] is False
    assert by_id["DEFER"]["kernel_mode"] is None
    assert all(item["meaning"] for item in catalog)


def evidence(
    evidence_id: str,
    claim_id: str,
    *,
    kind: EvidenceKind,
    stance: EvidenceStance = EvidenceStance.SUPPORTS,
    lineage: str = "lineage:source-a",
) -> EvidenceEvent:
    return EvidenceEvent(
        evidence_id=evidence_id,
        claim_id=claim_id,
        evidence_kind=kind,
        stance=stance,
        source_actor="actor:source-author",
        source_locator=f"source:{evidence_id}",
        source_lineage=lineage,
        context_id="context:test",
        method="bounded fixture",
        observed_at="2026-07-25T00:00:00Z",
        scope=SCOPE,
    )


def graph(
    claim: EpistemicClaim,
    *events: EvidenceEvent,
) -> EpistemicEvidenceGraph:
    return EpistemicEvidenceGraph(
        analysis_id="analysis:epistemic-test",
        object_ref="object:test",
        scope=SCOPE,
        claims=(claim,),
        evidence_events=events,
    )


def claim(
    mode: ClaimMode,
    *evidence_ids: str,
    **overrides,
) -> EpistemicClaim:
    values = {
        "claim_id": "claim:test",
        "content": "A source makes one bounded claim",
        "subject_ref": "subject:test",
        "owner_ref": "owner:source-document",
        "scope": SCOPE,
        "claim_mode": mode,
        "evidence_ids": evidence_ids,
    }
    values.update(overrides)
    return EpistemicClaim(**values)


def test_attestation_preserves_source_and_subject_without_becoming_observation() -> None:
    item = claim(ClaimMode.ATTESTATION, "e1")
    event = evidence("e1", item.claim_id, kind=EvidenceKind.ATTESTATION)

    attestation = EpistemicValidator().validate(graph(item, event))
    observation = EpistemicValidator().validate(
        graph(replace(item, claim_mode=ClaimMode.OBSERVATION), event)
    )

    assert attestation.epistemic_closed is True
    assert observation.epistemic_closed is False
    assert any(
        "direct observation" in remainder.description
        for remainder in observation.active_remainders
    )


def test_derivation_requires_premises_constraints_and_direction() -> None:
    item = claim(ClaimMode.DERIVATION, "e1")
    event = evidence("e1", item.claim_id, kind=EvidenceKind.PREMISE)

    report = EpistemicValidator().validate(graph(item, event))

    assert report.epistemic_closed is False
    descriptions = {item.description for item in report.active_remainders}
    assert any("premise references" in item for item in descriptions)
    assert any("applied constraints" in item for item in descriptions)
    assert any("auditable direction" in item for item in descriptions)

    completed = replace(
        item,
        premise_refs=("card:premise",),
        applied_constraints=("constraint:bounded",),
        derivation_direction="premise -> relation -> claim",
    )
    assert EpistemicValidator().validate(graph(completed, event)).epistemic_closed


def test_hypothesis_requires_a_bounded_test_but_not_confirmation_language() -> None:
    item = claim(ClaimMode.HYPOTHESIS, "e1")
    event = evidence("e1", item.claim_id, kind=EvidenceKind.ATTESTATION)

    open_report = EpistemicValidator().validate(graph(item, event))
    closed_report = EpistemicValidator().validate(
        graph(replace(item, test_criterion="A later observation can refute it"), event)
    )

    assert open_report.epistemic_closed is False
    assert closed_report.epistemic_closed is True
    assert closed_report.claim_reports[0].claim_mode is ClaimMode.HYPOTHESIS


def test_invariant_counts_independent_lineages_not_repeated_copies() -> None:
    item = claim(
        ClaimMode.INVARIANT,
        "e1",
        "e2",
        counterexample_searches=("search:bounded-adversarial",),
    )
    copied = (
        evidence("e1", item.claim_id, kind=EvidenceKind.TEST_RESULT),
        evidence("e2", item.claim_id, kind=EvidenceKind.TEST_RESULT),
    )
    independent = (
        copied[0],
        replace(copied[1], source_lineage="lineage:source-b"),
    )

    copied_report = EpistemicValidator().validate(graph(item, *copied))
    independent_report = EpistemicValidator().validate(graph(item, *independent))

    assert copied_report.epistemic_closed is False
    assert independent_report.epistemic_closed is True


def test_live_counterevidence_prevents_epistemic_closure() -> None:
    item = claim(ClaimMode.ATTESTATION, "support", "counter")
    support = evidence(
        "support", item.claim_id, kind=EvidenceKind.ATTESTATION
    )
    counter = evidence(
        "counter",
        item.claim_id,
        kind=EvidenceKind.TEST_RESULT,
        stance=EvidenceStance.CONTRADICTS,
    )

    report = EpistemicValidator().validate(graph(item, support, counter))

    assert report.epistemic_closed is False
    assert any(
        item.kind is RemainderKind.CONTRADICTION
        for item in report.active_remainders
    )


def test_epistemic_codec_round_trip_preserves_mode_and_lineage() -> None:
    item = claim(ClaimMode.FORECAST, "e1", horizon="2027", assumptions=("A",))
    event = evidence("e1", item.claim_id, kind=EvidenceKind.ATTESTATION)
    original = graph(item, event)

    decoded = decode_epistemic_evidence_graph(
        encode_epistemic_evidence_graph(original)
    )

    assert decoded == original
    assert decoded.evidence_events[0].source_lineage == "lineage:source-a"


def test_controller_calculates_epistemic_axis_without_claiming_structure() -> None:
    item = claim(ClaimMode.ATTESTATION, "e1")
    proposed = graph(
        item,
        evidence("e1", item.claim_id, kind=EvidenceKind.ATTESTATION),
    )
    operation = OperationContract(
        operation_id="claims.propose-evidence",
        version="1.0.0",
        capabilities=("claims.propose-evidence@1",),
        inputs={"object": OBJECT_SCHEMA},
        outputs={"evidence": EPISTEMIC_EVIDENCE_SCHEMA},
    )
    manifest = ModuleManifest(
        module_id="epistemic-provider",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )
    registry = ModuleRegistry()
    registry.discover(manifest)
    registry.verify(manifest.module_id)
    registry.enable(
        manifest.module_id,
        {operation.operation_id: lambda *_: {
            "evidence": encode_epistemic_evidence_graph(proposed)
        }},
    )
    blueprint = BlueprintSpec(
        blueprint_id="epistemic-evidence",
        version=1,
        intent="Evaluate the burden of one bounded claim",
        requirement=CapabilityRequirement(
            "claims.propose-evidence@1",
            "object",
            OBJECT_SCHEMA,
            "evidence",
            EPISTEMIC_EVIDENCE_SCHEMA,
        ),
    )

    result = DiamondController(registry).execute(
        blueprint,
        "evaluate a source report",
        {"object": Artifact(OBJECT_SCHEMA, {"object_ref": "object:test"})},
    )

    assert result.execution.closure.epistemic_closed is True
    assert result.execution.closure.structural_closed is None
    assert len(result.epistemic_reports) == 1


def test_malformed_epistemic_artifact_cannot_close() -> None:
    operation = OperationContract(
        operation_id="claims.malformed",
        version="1.0.0",
        capabilities=("claims.malformed@1",),
        inputs={"object": OBJECT_SCHEMA},
        outputs={"evidence": EPISTEMIC_EVIDENCE_SCHEMA},
    )
    manifest = ModuleManifest(
        "malformed-provider",
        "1.0.0",
        ">=3.0,<4.0",
        ">=1.0,<2.0",
        (operation,),
    )
    registry = ModuleRegistry()
    registry.discover(manifest)
    registry.verify(manifest.module_id)
    registry.enable(
        manifest.module_id,
        {operation.operation_id: lambda *_: {
            "evidence": {"analysis_id": "incomplete"}
        }},
    )
    blueprint = BlueprintSpec(
        "malformed-epistemic",
        1,
        "Reject malformed evidence",
        requirement=CapabilityRequirement(
            "claims.malformed@1",
            "object",
            OBJECT_SCHEMA,
            "evidence",
            EPISTEMIC_EVIDENCE_SCHEMA,
        ),
    )

    result = DiamondController(registry).execute(
        blueprint,
        "reject malformed evidence",
        {"object": Artifact(OBJECT_SCHEMA, {"object_ref": "object:test"})},
    )

    assert result.execution.closure.epistemic_closed is False
    assert result.epistemic_reports == ()
    assert any(
        "Malformed epistemic evidence" in item.description
        for item in result.execution.remainders
    )
