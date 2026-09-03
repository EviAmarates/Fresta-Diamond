"""Immutable contracts for the Fresta Diamond prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
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


class ProvenanceKind(str, Enum):
    """Conservative provenance domains understood by the kernel."""

    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"
    INTERNAL_ONLY = "INTERNAL"
    EXTERNAL_ONLY = "EXTERNAL"
    MIXED_PROVENANCE = "MIXED"


# Domain is the name used by a few older callers.
ProvenanceDomain = ProvenanceKind
ProvenanceType = ProvenanceKind


class SearchIntent(str, Enum):
    """Intent classes for bounded retrieval plans."""

    NEUTRAL = "NEUTRAL"
    LABEL_REVEALING = "LABEL_REVEALING"
    DISCOVERY = "NEUTRAL"
    LABEL_RECOGNITION = "LABEL_REVEALING"


ResearchIntent = SearchIntent


@dataclass(frozen=True)
class TypedProvenance:
    """Immutable, host-derived provenance rather than a caller assertion."""

    refs: tuple[str, ...] = ()
    kind: ProvenanceKind = ProvenanceKind.UNKNOWN
    source_lineage: str | None = None

    def __post_init__(self) -> None:
        refs = tuple(dict.fromkeys(
            item.strip() for item in self.refs
            if isinstance(item, str) and item.strip()
        ))
        object.__setattr__(self, "refs", refs)
        if self.source_lineage is not None:
            if (
                not isinstance(self.source_lineage, str)
                or not self.source_lineage.strip()
            ):
                raise ValueError("Source lineage must be a non-empty reference")
            object.__setattr__(
                self, "source_lineage", self.source_lineage.strip()
            )
        derived = classify_provenance(refs)
        # A supplied domain may only narrow an empty/unknown legacy value;
        # never let an artifact claim internal or external authority.
        if self.kind is not ProvenanceKind.UNKNOWN and self.kind is not derived:
            object.__setattr__(self, "kind", derived)
        elif not refs:
            object.__setattr__(self, "kind", ProvenanceKind.UNKNOWN)
        else:
            object.__setattr__(self, "kind", derived)

    @property
    def domain(self) -> ProvenanceKind:
        return self.kind

    @property
    def references(self) -> tuple[str, ...]:
        return self.refs

    @property
    def provenance_kind(self) -> ProvenanceKind:
        return self.kind


Provenance = TypedProvenance


def classify_provenance(refs: Any) -> ProvenanceKind:
    """Classify legacy refs without guessing when a prefix is unfamiliar."""

    if isinstance(refs, str):
        refs = (refs,)
    if not isinstance(refs, (tuple, list, set, frozenset)):
        return ProvenanceKind.UNKNOWN
    domains: set[ProvenanceKind] = set()
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            continue
        value = ref.strip().lower()
        if value.startswith((
            "memory:", "workspace:", "chat:", "profile:", "personality:",
            "operator:", "runtime:", "concept:", "crystal:",
        )):
            domains.add(ProvenanceKind.INTERNAL)
        elif value.startswith((
            "http://", "https://", "document:", "source:",
        )):
            domains.add(ProvenanceKind.EXTERNAL)
        else:
            domains.add(ProvenanceKind.UNKNOWN)
    if domains == {ProvenanceKind.INTERNAL}:
        return ProvenanceKind.INTERNAL
    if domains == {ProvenanceKind.EXTERNAL}:
        return ProvenanceKind.EXTERNAL
    if ProvenanceKind.INTERNAL in domains and ProvenanceKind.EXTERNAL in domains:
        return ProvenanceKind.MIXED
    return ProvenanceKind.UNKNOWN


def decode_provenance(value: Any) -> TypedProvenance:
    """Decode typed or legacy provenance, defaulting unknown conservatively."""

    if isinstance(value, TypedProvenance):
        return value
    if isinstance(value, Mapping):
        raw = value.get("refs", value.get("provenance", ()))
        if isinstance(raw, str):
            raw = (raw,)
        if not isinstance(raw, (list, tuple, set, frozenset)):
            raw = ()
        return TypedProvenance(
            tuple(raw),
            source_lineage=value.get("source_lineage"),
        )
    if isinstance(value, str):
        return TypedProvenance((value,))
    if isinstance(value, (list, tuple, set, frozenset)):
        return TypedProvenance(tuple(value))
    return TypedProvenance()


# Explicit alias for callers migrating from the legacy list codec.
decode_typed_provenance = decode_provenance


@dataclass(frozen=True)
class SourceDocument:
    """A source container whose identity is stable across extracted units."""

    document_ref: str
    locator: str
    content_hash: str
    retrieved_at: str = ""
    provenance: TypedProvenance = field(default_factory=TypedProvenance)
    content: str = ""
    source_lineage: str | None = None

    def __post_init__(self) -> None:
        if not self.document_ref.strip() or not self.locator.strip():
            raise ValueError("Source document references are required")
        if not self.content_hash.strip():
            raise ValueError("Source document content hash is required")
        if self.content and sha256(self.content.encode("utf-8")).hexdigest() != (
            self.content_hash
        ):
            raise ValueError("Source document content hash mismatch")
        provenance = decode_provenance(self.provenance)
        if (
            self.source_lineage is not None
            and provenance.source_lineage is not None
            and self.source_lineage != provenance.source_lineage
        ):
            raise ValueError("Source document lineage does not match provenance")
        lineage = self.source_lineage or provenance.source_lineage
        if lineage is not None:
            provenance = TypedProvenance(
                provenance.refs, provenance.kind, source_lineage=lineage
            )
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "source_lineage", lineage)

    @property
    def source_document_ref(self) -> str:
        return self.document_ref

    @property
    def source_document_id(self) -> str:
        return self.document_ref


@dataclass(frozen=True)
class ExtractedUnit:
    """A bounded extraction that must retain its source-document parent."""

    unit_ref: str
    source_document_ref: str
    content_hash: str
    content: str = ""
    provenance: TypedProvenance = field(default_factory=TypedProvenance)
    source_lineage: str | None = None

    def __post_init__(self) -> None:
        if not self.unit_ref.strip() or not self.source_document_ref.strip():
            raise ValueError("Extracted-unit lineage references are required")
        if not self.content_hash.strip():
            raise ValueError("Extracted-unit content hash is required")
        provenance = decode_provenance(self.provenance)
        if (
            self.source_lineage is not None
            and provenance.source_lineage is not None
            and self.source_lineage != provenance.source_lineage
        ):
            raise ValueError("Extracted unit lineage does not match provenance")
        lineage = self.source_lineage or provenance.source_lineage
        if lineage is not None:
            provenance = TypedProvenance(
                provenance.refs, provenance.kind, source_lineage=lineage
            )
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "source_lineage", lineage)

    @property
    def extracted_unit_ref(self) -> str:
        return self.unit_ref

    @property
    def extracted_unit_id(self) -> str:
        return self.unit_ref

    @property
    def source_document_id(self) -> str:
        return self.source_document_ref


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

    @property
    def typed_provenance(self) -> TypedProvenance:
        """Typed view retained alongside the legacy tuple API."""
        return decode_provenance(self.provenance)


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
