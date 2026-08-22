"""Manual bounded Qwen run through the real Diamond controller path."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.contracts import (  # noqa: E402
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.controller import DiamondController  # noqa: E402
from fresta_diamond.effects import EffectBroker  # noqa: E402
from fresta_diamond.llm_evidence import (  # noqa: E402
    ANALYSIS_REQUEST_SCHEMA,
    EVIDENCE_REPAIR_CAPABILITY,
    EVIDENCE_REPAIR_REQUEST_SCHEMA,
    EVIDENCE_CAPABILITY,
    LlmEvidenceOperation,
    LlmEvidenceRepairOperation,
)
from fresta_diamond.ontology import (  # noqa: E402
    STRUCTURAL_EVIDENCE_SCHEMA,
    AnalysisDepth,
)
from fresta_diamond.registry import ModuleRegistry  # noqa: E402


DEFAULT_BASE_URL = "http://127.0.0.1:1234"
DEFAULT_MODEL = "qwen/qwen3-14b"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a local Qwen to propose a graph and let Diamond validate it."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--object", help="Text/object to analyze.")
    source.add_argument("--file", type=Path, help="UTF-8 text file to analyze.")
    parser.add_argument(
        "--depth",
        choices=("contextual", "constitutional"),
        default="contextual",
        help="How far the analysis is explicitly required to ground itself.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scope", default="scope:manual-qwen-run")
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--repair-attempts",
        type=bounded_repair_attempts,
        default=1,
        help="Number of validator-guided repair calls after the initial proposal (0-3).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print the raw model response after the Diamond verdict.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    object_text = load_object_text(args)
    depth = AnalysisDepth(args.depth.upper())
    object_hash = hashlib.sha256(object_text.encode("utf-8")).hexdigest()[:16]
    object_ref = f"object:manual:{object_hash}"
    analysis_id = f"analysis:{uuid4()}"

    adapter = OpenAICompatibleChatAdapter(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )
    proposal_operation = OperationContract(
        operation_id="local-qwen.propose-evidence",
        version="1.0.0",
        capabilities=(EVIDENCE_CAPABILITY,),
        inputs={"request": ANALYSIS_REQUEST_SCHEMA},
        outputs={"evidence": STRUCTURAL_EVIDENCE_SCHEMA},
        effects=("llm.generate",),
        permissions=adapter.required_permissions,
        determinism="STOCHASTIC",
        cost=args.max_tokens,
    )
    repair_operation = OperationContract(
        operation_id="local-qwen.repair-evidence",
        version="1.0.0",
        capabilities=(EVIDENCE_REPAIR_CAPABILITY,),
        inputs={"repair_request": EVIDENCE_REPAIR_REQUEST_SCHEMA},
        outputs={"evidence": STRUCTURAL_EVIDENCE_SCHEMA},
        effects=("llm.generate",),
        permissions=adapter.required_permissions,
        determinism="STOCHASTIC",
        cost=args.max_tokens,
    )
    manifest = ModuleManifest(
        module_id="local-qwen",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(proposal_operation, repair_operation),
    )
    registry = ModuleRegistry()
    registry.discover(manifest)
    registry.verify(manifest.module_id)
    registry.enable(
        manifest.module_id,
        {
            proposal_operation.operation_id: LlmEvidenceOperation(
                max_tokens=args.max_tokens
            ),
            repair_operation.operation_id: LlmEvidenceRepairOperation(
                max_tokens=args.max_tokens
            ),
        },
    )
    proposal_blueprint = BlueprintSpec(
        blueprint_id=f"manual-qwen-{depth.value.lower()}",
        version=1,
        intent="Propose and validate a bounded Three-Order evidence graph",
        requirement=CapabilityRequirement(
            capability=EVIDENCE_CAPABILITY,
            input_name="request",
            input_schema=ANALYSIS_REQUEST_SCHEMA,
            output_name="evidence",
            output_schema=STRUCTURAL_EVIDENCE_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=adapter.required_permissions,
    )
    repair_blueprint = BlueprintSpec(
        blueprint_id=f"manual-qwen-repair-{depth.value.lower()}",
        version=1,
        intent="Repair one rejected evidence graph from typed remainders",
        requirement=CapabilityRequirement(
            capability=EVIDENCE_REPAIR_CAPABILITY,
            input_name="repair_request",
            input_schema=EVIDENCE_REPAIR_REQUEST_SCHEMA,
            output_name="evidence",
            output_schema=STRUCTURAL_EVIDENCE_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=adapter.required_permissions,
    )
    broker = EffectBroker({"llm.generate": adapter})
    controller = DiamondController(registry, effect_broker=broker)
    request_artifact = Artifact(
        schema=ANALYSIS_REQUEST_SCHEMA,
        payload={
            "analysis_id": analysis_id,
            "object_ref": object_ref,
            "scope": args.scope,
            "object_text": object_text,
            "analysis_depth": depth.value,
        },
    )

    print(
        f"[Diamond] model={args.model} depth={depth.value} "
        f"object_ref={object_ref}",
        flush=True,
    )
    result = controller.execute(
        proposal_blueprint,
        f"Analyze {object_ref} at {depth.value} depth",
        {"request": request_artifact},
    )
    print_summary(result, version="V1")
    print_raw(result, enabled=args.debug, version="V1")

    for attempt in range(1, args.repair_attempts + 1):
        if result.execution.closure.structural_closed is True:
            break
        evidence = result.execution.artifacts.get("evidence")
        if evidence is None or not result.execution.remainders:
            break
        print(f"\n[Diamond] repair attempt {attempt}/{args.repair_attempts}", flush=True)
        repair_request = Artifact(
            schema=EVIDENCE_REPAIR_REQUEST_SCHEMA,
            payload={
                "analysis_id": f"{analysis_id}:repair:{attempt}",
                "object_ref": object_ref,
                "scope": args.scope,
                "object_text": object_text,
                "analysis_depth": depth.value,
                "parent_artifact_id": evidence.artifact_id,
                "repair_attempt": attempt,
                "original_graph": canonical_graph_payload(evidence.payload),
                "validator_remainders": remainder_payload(result),
            },
            provenance=(evidence.artifact_id,),
        )
        result = controller.execute(
            repair_blueprint,
            f"Repair evidence for {object_ref}, attempt {attempt}",
            {"repair_request": repair_request},
        )
        version = f"V{attempt + 1}"
        print_summary(result, version=version)
        print_raw(result, enabled=args.debug, version=version)

    return 0 if result.execution.closure.structural_closed is True else 2


def load_object_text(args: argparse.Namespace) -> str:
    if args.file is not None:
        text = args.file.read_text(encoding="utf-8")
    elif args.object is not None:
        text = args.object
    else:
        text = input("Objeto/texto a analisar: ")
    if not text.strip():
        raise SystemExit("The analyzed object cannot be empty.")
    return text.strip()


def bounded_repair_attempts(value: str) -> int:
    attempts = int(value)
    if not 0 <= attempts <= 3:
        raise argparse.ArgumentTypeError("repair attempts must be between 0 and 3")
    return attempts


def canonical_graph_payload(payload) -> dict:
    keys = (
        "analysis_id",
        "object_ref",
        "scope",
        "analysis_depth",
        "manifestations",
        "relations",
        "constraints",
        "filters",
        "excluded_costs",
        "groundings",
        "advisory_model_closed",
    )
    return {
        key: json_ready(payload[key])
        for key in keys
        if key in payload
    }


def json_ready(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(json_ready(item) for item in value)
    return value


def remainder_payload(result) -> list[dict[str, str]]:
    return [
        {
            "kind": item.kind.value,
            "required_for": item.required_for,
            "description": item.description,
        }
        for item in result.execution.remainders
    ]


def print_summary(result, *, version: str) -> None:
    closure = result.execution.closure
    payload = {
        "plan_state": result.plan.state.value,
        "authorization_state": result.authorization.state.value,
        "execution_state": result.execution.state.value,
        "technical_completed": closure.technical_completed,
        "operational_converged": closure.operational_converged,
        "structural_closed": closure.structural_closed,
        "constitutional_closed": closure.constitutional_closed,
        "ontological_reports": len(result.ontological_reports),
        "remainders": [
            {
                "kind": item.kind.value,
                "required_for": item.required_for,
                "description": item.description,
            }
            for item in result.execution.remainders
        ],
    }
    print(f"\n--- Diamond verdict {version} ---")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_raw(result, *, enabled: bool, version: str) -> None:
    evidence = result.execution.artifacts.get("evidence")
    if not enabled or evidence is None:
        return
    raw = evidence.payload.get("_provider_raw")
    if raw:
        print(f"\n--- raw model response {version} ---")
        print(raw)


if __name__ == "__main__":
    raise SystemExit(main())
