from __future__ import annotations

from fresta_diamond.contracts import (
    Artifact,
    AuthorizationState,
    BlueprintSpec,
    CapabilityRequirement,
    ExecutionState,
    ModuleManifest,
    OperationContract,
    RemainderKind,
    PlanState,
)
from fresta_diamond.controller import DiamondController
from fresta_diamond.effects import EffectBroker
from fresta_diamond.engine import PlanValidator, Resolver, Runtime
from fresta_diamond.registry import ModuleRegistry


INPUT = "artifact://query@1"
OUTPUT = "artifact://source@1"


def system(
    handler,
    *,
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> tuple[ModuleRegistry, BlueprintSpec]:
    operation = OperationContract(
        operation_id="source.fetch",
        version="1.0.0",
        capabilities=("source.fetch@1",),
        inputs={"query": INPUT},
        outputs={"source": OUTPUT},
        effects=effects,
        permissions=permissions,
    )
    manifest = ModuleManifest(
        module_id="source-provider",
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
        blueprint_id="fetch-source",
        version=1,
        intent="Fetch one bounded source",
        requirement=CapabilityRequirement(
            "source.fetch@1", "query", INPUT, "source", OUTPUT
        ),
        allowed_effects=effects,
        granted_permissions=permissions,
    )
    return registry, blueprint


def query() -> dict[str, Artifact]:
    return {"query": Artifact(schema=INPUT, payload={"path": "/concept"})}


def test_declared_and_allowed_effect_still_requires_an_installed_adapter() -> None:
    called = False

    def handler(_inputs, _context):
        nonlocal called
        called = True
        return {"source": {"text": "should not run"}}

    registry, blueprint = system(
        handler,
        effects=("network.read",),
        permissions=("network.host:example.org",),
    )

    run = DiamondController(registry).execute(blueprint, "fetch", query())

    assert run.plan.state == PlanState.VALIDATED
    assert run.authorization.state == AuthorizationState.DENIED
    assert run.authorization.remainders[0].kind == RemainderKind.MISSING_CAPABILITY
    assert run.execution.state == ExecutionState.DENIED
    assert called is False


def test_handler_can_invoke_only_the_adapter_in_its_scoped_grant() -> None:
    observed = {}

    def network_adapter(grant, path):
        observed["grant"] = grant
        observed["path"] = path
        return {"text": "bounded response"}

    def handler(inputs, context):
        response = context.invoke("network.read", inputs["query"]["path"])
        return {"source": response}

    registry, blueprint = system(
        handler,
        effects=("network.read",),
        permissions=("network.host:example.org",),
    )
    broker = EffectBroker({"network.read": network_adapter})

    run = DiamondController(registry, effect_broker=broker).execute(
        blueprint, "fetch", query()
    )

    assert run.authorization.state == AuthorizationState.AUTHORIZED
    assert run.execution.state == ExecutionState.COMPLETED
    assert observed["path"] == "/concept"
    assert observed["grant"].permissions == ("network.host:example.org",)
    assert observed["grant"].plan_id == run.plan.plan_id
    assert run.execution.artifacts["source"].payload["text"] == "bounded response"


def test_handler_cannot_expand_an_effectless_grant_at_runtime() -> None:
    def handler(_inputs, context):
        context.invoke("filesystem.write", "secret")
        return {"source": {"text": "unreachable"}}

    registry, blueprint = system(handler)
    broker = EffectBroker({"filesystem.write": lambda *_: None})

    run = DiamondController(registry, effect_broker=broker).execute(
        blueprint, "fetch", query()
    )

    assert run.authorization.state == AuthorizationState.AUTHORIZED
    assert run.execution.state == ExecutionState.DENIED
    assert run.execution.remainders[0].kind == RemainderKind.PERMISSION_DENIED


def test_validated_plan_cannot_run_without_its_authorization() -> None:
    registry, blueprint = system(
        lambda *_: {"source": {"text": "unreachable"}}
    )
    proposed = Resolver().resolve(blueprint, "fetch", query(), registry)
    validated = PlanValidator().validate(proposed, blueprint, registry)

    result = Runtime().execute(validated, registry)

    assert validated.state == PlanState.VALIDATED
    assert result.state == ExecutionState.DENIED
    assert result.remainders[0].kind == RemainderKind.PERMISSION_DENIED


def test_non_permission_handler_exception_remains_a_failed_execution() -> None:
    def handler(_inputs, _context):
        raise ValueError("broken provider")

    registry, blueprint = system(handler)

    run = DiamondController(registry).execute(blueprint, "fetch", query())

    assert run.authorization.state == AuthorizationState.AUTHORIZED
    assert run.execution.state == ExecutionState.FAILED
    assert "broken provider" in run.execution.remainders[0].description
