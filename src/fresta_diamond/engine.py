"""Deterministic DAG resolver, validator, and runtime for Fresta Diamond."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping
from uuid import uuid4

from fresta_diamond.contracts import (
    Artifact,
    AuthorizationResult,
    AuthorizationState,
    BlueprintSpec,
    ClosureReport,
    ExecutionPlan,
    ExecutionResult,
    ExecutionState,
    Remainder,
    RemainderKind,
    PlanEdge,
    PlanNode,
    PlanState,
)
from fresta_diamond.effects import EffectBroker
from fresta_diamond.journal import EventJournal, JournalEventKind
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.workspace import ExecutionBudget, RuntimeCheckpoint


def _remainder(
    kind: RemainderKind,
    description: str,
    required_for: str,
    *,
    suggested: str | None = None,
) -> Remainder:
    return Remainder(
        kind=kind,
        description=description,
        required_for=required_for,
        resolvable=True,
        suggested_capability=suggested,
    )


class Resolver:
    """Nominate providers and derive a bounded dependency DAG.

    Resolution is deliberately not validation. Requirements may be declared in
    any order; a node becomes derivable only when its named, typed input exists.
    """

    def resolve(
        self,
        blueprint: BlueprintSpec,
        objective: str,
        external_artifacts: Mapping[str, Artifact],
        registry: ModuleRegistry,
    ) -> ExecutionPlan:
        available: dict[str, tuple[str, str, str | None, str | None]] = {
            name: (artifact.artifact_id, artifact.schema, None, None)
            for name, artifact in external_artifacts.items()
        }
        pending = list(blueprint.requirements)
        nodes: list[PlanNode] = []
        edges: list[PlanEdge] = []
        remainders: list[Remainder] = []

        while pending:
            progressed = False
            for requirement in tuple(pending):
                source = available.get(requirement.input_name)
                if source is None or source[1] != requirement.input_schema:
                    continue
                selection, failure = self._select_provider(blueprint, requirement, registry)
                if selection is None:
                    remainders.append(failure)
                    pending.remove(requirement)
                    progressed = True
                    continue

                module_id, operation = selection
                node_id = str(uuid4())
                artifact_ref = f"plan:{node_id}:{requirement.output_name}"
                node = PlanNode(
                    node_id=node_id,
                    module_id=module_id,
                    operation_id=operation.operation_id,
                    operation_version=operation.version,
                    input_bindings={requirement.input_name: source[0]},
                    output_schemas=operation.outputs,
                    output_bindings={requirement.output_name: artifact_ref},
                    contextual_roles=requirement.contextual_roles,
                )
                nodes.append(node)
                if source[2] is not None:
                    edges.append(PlanEdge(
                        producer_node_id=source[2],
                        producer_output=source[3] or requirement.input_name,
                        consumer_node_id=node_id,
                        consumer_input=requirement.input_name,
                        artifact_ref=source[0],
                        schema=source[1],
                    ))
                available[requirement.output_name] = (
                    artifact_ref,
                    requirement.output_schema,
                    node_id,
                    requirement.output_name,
                )
                pending.remove(requirement)
                progressed = True

            if progressed:
                continue
            for requirement in pending:
                source = available.get(requirement.input_name)
                if source is None:
                    description = f"No artifact can satisfy input {requirement.input_name}"
                else:
                    description = (
                        f"Input {requirement.input_name} requires {requirement.input_schema}; "
                        f"got {source[1]}"
                    )
                remainders.append(_remainder(
                    RemainderKind.MISSING_INPUT,
                    description,
                    requirement.capability,
                    suggested=requirement.capability,
                ))
            break

        return ExecutionPlan(
            blueprint_id=blueprint.blueprint_id,
            blueprint_version=blueprint.version,
            objective=objective,
            nodes=tuple(nodes),
            edges=tuple(edges),
            external_artifacts=external_artifacts,
            state=PlanState.PROPOSED,
            remainders=tuple(remainders),
        )

    @staticmethod
    def _select_provider(blueprint, requirement, registry):
        candidates = registry.capability_candidates(requirement.capability)
        if not candidates:
            return None, _remainder(
                RemainderKind.MISSING_CAPABILITY,
                f"No enabled provider supplies {requirement.capability}",
                requirement.capability,
                suggested=requirement.capability,
            )

        incompatibilities = []
        permission_failures = []
        for module_id, operation in candidates:
            if operation.inputs.get(requirement.input_name) != requirement.input_schema:
                incompatibilities.append(f"{module_id}:{operation.operation_id}:input_schema")
                continue
            if operation.outputs.get(requirement.output_name) != requirement.output_schema:
                incompatibilities.append(f"{module_id}:{operation.operation_id}:output_schema")
                continue
            if not set(operation.effects).issubset(blueprint.allowed_effects):
                permission_failures.append(f"{module_id}:{operation.operation_id}:effect")
                continue
            if not set(operation.permissions).issubset(blueprint.granted_permissions):
                permission_failures.append(f"{module_id}:{operation.operation_id}:permission")
                continue
            return (module_id, operation), None

        if permission_failures:
            return None, _remainder(
                RemainderKind.PERMISSION_DENIED,
                "Compatible providers require unauthorized effects or permissions: "
                + ", ".join(permission_failures),
                requirement.capability,
            )
        return None, _remainder(
            RemainderKind.MISSING_CAPABILITY,
            "Capability providers are schema-incompatible: " + ", ".join(incompatibilities),
            requirement.capability,
            suggested=requirement.capability,
        )


class PlanValidator:
    """Validate technical, effect, dataflow, and contextual-order closure."""

    def validate(
        self,
        plan: ExecutionPlan,
        blueprint: BlueprintSpec,
        registry: ModuleRegistry,
    ) -> ExecutionPlan:
        problems = list(plan.remainders)
        available: dict[str, str] = {
            artifact.artifact_id: artifact.schema
            for artifact in plan.external_artifacts.values()
        }
        producers: dict[str, tuple[str, str, str]] = {}
        expected_edges: set[tuple[str, str, str, str, str, str]] = set()
        represented: set[tuple[str, str, str]] = set()

        for node in plan.nodes:
            try:
                registered = registry.operation(node.module_id, node.operation_id)
            except (KeyError, PermissionError) as exc:
                problems.append(_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    f"Planned operation is unavailable: {exc}",
                    node.node_id,
                ))
                continue
            operation = registered.contract
            if operation.version != node.operation_version:
                problems.append(_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    "Planned operation version no longer matches its manifest",
                    node.node_id,
                ))
            if not set(operation.effects).issubset(blueprint.allowed_effects) or not set(
                operation.permissions
            ).issubset(blueprint.granted_permissions):
                problems.append(_remainder(
                    RemainderKind.PERMISSION_DENIED,
                    "Plan requests effects or permissions outside the blueprint grant",
                    node.node_id,
                ))
            if set(node.input_bindings) != set(operation.inputs):
                problems.append(_remainder(
                    RemainderKind.MISSING_INPUT,
                    "Node input bindings do not match its operation contract",
                    node.node_id,
                ))
            for input_name, artifact_ref in node.input_bindings.items():
                schema = available.get(artifact_ref)
                expected = operation.inputs.get(input_name)
                if schema != expected:
                    problems.append(_remainder(
                        RemainderKind.MISSING_INPUT,
                        f"Input {input_name} requires {expected}; got {schema}",
                        node.node_id,
                    ))
                producer = producers.get(artifact_ref)
                if producer is not None:
                    expected_edges.add((
                        producer[0], producer[1], node.node_id, input_name,
                        artifact_ref, producer[2],
                    ))
            if dict(node.output_schemas) != dict(operation.outputs):
                problems.append(_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    "Node output schemas do not match its operation contract",
                    node.node_id,
                ))
            if set(node.output_bindings) != set(operation.outputs):
                problems.append(_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    "Node output bindings do not match its operation contract",
                    node.node_id,
                ))
            for output_name, artifact_ref in node.output_bindings.items():
                if artifact_ref in available:
                    problems.append(_remainder(
                        RemainderKind.CONTRADICTION,
                        f"Duplicate artifact reference: {artifact_ref}",
                        node.node_id,
                    ))
                schema = operation.outputs.get(output_name)
                if schema is not None:
                    available[artifact_ref] = schema
                    producers[artifact_ref] = (node.node_id, output_name, schema)
                    for capability in operation.capabilities:
                        represented.add((capability, output_name, schema))

        actual_edges = {
            (
                edge.producer_node_id,
                edge.producer_output,
                edge.consumer_node_id,
                edge.consumer_input,
                edge.artifact_ref,
                edge.schema,
            )
            for edge in plan.edges
        }
        if actual_edges != expected_edges:
            problems.append(_remainder(
                RemainderKind.CONTRADICTION,
                "Declared plan edges do not match the actual artifact dependencies",
                plan.blueprint_id,
            ))

        for requirement in blueprint.requirements:
            if (
                requirement.capability,
                requirement.output_name,
                requirement.output_schema,
            ) not in represented:
                problems.append(_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    f"Required outcome is absent: {requirement.output_name}",
                    requirement.capability,
                    suggested=requirement.capability,
                ))

        return replace(
            plan,
            state=PlanState.REJECTED if problems else PlanState.VALIDATED,
            remainders=tuple(problems),
        )


class Runtime:
    """Execute a validated acyclic plan in its validator-approved node order."""

    def execute(
        self,
        plan: ExecutionPlan,
        registry: ModuleRegistry,
        authorization: AuthorizationResult | None = None,
        effect_broker: EffectBroker | None = None,
        journal: EventJournal | None = None,
        causation_id: str | None = None,
        budget: ExecutionBudget | None = None,
        checkpoint: RuntimeCheckpoint | None = None,
    ) -> ExecutionResult:
        if plan.state != PlanState.VALIDATED:
            return self._open(plan.remainders or (_remainder(
                RemainderKind.MISSING_EVIDENCE,
                "Runtime requires a validated plan",
                plan.blueprint_id,
            ),))
        if (
            authorization is None
            or authorization.state != AuthorizationState.AUTHORIZED
            or authorization.plan_id != plan.plan_id
            or effect_broker is None
        ):
            remainders = authorization.remainders if authorization is not None else ()
            return self._denied(remainders or (_remainder(
                RemainderKind.PERMISSION_DENIED,
                "Runtime requires authorization scoped to this exact plan",
                plan.plan_id,
            ),))

        if checkpoint is not None and checkpoint.plan.plan_id != plan.plan_id:
            return self._open((_remainder(
                RemainderKind.CONTRADICTION,
                "Checkpoint belongs to a different execution plan",
                checkpoint.checkpoint_id,
            ),))

        episode_budget = budget or ExecutionBudget(max_operations=None)
        artifacts_by_ref = (
            dict(checkpoint.artifacts_by_ref)
            if checkpoint is not None
            else {
                artifact.artifact_id: artifact
                for artifact in plan.external_artifacts.values()
            }
        )
        public_outputs: dict[str, Artifact] = (
            dict(checkpoint.public_outputs) if checkpoint is not None else {}
        )
        completed_node_ids = list(
            checkpoint.completed_node_ids if checkpoint is not None else ()
        )
        completed = set(completed_node_ids)
        operation_cause = causation_id
        for node in plan.nodes:
            if node.node_id in completed:
                continue
            if episode_budget.exhausted:
                return self._paused(
                    plan=plan,
                    completed_node_ids=tuple(completed_node_ids),
                    artifacts_by_ref=artifacts_by_ref,
                    public_outputs=public_outputs,
                    budget=episode_budget,
                    previous_checkpoint=checkpoint,
                    journal=journal,
                    causation_id=operation_cause,
                )
            operation_started = self._record(
                journal,
                JournalEventKind.OPERATION_STARTED,
                plan.plan_id,
                node.node_id,
                {
                    "module_id": node.module_id,
                    "operation_id": node.operation_id,
                    "operation_version": node.operation_version,
                },
                causation_id=operation_cause,
            )
            grant = authorization.grants.get(node.node_id)
            if (
                grant is None
                or grant.plan_id != plan.plan_id
                or grant.module_id != node.module_id
                or grant.operation_id != node.operation_id
            ):
                return self._denied((_remainder(
                    RemainderKind.PERMISSION_DENIED,
                    "Node has no matching scoped effect grant",
                    node.node_id,
                ),))
            try:
                registered = registry.operation(node.module_id, node.operation_id)
            except (KeyError, PermissionError) as exc:
                return self._open((_remainder(
                    RemainderKind.MISSING_CAPABILITY,
                    f"Validated operation became unavailable: {exc}",
                    node.node_id,
                ),))
            handler_inputs = {}
            for input_name, artifact_ref in node.input_bindings.items():
                artifact = artifacts_by_ref.get(artifact_ref)
                if artifact is None:
                    return self._open((_remainder(
                        RemainderKind.MISSING_INPUT,
                        f"Bound artifact is unavailable: {artifact_ref}",
                        node.node_id,
                    ),))
                handler_inputs[input_name] = artifact.payload

            context = effect_broker.context(
                grant, journal, causation_id=operation_started
            )
            try:
                raw_outputs = registered.handler(handler_inputs, context)
            except PermissionError as exc:
                self._record(
                    journal,
                    JournalEventKind.OPERATION_FAILED,
                    plan.plan_id,
                    node.node_id,
                    {"failure_kind": "PERMISSION_DENIED"},
                    causation_id=operation_started,
                )
                return self._denied((_remainder(
                    RemainderKind.PERMISSION_DENIED,
                    f"Operation attempted an unauthorized effect: {exc}",
                    node.node_id,
                ),))
            except Exception as exc:
                self._record(
                    journal,
                    JournalEventKind.OPERATION_FAILED,
                    plan.plan_id,
                    node.node_id,
                    {"failure_kind": type(exc).__name__},
                    causation_id=operation_started,
                )
                return self._failed(node.node_id, exc)

            expected = dict(node.output_schemas)
            if set(raw_outputs) != set(expected):
                self._record(
                    journal,
                    JournalEventKind.OPERATION_FAILED,
                    plan.plan_id,
                    node.node_id,
                    {"failure_kind": "OUTPUT_CONTRACT_MISMATCH"},
                    causation_id=operation_started,
                )
                return self._open((_remainder(
                    RemainderKind.MISSING_EVIDENCE,
                    "Handler outputs do not match the operation contract",
                    node.node_id,
                ),))
            for output_name, payload in raw_outputs.items():
                artifact = Artifact(
                    schema=expected[output_name],
                    payload=payload,
                    producer_module=node.module_id,
                    producer_operation=node.operation_id,
                    provenance=tuple(node.input_bindings.values()),
                )
                artifacts_by_ref[node.output_bindings[output_name]] = artifact
                public_outputs[output_name] = artifact
            operation_cause = self._record(
                journal,
                JournalEventKind.OPERATION_OUTPUT,
                plan.plan_id,
                node.node_id,
                {
                    "artifact_ids": tuple(
                        public_outputs[name].artifact_id for name in raw_outputs
                    ),
                    "output_names": tuple(raw_outputs),
                },
                causation_id=operation_started,
            )
            episode_budget = episode_budget.consume_operation()
            completed_node_ids.append(node.node_id)
            completed.add(node.node_id)

        closure = ClosureReport(
            technical_completed=True,
            constitutional_closed=None,
            structural_closed=None,
            operational_converged=True,
            epistemic_closed=None,
            stopping_reason="OBJECTIVE_SATISFIED",
        )
        return ExecutionResult(
            state=ExecutionState.COMPLETED,
            artifacts=public_outputs,
            closure=closure,
        )

    def _paused(
        self,
        *,
        plan: ExecutionPlan,
        completed_node_ids: tuple[str, ...],
        artifacts_by_ref: Mapping[str, Artifact],
        public_outputs: Mapping[str, Artifact],
        budget: ExecutionBudget,
        previous_checkpoint: RuntimeCheckpoint | None,
        journal: EventJournal | None,
        causation_id: str | None,
    ) -> ExecutionResult:
        remainder = _remainder(
            RemainderKind.BUDGET_EXHAUSTED,
            "Operation budget exhausted before the remaining frontier",
            plan.plan_id,
        )
        completed = set(completed_node_ids)
        checkpoint = RuntimeCheckpoint(
            plan=plan,
            completed_node_ids=completed_node_ids,
            next_node_ids=tuple(
                node.node_id for node in plan.nodes if node.node_id not in completed
            ),
            artifacts_by_ref=artifacts_by_ref,
            public_outputs=public_outputs,
            budget=budget,
            active_remainders=(remainder,),
            previous_checkpoint_id=(
                previous_checkpoint.checkpoint_id
                if previous_checkpoint is not None else None
            ),
        )
        checkpoint_event = self._record(
            journal,
            JournalEventKind.CHECKPOINT_CREATED,
            plan.plan_id,
            checkpoint.checkpoint_id,
            {
                "completed_node_ids": checkpoint.completed_node_ids,
                "next_node_ids": checkpoint.next_node_ids,
                "consumed_operations": budget.consumed_operations,
                "max_operations": budget.max_operations,
                "previous_checkpoint_id": checkpoint.previous_checkpoint_id,
            },
            causation_id=causation_id,
        )
        self._record(
            journal,
            JournalEventKind.EXECUTION_PAUSED,
            plan.plan_id,
            checkpoint.checkpoint_id,
            {"reason": checkpoint.reason},
            causation_id=checkpoint_event,
        )
        return ExecutionResult(
            state=ExecutionState.PAUSED,
            artifacts=public_outputs,
            remainders=(remainder,),
            checkpoint=checkpoint,
            closure=ClosureReport(
                technical_completed=False,
                constitutional_closed=None,
                structural_closed=None,
                operational_converged=False,
                epistemic_closed=None,
                stopping_reason="BUDGET_EXHAUSTED",
                active_remainders=(remainder,),
            ),
        )

    @staticmethod
    def _record(
        journal: EventJournal | None,
        kind: JournalEventKind,
        correlation_id: str,
        subject_ref: str,
        payload: Mapping[str, object],
        *,
        causation_id: str | None = None,
    ) -> str | None:
        if journal is None:
            return None
        return journal.append(
            kind,
            correlation_id=correlation_id,
            subject_ref=subject_ref,
            payload=payload,
            causation_id=causation_id,
        ).event_id

    @staticmethod
    def _failed(node_id: str, exc: Exception) -> ExecutionResult:
        remainder = _remainder(
            RemainderKind.MISSING_EVIDENCE,
            f"Operation failed: {type(exc).__name__}: {exc}",
            node_id,
        )
        return ExecutionResult(
            state=ExecutionState.FAILED,
            artifacts={},
            remainders=(remainder,),
            closure=ClosureReport(
                technical_completed=False,
                constitutional_closed=None,
                structural_closed=None,
                operational_converged=False,
                epistemic_closed=None,
                stopping_reason="FAILED",
                active_remainders=(remainder,),
            ),
        )

    @staticmethod
    def _denied(remainders: tuple[Remainder, ...]) -> ExecutionResult:
        return ExecutionResult(
            state=ExecutionState.DENIED,
            artifacts={},
            remainders=remainders,
            closure=ClosureReport(
                technical_completed=False,
                constitutional_closed=None,
                structural_closed=None,
                operational_converged=False,
                epistemic_closed=None,
                stopping_reason="DENIED",
                active_remainders=remainders,
            ),
        )

    @staticmethod
    def _open(remainders: tuple[Remainder, ...]) -> ExecutionResult:
        return ExecutionResult(
            state=ExecutionState.OPEN,
            artifacts={},
            remainders=remainders,
            closure=ClosureReport(
                technical_completed=False,
                constitutional_closed=None,
                structural_closed=None,
                operational_converged=False,
                epistemic_closed=None,
                stopping_reason="OPEN",
                active_remainders=remainders,
            ),
        )
