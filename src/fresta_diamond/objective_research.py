"""Bounded model proposals for objective-relative Web research queries."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

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


OBJECTIVE_RESEARCH_QUERY_REQUEST_SCHEMA = (
    "artifact://objective-research-query-request@1"
)
OBJECTIVE_RESEARCH_QUERY_SCHEMA = "artifact://objective-research-query@1"
OBJECTIVE_RESEARCH_QUERY_CAPABILITY = "research.propose-objective-queries@1"


@dataclass(frozen=True)
class LlmObjectiveResearchQueryOperation:
    max_tokens: int = 1_000

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("request")
        if not isinstance(request, Mapping):
            raise ValueError("Objective research query request is required")
        objective = _text(request, "objective")
        scope = _text(request, "scope")
        retrieval_hint = request.get("retrieval_hint", "")
        if not isinstance(retrieval_hint, str):
            raise ValueError("Objective research retrieval hint is invalid")
        max_queries = request.get("max_queries", 4)
        if (
            not isinstance(max_queries, int)
            or isinstance(max_queries, bool)
            or not 1 <= max_queries <= 6
        ):
            raise ValueError("Objective research query budget is invalid")
        response = context.invoke(
            "llm.generate",
            messages=_messages(objective, scope, max_queries, retrieval_hint),
            temperature=0.1,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("llm.generate returned no query proposal")
        payload = _extract_object(content)
        raw_queries = payload.get("queries")
        if not isinstance(raw_queries, list) or not raw_queries:
            raise ValueError("Query proposal must contain a non-empty queries array")
        if len(raw_queries) > max_queries:
            raise ValueError("Query proposal exceeds its budget")
        queries = []
        for item in raw_queries:
            if not isinstance(item, Mapping):
                raise ValueError("Research query must be an object")
            query_id = _query_id(item)
            text = _text(item, "text")
            purpose = _text(item, "purpose")
            preferences = item.get("preferred_source_types")
            if not isinstance(preferences, list) or not preferences:
                raise ValueError("Research query lacks source preferences")
            if any(not isinstance(value, str) or not value.strip() for value in preferences):
                raise ValueError("Research query source preferences are invalid")
            if len(text) > 1_000:
                raise ValueError("Research query exceeds the text budget")
            queries.append({
                "query_id": query_id,
                "text": text,
                "purpose": purpose,
                "preferred_source_types": preferences,
                "reveals_candidate_label": False,
                "intent": "NEUTRAL",
            })
        if len({item["query_id"] for item in queries}) != len(queries):
            raise ValueError("Research query IDs must be unique")
        return {"query_proposal": {
            "objective": objective,
            "scope": scope,
            "queries": queries,
            "authority": "UNVALIDATED_QUERY_PROPOSAL",
            "promotion_authority": False,
        }}


def objective_research_query_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="workspace.propose-objective-research",
        version=1,
        intent="Propose bounded neutral Web queries for one objective.",
        requirement=CapabilityRequirement(
            capability=OBJECTIVE_RESEARCH_QUERY_CAPABILITY,
            input_name="request",
            input_schema=OBJECTIVE_RESEARCH_QUERY_REQUEST_SCHEMA,
            output_name="query_proposal",
            output_schema=OBJECTIVE_RESEARCH_QUERY_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def objective_research_query_manifest(
    required_permissions: tuple[str, ...],
) -> ModuleManifest:
    return ModuleManifest(
        module_id="llm-objective-research",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(OperationContract(
            operation_id="llm-objective-research.propose",
            version="1.0.0",
            capabilities=(OBJECTIVE_RESEARCH_QUERY_CAPABILITY,),
            inputs={"request": OBJECTIVE_RESEARCH_QUERY_REQUEST_SCHEMA},
            outputs={"query_proposal": OBJECTIVE_RESEARCH_QUERY_SCHEMA},
            effects=("llm.generate",),
            permissions=required_permissions,
            failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_RESPONSE"),
            determinism="STOCHASTIC",
        ),),
    )


def research_query_request(
    objective: str,
    scope: str,
    *,
    max_queries: int = 4,
    retrieval_hint: str = "",
) -> Artifact:
    if not objective.strip() or not scope.strip():
        raise ValueError("Objective research request fields are required")
    return Artifact(
        schema=OBJECTIVE_RESEARCH_QUERY_REQUEST_SCHEMA,
        payload={
            "objective": objective,
            "scope": scope,
            "max_queries": max_queries,
            "retrieval_hint": retrieval_hint,
        },
    )


def decode_research_query_proposal(
    artifact: Artifact,
) -> tuple[Mapping[str, Any], ...]:
    if artifact.schema != OBJECTIVE_RESEARCH_QUERY_SCHEMA:
        raise ValueError("Unknown objective research query schema")
    payload = artifact.payload
    nested = payload.get("query_proposal")
    if isinstance(nested, Mapping):
        payload = nested
    if payload.get("authority") != "UNVALIDATED_QUERY_PROPOSAL":
        raise PermissionError("Query proposal authority is invalid")
    if payload.get("promotion_authority") is not False:
        raise PermissionError("Query proposal cannot grant promotion")
    queries = payload.get("queries")
    if not isinstance(queries, (list, tuple)) or not queries:
        raise ValueError("Query proposal contains no queries")
    return tuple(queries)


def register_objective_research_query_provider(
    registry: ModuleRegistry,
    operation: LlmObjectiveResearchQueryOperation,
    required_permissions: tuple[str, ...],
) -> None:
    manifest = objective_research_query_manifest(required_permissions)
    registry.discover(manifest)
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Objective research query provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: operation},
    )


def _messages(
    objective: str,
    scope: str,
    max_queries: int,
    retrieval_hint: str,
) -> tuple[Mapping[str, str], ...]:
    return (
        {
            "role": "system",
            "content": (
                "Propose neutral Web search queries for a bounded objective. "
                "Return only one JSON object with a queries array. Each item "
                "must contain query_id, text, purpose, and "
                "preferred_source_types. Do not claim facts, authority, or "
                "promotion. Do not reveal a candidate label because none is "
                "provided.\n\n"
                + DATA_BOUNDARY_INSTRUCTION
            ),
        },
        {
            "role": "user",
            "content": render_inert_data("objective_research_request", {
                "objective": objective,
                "scope": scope,
                "max_queries": max_queries,
                "retrieval_hint": retrieval_hint,
            }),
        },
    )


def _extract_object(content: str) -> Mapping[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        candidate = candidate.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("Query proposal is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("Query proposal must be a JSON object")
    return value


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item.strip()


def _query_id(value: Mapping[str, Any]) -> str:
    item = value.get("query_id")
    if isinstance(item, bool) or not isinstance(item, (int, str)):
        raise ValueError("query_id must be non-empty text or integer")
    normalized = str(item).strip()
    if not normalized:
        raise ValueError("query_id must be non-empty text or integer")
    return normalized
