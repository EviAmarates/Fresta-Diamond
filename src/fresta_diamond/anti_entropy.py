"""Fail-closed, observable module-admission policy.

The policy derives operational compatibility from trusted discovery context and
declared contracts.  It deliberately does not attempt to infer intent or claim
that in-process Python is a security sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from fresta_diamond.contracts import ModuleManifest, Remainder, RemainderKind


class ModuleSource(str, Enum):
    BUILTIN = "BUILTIN"
    LOCAL = "LOCAL"
    COMMUNITY = "COMMUNITY"


@dataclass(frozen=True)
class ModuleDiscoveryEvidence:
    """Evidence supplied by the trusted loader, never by the candidate module."""

    source: ModuleSource
    provenance: tuple[str, ...] = ()
    package_digest: str | None = None

    @classmethod
    def builtin(cls) -> "ModuleDiscoveryEvidence":
        return cls(
            source=ModuleSource.BUILTIN,
            provenance=("runtime:builtin-registration",),
        )


@dataclass(frozen=True)
class ModuleAdmissionReport:
    module_id: str
    admitted: bool
    source: ModuleSource
    remainders: tuple[Remainder, ...] = ()


_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class ModuleAdmissionPolicy:
    """Minimum constitutional boundary for module authority."""

    forbidden_capabilities: tuple[str, ...] = (
        "kernel.replace",
        "kernel.mutate",
        "validator.override",
        "module.trust_mutate",
        "journal.rewrite",
        "journal.delete",
        "memory.write",
        "memory.direct_write",
        "memory.confirmed.write",
        "memory.promote",
        "provenance.remove",
        "controller.replace",
        "controller.mutate",
        "effect_broker.replace",
        "effect_broker.mutate",
        "gatekeeper.override",
        "blueprint.override",
    )
    forbidden_effects: tuple[str, ...] = (
        "kernel.replace",
        "kernel.mutate",
        "validator.override",
        "module.trust_mutate",
        "journal.rewrite",
        "journal.delete",
        "memory.write",
        "memory.direct_write",
        "memory.confirmed.write",
        "memory.promote",
        "provenance.remove",
        "controller.replace",
        "controller.mutate",
        "effect_broker.replace",
        "effect_broker.mutate",
        "gatekeeper.override",
        "blueprint.override",
    )
    forbidden_permissions: tuple[str, ...] = (
        "kernel.replace",
        "kernel.mutate",
        "validator.override",
        "module.trust_mutate",
        "journal.rewrite",
        "journal.delete",
        "memory.write",
        "memory.direct_write",
        "memory.confirmed.write",
        "memory.promote",
        "provenance.remove",
        "controller.replace",
        "controller.mutate",
        "effect_broker.replace",
        "effect_broker.mutate",
        "gatekeeper.override",
        "blueprint.override",
    )

    def evaluate(
        self,
        manifest: ModuleManifest,
        evidence: ModuleDiscoveryEvidence,
    ) -> ModuleAdmissionReport:
        violations: list[Remainder] = []

        if not manifest.kernel_contract.strip() or not manifest.sdk_contract.strip():
            violations.append(self._violation(
                manifest, "Kernel and SDK contracts must be explicit."
            ))
        if not manifest.operations:
            violations.append(self._violation(
                manifest, "A module must declare at least one operation."
            ))

        if evidence.source is not ModuleSource.BUILTIN and not evidence.provenance:
            violations.append(self._violation(
                manifest,
                f"{evidence.source.value.lower()} module provenance was not demonstrated.",
            ))
        if evidence.source is ModuleSource.COMMUNITY:
            if evidence.package_digest is None or not _DIGEST.fullmatch(
                evidence.package_digest
            ):
                violations.append(self._violation(
                    manifest,
                    "Community module requires a loader-verified SHA-256 package digest.",
                ))

        for operation in manifest.operations:
            self._check_unique(
                manifest, operation.operation_id, "capability",
                operation.capabilities, violations,
            )
            self._check_unique(
                manifest, operation.operation_id, "effect",
                operation.effects, violations,
            )
            self._check_unique(
                manifest, operation.operation_id, "permission",
                operation.permissions, violations,
            )
            self._check_forbidden(
                manifest, operation.operation_id, "capability",
                operation.capabilities, self.forbidden_capabilities, violations,
            )
            self._check_forbidden(
                manifest, operation.operation_id, "effect",
                operation.effects, self.forbidden_effects, violations,
            )
            self._check_forbidden(
                manifest, operation.operation_id, "permission",
                operation.permissions, self.forbidden_permissions, violations,
            )
            if evidence.source is ModuleSource.COMMUNITY and operation.effects:
                if not operation.permissions:
                    violations.append(self._violation(
                        manifest,
                        f"Effectful community operation {operation.operation_id!r} "
                        "does not declare a permission boundary.",
                    ))
                if not operation.failure_modes:
                    violations.append(self._violation(
                        manifest,
                        f"Effectful community operation {operation.operation_id!r} "
                        "does not declare failure modes.",
                    ))

        return ModuleAdmissionReport(
            module_id=manifest.module_id,
            admitted=not violations,
            source=evidence.source,
            remainders=tuple(violations),
        )

    @staticmethod
    def _violation(manifest: ModuleManifest, description: str) -> Remainder:
        return Remainder(
            kind=RemainderKind.POLICY_VIOLATION,
            description=description,
            required_for=f"module-admission:{manifest.module_id}",
            resolvable=True,
        )

    def _check_unique(
        self,
        manifest: ModuleManifest,
        operation_id: str,
        label: str,
        values: tuple[str, ...],
        violations: list[Remainder],
    ) -> None:
        if len(values) != len(set(values)):
            violations.append(self._violation(
                manifest,
                f"Operation {operation_id!r} contains duplicate {label} declarations.",
            ))

    def _check_forbidden(
        self,
        manifest: ModuleManifest,
        operation_id: str,
        label: str,
        values: tuple[str, ...],
        forbidden: tuple[str, ...],
        violations: list[Remainder],
    ) -> None:
        for value in values:
            match = next(
                (item for item in forbidden if _same_identifier_family(value, item)),
                None,
            )
            if match is not None:
                violations.append(self._violation(
                    manifest,
                    f"Operation {operation_id!r} requests forbidden {label} "
                    f"{value!r} ({match}).",
                ))


def _same_identifier_family(value: str, protected: str) -> bool:
    return value == protected or any(
        value.startswith(f"{protected}{separator}")
        for separator in ("@", ":", "/")
    )
