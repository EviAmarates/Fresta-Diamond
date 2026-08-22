"""Immutable contracts for the Fresta Diamond prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping
from uuid import uuid4

if TYPE_CHECKING:
    from fresta_diamond.constitutional_firewall import FirewallAttestation
    from fresta_diamond.epistemology import EpistemicValidationReport
    from fresta_diamond.journal import JournalEvent
    from fresta_diamond.journal import JournalSegment
    from fresta_diamond.ontology import StructuralValidationReport
    from fresta_diamond.workspace import RuntimeCheckpoint
    from fresta_diamond.workspace import StoredCheckpointRef


def frozen_mapping(value: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Return a deeply immutable snapshot suitable for contract boundaries."""
    return MappingProxyType({
        str(key): _freeze_contract_value(item)
        for key, item in dict(value or {}).items()
    })


def _freeze_contract_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return frozen_mapping(value)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_contract_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_contract_value(item) for item in value)
    return value


class TrustState(str, Enum):
    DISCOVERED = "DISCOVERED"
    QUARANTINED = "QUARANTINED"
    VERIFIED = "VERIFIED"
    ENABLED = "ENABLED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


class PlanState(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class ExecutionState(str, Enum):
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    OPEN = "OPEN"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class RemainderKind(str, Enum):
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    MISSING_INPUT = "MISSING_INPUT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONTRADICTION = "CONTRADICTION"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    EXTERNAL_UNCERTAINTY = "EXTERNAL_UNCERTAINTY"
    INVALID_DIRECTION = "INVALID_DIRECTION"
    INVALID_SCOPE = "INVALID_SCOPE"
    UNUSED_EVIDENCE = "UNUSED_EVIDENCE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    CONSTITUTIONAL_REMAINDER = "CONSTITUTIONAL_REMAINDER"


class AuthorizationState(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class Remainder:
    """A bounded unresolved item; only one kind denotes constitutional PHI."""

    kind: RemainderKind
    description: str
    required_for: str
    resolvable: bool | None = None
    suggested_capability: str | None = None
    remainder_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "OPEN"

    @property
    def phi_id(self) -> str:
        """Deprecated read alias for pre-Diamond-persistence consumers."""
        return self.remainder_id


# Temporary import aliases. New code must use RemainderKind and Remainder.
PhiKind = RemainderKind
PhiRemainder = Remainder


@dataclass(frozen=True)
class Artifact:
    schema: str
    payload: Mapping[str, Any]
    artifact_id: str = field(default_factory=lambda: str(uuid4()))
    producer_module: str | None = None
    producer_operation: str | None = None
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema.strip():
            raise ValueError("Artifact schema is required")
        object.__setattr__(self, "payload", frozen_mapping(self.payload))


@dataclass(frozen=True)
class OperationContract:
    operation_id: str
    version: str
    capabilities: tuple[str, ...]
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    effects: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    idempotency: str = "SAFE_RETRY"
    determinism: str = "DETERMINISTIC"
    cost: int = 0

    def __post_init__(self) -> None:
        if not self.operation_id.strip() or not self.version.strip():
            raise ValueError("Operation ID and version are required")
        if not self.capabilities:
            raise ValueError("An operation must provide at least one capability")
        if not self.outputs:
            raise ValueError("An operation must declare at least one output")
        object.__setattr__(self, "inputs", frozen_mapping(self.inputs))
        object.__setattr__(self, "outputs", frozen_mapping(self.outputs))


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    version: str
    kernel_contract: str
    sdk_contract: str
    operations: tuple[OperationContract, ...]

    def __post_init__(self) -> None:
        if not self.module_id.strip() or not self.version.strip():
            raise ValueError("Module ID and version are required")
        operation_ids = [operation.operation_id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("A module manifest contains duplicate operation IDs")


@dataclass(frozen=True)
class CapabilityRequirement:
    capability: str
    input_name: str
    input_schema: str
    output_name: str
    output_schema: str
    contextual_roles: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise ValueError("Capability is required")
        if not set(self.contextual_roles).issubset({1, 2, 3}):
            raise ValueError("Contextual roles must be a subset of O1/O2/O3")


@dataclass(frozen=True)
class BlueprintSpec:
    blueprint_id: str
    version: int
    intent: str
    requirement: CapabilityRequirement | None = None
    requirements: tuple[CapabilityRequirement, ...] = ()
    allowed_effects: tuple[str, ...] = ()
    granted_permissions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        declared = self.requirements
        if self.requirement is not None:
            if declared:
                raise ValueError("Use requirement or requirements, not both")
            declared = (self.requirement,)
        if not declared:
            raise ValueError("A blueprint requires at least one capability")
        output_names = [item.output_name for item in declared]
        if len(output_names) != len(set(output_names)):
            raise ValueError("Blueprint requirement outputs must have unique names")
        object.__setattr__(self, "requirements", tuple(declared))


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    module_id: str
    operation_id: str
    operation_version: str
    input_bindings: Mapping[str, str]
    output_schemas: Mapping[str, str]
    output_bindings: Mapping[str, str]
    contextual_roles: tuple[int, ...] = (1, 2, 3)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_bindings", frozen_mapping(self.input_bindings))
        object.__setattr__(self, "output_schemas", frozen_mapping(self.output_schemas))
        object.__setattr__(self, "output_bindings", frozen_mapping(self.output_bindings))


@dataclass(frozen=True)
class PlanEdge:
    producer_node_id: str
    producer_output: str
    consumer_node_id: str
    consumer_input: str
    artifact_ref: str
    schema: str


@dataclass(frozen=True)
class ExecutionPlan:
    blueprint_id: str
    blueprint_version: int
    objective: str
    nodes: tuple[PlanNode, ...]
    external_artifacts: Mapping[str, Artifact]
    state: PlanState
    edges: tuple[PlanEdge, ...] = ()
    remainders: tuple[Remainder, ...] = ()
    plan_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        object.__setattr__(self, "external_artifacts", frozen_mapping(self.external_artifacts))

    @property
    def phi(self) -> tuple[Remainder, ...]:
        """Deprecated read alias; finite gaps are not constitutional PHI."""
        return self.remainders


@dataclass(frozen=True)
class EffectGrant:
    plan_id: str
    node_id: str
    module_id: str
    operation_id: str
    effects: tuple[str, ...]
    permissions: tuple[str, ...]
    grant_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class AuthorizationResult:
    plan_id: str
    state: AuthorizationState
    grants: Mapping[str, EffectGrant]
    remainders: tuple[Remainder, ...] = ()
    authorization_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        object.__setattr__(self, "grants", frozen_mapping(self.grants))

    @property
    def phi(self) -> tuple[Remainder, ...]:
        """Deprecated read alias; finite gaps are not constitutional PHI."""
        return self.remainders


@dataclass(frozen=True)
class ClosureReport:
    technical_completed: bool
    constitutional_closed: bool | None
    structural_closed: bool | None
    operational_converged: bool
    epistemic_closed: bool | None
    stopping_reason: str
    active_remainders: tuple[Remainder, ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    state: ExecutionState
    artifacts: Mapping[str, Artifact]
    closure: ClosureReport
    remainders: tuple[Remainder, ...] = ()
    checkpoint: RuntimeCheckpoint | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", frozen_mapping(self.artifacts))

    @property
    def phi(self) -> tuple[Remainder, ...]:
        """Deprecated read alias; finite gaps are not constitutional PHI."""
        return self.remainders


@dataclass(frozen=True)
class ControllerResult:
    """Observable result of one controller request, including its derived plan."""

    plan: ExecutionPlan
    authorization: AuthorizationResult
    execution: ExecutionResult
    firewall_attestation: FirewallAttestation
    ontological_reports: tuple[StructuralValidationReport, ...] = ()
    epistemic_reports: tuple[EpistemicValidationReport, ...] = ()
    journal_events: tuple[JournalEvent, ...] = ()
    archived_journal_segment: JournalSegment | None = None
    stored_checkpoint: StoredCheckpointRef | None = None
