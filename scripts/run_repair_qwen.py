"""Live smokes for deliberately rejected Diamond evidence bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.contracts import Artifact, EffectGrant  # noqa: E402
from fresta_diamond.controller import DiamondController  # noqa: E402
from fresta_diamond.effects import EffectBroker, ExecutionContext  # noqa: E402
from fresta_diamond.llm_evidence import LlmEvidenceRepairOperation  # noqa: E402
from fresta_diamond.llm_learning import (  # noqa: E402
    LEARNING_REPAIR_REQUEST_SCHEMA,
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    learning_repair_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.registry import ModuleRegistry  # noqa: E402
from fresta_diamond.ontology import (  # noqa: E402
    OntologicalValidator,
    decode_structural_evidence_graph,
)


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(json_ready(item) for item in value)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Force one isolated canonical repair with local Qwen."
    )
    parser.add_argument(
        "--path", choices=("learning", "evidence"), default="learning"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=3_000)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    adapter = OpenAICompatibleChatAdapter(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )
    if args.path == "evidence":
        return run_evidence_repair(adapter, args)
    registry = ModuleRegistry()
    manifest = llm_learning_manifest(adapter.required_permissions)
    registry.discover(manifest)
    if not registry.verify(manifest.module_id).admitted:
        raise RuntimeError("Learning provider was not admitted")
    registry.enable(manifest.module_id, {
        manifest.operations[0].operation_id: LlmLearningStructuralOperation(),
        manifest.operations[1].operation_id: LlmLearningEpistemicOperation(),
        manifest.operations[2].operation_id: LlmLearningRepairOperation(
            max_tokens=args.max_tokens
        ),
    })
    responses = []

    def recording_adapter(grant, **kwargs):
        response = adapter(grant, **kwargs)
        responses.append(dict(response))
        return response

    controller = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": recording_adapter}),
    )
    proposal = {
        "proposal_id": "learn-proposal:forced-repair",
        "selection_id": "selection:forced-repair",
        "source_sheet_id": "forced-repair",
        "source_revision_id": "forced-repair-v1",
        "objective": "Repair an invalid observation classification conservatively.",
        "proposal_state": "PROPOSED",
        "promotion_authority": False,
        "candidates": [{
            "candidate_id": "candidate:reported-fact",
            "source_element_id": "claim:reported-fact",
            "kind": "CLAIM",
            "content": "Segundo este documento, Roma é a capital de Itália.",
            "scope": "scope:test:forced-repair",
            "provenance": ["document:synthetic:forced-repair"],
            "contextual_roles": [1, 2, 3],
            "status": "UNVALIDATED",
        }],
    }
    request = Artifact(
        schema=LEARNING_REPAIR_REQUEST_SCHEMA,
        payload={
            "learning_proposal": proposal,
            "original_bundle": {
                "structural_evidence": {"manifestations": []},
                "candidate_assessments": [{
                    "source_element_id": "claim:reported-fact",
                    "classification_id": "OBSERVATION",
                }],
            },
            "parent_artifact_id": "artifact:deliberately-rejected",
            "repair_attempt": 1,
            "validator_remainders": [{
                "kind": "MISSING_EVIDENCE",
                "required_for": "claim:reported-fact",
                "description": "OBSERVATION requires a direct observation event",
            }],
        },
    )
    result = controller.execute(
        learning_repair_blueprint(adapter.required_permissions),
        "Repair one deliberately rejected learning bundle",
        {"repair_request": request},
    )
    structural = result.execution.artifacts.get("structural_evidence")
    payload = structural.payload if structural is not None else {}
    summary = {
        "model_calls": len(responses),
        "structural_closed": result.execution.closure.structural_closed,
        "epistemic_closed": result.execution.closure.epistemic_closed,
        "repair_actions": payload.get("_repair_actions", ()),
        "repair_action_errors": payload.get("_repair_action_errors", ()),
        "remainders": [item.description for item in result.execution.remainders],
    }
    print(json.dumps(json_ready(summary), ensure_ascii=False, indent=2), flush=True)
    if args.debug and responses:
        print("\n--- raw model response ---")
        print(responses[-1].get("content"), flush=True)
    return 0 if not summary["repair_action_errors"] else 1


def run_evidence_repair(
    adapter: OpenAICompatibleChatAdapter,
    args: argparse.Namespace,
) -> int:
    grant = EffectGrant(
        plan_id="plan:forced-evidence-repair",
        node_id="node:forced-evidence-repair",
        module_id="local-qwen",
        operation_id="three-orders.repair-evidence",
        effects=("llm.generate",),
        permissions=adapter.required_permissions,
    )
    responses = []

    def recording_adapter(effect_grant, **kwargs):
        response = adapter(effect_grant, **kwargs)
        responses.append(dict(response))
        return response

    operation = LlmEvidenceRepairOperation(max_tokens=args.max_tokens)
    result = operation({
        "repair_request": {
            "analysis_id": "analysis:forced-evidence-repair",
            "object_ref": "object:forced-evidence-repair",
            "scope": "scope:test:forced-evidence-repair",
            "object_text": (
                "A incompletude é condição de possibilidade da diferenciação."
            ),
            "analysis_depth": "CONSTITUTIONAL",
            "parent_artifact_id": "artifact:deliberately-rejected",
            "repair_attempt": 1,
            "original_graph": {
                "analysis_id": "analysis:rejected",
                "manifestations": [],
            },
            "validator_remainders": [{
                "kind": "INVALID_DIRECTION",
                "required_for": "grounding:rejected",
                "description": (
                    "Grounding must preserve OPENNESS -> FILTER -> OBJECT"
                ),
            }],
        }
    }, ExecutionContext(grant, {"llm.generate": recording_adapter}))
    payload = result["evidence"]
    report = OntologicalValidator().validate(
        decode_structural_evidence_graph(payload)
    )
    summary = {
        "model_calls": len(responses),
        "structural_closed": report.structural_closed,
        "constitutional_closed": report.constitutional_closed,
        "repair_actions": payload.get("_repair_actions", ()),
        "repair_action_errors": payload.get("_repair_action_errors", ()),
        "remainders": [item.description for item in report.active_remainders],
    }
    print(json.dumps(json_ready(summary), ensure_ascii=False, indent=2), flush=True)
    if args.debug and responses:
        print("\n--- raw model response ---")
        print(responses[-1].get("content"), flush=True)
    return 0 if (
        report.structural_closed
        and report.constitutional_closed
        and not summary["repair_action_errors"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
