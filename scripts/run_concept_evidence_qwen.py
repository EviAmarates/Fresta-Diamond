"""Isolated live smoke for concept evidence with deterministic seed memory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DIAMOND_ROOT / "src"))

from fresta_diamond.adapters import OpenAICompatibleChatAdapter  # noqa: E402
from fresta_diamond.application import DiamondApplication  # noqa: E402
from fresta_diamond.concepts import ConceptSignature, ConceptState  # noqa: E402


SEED_PERMISSION = ("llm.model:deterministic-concept-seed",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed two ACTIVE crystals deterministically, then make exactly "
            "one local-model call for concept evidence and validation."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234")
    parser.add_argument("--model", default="qwen/qwen3-14b")
    parser.add_argument("--max-tokens", type=int, default=4_000)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--resolve-gaps",
        action="store_true",
        help="Research exact missing seals, learn sources, and re-evaluate.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Optional isolated root; omitted uses a temporary directory.",
    )
    return parser.parse_args()


def seed_bundle(element_id: str, description: str) -> dict:
    return {
        "structural_evidence": {
            "analysis_id": "seed:model-value-is-reanchored",
            "object_ref": "seed:model-value-is-reanchored",
            "scope": "scope:diamond-smoke:cars",
            "analysis_depth": "CONTEXTUAL",
            "manifestations": [{
                "manifestation_id": "m1",
                "object_ref": "seed:model-value-is-reanchored",
                "description": description,
                "provenance": ["document:synthetic-concept-seed"],
            }],
            "relations": [{
                "relation_id": "r1",
                "manifestation_id": "m1",
                "constraint_id": "c1",
                "forward_justification": (
                    "The bounded statement is explicitly present in the source."
                ),
                "constraint_effect": (
                    "Only the source-attested functional statement remains."
                ),
                "return_witness": "The claim remains tied to its source.",
                "excluded_cost_id": "cost1",
                "scope": "scope:diamond-smoke:cars",
            }],
            "constraints": [{
                "constraint_id": "c1",
                "description": "Preserve bounded scope and provenance.",
                "scope": "scope:diamond-smoke:cars",
            }],
            "filters": [{
                "filter_id": "f1",
                "constraint_id": "c1",
                "manifestation_id": "m1",
                "excluded_cost_id": "cost1",
                "selection_justification": (
                    "Rejects meanings not attested by the supplied statement."
                ),
            }],
            "excluded_costs": [{
                "cost_id": "cost1",
                "description": "Loss of bounded source meaning.",
                "excluded_alternatives": ["unsupported generalization"],
            }],
            "groundings": [],
            "advisory_model_closed": True,
        },
        "candidate_assessments": [{
            "source_element_id": element_id,
            "claim_mode": "ATTESTATION",
            "premise_refs": [],
            "applied_constraints": [],
            "derivation_direction": None,
            "test_criterion": None,
            "horizon": None,
            "assumptions": [],
            "counterexample_searches": [],
        }],
    }


def run(root: Path, args: argparse.Namespace) -> int:
    run_ids = iter(("concept-seed-a", "concept-seed-b"))
    seed_responses = iter((
        seed_bundle(
            "candidate:concept-seed-a",
            "A bounded statement about energy transformation.",
        ),
        seed_bundle(
            "candidate:concept-seed-b",
            "A bounded statement about component organization.",
        ),
    ))

    def seed_adapter(_grant, **_kwargs):
        return {
            "content": json.dumps(next(seed_responses)),
            "model": "deterministic-concept-seed",
        }

    seed_app = DiamondApplication(
        root,
        seed_adapter,
        required_permissions=SEED_PERMISSION,
        repair_attempts=0,
        run_id_factory=lambda: next(run_ids),
    )
    candidates = (
        "Um automóvel transforma energia em movimento através dos componentes.",
        "A organização dos componentes sustenta a identidade funcional do automóvel.",
    )
    for content in candidates:
        learned = seed_app.learn_text(
            content,
            scope="scope:diamond-smoke:cars",
            provenance=("document:synthetic-concept-seed",),
        )
        if not (
            learned.result.execution.closure.structural_closed is True
            and learned.result.execution.closure.epistemic_closed is True
        ):
            raise RuntimeError("Deterministic concept seed did not close")

    adapter = OpenAICompatibleChatAdapter(
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )
    raw_responses = []

    def recording_adapter(grant, **kwargs):
        response = adapter(grant, **kwargs)
        raw_responses.append(dict(response))
        return response

    app = DiamondApplication(
        root,
        recording_adapter,
        required_permissions=adapter.required_permissions,
        max_tokens=args.max_tokens,
        repair_attempts=0,
    )
    crystals = app.crystals(scope="scope:diamond-smoke:cars")
    if len(crystals) != 2:
        raise RuntimeError(f"Expected two ACTIVE seed crystals, got {len(crystals)}")
    concept = app.propose_concept(
        canonical_name="Estrutura funcional do automóvel",
        aliases=("Sistema funcional automóvel",),
        scope="scope:diamond-smoke:cars",
        crystal_ids=tuple(item.crystal_id for item in crystals),
        signature=ConceptSignature(
            characteristics=("identidade funcional delimitada",),
            relations=("componentes organizados sustentam a função",),
            functions=("transformar energia em movimento",),
            constraints=("a organização deve preservar a função",),
            exclusions=("agregados de componentes sem função coerente",),
        ),
    )

    print(
        f"[Diamond concept evidence smoke] model={args.model} calls=1",
        flush=True,
    )
    outcome = app.evaluate_concept(
        concept.concept_id,
        objective=(
            "Evaluate whether the two committed source-bounded crystals "
            "justify every part of this concept candidate. Omit unsupported "
            "seals rather than inventing evidence."
        ),
    )
    validation = outcome.validation
    print(json.dumps({
        "model_calls": outcome.model_call_count,
        "execution_state": outcome.result.execution.state.value,
        "structural_closed": outcome.result.execution.closure.structural_closed,
        "epistemic_closed": outcome.result.execution.closure.epistemic_closed,
        "controller_remainders": [
            item.description for item in outcome.result.execution.remainders
        ],
        "recommended_state": (
            validation.report.recommended_state.value if validation else None
        ),
        "stored_state": validation.record.state.value if validation else None,
        "stored_version": validation.record.version if validation else None,
        "validation_remainders": (
            [
                item.description
                for item in validation.report.active_remainders
            ]
            if validation else []
        ),
    }, ensure_ascii=False, indent=2), flush=True)
    if args.debug and raw_responses:
        print("\n--- raw model response ---")
        print(raw_responses[-1].get("content"), flush=True)
    if (
        args.resolve_gaps
        and validation is not None
        and validation.record.state is ConceptState.CANDIDATE
    ):
        resolved = app.resolve_concept_gaps(
            concept.concept_id,
            validation.report,
            max_queries=1,
            max_results_per_query=1,
        )
        reevaluation = resolved.evaluation
        print("\n--- targeted gap resolution ---")
        print(json.dumps({
            "query_ids": [
                item.query_id for item in resolved.research_request.queries
            ],
            "source_units": (
                len(resolved.source_artifact.payload["source_units"])
                if resolved.source_artifact is not None else 0
            ),
            "learning_commit": (
                resolved.learning.stored_commit.commit.commit_id
                if resolved.learning is not None else None
            ),
            "revised_concept": (
                resolved.revised_concept.version_ref
                if resolved.revised_concept is not None else None
            ),
            "reevaluated_state": (
                reevaluation.validation.record.state.value
                if reevaluation is not None and reevaluation.validation is not None
                else None
            ),
            "model_calls": resolved.model_call_count,
        }, ensure_ascii=False, indent=2), flush=True)
        if args.debug and raw_responses:
            print("\n--- last gap-resolution model response ---")
            print(raw_responses[-1].get("content"), flush=True)
    return 0 if validation is not None else 2


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    if args.data_root is not None:
        args.data_root.mkdir(parents=True, exist_ok=True)
        return run(args.data_root, args)
    with TemporaryDirectory(prefix="fresta-diamond-concept-evidence-") as root:
        return run(Path(root), args)


if __name__ == "__main__":
    raise SystemExit(main())
