"""Architectural guards proving Diamond does not import the Frankenstein."""

from __future__ import annotations

import ast
import json
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "fresta_diamond"
CATALOG_ROOT = (
    Path(__file__).resolve().parents[1] / "testdata" / "concept-catalog"
)


def test_diamond_source_never_imports_frankenstein_package() -> None:
    violations: list[str] = []

    for source_path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            imported: tuple[str, ...]
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported = (node.module or "",)
            else:
                continue

            for module_name in imported:
                if module_name == "fresta" or module_name.startswith("fresta."):
                    relative = source_path.relative_to(SOURCE_ROOT)
                    violations.append(f"{relative}:{node.lineno}: {module_name}")

    assert not violations, (
        "Diamond must use explicit adapters instead of importing Frankenstein:\n"
        + "\n".join(violations)
    )


def test_diamond_package_contains_no_path_back_to_frankenstein() -> None:
    for source_path in sorted(SOURCE_ROOT.rglob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        assert "fresta-novo" not in source
        assert "..\\fresta" not in source
        assert "../fresta" not in source


def test_concept_catalog_fixture_has_no_external_runtime_dependency() -> None:
    fixture = CATALOG_ROOT / "notebooklm-ontology-index.json"
    value = json.loads(fixture.read_text(encoding="utf-8"))
    serialized = json.dumps(value, ensure_ascii=False)

    assert fixture.resolve().is_relative_to(CATALOG_ROOT.resolve())
    assert "fresta-novo" not in serialized
    assert "C:\\" not in serialized
    assert "../data" not in serialized
    assert "/Downloads/" not in serialized
    assert value["source"]["filename"].endswith(".xlsx")
