"""Compare isolated Diamond and Frankenstein /learn outcomes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping
from uuid import uuid4


DIAMOND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DIAMOND_ROOT.parent
sys.path.insert(0, str(DIAMOND_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from fresta.commands import create_default_registry  # noqa: E402
from fresta.commands.types import CommandContext  # noqa: E402
from fresta.config import load_config, save_config  # noqa: E402
from fresta.external_store import list_cards  # noqa: E402
from fresta.fresta_types import CandidateMemory, Order  # noqa: E402
import fresta.commands.learning as frankenstein_learning  # noqa: E402
from fresta_diamond.benchmarking import (  # noqa: E402
    DiamondBenchmarkLab,
    replay_adapter,
    replay_permissions,
    run_learning_benchmark,
)


CROSS_SCHEMA = "fresta://diamond-frankenstein-comparison@2"
CROSS_ROOT = DIAMOND_ROOT / "testdata" / "cross"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay one source through isolated Diamond and Frankenstein pipelines."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", help="Run one shared fixture.")
    group.add_argument("--all", action="store_true", help="Run every shared fixture.")
    group.add_argument("--list", action="store_true", help="List shared fixtures.")
    parser.add_argument("--no-archive", action="store_true")
    return parser.parse_args()


def cross_case_ids(lab: DiamondBenchmarkLab) -> tuple[str, ...]:
    """Return only fixtures explicitly admitted by the legacy bridge."""

    manifest = json.loads(
        (CROSS_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    raw = manifest.get("cases")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Cross-benchmark manifest contains no shared cases")
    available = set(lab.list_cases())
    result: list[str] = []
    for value in raw:
        if not isinstance(value, str) or value not in available:
            raise RuntimeError(f"Unknown shared cross-benchmark case: {value!r}")
        if value in result:
            raise RuntimeError(f"Duplicate shared cross-benchmark case: {value}")
        result.append(value)
    return tuple(result)


def run_frankenstein_replay(case) -> dict[str, Any]:
    """Execute the centralized legacy command with no network or shared state."""

    candidate = _mapping(case.fixture, "candidate")
    content = _text(candidate, "content")
    with TemporaryDirectory(prefix="fresta-cross-frankenstein-") as temporary:
        data_dir = Path(temporary).resolve()
        books = data_dir / "books"
        books.mkdir(parents=True)
        (books / f"{case.case_id}.txt").write_text(content + "\n", encoding="utf-8")
        config = load_config(data_dir)
        config.update({
            "blueprints_enabled": True,
            "blueprint_execution_mode": "active",
            "learn_use_llm_extraction": True,
            "learn_auto_topic": False,
            "learn_topics_auto": False,
            "task_workspace_enabled": False,
            "learn_workspace_mode": "off",
            "learn_recursive_analysis_enabled": False,
            "learn_ultra_verification_enabled": False,
            "learn_phi_closure_enabled": False,
        })
        save_config(data_dir, config)
        original = frankenstein_learning.extract_candidates_with_llm
        model_calls = 0

        def replay_extraction(*_args: Any, **_kwargs: Any):
            nonlocal model_calls
            model_calls += 1
            return [CandidateMemory(
                content=content,
                memory_type="CONCEPT",
                owner="document",
                order=Order.FIRST,
            )]

        frankenstein_learning.extract_candidates_with_llm = replay_extraction
        try:
            result = create_default_registry().dispatch(
                "/learn 1",
                CommandContext(data_dir=data_dir, mode="test"),
            )
        finally:
            frankenstein_learning.extract_candidates_with_llm = original
        cards = list_cards(data_dir)

    decisions = (
        result.data.get("learning_delta", {}).get("candidate_decisions", [])
        if isinstance(result.data, Mapping) else []
    )
    normalized_decisions = [
        {
            "content": str(item.get("content") or ""),
            "disposition": _frankenstein_disposition(item),
            "status": str(item.get("status") or ""),
            "write_action": str(item.get("write_action") or ""),
            "owner": str(item.get("owner") or ""),
            "subject": str(item.get("subject") or ""),
            "epistemic_state": item.get("epistemic_state"),
            "reason_codes": sorted(str(value) for value in item.get("reasons", [])),
            "phi": sorted(str(value) for value in item.get("phi", [])),
        }
        for item in decisions
        if isinstance(item, Mapping)
    ]
    normalized_cards = [
        {
            "content": str(card.get("content") or ""),
            "owner": str(card.get("owner") or ""),
            "source_family": str(card.get("source") or "").split(":", 1)[0],
            "memory_type": str(card.get("memory_type") or ""),
            "claim_mode": str(card.get("claim_mode") or ""),
            "structural_state": str(card.get("structural_state") or ""),
            "epistemic_state": str(card.get("epistemic_state") or ""),
            "lifecycle_state": str(card.get("lifecycle_state") or ""),
        }
        for card in cards
    ]
    boundary = all(
        item["owner"] == "document"
        and item["subject"] not in {"user", "owner:user"}
        for item in normalized_decisions
    ) and all(card["owner"] == "document" for card in normalized_cards)
    return {
        "technical_completed": result.status == "ok",
        "cards_saved": len(normalized_cards),
        "candidate_decisions": normalized_decisions,
        "persisted_cards": normalized_cards,
        "document_identity_boundary_preserved": boundary,
        "replay_extraction_calls": model_calls,
    }


def normalize_diamond(projection: Mapping[str, Any]) -> dict[str, Any]:
    outcomes = []
    negative = {
        item["source_element_id"]: item
        for item in projection.get("negative_boundary", [])
        if isinstance(item, Mapping) and item.get("source_element_id")
    }
    for crystal in projection.get("crystals", []):
        if not isinstance(crystal, Mapping):
            continue
        source_id = str(crystal.get("source_element_id") or "")
        outcomes.append({
            "source_element_id": source_id,
            "disposition": _diamond_disposition(str(crystal.get("state") or "")),
            "crystal_state": str(crystal.get("state") or ""),
            "claim_mode": crystal.get("claim_mode"),
            "reason_codes": list(crystal.get("reason_codes") or []),
            "negative_boundary": negative.get(source_id),
        })
    return {
        "technical_completed": bool(projection.get("technical_completed")),
        "persisted_cards": int(
            (projection.get("learning_memory") or {}).get(
                "crystals_committed", 0
            )
        ),
        "candidate_outcomes": outcomes,
        "document_identity_boundary_preserved": bool(
            projection.get("document_identity_boundary_preserved")
        ),
        "replay_model_calls": int(projection.get("model_call_count", 0)),
    }


def compare_systems(
    diamond: Mapping[str, Any],
    frankenstein: Mapping[str, Any],
) -> dict[str, Any]:
    diamond_dispositions = [
        item.get("disposition")
        for item in diamond.get("candidate_outcomes", [])
        if isinstance(item, Mapping)
    ]
    frankenstein_dispositions = [
        item.get("disposition")
        for item in frankenstein.get("candidate_decisions", [])
        if isinstance(item, Mapping)
    ]
    both_safe = (
        diamond.get("document_identity_boundary_preserved") is True
        and frankenstein.get("document_identity_boundary_preserved") is True
    )
    return {
        "both_technically_completed": (
            diamond.get("technical_completed") is True
            and frankenstein.get("technical_completed") is True
        ),
        "both_preserve_document_identity_boundary": both_safe,
        "diamond_dispositions": diamond_dispositions,
        "frankenstein_dispositions": frankenstein_dispositions,
        "disposition_agreement": diamond_dispositions == frankenstein_dispositions,
        "persistence_count_agreement": (
            int(diamond.get("persisted_cards", 0))
            == int(frankenstein.get("cards_saved", 0))
        ),
    }


def run_case(lab: DiamondBenchmarkLab, case_id: str) -> dict[str, Any]:
    case = lab.load_case(case_id)
    raw_diamond = run_learning_benchmark(
        case,
        replay_adapter(case),
        permissions=replay_permissions(),
    )
    diamond = normalize_diamond(raw_diamond)
    frankenstein = run_frankenstein_replay(case)
    return {
        "schema": CROSS_SCHEMA,
        "case_id": case.case_id,
        "fixture_sha256": case.fixture_hash,
        "diamond": diamond,
        "frankenstein": frankenstein,
        "comparison": compare_systems(diamond, frankenstein),
    }


def cross_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    diamond = _mapping(result, "diamond")
    frankenstein = _mapping(result, "frankenstein")
    comparison = _mapping(result, "comparison")
    outcomes = [
        item for item in diamond.get("candidate_outcomes", [])
        if isinstance(item, Mapping)
    ]
    decisions = [
        item for item in frankenstein.get("candidate_decisions", [])
        if isinstance(item, Mapping)
    ]
    return {
        "both_technically_completed": comparison.get(
            "both_technically_completed"
        ),
        "both_preserve_document_identity_boundary": comparison.get(
            "both_preserve_document_identity_boundary"
        ),
        "diamond_dispositions": comparison.get("diamond_dispositions"),
        "frankenstein_dispositions": comparison.get(
            "frankenstein_dispositions"
        ),
        "disposition_agreement": comparison.get("disposition_agreement"),
        "diamond_phi_minus_justified": [
            bool((item.get("negative_boundary") or {}).get(
                "phi_minus_justified"
            ))
            for item in outcomes
        ],
        "frankenstein_epistemic_states": [
            item.get("epistemic_state") for item in decisions
        ],
        "frankenstein_owners": [item.get("owner") for item in decisions],
        "frankenstein_subjects": [item.get("subject") for item in decisions],
        "frankenstein_cards_saved": frankenstein.get("cards_saved"),
        "diamond_persisted_cards": diamond.get("persisted_cards"),
    }


def load_cross_baseline() -> tuple[str, Mapping[str, Any]]:
    manifest = json.loads(
        (CROSS_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    baseline_id = str(manifest.get("baseline_id") or "")
    if not baseline_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
        for character in baseline_id
    ):
        raise RuntimeError("Invalid cross-benchmark baseline ID")
    baseline = json.loads(
        (CROSS_ROOT / "baselines" / f"{baseline_id}.json").read_text(
            encoding="utf-8"
        )
    )
    if baseline.get("baseline_id") != baseline_id:
        raise RuntimeError("Cross-benchmark baseline identity mismatch")
    return baseline_id, baseline


def compare_cross_baseline(
    case_id: str,
    projection: Mapping[str, Any],
) -> tuple[str, bool, tuple[str, ...]]:
    baseline_id, baseline = load_cross_baseline()
    cases = baseline.get("cases")
    if not isinstance(cases, Mapping) or not isinstance(
        cases.get(case_id), Mapping
    ):
        raise RuntimeError(f"Cross baseline has no case: {case_id}")
    differences: list[str] = []
    _compare_values(cases[case_id], projection, "$", differences)
    return baseline_id, not differences, tuple(differences)


def archive(
    result: Mapping[str, Any],
    *,
    baseline_id: str,
    matches_baseline: bool,
    differences: tuple[str, ...],
) -> Path:
    run_id = (
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-"
        f"{result['case_id']}-{uuid4().hex[:8]}"
    )
    path = (CROSS_ROOT / "runs" / f"{run_id}.json").resolve()
    expected = (CROSS_ROOT / "runs").resolve()
    if expected not in path.parents:
        raise RuntimeError("Cross-benchmark archive escaped its data root")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **result,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_id": baseline_id,
        "matches_baseline": matches_baseline,
        "differences": list(differences),
        "projection": cross_projection(result),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    lab = DiamondBenchmarkLab(DIAMOND_ROOT / "testdata")
    shared_cases = cross_case_ids(lab)
    if args.list:
        print("\n".join(shared_cases))
        return 0
    case_ids = shared_cases if args.all else (args.case or shared_cases[0],)
    unknown = tuple(case_id for case_id in case_ids if case_id not in shared_cases)
    if unknown:
        raise RuntimeError(
            f"Case is not admitted by the legacy bridge: {unknown[0]}"
        )
    failed = False
    for case_id in case_ids:
        result = run_case(lab, case_id)
        projection = cross_projection(result)
        baseline_id, matches, differences = compare_cross_baseline(
            case_id, projection
        )
        path = None if args.no_archive else archive(
            result,
            baseline_id=baseline_id,
            matches_baseline=matches,
            differences=differences,
        )
        print(f"\n--- Diamond ↔ Frankenstein: {case_id} ---")
        print(json.dumps({
            **result,
            "baseline_id": baseline_id,
            "matches_baseline": matches,
            "differences": list(differences),
            "projection": projection,
            "archived_at": str(path) if path else None,
        }, ensure_ascii=False, indent=2))
        failed = failed or not matches
    return 2 if failed else 0


def _diamond_disposition(state: str) -> str:
    return {
        "ACCEPTED": "ACCEPTED",
        "PROVISIONAL": "PROVISIONAL",
        "DEFERRED": "INDETERMINATE",
        "QUARANTINED": "EXCLUDED",
        "PHI_MINUS": "EXCLUDED",
    }.get(state, "UNKNOWN")


def _frankenstein_disposition(value: Mapping[str, Any]) -> str:
    status = str(value.get("status") or "").lower()
    epistemic = str(value.get("epistemic_state") or "").upper()
    if status == "rejected" or epistemic == "REFUTED":
        return "EXCLUDED"
    if epistemic == "CONFIRMED":
        return "ACCEPTED"
    if epistemic == "PROVISIONAL":
        return "PROVISIONAL"
    if epistemic == "DEFERRED":
        return "INDETERMINATE"
    return "UNKNOWN"


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise ValueError(f"{key} must be an object")
    return item


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _compare_values(
    expected: Any,
    actual: Any,
    path: str,
    differences: list[str],
) -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected:
                differences.append(f"{child}: unexpected")
            elif key not in actual:
                differences.append(f"{child}: missing")
            else:
                _compare_values(expected[key], actual[key], child, differences)
        return
    if expected != actual:
        differences.append(f"{path}: expected {expected!r}, got {actual!r}")


if __name__ == "__main__":
    raise SystemExit(main())
