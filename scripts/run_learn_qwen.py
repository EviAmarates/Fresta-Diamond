"""Manual workspace -> learn proposal -> local-Qwen evaluation run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.anti_entropy import (  # noqa: E402
    ModuleDiscoveryEvidence,
    ModuleSource,
)
from fresta_diamond.cognitive_workspace import (  # noqa: E402
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.controller import DiamondController  # noqa: E402
from fresta_diamond.contracts import Artifact  # noqa: E402
from fresta_diamond.effects import EffectBroker  # noqa: E402
from fresta_diamond.learning import (  # noqa: E402
    build_workspace_learn_request,
    register_workspace_learn_provider,
)
from fresta_diamond.llm_learning import (  # noqa: E402
    LlmLearningEpistemicOperation,
    LlmLearningRepairOperation,
    LlmLearningStructuralOperation,
    LEARNING_REPAIR_REQUEST_SCHEMA,
    learning_evaluation_blueprint,
    learning_repair_blueprint,
    llm_learning_manifest,
)
from fresta_diamond.registry import ModuleRegistry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one bounded learning candidate through local Qwen."
    )
    parser.add_argument("--object", required=True, help="Candidate text.")
    parser.add_argument(
        "--kind",
        choices=tuple(item.value.lower() for item in SheetElementKind),
        default="claim",
    )
    parser.add_argument("--scope", default="scope:manual-learn")
    parser.add_argument("--provenance", default="manual:user-supplied")
    parser.add_argument(
        "--objective",
        default="Evaluate this candidate without assuming it is true.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--repair-attempts",
        type=int,
        choices=(0, 1, 2),
        default=1,
    )
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
    registry = ModuleRegistry()
    register_workspace_learn_provider(registry)

    with TemporaryDirectory(prefix="fresta-diamond-learn-") as temporary:
        workspace = JsonlCognitiveWorkspace(temporary)
        workspace.save(SheetRevision(
            sheet_id="manual-learn",
            revision_number=1,
            title="Manual learning candidate",
            state=SheetState.STAGED,
            elements=(SheetElement(
                element_id="candidate:manual",
                kind=SheetElementKind(args.kind.upper()),
                content=args.object,
                scope=args.scope,
                provenance=(args.provenance,),
            ),),
        ))
        selection, selection_artifact = workspace.select(
            "manual-learn",
            ("candidate:manual",),
            objective=args.objective,
        )
        request = build_workspace_learn_request(selection, selection_artifact)
        intake = DiamondController(registry).execute(
            request.blueprint, request.objective, request.inputs
        )

    learning_proposal = intake.execution.artifacts["learning_proposal"]
    manifest = llm_learning_manifest(adapter.required_permissions)
    registry.discover(
        manifest,
        ModuleDiscoveryEvidence(
            source=ModuleSource.LOCAL,
            provenance=("runtime:local-qwen-adapter",),
        ),
    )
    admission = registry.verify(manifest.module_id)
    if not admission.admitted:
        raise SystemExit("Local learning provider was rejected")
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: LlmLearningStructuralOperation(
                max_tokens=args.max_tokens
            ),
            manifest.operations[1].operation_id: LlmLearningEpistemicOperation(),
            manifest.operations[2].operation_id: LlmLearningRepairOperation(
                max_tokens=args.max_tokens
            ),
        },
    )
    controller = DiamondController(
        registry,
        effect_broker=EffectBroker({"llm.generate": adapter}),
    )
    print(
        f"[Diamond /learn] model={args.model} scope={args.scope} "
        f"kind={args.kind.upper()}",
        flush=True,
    )
    result = controller.execute(
        learning_evaluation_blueprint(adapter.required_permissions),
        args.objective,
        {"learning_proposal": learning_proposal},
    )
    print_result(result, version="V1", debug=args.debug)

    for attempt in range(1, args.repair_attempts + 1):
        closure = result.execution.closure
        if closure.structural_closed is True and closure.epistemic_closed is True:
            break
        structural = result.execution.artifacts.get("structural_evidence")
        if structural is None or not result.execution.remainders:
            break
        print(
            f"\n[Diamond /learn] repair attempt "
            f"{attempt}/{args.repair_attempts}",
            flush=True,
        )
        repair_request = Artifact(
            schema=LEARNING_REPAIR_REQUEST_SCHEMA,
            payload={
                "learning_proposal": learning_proposal.payload,
                "original_bundle": structural.payload["_provider_bundle"],
                "parent_artifact_id": structural.artifact_id,
                "repair_attempt": attempt,
                "validator_remainders": [
                    {
                        "kind": item.kind.value,
                        "required_for": item.required_for,
                        "description": item.description,
                    }
                    for item in result.execution.remainders
                ],
            },
            provenance=(structural.artifact_id,),
        )
        result = controller.execute(
            learning_repair_blueprint(adapter.required_permissions),
            f"Repair learning evidence, attempt {attempt}",
            {"repair_request": repair_request},
        )
        print_result(result, version=f"V{attempt + 1}", debug=args.debug)

    closure = result.execution.closure
    return 0 if (
        closure.structural_closed is True
        and closure.epistemic_closed is True
    ) else 2


def print_result(result, *, version: str, debug: bool) -> None:
    closure = result.execution.closure
    summary = {
        "plan_state": result.plan.state.value,
        "authorization_state": result.authorization.state.value,
        "execution_state": result.execution.state.value,
        "technical_completed": closure.technical_completed,
        "operational_converged": closure.operational_converged,
        "structural_closed": closure.structural_closed,
        "constitutional_closed": closure.constitutional_closed,
        "epistemic_closed": closure.epistemic_closed,
        "ontological_reports": len(result.ontological_reports),
        "epistemic_reports": len(result.epistemic_reports),
        "remainders": [
            {
                "kind": item.kind.value,
                "required_for": item.required_for,
                "description": item.description,
            }
            for item in result.execution.remainders
        ],
    }
    print(f"\n--- Diamond /learn verdict {version} ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if debug:
        for name in ("structural_evidence", "epistemic_evidence"):
            artifact = result.execution.artifacts.get(name)
            if artifact is not None:
                print(f"\n--- {name} raw provider response ---")
                print(artifact.payload.get("_provider_raw"))


if __name__ == "__main__":
    raise SystemExit(main())
