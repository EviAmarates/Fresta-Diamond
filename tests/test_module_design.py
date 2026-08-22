from __future__ import annotations

import json

import pytest

from fresta_diamond.application import DiamondApplication
from fresta_diamond.contracts import (
    ModuleManifest,
    OperationContract,
    Remainder,
    RemainderKind,
)
from fresta_diamond.learning import LEARN_PREPARE_CAPABILITY
from fresta_diamond.module_design import (
    MODULE_LAYER,
    MODULE_SUGGESTION_AUTHORITY,
    AtomicModuleSuggestionArchive,
    ModuleSuggestionArchiveError,
    ModuleSuggestionDecision,
    build_module_suggestion_request,
    deterministic_existing_provider_suggestion,
)

from .test_application import PERMISSIONS


def missing(capability: str) -> Remainder:
    return Remainder(
        kind=RemainderKind.MISSING_CAPABILITY,
        description="No compatible provider completed the bounded objective.",
        required_for="objective:test-module-gap",
        resolvable=True,
        suggested_capability=capability,
    )


def manifest(capability: str, output_schema: str) -> ModuleManifest:
    return ModuleManifest(
        module_id="existing.module",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="existing.operation",
            version="1.0.0",
            capabilities=(capability,),
            inputs={"source": "artifact://source@1"},
            outputs={"result": output_schema},
        ),),
    )


def proposal_response(*, effects=(), permissions=()) -> dict:
    return {
        "decision": "PROPOSE_MODULE",
        "rationale": "No existing composition produces the bounded output.",
        "o1_required_outcomes": ["Produce one bounded transformed artifact."],
        "o2_composition_analysis": [
            "Existing providers expose no compatible capability or output."
        ],
        "o2_dependencies": ["artifact://source@1"],
        "o3_constraints": [
            "Remain below the controller and never write promoted memory."
        ],
        "o3_completion_conditions": [
            "One output passes its declared schema without hidden effects."
        ],
        "module_id": "generated.bounded-transform",
        "operation_id": "bounded-transform.execute",
        "effects": list(effects),
        "permissions": list(permissions),
        "failure_modes": ["INVALID_SOURCE", "OUTPUT_SCHEMA_FAILURE"],
        "determinism": "DETERMINISTIC",
    }


def test_exact_provider_refuses_duplicate_without_model_call(tmp_path) -> None:
    called = []
    app = DiamondApplication(
        tmp_path,
        lambda *_args, **_kwargs: called.append(True),
        required_permissions=PERMISSIONS,
    )

    outcome = app.suggest_module(
        objective="Prepare an existing learning proposal.",
        required_capability=LEARN_PREPARE_CAPABILITY,
        output_schema="artifact://learning-proposal@1",
    )

    assert called == []
    assert outcome.model_call_count == 0
    assert outcome.deterministic_reuse is True
    assert outcome.suggestion is not None
    assert outcome.suggestion.decision is ModuleSuggestionDecision.NO_NEW_MODULE
    assert outcome.suggestion.exact_provider_refs
    assert outcome.stored is not None
    assert outcome.stored.path.exists()


def test_request_maps_exact_and_schema_reuse_candidates() -> None:
    exact_capability = "example.transform@1"
    request = build_module_suggestion_request(
        (
            manifest(exact_capability, "artifact://different@1"),
            ModuleManifest(
                module_id="reuse.module",
                version="1.0.0",
                kernel_contract=">=3.0,<4.0",
                sdk_contract=">=1.0,<2.0",
                operations=(OperationContract(
                    operation_id="reuse.operation",
                    version="1.0.0",
                    capabilities=("other.capability@1",),
                    inputs={},
                    outputs={"result": "artifact://target@1"},
                ),),
            ),
        ),
        objective="Transform a bounded source.",
        required_capability=exact_capability,
        input_schemas={"source": "artifact://source@1"},
        output_schema="artifact://target@1",
        remainders=(missing(exact_capability),),
    )

    assert request.payload["exact_provider_refs"] == (
        "existing.module:existing.operation",
    )
    assert request.payload["reuse_candidate_refs"] == (
        "reuse.module:reuse.operation",
    )
    assert deterministic_existing_provider_suggestion(request) is not None


def test_llm_design_is_anchored_prechecked_and_never_enabled(tmp_path) -> None:
    calls = []

    def adapter(_grant, **kwargs):
        calls.append(kwargs)
        payload = proposal_response()
        payload["required_capability"] = "kernel.replace"
        payload["layer"] = "ABOVE_CONTROLLER"
        return {"content": json.dumps(payload), "model": "module-replay"}

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
        max_response_tokens=1_500,
    )
    outcome = app.suggest_module(
        objective="Transform one isolated source into a bounded report.",
        required_capability="report.transform-bounded@1",
        input_schemas={"source": "artifact://source@1"},
        output_schema="artifact://bounded-report@1",
        remainders=(missing("report.transform-bounded@1"),),
        occurrence_count=3,
    )

    assert len(calls) == 1
    suggestion = outcome.suggestion
    assert suggestion is not None
    assert suggestion.decision is ModuleSuggestionDecision.PROPOSE_MODULE
    assert suggestion.required_capability == "report.transform-bounded@1"
    assert suggestion.layer == MODULE_LAYER
    assert suggestion.authority == MODULE_SUGGESTION_AUTHORITY
    assert suggestion.admission_precheck_passed is True
    assert suggestion.operation is not None
    assert suggestion.operation.capability == "report.transform-bounded@1"
    assert suggestion.operation.outputs == {
        "result": "artifact://bounded-report@1"
    }
    assert not list(tmp_path.rglob("*.py"))
    assert app.module_suggestions()[0].suggestion == suggestion


def test_narrative_order_fields_accept_single_string_equivalence(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        payload = proposal_response()
        payload["o2_composition_analysis"] = "No compatible composition exists."
        payload["o3_constraints"] = "Remain below the controller."
        return {"content": json.dumps(payload), "model": "module-replay"}

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Transform one bounded source.",
        required_capability="bounded.transform@1",
        output_schema="artifact://bounded@1",
        remainders=(missing("bounded.transform@1"),),
    )

    assert outcome.suggestion is not None
    assert outcome.suggestion.o2_composition_analysis == (
        "No compatible composition exists.",
    )
    assert outcome.suggestion.o3_constraints == (
        "Remain below the controller.",
    )


def test_missing_rationale_is_derived_from_composition_analysis(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        payload = proposal_response()
        payload.pop("rationale")
        return {"content": json.dumps(payload), "model": "module-replay"}

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Transform one bounded source.",
        required_capability="bounded.transform@1",
        output_schema="artifact://bounded@1",
        remainders=(missing("bounded.transform@1"),),
    )

    assert outcome.suggestion is not None
    assert outcome.suggestion.rationale == (
        outcome.suggestion.o2_composition_analysis[0]
    )


def test_explicit_none_permissions_normalize_to_empty_without_widening(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        payload = proposal_response()
        payload["effects"] = "none"
        payload["permissions"] = "no permissions"
        payload["failure_modes"] = "Invalid bounded input"
        return {"content": json.dumps(payload), "model": "module-replay"}

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Transform one bounded source.",
        required_capability="bounded.transform@1",
        output_schema="artifact://bounded@1",
        remainders=(missing("bounded.transform@1"),),
    )

    operation = outcome.suggestion.operation
    assert operation is not None
    assert operation.effects == ()
    assert operation.permissions == ()
    assert operation.failure_modes == ("Invalid bounded input",)


def test_arbitrary_text_permission_is_not_normalized(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        payload = proposal_response()
        payload["permissions"] = "controller.replace"
        return {"content": json.dumps(payload), "model": "module-replay"}

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Attempt a textual permission escape.",
        required_capability="bounded.transform@1",
        output_schema="artifact://bounded@1",
        remainders=(missing("bounded.transform@1"),),
    )

    assert outcome.suggestion is None
    assert outcome.result is not None
    assert outcome.result.execution.remainders


def test_forbidden_below_controller_escape_is_archived_as_rejected(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(proposal_response(
                effects=("controller.replace",),
                permissions=("controller.replace",),
            )),
            "model": "module-replay",
        }

    app = DiamondApplication(
        tmp_path,
        adapter,
        required_permissions=PERMISSIONS,
    )
    outcome = app.suggest_module(
        objective="Propose an unsafe controller replacement.",
        required_capability="unsafe.control@1",
        output_schema="artifact://unsafe@1",
        remainders=(missing("unsafe.control@1"),),
    )

    suggestion = outcome.suggestion
    assert suggestion is not None
    assert suggestion.decision is ModuleSuggestionDecision.REJECTED_PROPOSAL
    assert suggestion.admission_precheck_passed is False
    assert suggestion.policy_remainders
    assert any(
        "controller.replace" in item.description
        for item in suggestion.policy_remainders
    )
    assert outcome.stored is not None


def test_design_cannot_invent_effects_or_permissions_outside_host_boundary(
    tmp_path,
) -> None:
    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(proposal_response(
                effects=("llm.generate",),
                permissions=("artifact.write:module-output",),
            )),
            "model": "module-replay",
        }

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Propose a bounded document transformer.",
        required_capability="document.transform-bounded@1",
        output_schema="artifact://bounded-document@1",
        remainders=(missing("document.transform-bounded@1"),),
        # The default host boundary grants neither effects nor permissions.
    )

    suggestion = outcome.suggestion
    assert suggestion is not None
    assert suggestion.decision is ModuleSuggestionDecision.REJECTED_PROPOSAL
    assert suggestion.allowed_effects == ()
    assert suggestion.allowed_permissions == ()
    assert suggestion.admission_precheck_passed is False
    assert {item.kind for item in suggestion.policy_remainders} == {
        RemainderKind.PERMISSION_DENIED
    }
    assert any("llm.generate" in item.description for item in suggestion.policy_remainders)
    assert any(
        "artifact.write:module-output" in item.description
        for item in suggestion.policy_remainders
    )


def test_host_may_explicitly_bound_safe_design_effects_and_permissions(tmp_path) -> None:
    def adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(proposal_response(
                effects=("llm.generate",),
                permissions=("llm.model:qwen",),
            )),
            "model": "module-replay",
        }

    app = DiamondApplication(tmp_path, adapter, required_permissions=PERMISSIONS)
    outcome = app.suggest_module(
        objective="Propose a bounded document transformer.",
        required_capability="document.transform-bounded@1",
        output_schema="artifact://bounded-document@1",
        remainders=(missing("document.transform-bounded@1"),),
        allowed_effects=("llm.generate",),
        allowed_permissions=("llm.model:qwen",),
    )

    suggestion = outcome.suggestion
    assert suggestion is not None
    assert suggestion.decision is ModuleSuggestionDecision.PROPOSE_MODULE
    assert suggestion.admission_precheck_passed is True
    assert suggestion.allowed_effects == ("llm.generate",)
    assert suggestion.allowed_permissions == ("llm.model:qwen",)


def test_archive_detects_tampering(tmp_path) -> None:
    archive = AtomicModuleSuggestionArchive(tmp_path)
    request = build_module_suggestion_request(
        (manifest("existing@1", "artifact://result@1"),),
        objective="Reuse an exact provider.",
        required_capability="existing@1",
        input_schemas={},
        output_schema="artifact://result@1",
        remainders=(missing("existing@1"),),
    )
    suggestion = deterministic_existing_provider_suggestion(
        request,
        suggestion_id="module-suggestion:tamper-test",
    )
    assert suggestion is not None
    stored = archive.save(suggestion)
    stored.path.write_text(
        stored.path.read_text(encoding="utf-8").replace(
            "Reuse an exact provider.",
            "Rewritten objective.",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModuleSuggestionArchiveError, match="hash mismatch"):
        archive.load(suggestion.suggestion_id)
