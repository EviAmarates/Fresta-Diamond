"""Scoped effect authorization and invocation for Fresta Diamond."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from fresta_diamond.contracts import (
    AuthorizationResult,
    AuthorizationState,
    BlueprintSpec,
    EffectGrant,
    ExecutionPlan,
    Remainder,
    RemainderKind,
    PlanState,
)
from fresta_diamond.journal import EventJournal, JournalEventKind
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.prompt_boundary import validate_model_messages


EffectAdapter = Callable[..., Any]


@dataclass(frozen=True)
class ExecutionContext:
    """The only effect-facing API supplied to an in-process handler."""

    grant: EffectGrant
    _adapters: Mapping[str, EffectAdapter]
    _journal: EventJournal | None = None
    _causation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "_adapters", MappingProxyType(dict(self._adapters)))

    @property
    def module_id(self) -> str:
        return self.grant.module_id

    @property
    def operation_id(self) -> str:
        return self.grant.operation_id

    @property
    def granted_permissions(self) -> tuple[str, ...]:
        return self.grant.permissions

    @property
    def allowed_effects(self) -> tuple[str, ...]:
        return self.grant.effects

    def invoke(self, effect: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke one broker-provided adapter within this node's grant."""
        requested = self._record(
            JournalEventKind.EFFECT_REQUESTED,
            effect,
            {"grant_id": self.grant.grant_id},
            causation_id=self._causation_id,
        )
        if effect not in self.grant.effects:
            self._record(
                JournalEventKind.EFFECT_REJECTED,
                effect,
                {"reason": "EFFECT_NOT_GRANTED"},
                causation_id=requested,
            )
            raise PermissionError(f"Effect is not granted to this operation: {effect}")
        adapter = self._adapters.get(effect)
        if adapter is None:
            self._record(
                JournalEventKind.EFFECT_REJECTED,
                effect,
                {"reason": "ADAPTER_UNAVAILABLE"},
                causation_id=requested,
            )
            raise PermissionError(f"No authorized adapter is available for: {effect}")
        if effect == "llm.generate":
            try:
                messages = kwargs.get("messages")
                if not isinstance(messages, (list, tuple)):
                    raise ValueError("llm.generate requires bounded messages")
                kwargs["messages"] = validate_model_messages(messages)
            except Exception as exc:
                self._record(
                    JournalEventKind.EFFECT_REJECTED,
                    effect,
                    {
                        "reason": "PROMPT_BOUNDARY_REJECTED",
                        "error_type": type(exc).__name__,
                    },
                    causation_id=requested,
                )
                raise
        try:
            result = adapter(self.grant, *args, **kwargs)
        except Exception as exc:
            self._record(
                JournalEventKind.EFFECT_REJECTED,
                effect,
                {"reason": "ADAPTER_FAILED", "error_type": type(exc).__name__},
                causation_id=requested,
            )
            raise
        self._record(
            JournalEventKind.EFFECT_COMMITTED,
            effect,
            {"grant_id": self.grant.grant_id},
            causation_id=requested,
        )
        return result

    def _record(
        self,
        kind: JournalEventKind,
        effect: str,
        payload: Mapping[str, Any],
        *,
        causation_id: str | None = None,
    ) -> str | None:
        if self._journal is None:
            return None
        event = self._journal.append(
            kind,
            correlation_id=self.grant.plan_id,
            subject_ref=f"effect:{effect}",
            payload={
                "node_id": self.grant.node_id,
                "module_id": self.grant.module_id,
                "operation_id": self.grant.operation_id,
                **payload,
            },
            causation_id=causation_id,
        )
        return event.event_id


class EffectBroker:
    """Authorize declared effects and expose only injected, scoped adapters."""

    def __init__(self, adapters: Mapping[str, EffectAdapter] | None = None) -> None:
        self._adapters = MappingProxyType(dict(adapters or {}))

    def authorize(
        self,
        plan: ExecutionPlan,
        blueprint: BlueprintSpec,
        registry: ModuleRegistry,
    ) -> AuthorizationResult:
        if plan.state != PlanState.VALIDATED:
            remainders = plan.remainders or (self._remainder(
                "Authorization requires a validated plan", plan.blueprint_id
            ),)
            return AuthorizationResult(
                plan_id=plan.plan_id,
                state=AuthorizationState.DENIED,
                grants={},
                remainders=remainders,
            )

        grants: dict[str, EffectGrant] = {}
        problems: list[Remainder] = []
        for node in plan.nodes:
            try:
                operation = registry.operation(node.module_id, node.operation_id).contract
            except (KeyError, PermissionError) as exc:
                problems.append(Remainder(
                    kind=RemainderKind.MISSING_CAPABILITY,
                    description=f"Cannot authorize unavailable operation: {exc}",
                    required_for=node.node_id,
                    resolvable=True,
                ))
                continue

            if not set(operation.effects).issubset(blueprint.allowed_effects) or not set(
                operation.permissions
            ).issubset(blueprint.granted_permissions):
                problems.append(self._remainder(
                    "Operation requests effects or permissions beyond the blueprint grant",
                    node.node_id,
                ))
                continue
            missing_adapters = sorted(set(operation.effects) - set(self._adapters))
            if missing_adapters:
                problems.append(Remainder(
                    kind=RemainderKind.MISSING_CAPABILITY,
                    description="No effect adapter is installed for: " + ", ".join(missing_adapters),
                    required_for=node.node_id,
                    resolvable=True,
                    suggested_capability=missing_adapters[0],
                ))
                continue
            grants[node.node_id] = EffectGrant(
                plan_id=plan.plan_id,
                node_id=node.node_id,
                module_id=node.module_id,
                operation_id=node.operation_id,
                effects=operation.effects,
                permissions=operation.permissions,
            )

        return AuthorizationResult(
            plan_id=plan.plan_id,
            state=AuthorizationState.DENIED if problems else AuthorizationState.AUTHORIZED,
            grants={} if problems else grants,
            remainders=tuple(problems),
        )

    def context(
        self,
        grant: EffectGrant,
        journal: EventJournal | None = None,
        causation_id: str | None = None,
    ) -> ExecutionContext:
        adapters = {effect: self._adapters[effect] for effect in grant.effects}
        return ExecutionContext(
            grant=grant,
            _adapters=adapters,
            _journal=journal,
            _causation_id=causation_id,
        )

    @staticmethod
    def _remainder(description: str, required_for: str) -> Remainder:
        return Remainder(
            kind=RemainderKind.PERMISSION_DENIED,
            description=description,
            required_for=required_for,
            resolvable=True,
        )
