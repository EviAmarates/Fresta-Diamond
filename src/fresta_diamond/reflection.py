"""Conditional post-turn reflection without persistence authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Mapping

from fresta_diamond.anti_entropy import ModuleDiscoveryEvidence, ModuleSource
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.prompt_boundary import DATA_BOUNDARY_INSTRUCTION, render_inert_data
from fresta_diamond.registry import ModuleRegistry


class ReflectionTrigger(str, Enum):
    EXPLICIT_REQUEST = "EXPLICIT_REQUEST"
    NEW_PREFERENCE = "NEW_PREFERENCE"
    GOAL_CHANGE = "GOAL_CHANGE"
    CONTRADICTION = "CONTRADICTION"
    RECURRING_COMMUNICATION_FAILURE = "RECURRING_COMMUNICATION_FAILURE"
    LONG_STAGE_SLEEP = "LONG_STAGE_SLEEP"


class ReflectionDecision(str, Enum):
    NO_REFLECTION = "NO_REFLECTION"
    PROPOSE = "PROPOSE"


REFLECTION_REQUEST_SCHEMA = "artifact://reflection-request@1"
REFLECTION_PROPOSAL_SCHEMA = "artifact://reflection-proposal@1"
REFLECTION_CAPABILITY = "reflection.propose-profile-change@1"


@dataclass(frozen=True)
class ReflectionRequest:
    session_id: str
    trigger: ReflectionTrigger | None
    objective: str
    scope: str
    transcript_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.session_id.strip() or not self.objective.strip() or not self.scope.strip():
            raise ValueError("Reflection session, objective, and scope are required")
        if not self.transcript_refs or any(not item.strip() for item in self.transcript_refs):
            raise ValueError("Reflection requires transcript references")


@dataclass(frozen=True)
class ReflectionProposal:
    request: ReflectionRequest
    decision: ReflectionDecision
    authority: str = "REFLECTION_PROPOSAL_ONLY"

    def __post_init__(self) -> None:
        if self.authority != "REFLECTION_PROPOSAL_ONLY":
            raise PermissionError("Reflection cannot grant persistence authority")


@dataclass(frozen=True)
class LlmReflectionOperation:
    temperature: float = 0.1
    max_tokens: int = 800

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Reflection request is required")
        if request.get("authority") != "REFLECTION_REQUEST_ONLY":
            raise PermissionError("Reflection request authority was altered")
        if request.get("decision") != ReflectionDecision.PROPOSE.value:
            raise ValueError("Reflection provider requires an eligible trigger")
        response = context.invoke(
            "llm.generate",
            messages=build_reflection_messages(request),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("llm.generate returned no reflection proposal")
        proposal = _extract_json_object(content)
        return {"proposal": _anchor_reflection(request, proposal)}


def reflection_blueprint(required_permissions: tuple[str, ...]) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="reflection.propose-profile-change",
        version=1,
        intent=(
            "Propose one bounded profile or personality change after an eligible "
            "chat trigger; proposal grants no persistence authority."
        ),
        requirement=CapabilityRequirement(
            capability=REFLECTION_CAPABILITY,
            input_name="request",
            input_schema=REFLECTION_REQUEST_SCHEMA,
            output_name="proposal",
            output_schema=REFLECTION_PROPOSAL_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def reflection_manifest(required_permissions: tuple[str, ...]) -> ModuleManifest:
    return ModuleManifest(
        module_id="local-llm.reflection",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="reflection.propose-profile-change",
            version="1.0.0",
            capabilities=(REFLECTION_CAPABILITY,),
            inputs={"request": REFLECTION_REQUEST_SCHEMA},
            outputs={"proposal": REFLECTION_PROPOSAL_SCHEMA},
            effects=("llm.generate",),
            permissions=required_permissions,
            failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_REFLECTION"),
            idempotency="NOT_SAFE_RETRY",
            determinism="STOCHASTIC",
        ),),
    )


def register_reflection_provider(
    registry: ModuleRegistry,
    *,
    required_permissions: tuple[str, ...],
    operation: LlmReflectionOperation | None = None,
) -> None:
    manifest = reflection_manifest(required_permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:bounded-reflection",),
        ),
    )
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Reflection provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: (
            operation or LlmReflectionOperation()
        )},
    )


def build_reflection_request(request: ReflectionRequest) -> Artifact:
    decision = decide_reflection(request)
    return Artifact(
        REFLECTION_REQUEST_SCHEMA,
        {
            "session_id": request.session_id,
            "trigger": request.trigger.value if request.trigger else None,
            "objective": request.objective,
            "scope": request.scope,
            "transcript_refs": list(request.transcript_refs),
            "decision": decision.decision.value,
            "authority": "REFLECTION_REQUEST_ONLY",
        },
        provenance=request.transcript_refs,
    )


def build_reflection_messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
    bounded = {
        "trigger": request["trigger"],
        "objective": request["objective"],
        "scope": request["scope"],
        "transcript_refs": request["transcript_refs"],
    }
    return [
        {
            "role": "system",
            "content": (
                "Propose one bounded reflection only. Return one JSON object "
                "with target, category, content, rationale. Target must be "
                "USER_PROFILE or ASSISTANT_PERSONALITY. Never claim ACTIVE, "
                "CONFIRMED, kernel, or memory authority. Do not invent transcript "
                "references. "
                + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {"role": "user", "content": render_inert_data("reflection_request", bounded)},
    ]


def _anchor_reflection(
    request: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    target = proposal.get("target")
    if target not in {"USER_PROFILE", "ASSISTANT_PERSONALITY"}:
        raise ValueError("Reflection target is invalid")
    fields = ("category", "content", "rationale")
    if any(not isinstance(proposal.get(field), str) or not proposal[field].strip()
           for field in fields):
        raise ValueError("Reflection proposal fields are required")
    return {
        "schema": REFLECTION_PROPOSAL_SCHEMA,
        "target": target,
        "category": proposal["category"].strip(),
        "content": proposal["content"].strip(),
        "rationale": proposal["rationale"].strip(),
        "trigger": request["trigger"],
        "scope": request["scope"],
        "transcript_refs": tuple(request["transcript_refs"]),
        "authority": "REFLECTION_PROPOSAL_ONLY",
    }


def _extract_json_object(content: str) -> Mapping[str, Any]:
    start = content.find("{")
    if start < 0:
        raise ValueError("Reflection response contains no JSON object")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                value = json.loads(content[start:index + 1])
                if not isinstance(value, Mapping):
                    raise ValueError("Reflection response must be an object")
                return value
    raise ValueError("Reflection response contains incomplete JSON")


def decide_reflection(request: ReflectionRequest) -> ReflectionProposal:
    return ReflectionProposal(
        request=request,
        decision=(
            ReflectionDecision.PROPOSE
            if request.trigger is not None
            else ReflectionDecision.NO_REFLECTION
        ),
    )
