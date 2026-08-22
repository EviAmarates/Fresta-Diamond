"""Manifest-first module registry for the Diamond prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping

from fresta_diamond.anti_entropy import (
    ModuleAdmissionPolicy,
    ModuleAdmissionReport,
    ModuleDiscoveryEvidence,
)
from fresta_diamond.contracts import ModuleManifest, OperationContract, TrustState
from fresta_diamond.journal import EventJournal, JournalEventKind

if TYPE_CHECKING:
    from fresta_diamond.effects import ExecutionContext


OperationHandler = Callable[[Mapping[str, Any], "ExecutionContext"], Mapping[str, Mapping[str, Any]]]


@dataclass(frozen=True)
class RegisteredOperation:
    module_id: str
    contract: OperationContract
    handler: OperationHandler


class ModuleRegistry:
    """Discover metadata first and bind code only after explicit enablement."""

    def __init__(
        self,
        *,
        admission_policy: ModuleAdmissionPolicy | None = None,
        journal: EventJournal | None = None,
    ) -> None:
        self._manifests: dict[str, ModuleManifest] = {}
        self._states: dict[str, TrustState] = {}
        self._discovery_evidence: dict[str, ModuleDiscoveryEvidence] = {}
        self._admission_reports: dict[str, ModuleAdmissionReport] = {}
        self._handlers: dict[tuple[str, str], OperationHandler] = {}
        self._admission_policy = admission_policy or ModuleAdmissionPolicy()
        self._journal = journal

    def discover(
        self,
        manifest: ModuleManifest,
        evidence: ModuleDiscoveryEvidence | None = None,
    ) -> None:
        if manifest.module_id in self._manifests:
            raise ValueError(f"Duplicate module ID: {manifest.module_id}")
        self._manifests[manifest.module_id] = manifest
        self._states[manifest.module_id] = TrustState.DISCOVERED
        self._discovery_evidence[manifest.module_id] = (
            evidence or ModuleDiscoveryEvidence.builtin()
        )
        self._record(
            JournalEventKind.MODULE_DISCOVERED,
            manifest,
            payload={
                "source": self._discovery_evidence[manifest.module_id].source.value,
                "operation_count": len(manifest.operations),
            },
        )

    def verify(self, module_id: str) -> ModuleAdmissionReport:
        manifest = self._require_manifest(module_id)
        if self._states[module_id] not in {TrustState.DISCOVERED, TrustState.QUARANTINED}:
            raise ValueError(f"Module cannot be verified from {self._states[module_id].value}")
        report = self._admission_policy.evaluate(
            manifest, self._discovery_evidence[module_id]
        )
        self._admission_reports[module_id] = report
        self._states[module_id] = (
            TrustState.VERIFIED if report.admitted else TrustState.REJECTED
        )
        self._record(
            JournalEventKind.MODULE_ADMITTED
            if report.admitted else JournalEventKind.MODULE_REJECTED,
            manifest,
            payload={
                "source": report.source.value,
                "admitted": report.admitted,
                "violations": tuple(
                    {
                        "kind": item.kind.value,
                        "description": item.description,
                    }
                    for item in report.remainders
                ),
            },
        )
        return report

    def enable(self, module_id: str, handlers: Mapping[str, OperationHandler]) -> None:
        manifest = self._require_manifest(module_id)
        if self._states[module_id] != TrustState.VERIFIED:
            raise PermissionError("Only a verified module may load executable handlers")
        expected = {operation.operation_id for operation in manifest.operations}
        supplied = set(handlers)
        if supplied != expected:
            raise ValueError(
                f"Handler bindings do not match manifest: missing={sorted(expected - supplied)}, "
                f"unknown={sorted(supplied - expected)}"
            )
        for operation_id, handler in handlers.items():
            if not callable(handler):
                raise TypeError(f"Handler is not callable: {operation_id}")
            self._handlers[(module_id, operation_id)] = handler
        self._states[module_id] = TrustState.ENABLED

    def disable(self, module_id: str) -> None:
        self._require_manifest(module_id)
        self._states[module_id] = TrustState.DISABLED
        for key in [key for key in self._handlers if key[0] == module_id]:
            self._handlers.pop(key, None)

    def state(self, module_id: str) -> TrustState:
        self._require_manifest(module_id)
        return self._states[module_id]

    def admission_report(self, module_id: str) -> ModuleAdmissionReport:
        self._require_manifest(module_id)
        try:
            return self._admission_reports[module_id]
        except KeyError as exc:
            raise KeyError(f"Module has not been verified: {module_id}") from exc

    def capability_candidates(self, capability: str) -> tuple[tuple[str, OperationContract], ...]:
        candidates = []
        for module_id, manifest in self._manifests.items():
            if self._states[module_id] != TrustState.ENABLED:
                continue
            for operation in manifest.operations:
                if capability in operation.capabilities:
                    candidates.append((module_id, operation))
        return tuple(sorted(candidates, key=lambda item: (item[1].cost, item[0], item[1].operation_id)))

    def operation(self, module_id: str, operation_id: str) -> RegisteredOperation:
        manifest = self._require_manifest(module_id)
        if self._states[module_id] != TrustState.ENABLED:
            raise PermissionError(f"Module is not enabled: {module_id}")
        contract = next(
            (item for item in manifest.operations if item.operation_id == operation_id), None
        )
        handler = self._handlers.get((module_id, operation_id))
        if contract is None or handler is None:
            raise KeyError(f"Operation is not bound: {module_id}:{operation_id}")
        return RegisteredOperation(module_id, contract, handler)

    def _require_manifest(self, module_id: str) -> ModuleManifest:
        try:
            return self._manifests[module_id]
        except KeyError as exc:
            raise KeyError(f"Unknown module: {module_id}") from exc

    def _record(
        self,
        kind: JournalEventKind,
        manifest: ModuleManifest,
        *,
        payload: Mapping[str, Any],
    ) -> None:
        if self._journal is None:
            return
        self._journal.append(
            kind,
            correlation_id=(
                f"module-admission:{manifest.module_id}:{manifest.version}"
            ),
            subject_ref=f"module:{manifest.module_id}",
            payload=payload,
        )
