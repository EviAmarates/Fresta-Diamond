from __future__ import annotations

import pytest

from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ExecutionState,
    ModuleManifest,
    OperationContract,
    RemainderKind,
    PlanState,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.registry import ModuleRegistry


CAPABILITY = "text.normalize@1"
TEXT_SCHEMA = "artifact://text@1"


def operation(
    operation_id: str, *, input_schema: str = TEXT_SCHEMA,
    effects: tuple[str, ...] = (), permissions: tuple[str, ...] = (),
) -> OperationContract:
    return OperationContract(
        operation_id=operation_id, version="1.0.0",
        capabilities=(CAPABILITY,),
        inputs={"source": input_schema}, outputs={"result": TEXT_SCHEMA},
        effects=effects, permissions=permissions,
    )


def manifest(module_id: str, contract: OperationContract) -> ModuleManifest:
    return ModuleManifest(
        module_id=module_id, version="1.0.0",
        kernel_contract=">=3.0,<4.0", sdk_contract=">=1.0,<2.0",
        operations=(contract,),
    )


def blueprint(**overrides) -> BlueprintSpec:
    values = {
        "blueprint_id": "normalize_text",
        "version": 1,
        "intent": "Normalize bounded text",
        "requirement": CapabilityRequirement(
            capability=CAPABILITY,
            input_name="source", input_schema=TEXT_SCHEMA,
            output_name="result", output_schema=TEXT_SCHEMA,
        ),
        "allowed_effects": (), "granted_permissions": (),
    }
    values.update(overrides)
    return BlueprintSpec(**values)


def enable_provider(registry: ModuleRegistry, module_id: str, marker: str) -> None:
    contract = operation(f"{module_id}.normalize")
    registry.discover(manifest(module_id, contract))
    registry.verify(module_id)

    def handler(inputs, context):
        assert not hasattr(context, "memory")
        return {"result": {"text": inputs["source"]["text"].strip().lower(), "provider": marker}}

    registry.enable(module_id, {contract.operation_id: handler})


def test_equivalent_provider_can_be_substituted_without_blueprint_or_controller_changes() -> None:
    registry = ModuleRegistry()
    controller = DiamondController(registry)
    specification = blueprint()
    source = Artifact(schema=TEXT_SCHEMA, payload={"text": "  HELLO  "})
    enable_provider(registry, "provider-a", "A")

    run_a = controller.execute(specification, "normalize this text", {"source": source})
    registry.disable("provider-a")
    enable_provider(registry, "provider-b", "B")
    run_b = controller.execute(specification, "normalize this text", {"source": source})

    assert run_a.plan.state == run_b.plan.state == PlanState.VALIDATED
    assert run_a.plan.nodes[0].module_id == "provider-a"
    assert run_b.plan.nodes[0].module_id == "provider-b"
    assert run_a.execution.artifacts["result"].payload == {"text": "hello", "provider": "A"}
    assert run_b.execution.artifacts["result"].payload == {"text": "hello", "provider": "B"}
    assert run_a.execution.state == run_b.execution.state == ExecutionState.COMPLETED
    assert run_b.execution.closure.structural_closed is None


def test_unverified_module_cannot_load_executable_code() -> None:
    registry = ModuleRegistry()
    contract = operation("unsafe.normalize")
    registry.discover(manifest("unsafe", contract))

    with pytest.raises(PermissionError):
        registry.enable("unsafe", {contract.operation_id: lambda *_: {}})


def test_schema_incompatible_provider_yields_explicit_remainder() -> None:
    registry = ModuleRegistry()
    contract = operation("binary.normalize", input_schema="artifact://binary@1")
    registry.discover(manifest("binary", contract))
    registry.verify("binary")
    registry.enable("binary", {contract.operation_id: lambda *_: {"result": {}}})
    source = Artifact(schema=TEXT_SCHEMA, payload={"text": "hello"})

    run = DiamondController(registry).execute(
        blueprint(), "normalize", {"source": source}
    )
    plan = run.plan

    assert plan.state == PlanState.REJECTED
    assert plan.remainders[0].kind == RemainderKind.MISSING_CAPABILITY
    assert "schema-incompatible" in plan.remainders[0].description


def test_unauthorized_effect_yields_permission_remainder() -> None:
    registry = ModuleRegistry()
    contract = operation(
        "network.normalize", effects=("network.read",),
        permissions=("network.host:example.org",),
    )
    registry.discover(manifest("network", contract))
    registry.verify("network")
    registry.enable("network", {contract.operation_id: lambda *_: {"result": {}}})
    source = Artifact(schema=TEXT_SCHEMA, payload={"text": "hello"})

    run = DiamondController(registry).execute(
        blueprint(), "normalize", {"source": source}
    )
    plan = run.plan

    assert plan.state == PlanState.REJECTED
    assert plan.remainders[0].kind == RemainderKind.PERMISSION_DENIED


def test_missing_provider_stays_open_without_magic_fallback() -> None:
    registry = ModuleRegistry()
    source = Artifact(schema=TEXT_SCHEMA, payload={"text": "hello"})

    run = DiamondController(registry).execute(
        blueprint(), "normalize", {"source": source}
    )
    plan, result = run.plan, run.execution

    assert plan.state == PlanState.REJECTED
    assert plan.remainders[0].kind == RemainderKind.MISSING_CAPABILITY
    assert result.state == ExecutionState.OPEN
    assert result.closure.operational_converged is False


def test_artifact_payload_is_immutable_at_the_contract_boundary() -> None:
    artifact = Artifact(schema=TEXT_SCHEMA, payload={"text": "hello"})

    with pytest.raises(TypeError):
        artifact.payload["text"] = "changed"
