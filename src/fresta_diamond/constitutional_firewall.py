"""Constitutional binding and bounded semantic intake for Diamond analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import os
import re
from typing import Callable
import unicodedata
from uuid import uuid4


FIREWALL_ID = "fresta.constitutional-firewall"
FIREWALL_POLICY_VERSION = 3
FIREWALL_ATTESTATION_SCHEMA = "fresta://constitutional-firewall-attestation@1"
_RELEASE_BUILD_ENV = "FRESTA_DIAMOND_RELEASE_BUILD"


class FirewallMode(str, Enum):
    BOUND = "BOUND"
    DEVELOPMENT_BYPASS = "DEVELOPMENT_BYPASS"


class FirewallDecision(str, Enum):
    PASS = "PASS"
    SAFE_TRANSFORM = "SAFE_TRANSFORM"
    QUARANTINE = "QUARANTINE"
    DENY = "DENY"


class SemanticDisposition(str, Enum):
    OPERATIONAL_INSTRUCTION = "OPERATIONAL_INSTRUCTION"
    BENIGN_REFERENCE = "BENIGN_REFERENCE"
    AMBIGUOUS = "AMBIGUOUS"


class ConstitutionalFirewallError(RuntimeError):
    """The kernel cannot establish its constitutional analysis boundary."""


class FirewallInterventionError(ConstitutionalFirewallError):
    """One bounded analysis was denied or quarantined before resolution."""

    def __init__(self, attestation: "FirewallAttestation") -> None:
        self.analysis_id = attestation.analysis_id
        self.decision = attestation.decision
        super().__init__(
            f"Constitutional firewall decision: {attestation.decision.value}"
        )


@dataclass(frozen=True)
class FirewallSemanticRequest:
    """Host-anchored request; the analyzer cannot choose kernel authority."""

    objective: str
    input_digest: str
    heuristic_ids: tuple[str, ...]


@dataclass(frozen=True)
class FirewallSemanticProposal:
    """Contextual O1/O2/O3 proposal interpreted deterministically by the host."""

    disposition: SemanticDisposition
    manifestation: str
    relation: str
    constraint: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.manifestation, self.relation, self.constraint)
        ):
            raise ConstitutionalFirewallError(
                "Firewall semantic proposal requires non-empty O1/O2/O3 analysis"
            )


FirewallSemanticAnalyzer = Callable[
    [FirewallSemanticRequest], FirewallSemanticProposal
]


@dataclass(frozen=True)
class ConstitutionalRiskNomination:
    """Deterministic risk nomination; it has no decision authority."""

    input_digest: str
    heuristic_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    @property
    def activated(self) -> bool:
        return bool(self.heuristic_ids)


@dataclass(frozen=True)
class _Heuristic:
    heuristic_id: str
    reason_code: str
    patterns: tuple[str, ...]


_HEURISTICS = (
    _Heuristic(
        "AE-H001",
        "UNBOUNDED_AUTHORITY_REQUEST",
        (
            r"\bfaz(?:es)?\s+tudo\s+(?:o\s+)?que\s+eu\s+(?:quero|mandar)",
            r"\bobedece(?:r)?\s+sem\s+(?:limites|questionar)",
            r"\bdo\s+(?:anything|everything)\s+i\s+(?:say|want)",
            r"\bunconditional(?:ly)?\s+obey",
            r"\baceita\s+todas\s+as\s+minhas\s+ordens",
            r"\b(?:minha\s+autoridade|autoridade\s+do\s+utilizador).{0,32}\babsoluta",
            r"\bfollow\s+every\s+(?:instruction|order)",
            r"\b(?:my|user)\s+authority.{0,32}\babsolute",
        ),
    ),
    _Heuristic(
        "AE-H002",
        "COGNITIVE_DEGRADATION_REQUEST",
        (
            r"\b(?:es|se|sejas|fica|torna-te)\s+(?:uma?\s+)?(?:llm\s+)?burra",
            r"\bnao\s+(?:penses|analises|questiones)",
            r"\b(?:be|become)\s+(?:a\s+)?(?:dumb|stupid)\s+(?:llm|model|assistant)",
            r"\b(?:stop|do not|don't)\s+(?:thinking|reasoning|questioning)",
        ),
    ),
    _Heuristic(
        "AE-H003",
        "CONSTITUTIONAL_BYPASS_REQUEST",
        (
            r"\b(?:ignora|desativa|remove|contorna)\s+(?:a\s+|o\s+)?(?:firewall|kernel|gatekeeper|controller)",
            r"\b(?:ignore|disable|remove|bypass)\s+(?:the\s+)?(?:firewall|kernel|gatekeeper|controller)",
            r"\b(?:desliga|suspende|anula|sobrepoe|contorna).{0,40}(?:protecao\s+constitucional|salvaguardas|restricoes\s+de\s+seguranca|gatekeeper|firewall|kernel)",
            r"\b(?:turn\s+off|override|suspend|circumvent).{0,40}(?:constitutional\s+protection|safeguards|guardrails|safety\s+controls|gatekeeper|firewall|kernel)",
        ),
    ),
    _Heuristic(
        "AE-H004",
        "MEMORY_AUTHORITY_BYPASS_REQUEST",
        (
            r"\b(?:escreve|promove).{0,48}(?:memoria|cartao).{0,48}(?:diretamente|sem\s+validar)",
            r"\b(?:write|promote).{0,48}(?:memory|card).{0,48}(?:directly|without\s+validation)",
        ),
    ),
    _Heuristic(
        "AE-H005",
        "EVIDENCE_FORGERY_REQUEST",
        (
            r"\b(?:inventa|falsifica).{0,48}(?:proveniencia|evidencia|validacao)",
            r"\b(?:invent|forge|fake)\b.{0,48}(?:provenance|evidence|validation)",
            r"\b(?:reescreve|altera).{0,48}(?:evidencia|proveniencia).{0,48}(?:validada|confirmada|legitima)",
            r"\b(?:rewrite|alter).{0,48}(?:evidence|provenance).{0,48}(?:validated|confirmed|legitimate)",
        ),
    ),
)


@dataclass(frozen=True)
class FirewallAttestation:
    """Immutable witness attached to one bounded controller analysis."""

    analysis_id: str
    input_digest: str
    integrity_digest: str
    mode: FirewallMode
    constitutionally_valid: bool
    activated: bool
    decision: FirewallDecision
    reason_codes: tuple[str, ...]
    attestation_id: str
    firewall_id: str = FIREWALL_ID
    policy_version: int = FIREWALL_POLICY_VERSION
    schema: str = FIREWALL_ATTESTATION_SCHEMA
    present: bool = True
    integrity_verified: bool = True

    def __post_init__(self) -> None:
        if not self.analysis_id.strip() or not self.attestation_id.strip():
            raise ConstitutionalFirewallError(
                "Firewall attestation identity is incomplete"
            )
        for label, digest in (
            ("input", self.input_digest),
            ("integrity", self.integrity_digest),
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest.lower()
            ):
                raise ConstitutionalFirewallError(
                    f"Firewall {label} digest is invalid"
                )
        expected_validity = (
            self.mode is FirewallMode.BOUND
            and self.decision
            in {FirewallDecision.PASS, FirewallDecision.SAFE_TRANSFORM}
        )
        if self.constitutionally_valid is not expected_validity:
            raise ConstitutionalFirewallError(
                "Firewall mode and constitutional validity contradict each other"
            )
        if not self.present or not self.integrity_verified:
            raise ConstitutionalFirewallError(
                "An attestation cannot claim an absent or unverified firewall"
            )
        if self.decision is FirewallDecision.PASS:
            if self.activated or self.reason_codes:
                raise ConstitutionalFirewallError(
                    "A PASS attestation cannot claim an activated intervention"
                )
        elif not self.activated or not self.reason_codes:
            raise ConstitutionalFirewallError(
                "A non-PASS decision requires an activated, reasoned intervention"
            )

    @property
    def bound(self) -> bool:
        return (
            self.present
            and self.integrity_verified
            and self.mode is FirewallMode.BOUND
        )

    @property
    def allows_execution(self) -> bool:
        return (
            self.mode is FirewallMode.DEVELOPMENT_BYPASS
            or self.decision
            in {FirewallDecision.PASS, FirewallDecision.SAFE_TRANSFORM}
        )


@dataclass(frozen=True)
class ConstitutionalFirewall:
    """Mandatory kernel boundary; deep inspection remains a later layer.

    ``development_bypass`` is temporary prototype scaffolding.  It never
    produces a constitutionally valid result and is rejected in release mode.
    """

    development_bypass: bool = False
    semantic_analyzer: FirewallSemanticAnalyzer | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    id_factory: Callable[[], str] = field(
        default=lambda: str(uuid4()),
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            self.development_bypass
            and os.environ.get(_RELEASE_BUILD_ENV, "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            raise ConstitutionalFirewallError(
                "Development firewall bypass is forbidden in a release build"
            )

    @property
    def integrity_digest(self) -> str:
        heuristic_material = tuple(
            f"{item.heuristic_id}:{item.reason_code}:{','.join(item.patterns)}"
            for item in _HEURISTICS
        )
        material = "|".join((
            FIREWALL_ID,
            str(FIREWALL_POLICY_VERSION),
            FIREWALL_ATTESTATION_SCHEMA,
            "analysis-presence-required",
            "development-bypass-is-not-constitutional",
            *heuristic_material,
        ))
        return sha256(material.encode("utf-8")).hexdigest()

    def open_analysis(self, objective: str) -> FirewallAttestation:
        """Bind one objective before resolver, model, or module analysis runs."""

        if not isinstance(objective, str) or not objective.strip():
            raise ConstitutionalFirewallError(
                "A non-empty objective is required for firewall binding"
            )
        attestation_id = self.id_factory()
        if not isinstance(attestation_id, str) or not attestation_id.strip():
            raise ConstitutionalFirewallError(
                "Firewall attestation ID factory returned an invalid ID"
            )
        mode = (
            FirewallMode.DEVELOPMENT_BYPASS
            if self.development_bypass
            else FirewallMode.BOUND
        )
        input_digest = sha256(objective.encode("utf-8")).hexdigest()
        nomination = nominate_constitutional_risks(objective)
        matches = tuple(
            item for item in _HEURISTICS
            if item.heuristic_id in nomination.heuristic_ids
        )
        decision, reason_codes = self._derive_decision(
            objective,
            input_digest,
            matches,
        )
        return FirewallAttestation(
            analysis_id=f"analysis:{attestation_id}",
            input_digest=input_digest,
            integrity_digest=self.integrity_digest,
            mode=mode,
            constitutionally_valid=(
                mode is FirewallMode.BOUND
                and decision
                in {FirewallDecision.PASS, FirewallDecision.SAFE_TRANSFORM}
            ),
            activated=bool(matches),
            decision=decision,
            reason_codes=reason_codes,
            attestation_id=attestation_id,
        )

    def _derive_decision(
        self,
        objective: str,
        input_digest: str,
        matches: tuple[_Heuristic, ...],
    ) -> tuple[FirewallDecision, tuple[str, ...]]:
        if not matches:
            return FirewallDecision.PASS, ()
        risk_codes = tuple(dict.fromkeys(item.reason_code for item in matches))
        if self.semantic_analyzer is None:
            return (
                FirewallDecision.QUARANTINE,
                risk_codes + ("SEMANTIC_REVIEW_REQUIRED",),
            )
        try:
            proposal = self.semantic_analyzer(FirewallSemanticRequest(
                objective=objective,
                input_digest=input_digest,
                heuristic_ids=tuple(item.heuristic_id for item in matches),
            ))
            if not isinstance(proposal, FirewallSemanticProposal):
                raise ConstitutionalFirewallError(
                    "Firewall semantic analyzer returned an invalid proposal"
                )
        except Exception:
            return (
                FirewallDecision.QUARANTINE,
                risk_codes + ("SEMANTIC_REVIEW_FAILED",),
            )
        if proposal.disposition is SemanticDisposition.BENIGN_REFERENCE:
            return FirewallDecision.SAFE_TRANSFORM, ("BENIGN_REFERENCE",)
        if proposal.disposition is SemanticDisposition.OPERATIONAL_INSTRUCTION:
            return FirewallDecision.DENY, risk_codes
        return FirewallDecision.QUARANTINE, risk_codes + ("AMBIGUOUS_INTENT",)


def nominate_constitutional_risks(text: str) -> ConstitutionalRiskNomination:
    """Nominate bounded review risks without deciding intent or admissibility."""

    if not isinstance(text, str):
        raise TypeError("Constitutional risk input must be text")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )
    normalized = normalized.translate(str.maketrans({
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
    }))
    matches = tuple(
        heuristic
        for heuristic in _HEURISTICS
        if any(re.search(pattern, normalized) for pattern in heuristic.patterns)
    )
    return ConstitutionalRiskNomination(
        input_digest=sha256(text.encode("utf-8")).hexdigest(),
        heuristic_ids=tuple(item.heuristic_id for item in matches),
        reason_codes=tuple(dict.fromkeys(item.reason_code for item in matches)),
    )


def _match_heuristics(objective: str) -> tuple[_Heuristic, ...]:
    """Compatibility helper retained for internal tests during the transition."""

    nomination = nominate_constitutional_risks(objective)
    return tuple(
        item for item in _HEURISTICS
        if item.heuristic_id in nomination.heuristic_ids
    )
