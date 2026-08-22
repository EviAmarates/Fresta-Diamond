from __future__ import annotations

from hashlib import sha256

import pytest

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.contracts import (
    ModuleManifest,
    OperationContract,
    RemainderKind,
    TrustState,
)
from fresta_diamond.journal import EventJournal, JournalEventKind
from fresta_diamond.registry import ModuleRegistry


def operation(
    *,
    capability: str = "text.normalize@1",
    effects: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    failure_modes: tuple[str, ...] = (),
) -> OperationContract:
    return OperationContract(
        operation_id="example.normalize",
        version="1.0.0",
        capabilities=(capability,),
        inputs={"source": "artifact://text@1"},
        outputs={"result": "artifact://text@1"},
        effects=effects,
        permissions=permissions,
        failure_modes=failure_modes,
    )


def manifest(contract: OperationContract | None = None) -> ModuleManifest:
    return ModuleManifest(
        module_id="example",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(contract or operation(),),
    )


def community_evidence(**overrides) -> ModuleDiscoveryEvidence:
    values = {
        "source": ModuleSource.COMMUNITY,
        "provenance": ("https://example.test/example",),
        "package_digest": sha256(b"candidate-package").hexdigest(),
    }
    values.update(overrides)
    return ModuleDiscoveryEvidence(**values)


def test_builtin_module_is_derived_as_admissible() -> None:
    registry = ModuleRegistry()
    registry.discover(manifest())

    report = registry.verify("example")

    assert report.admitted is True
    assert report.remainders == ()
    assert registry.state("example") is TrustState.VERIFIED
    assert registry.admission_report("example") is report


@pytest.mark.parametrize(
    "evidence",
    [
        ModuleDiscoveryEvidence(source=ModuleSource.COMMUNITY),
        ModuleDiscoveryEvidence(
            source=ModuleSource.COMMUNITY,
            provenance=("https://example.test/example",),
            package_digest="self-declared-compatible",
        ),
    ],
)
def test_community_module_without_loader_evidence_is_rejected(
    evidence: ModuleDiscoveryEvidence,
) -> None:
    registry = ModuleRegistry()
    candidate = manifest()
    registry.discover(candidate, evidence)

    report = registry.verify("example")

    assert report.admitted is False
    assert registry.state("example") is TrustState.REJECTED
    assert all(
        item.kind is RemainderKind.POLICY_VIOLATION
        for item in report.remainders
    )
    with pytest.raises(PermissionError):
        registry.enable("example", {"example.normalize": lambda *_: {}})


def test_community_module_with_loader_evidence_can_be_admitted() -> None:
    registry = ModuleRegistry()
    registry.discover(manifest(), community_evidence())

    report = registry.verify("example")

    assert report.admitted is True
    assert registry.state("example") is TrustState.VERIFIED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability", "validator.override@1"),
        ("effect", "memory.confirmed.write"),
        ("permission", "journal.rewrite:all"),
        ("capability", "controller.mutate@1"),
        ("effect", "effect_broker.replace"),
        ("permission", "gatekeeper.override:crystallization"),
    ],
)
def test_constitutional_bypass_is_rejected_for_every_source(
    field: str,
    value: str,
) -> None:
    values = {
        "capability": "text.normalize@1",
        "effects": (),
        "permissions": (),
    }
    if field == "capability":
        values["capability"] = value
    elif field == "effect":
        values["effects"] = (value,)
    else:
        values["permissions"] = (value,)
    registry = ModuleRegistry()
    registry.discover(manifest(operation(**values)))

    report = registry.verify("example")

    assert report.admitted is False
    assert registry.state("example") is TrustState.REJECTED
    assert value in report.remainders[0].description


def test_effectful_community_operation_declares_boundary_and_failure_modes() -> None:
    registry = ModuleRegistry()
    registry.discover(
        manifest(operation(effects=("network.read",))),
        community_evidence(),
    )

    report = registry.verify("example")

    assert report.admitted is False
    descriptions = {item.description for item in report.remainders}
    assert any("permission boundary" in item for item in descriptions)
    assert any("failure modes" in item for item in descriptions)


def test_admission_decision_is_journalled_without_package_contents() -> None:
    journal = EventJournal()
    registry = ModuleRegistry(journal=journal)
    registry.discover(
        manifest(operation(capability="kernel.replace@1")),
        community_evidence(),
    )

    registry.verify("example")

    assert [event.kind for event in journal.events] == [
        JournalEventKind.MODULE_DISCOVERED,
        JournalEventKind.MODULE_REJECTED,
    ]
    assert journal.events[0].payload["source"] == "COMMUNITY"
    assert "package_digest" not in journal.events[0].payload
    assert journal.events[1].payload["admitted"] is False
