from __future__ import annotations

import json
from pathlib import Path

import pytest

from fresta_diamond.benchmarking import (
    BENCHMARK_MANIFEST_SCHEMA,
    BenchmarkLabError,
    DiamondBenchmarkLab,
    replay_adapter,
    replay_permissions,
    run_learning_benchmark,
)


TESTDATA = Path(__file__).resolve().parents[1] / "testdata"


def test_canonical_replay_suite_matches_approved_baseline() -> None:
    lab = DiamondBenchmarkLab(TESTDATA)

    assert lab.list_cases()
    for case_id in lab.list_cases():
        case = lab.load_case(case_id)
        projection = run_learning_benchmark(
            case,
            replay_adapter(case),
            permissions=replay_permissions(),
        )
        comparison = lab.compare(case_id, projection)
        assert comparison.matches, comparison.differences


def test_canonical_testdata_is_owned_only_by_diamond() -> None:
    lab = DiamondBenchmarkLab(TESTDATA)
    diamond_root = TESTDATA.parent.resolve()
    frankenstein_data = diamond_root.parent / "data"
    frankenstein_testdata = diamond_root.parent / "data-tests"

    for case_id in lab.list_cases():
        path = lab.load_case(case_id).fixture_path
        assert TESTDATA.resolve() in path.parents
        assert frankenstein_data.resolve() not in path.parents
        assert frankenstein_testdata.resolve() not in path.parents


def test_fixture_digest_detects_silent_input_changes(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "baselines").mkdir()
    fixture = tmp_path / "fixtures" / "case.json"
    fixture.write_text('{"case_id":"case"}', encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema": BENCHMARK_MANIFEST_SCHEMA,
        "suite_id": "suite",
        "baseline_id": "baseline",
        "cases": [{
            "case_id": "case",
            "fixture": "fixtures/case.json",
            "sha256": "0" * 64,
        }],
    }), encoding="utf-8")

    with pytest.raises(BenchmarkLabError, match="digest mismatch"):
        DiamondBenchmarkLab(tmp_path).load_case("case")


def test_manifest_cannot_escape_fixture_directory(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema": BENCHMARK_MANIFEST_SCHEMA,
        "suite_id": "suite",
        "baseline_id": "baseline",
        "cases": [{
            "case_id": "case",
            "fixture": "../outside.json",
            "sha256": "0" * 64,
        }],
    }), encoding="utf-8")

    with pytest.raises(BenchmarkLabError, match="escapes fixtures"):
        DiamondBenchmarkLab(tmp_path).load_case("case")


def test_comparison_reports_exact_regression_path() -> None:
    lab = DiamondBenchmarkLab(TESTDATA)
    projection = dict(lab.expected_projection("automobile-attestation"))
    projection["structural_closed"] = False

    comparison = lab.compare("automobile-attestation", projection)

    assert comparison.matches is False
    assert comparison.differences == (
        "$.structural_closed: expected True, got False",
    )


def test_current_baseline_inherits_previous_canonical_cases() -> None:
    lab = DiamondBenchmarkLab(TESTDATA)
    baseline = lab.load_baseline()

    assert baseline["baseline_id"] == "learn-replay-v8"
    assert set(baseline["cases"]) == set(lab.list_cases())
    assert "automobile-attestation" in baseline["cases"]
    assert "automobile-concept-candidate" in baseline["cases"]
    assert "automobile-concept-integration" in baseline["cases"]


def test_archived_run_is_append_only_and_inside_runs(tmp_path: Path) -> None:
    lab = DiamondBenchmarkLab(TESTDATA)
    case = lab.load_case("automobile-attestation")
    projection = lab.expected_projection(case.case_id)
    comparison = lab.compare(case.case_id, projection)

    isolated = tmp_path / "testdata"
    (isolated / "fixtures").mkdir(parents=True)
    (isolated / "baselines").mkdir()
    (isolated / "runs").mkdir()
    (isolated / "manifest.json").write_text(
        TESTDATA.joinpath("manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    isolated_case_path = isolated / "fixtures" / case.fixture_path.name
    isolated_case_path.write_bytes(case.fixture_path.read_bytes())
    isolated_baseline = isolated / "baselines" / f"{lab.baseline_id}.json"
    isolated_baseline.write_text(
        TESTDATA.joinpath("baselines", f"{lab.baseline_id}.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    inherited_baseline = isolated / "baselines" / "learn-replay-v3.json"
    inherited_baseline.write_text(
        TESTDATA.joinpath("baselines", "learn-replay-v3.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    inherited_v4 = isolated / "baselines" / "learn-replay-v4.json"
    inherited_v4.write_text(
        TESTDATA.joinpath("baselines", "learn-replay-v4.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    inherited_v5 = isolated / "baselines" / "learn-replay-v5.json"
    inherited_v5.write_text(
        TESTDATA.joinpath("baselines", "learn-replay-v5.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    inherited_v6 = isolated / "baselines" / "learn-replay-v6.json"
    inherited_v6.write_text(
        TESTDATA.joinpath("baselines", "learn-replay-v6.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    inherited_v7 = isolated / "baselines" / "learn-replay-v7.json"
    inherited_v7.write_text(
        TESTDATA.joinpath("baselines", "learn-replay-v7.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    isolated_lab = DiamondBenchmarkLab(isolated)
    isolated_case = isolated_lab.load_case(case.case_id)

    first = isolated_lab.archive_run(
        case=isolated_case,
        mode="REPLAY",
        projection=projection,
        comparison=comparison,
        model="diamond-replay",
    )
    second = isolated_lab.archive_run(
        case=isolated_case,
        mode="REPLAY",
        projection=projection,
        comparison=comparison,
        model="diamond-replay",
    )

    assert first != second
    assert first.exists() and second.exists()
    assert first.parent == (isolated / "runs").resolve()
