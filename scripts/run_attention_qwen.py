"""Manual live Qwen turn through Diamond attention and controller contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.attention_continuation import (  # noqa: E402
    JsonAttentionContinuationStore,
)
from fresta_diamond.attention_memory import AttentionMemory  # noqa: E402
from fresta_diamond.attention_prompt import (  # noqa: E402
    AttentionPromptPreparationOperation,
    AttentionResponseOperation,
    build_attention_turn_request,
    register_attention_prompt_provider,
)
from fresta_diamond.attention_resolution import (  # noqa: E402
    AttentionMaterializationService,
    CompositeAttentionResolver,
    WorkspaceAttentionResolver,
)
from fresta_diamond.cognitive_workspace import (  # noqa: E402
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.controller import DiamondController  # noqa: E402
from fresta_diamond.effects import EffectBroker  # noqa: E402
from fresta_diamond.registry import ModuleRegistry  # noqa: E402


DEFAULT_BASE_URL = "http://127.0.0.1:1234"
DEFAULT_MODEL = "qwen/qwen3-14b"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one bounded local-LLM response through Diamond attention."
        )
    )
    parser.add_argument(
        "--note",
        default=(
            "A car converts energy into motion and preserves a functional "
            "identity through the organization of its components."
        ),
        help="Temporary workspace evidence supplied to attention.",
    )
    parser.add_argument(
        "--instruction",
        default=(
            "Briefly explain what the memory supports and what remains "
            "unvalidated."
        ),
    )
    parser.add_argument(
        "--objective",
        default="Interpret a bounded note without promoting it to knowledge.",
    )
    parser.add_argument("--scope", default="scope:manual-attention")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--attention-tokens", type=int, default=2_000)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--unresolved-source",
        action="store_true",
        help=(
            "Add one unresolved source ref, forcing PARTIAL projection and "
            "durable continuation before the model call."
        ),
    )
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
    with TemporaryDirectory(prefix="fresta-diamond-attention-") as root:
        data_root = Path(root)
        workspace = JsonlCognitiveWorkspace(data_root / "workspace")
        workspace.save(SheetRevision(
            sheet_id="manual",
            revision_id="revision:manual:1",
            revision_number=1,
            title="Manual bounded note",
            state=SheetState.DRAFT,
            elements=(SheetElement(
                element_id="note:manual:1",
                kind=SheetElementKind.NOTE,
                content=args.note,
                scope=args.scope,
                provenance=("operator:manual-run",),
                contextual_roles=(1, 2),
            ),),
            objective_ref="objective:manual-attention",
        ))
        attention_memory = AttentionMemory(data_root / "attention")
        context = attention_memory.create(
            objective=args.objective,
            scope=args.scope,
            summary=(
                "One unvalidated workspace note is in current attention."
            ),
            source_refs=(
                ("source:manual:unresolved",)
                if args.unresolved_source else ()
            ),
            workspace_sheet_refs=("sheet:manual",),
        )
        continuation_store = JsonAttentionContinuationStore(
            data_root / "continuations"
        )
        materializer = AttentionMaterializationService(
            CompositeAttentionResolver((
                WorkspaceAttentionResolver(workspace),
            )),
            continuation_store=continuation_store,
        )
        registry = ModuleRegistry()
        register_attention_prompt_provider(
            registry,
            preparation=AttentionPromptPreparationOperation(
                attention_memory,
                materializer,
                max_attention_tokens=args.attention_tokens,
            ),
            response=AttentionResponseOperation(max_tokens=args.max_tokens),
            granted_permissions=adapter.required_permissions,
        )
        model_calls = 0

        def counted_adapter(grant, **kwargs):
            nonlocal model_calls
            model_calls += 1
            return adapter(grant, **kwargs)

        request = build_attention_turn_request(
            context_id=context.context_id,
            context_ref=context.context_ref,
            objective=context.objective,
            instruction=args.instruction,
            token_budget=args.attention_tokens,
            granted_permissions=adapter.required_permissions,
        )
        result = DiamondController(
            registry,
            effect_broker=EffectBroker({"llm.generate": counted_adapter}),
        ).execute(
            request.blueprint,
            request.objective,
            request.inputs,
        )
        prompt = result.execution.artifacts.get("prompt")
        response = result.execution.artifacts.get("response")
        summary = {
            "execution_state": result.execution.state.value,
            "technical_completed": (
                result.execution.closure.technical_completed
            ),
            "operational_converged": (
                result.execution.closure.operational_converged
            ),
            "projection_state": (
                prompt.payload.get("projection_state")
                if prompt is not None else None
            ),
            "continuation_checkpoint_id": (
                prompt.payload.get("continuation_checkpoint_id")
                if prompt is not None else None
            ),
            "model_called": model_calls > 0,
            "model_call_count": model_calls,
            "remainders": [
                {
                    "kind": item.kind.value,
                    "description": item.description,
                }
                for item in result.execution.remainders
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if response is not None:
            print("\n--- response ---")
            print(response.payload["content"])
        return 0 if response is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
