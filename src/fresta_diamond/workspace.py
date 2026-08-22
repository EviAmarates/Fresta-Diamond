"""Volatile budget and checkpoint contracts for resumable Diamond execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Any, Mapping, Protocol
from uuid import uuid4

from fresta_diamond.contracts import (
    Artifact,
    ExecutionPlan,
    PlanEdge,
    PlanNode,
    PlanState,
    Remainder,
    RemainderKind,
)


CHECKPOINT_SCHEMA = "fresta://runtime-checkpoint@1"


@dataclass(frozen=True)
class ExecutionBudget:
    """A finite per-episode operation clock; None means explicitly unbounded."""

    max_operations: int | None
    consumed_operations: int = 0

    def __post_init__(self) -> None:
        if self.max_operations is not None and self.max_operations < 0:
            raise ValueError("Operation budget cannot be negative")
        if self.consumed_operations < 0:
            raise ValueError("Consumed operations cannot be negative")
        if (
            self.max_operations is not None
            and self.consumed_operations > self.max_operations
        ):
            raise ValueError("Consumed operations exceed the episode budget")

    @property
    def remaining_operations(self) -> int | None:
        if self.max_operations is None:
            return None
        return self.max_operations - self.consumed_operations

    @property
    def exhausted(self) -> bool:
        return self.remaining_operations == 0

    def consume_operation(self) -> ExecutionBudget:
        if self.exhausted:
            raise ValueError("Operation budget is exhausted")
        return ExecutionBudget(
            max_operations=self.max_operations,
            consumed_operations=self.consumed_operations + 1,
        )


@dataclass(frozen=True)
class RuntimeCheckpoint:
    """Immutable active frontier produced by a budget pause."""

    plan: ExecutionPlan
    completed_node_ids: tuple[str, ...]
    next_node_ids: tuple[str, ...]
    artifacts_by_ref: Mapping[str, Artifact]
    public_outputs: Mapping[str, Artifact]
    budget: ExecutionBudget
    active_remainders: tuple[Remainder, ...]
    previous_checkpoint_id: str | None = None
    journal_segment_hash: str | None = None
    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reason: str = "BUDGET_EXHAUSTED"

    def __post_init__(self) -> None:
        if not self.checkpoint_id.strip():
            raise ValueError("Checkpoint ID is required")
        if self.reason != "BUDGET_EXHAUSTED":
            raise ValueError("This checkpoint contract supports budget pauses only")
        planned = {node.node_id for node in self.plan.nodes}
        completed = set(self.completed_node_ids)
        pending = set(self.next_node_ids)
        if completed & pending:
            raise ValueError("Completed and pending checkpoint nodes overlap")
        if completed | pending != planned:
            raise ValueError("Checkpoint frontier does not cover the complete plan")
        object.__setattr__(
            self, "artifacts_by_ref", MappingProxyType(dict(self.artifacts_by_ref))
        )
        object.__setattr__(
            self, "public_outputs", MappingProxyType(dict(self.public_outputs))
        )


@dataclass(frozen=True)
class StoredCheckpointRef:
    checkpoint_id: str
    content_hash: str
    schema: str = CHECKPOINT_SCHEMA


class CheckpointStoreError(RuntimeError):
    """A checkpoint could not be persisted or verified."""


class CheckpointStore(Protocol):
    def save(self, checkpoint: RuntimeCheckpoint) -> StoredCheckpointRef:
        """Persist one immutable checkpoint."""

    def load(self, checkpoint_id: str) -> RuntimeCheckpoint:
        """Load and verify one immutable checkpoint."""


class JsonCheckpointStore:
    """Explicit file-backed checkpoint store for isolated Diamond workspaces."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._lock = Lock()

    @property
    def root(self) -> Path:
        return self._root

    def save(self, checkpoint: RuntimeCheckpoint) -> StoredCheckpointRef:
        body = encode_runtime_checkpoint(checkpoint)
        content_hash = _hash_body(body)
        record = {**body, "content_hash": content_hash}
        path = self._path(checkpoint.checkpoint_id)
        with self._lock:
            try:
                self._root.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(_canonical_json(record) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError as exc:
                raise CheckpointStoreError(
                    f"Checkpoint already exists: {checkpoint.checkpoint_id}"
                ) from exc
            except (OSError, TypeError, ValueError) as exc:
                raise CheckpointStoreError(
                    f"Could not persist checkpoint: {type(exc).__name__}"
                ) from exc
        return StoredCheckpointRef(
            checkpoint_id=checkpoint.checkpoint_id,
            content_hash=content_hash,
        )

    def load(self, checkpoint_id: str) -> RuntimeCheckpoint:
        path = self._path(checkpoint_id)
        with self._lock:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(record, dict):
                    raise TypeError("checkpoint record is not an object")
                content_hash = record.pop("content_hash")
                if not isinstance(content_hash, str):
                    raise TypeError("content_hash is not text")
                if _hash_body(record) != content_hash:
                    raise CheckpointStoreError("Checkpoint hash mismatch")
                checkpoint = decode_runtime_checkpoint(record)
                if checkpoint.checkpoint_id != checkpoint_id:
                    raise CheckpointStoreError("Checkpoint file identity mismatch")
                return checkpoint
            except CheckpointStoreError:
                raise
            except FileNotFoundError as exc:
                raise CheckpointStoreError(
                    f"Checkpoint does not exist: {checkpoint_id}"
                ) from exc
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise CheckpointStoreError(
                    f"Malformed checkpoint: {type(exc).__name__}: {exc}"
                ) from exc

    def _path(self, checkpoint_id: str) -> Path:
        if (
            not isinstance(checkpoint_id, str)
            or not checkpoint_id.strip()
            or checkpoint_id in {".", ".."}
            or "/" in checkpoint_id
            or "\\" in checkpoint_id
        ):
            raise CheckpointStoreError("Invalid checkpoint ID")
        return self._root / f"{checkpoint_id}.json"


def encode_runtime_checkpoint(checkpoint: RuntimeCheckpoint) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at,
        "reason": checkpoint.reason,
        "previous_checkpoint_id": checkpoint.previous_checkpoint_id,
        "journal_segment_hash": checkpoint.journal_segment_hash,
        "completed_node_ids": list(checkpoint.completed_node_ids),
        "next_node_ids": list(checkpoint.next_node_ids),
        "budget": {
            "max_operations": checkpoint.budget.max_operations,
            "consumed_operations": checkpoint.budget.consumed_operations,
        },
        "active_remainders": [
            _remainder_to_data(item) for item in checkpoint.active_remainders
        ],
        "plan": _plan_to_data(checkpoint.plan),
        "artifacts_by_ref": {
            key: _artifact_to_data(value)
            for key, value in checkpoint.artifacts_by_ref.items()
        },
        "public_outputs": {
            key: _artifact_to_data(value)
            for key, value in checkpoint.public_outputs.items()
        },
    }


def decode_runtime_checkpoint(value: Mapping[str, Any]) -> RuntimeCheckpoint:
    if value.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("unknown checkpoint schema")
    budget_data = _mapping(value, "budget")
    return RuntimeCheckpoint(
        checkpoint_id=_text(value, "checkpoint_id"),
        created_at=_text(value, "created_at"),
        reason=_text(value, "reason"),
        previous_checkpoint_id=_optional_text(value, "previous_checkpoint_id"),
        journal_segment_hash=_optional_text(value, "journal_segment_hash"),
        completed_node_ids=_text_tuple(value, "completed_node_ids"),
        next_node_ids=_text_tuple(value, "next_node_ids"),
        budget=ExecutionBudget(
            max_operations=_optional_int(budget_data, "max_operations"),
            consumed_operations=_int(budget_data, "consumed_operations"),
        ),
        active_remainders=tuple(
            _remainder_from_data(item)
            for item in _mapping_sequence(value, "active_remainders")
        ),
        plan=_plan_from_data(_mapping(value, "plan")),
        artifacts_by_ref={
            key: _artifact_from_data(item)
            for key, item in _mapping_map(value, "artifacts_by_ref").items()
        },
        public_outputs={
            key: _artifact_from_data(item)
            for key, item in _mapping_map(value, "public_outputs").items()
        },
    )


def _plan_to_data(plan: ExecutionPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "blueprint_id": plan.blueprint_id,
        "blueprint_version": plan.blueprint_version,
        "objective": plan.objective,
        "state": plan.state.value,
        "nodes": [
            {
                "node_id": item.node_id,
                "module_id": item.module_id,
                "operation_id": item.operation_id,
                "operation_version": item.operation_version,
                "input_bindings": dict(item.input_bindings),
                "output_schemas": dict(item.output_schemas),
                "output_bindings": dict(item.output_bindings),
                "contextual_roles": list(item.contextual_roles),
            }
            for item in plan.nodes
        ],
        "edges": [
            {
                "producer_node_id": item.producer_node_id,
                "producer_output": item.producer_output,
                "consumer_node_id": item.consumer_node_id,
                "consumer_input": item.consumer_input,
                "artifact_ref": item.artifact_ref,
                "schema": item.schema,
            }
            for item in plan.edges
        ],
        "external_artifacts": {
            key: _artifact_to_data(item)
            for key, item in plan.external_artifacts.items()
        },
        "remainders": [_remainder_to_data(item) for item in plan.remainders],
    }


def _plan_from_data(value: Mapping[str, Any]) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id=_text(value, "plan_id"),
        blueprint_id=_text(value, "blueprint_id"),
        blueprint_version=_int(value, "blueprint_version"),
        objective=_text(value, "objective"),
        state=PlanState(_text(value, "state")),
        nodes=tuple(
            PlanNode(
                node_id=_text(item, "node_id"),
                module_id=_text(item, "module_id"),
                operation_id=_text(item, "operation_id"),
                operation_version=_text(item, "operation_version"),
                input_bindings=_text_mapping(item, "input_bindings"),
                output_schemas=_text_mapping(item, "output_schemas"),
                output_bindings=_text_mapping(item, "output_bindings"),
                contextual_roles=tuple(
                    _int_sequence(item, "contextual_roles")
                ),
            )
            for item in _mapping_sequence(value, "nodes")
        ),
        edges=tuple(
            PlanEdge(
                producer_node_id=_text(item, "producer_node_id"),
                producer_output=_text(item, "producer_output"),
                consumer_node_id=_text(item, "consumer_node_id"),
                consumer_input=_text(item, "consumer_input"),
                artifact_ref=_text(item, "artifact_ref"),
                schema=_text(item, "schema"),
            )
            for item in _mapping_sequence(value, "edges")
        ),
        external_artifacts={
            key: _artifact_from_data(item)
            for key, item in _mapping_map(value, "external_artifacts").items()
        },
        remainders=tuple(
            _remainder_from_data(item)
            for item in _mapping_sequence(value, "remainders")
        ),
    )


def _artifact_to_data(artifact: Artifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "schema": artifact.schema,
        "payload": _json_value(artifact.payload),
        "producer_module": artifact.producer_module,
        "producer_operation": artifact.producer_operation,
        "provenance": list(artifact.provenance),
    }


def _artifact_from_data(value: Mapping[str, Any]) -> Artifact:
    return Artifact(
        artifact_id=_text(value, "artifact_id"),
        schema=_text(value, "schema"),
        payload=_mapping(value, "payload"),
        producer_module=_optional_text(value, "producer_module"),
        producer_operation=_optional_text(value, "producer_operation"),
        provenance=_text_tuple(value, "provenance"),
    )


def _remainder_to_data(remainder: Remainder) -> dict[str, Any]:
    return {
        "remainder_id": remainder.remainder_id,
        "kind": remainder.kind.value,
        "description": remainder.description,
        "required_for": remainder.required_for,
        "resolvable": remainder.resolvable,
        "suggested_capability": remainder.suggested_capability,
        "status": remainder.status,
    }


def _remainder_from_data(value: Mapping[str, Any]) -> Remainder:
    resolvable = value.get("resolvable")
    if resolvable is not None and not isinstance(resolvable, bool):
        raise TypeError("remainder resolvable is not boolean or null")
    return Remainder(
        remainder_id=_text(value, "remainder_id"),
        kind=RemainderKind(_text(value, "kind")),
        description=_text(value, "description"),
        required_for=_text(value, "required_for"),
        resolvable=resolvable,
        suggested_capability=_optional_text(value, "suggested_capability"),
        status=_text(value, "status"),
    )


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash_body(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_json_value(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Checkpoint payload is not JSON-compatible: {type(value).__name__}")


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise TypeError(f"{key} is not an object")
    return item


def _mapping_map(
    value: Mapping[str, Any], key: str
) -> dict[str, Mapping[str, Any]]:
    root = _mapping(value, key)
    result = {}
    for name, item in root.items():
        if not isinstance(name, str) or not isinstance(item, Mapping):
            raise TypeError(f"{key} must map text keys to objects")
        result[name] = item
    return result


def _mapping_sequence(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise TypeError(f"{key} is not an array")
    if any(not isinstance(item, Mapping) for item in items):
        raise TypeError(f"{key} contains a non-object")
    return tuple(items)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text or null")
    return item


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise TypeError(f"{key} is not an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid text")
    return tuple(items)


def _text_mapping(value: Mapping[str, Any], key: str) -> dict[str, str]:
    root = _mapping(value, key)
    if any(
        not isinstance(name, str)
        or not isinstance(item, str)
        or not name.strip()
        or not item.strip()
        for name, item in root.items()
    ):
        raise ValueError(f"{key} must map non-empty text to non-empty text")
    return dict(root)


def _int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise TypeError(f"{key} is not an integer")
    return item


def _optional_int(value: Mapping[str, Any], key: str) -> int | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, int) or isinstance(item, bool):
        raise TypeError(f"{key} is not an integer or null")
    return item


def _int_sequence(value: Mapping[str, Any], key: str) -> tuple[int, ...]:
    items = value.get(key)
    if not isinstance(items, list):
        raise TypeError(f"{key} is not an array")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in items):
        raise TypeError(f"{key} contains a non-integer")
    return tuple(items)
