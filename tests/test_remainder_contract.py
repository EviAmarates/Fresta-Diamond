"""Canonical remainder vocabulary and temporary compatibility boundary."""

from fresta_diamond.contracts import (
    PhiKind,
    PhiRemainder,
    Remainder,
    RemainderKind,
)


def test_finite_remainder_uses_non_phi_canonical_vocabulary() -> None:
    remainder = Remainder(
        kind=RemainderKind.MISSING_INPUT,
        description="A bounded input is absent",
        required_for="test-node",
        resolvable=True,
    )

    assert remainder.remainder_id
    assert remainder.kind is RemainderKind.MISSING_INPUT


def test_pre_persistence_aliases_are_read_compatible() -> None:
    remainder = PhiRemainder(
        kind=PhiKind.CONSTITUTIONAL_REMAINDER,
        description="Irreducible constitutional opening",
        required_for="constitutional-closure",
        resolvable=False,
    )

    assert isinstance(remainder, Remainder)
    assert PhiKind is RemainderKind
    assert remainder.phi_id == remainder.remainder_id
