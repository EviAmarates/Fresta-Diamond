from __future__ import annotations

from dataclasses import replace

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
from fresta_diamond.engine import PlanValidator, Resolver, Runtime
from fresta_diamond.registry import ModuleRegistry


RAW = "artifact://raw-text@1"
NORMALIZED = "artifact://normalized-text@1"
RELATIONS = "artifact://relations@1"
ANSWER = "artifact://answer@1"


def add_provider(
    registry: ModuleRegistry,
    module_id: str,
    contract: OperationContract,
    handler,
) -> None:
    registry.discover(ModuleManifest(
        module_id=module_id,
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(contract,),
    ))
    registry.verify(module_id)
    registry.enable(module_id, {contract.operation_id: handler})


def build_chain(registry: ModuleRegistry, calls: list[str]) -> BlueprintSpec:
    normalize = OperationContract(
        operation_id="normalizer.run",
        version="1.0.0",
        capabilities=("text.normalize@1",),
        inputs={"source": RAW},
        outputs={"normalized": NORMALIZED},
    )
    relate = OperationContract(
        operation_id="relater.run",
        version="1.0.0",
        capabilities=("relations.extract@1",),
        inputs={"normalized": NORMALIZED},
        outputs={"relations": RELATIONS},
    )
    synthesize = OperationContract(
        operation_id="synthesizer.run",
        version="1.0.0",
        capabilities=("answer.synthesize@1",),
        inputs={"relations": RELATIONS},
        outputs={"answer": ANSWER},
    )

    def normalize_handler(inputs, _context):
        calls.append("normalize")
        return {"normalized": {"text": inputs["source"]["text"].strip().lower()}}

    def relate_handler(inputs, _context):
        calls.append("relate")
        return {"relations": {"tokens": inputs["normalized"]["text"].split()}}

    def synthesize_handler(inputs, _context):
        calls.append("synthesize")
        return {"answer": {"text": "|".join(inputs["relations"]["tokens"])}}

    add_provider(registry, "normalizer", normalize, normalize_handler)
    add_provider(registry, "relater", relate, relate_handler)
    add_provider(registry, "synthesizer", synthesize, synthesize_handler)

    # Deliberately not dependency ordered: the resolver must derive the order.
    return BlueprintSpec(
        blueprint_id="three-stage-analysis",
        version=1,
        intent="Derive a typed answer through contextual O1/O2/O3 work",
        requirements=(
            CapabilityRequirement(
                "answer.synthesize@1", "relations", RELATIONS, "answer", ANSWER, (3,)
            ),
            CapabilityRequirement(
                "text.normalize@1", "source", RAW, "normalized", NORMALIZED, (1,)
            ),
            CapabilityRequirement(
                "relations.extract@1", "normalized", NORMALIZED, "relations", RELATIONS, (2,)
            ),
        ),
    )


def test_resolver_derives_and_runtime_executes_multi_node_dag() -> None:
    registry = ModuleRegistry()
    calls: list[str] = []
    specification = build_chain(registry, calls)
    source = Artifact(schema=RAW, payload={"text": "  HELLO DIAMOND  "})

    run = DiamondController(registry).execute(
        specification, "produce an answer", {"source": source}
    )

    assert run.plan.state == PlanState.VALIDATED
    assert [node.module_id for node in run.plan.nodes] == [
        "normalizer", "relater", "synthesizer"
    ]
    assert len(run.plan.edges) == 2
    assert calls == ["normalize", "relate", "synthesize"]
    assert run.execution.state == ExecutionState.COMPLETED
    assert run.execution.artifacts["answer"].payload["text"] == "hello|diamond"


def test_only_validator_may_turn_a_proposal_into_a_validated_plan() -> None:
    registry = ModuleRegistry()
    specification = build_chain(registry, [])
    source = Artifact(schema=RAW, payload={"text": "hello"})
    proposed = Resolver().resolve(
        specification, "produce an answer", {"source": source}, registry
    )

    assert proposed.state == PlanState.PROPOSED
    assert Runtime().execute(proposed, registry).state == ExecutionState.OPEN
    validated = PlanValidator().validate(proposed, specification, registry)
    assert validated.state == PlanState.VALIDATED


def test_validator_rejects_a_tampered_dependency_binding() -> None:
    registry = ModuleRegistry()
    specification = build_chain(registry, [])
    source = Artifact(schema=RAW, payload={"text": "hello"})
    proposed = Resolver().resolve(
        specification, "produce an answer", {"source": source}, registry
    )
    damaged_node = replace(
        proposed.nodes[1], input_bindings={"normalized": "missing-artifact"}
    )
    damaged = replace(proposed, nodes=(proposed.nodes[0], damaged_node, proposed.nodes[2]))

    rejected = PlanValidator().validate(damaged, specification, registry)

    assert rejected.state == PlanState.REJECTED
    assert any(item.kind == RemainderKind.MISSING_INPUT for item in rejected.remainders)
    assert any(item.kind == RemainderKind.CONTRADICTION for item in rejected.remainders)


def test_unresolvable_dependency_cycle_remains_explicitly_open() -> None:
    registry = ModuleRegistry()
    specification = BlueprintSpec(
        blueprint_id="unresolved-cycle",
        version=1,
        intent="A deliberately impossible dependency loop",
        requirements=(
            CapabilityRequirement("cap.a@1", "b", "artifact://b@1", "a", "artifact://a@1"),
            CapabilityRequirement("cap.b@1", "a", "artifact://a@1", "b", "artifact://b@1"),
        ),
    )

    run = DiamondController(registry).execute(specification, "resolve loop", {})

    assert run.plan.state == PlanState.REJECTED
    assert run.plan.nodes == ()
    assert sum(
        item.kind == RemainderKind.MISSING_INPUT for item in run.plan.remainders
    ) == 2
    assert any(
        item.kind == RemainderKind.MISSING_CAPABILITY for item in run.plan.remainders
    )
    assert run.execution.state == ExecutionState.OPEN
