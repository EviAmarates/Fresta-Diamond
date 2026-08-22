from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElementKind,
    SheetState,
)
from fresta_diamond.concept_catalog import (
    CATALOG_FIELDS,
    ConceptCatalogError,
    ConceptCatalogIntake,
    decode_concept_catalog,
    load_concept_catalog,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "testdata"
    / "concept-catalog"
    / "notebooklm-ontology-index.json"
)


def fixture_value():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_notebooklm_catalog_is_an_unvalidated_order_free_index() -> None:
    catalog = load_concept_catalog(FIXTURE)

    assert catalog.authority == "UNVALIDATED_CONCEPT_CATALOG"
    assert len(catalog.sources) == 7
    assert len(catalog.entries) == 17
    assert catalog.entries[0].canonical_name_candidate.startswith("Filtro")
    assert catalog.entries[0].source_indices == ("1", "2", "3")
    assert all(item.promotion_authority is False for item in catalog.entries)
    assert all(set(item.proposed_fields) == set(CATALOG_FIELDS) for item in catalog.entries)
    raw = fixture_value()
    assert all("order" not in item for item in raw["entries"])
    assert all(not item["validation_refs"] for item in raw["entries"])
    assert all(not item["derivation_seals"] for item in raw["entries"])


def test_catalog_intake_stages_hypotheses_not_concept_records(tmp_path) -> None:
    catalog = load_concept_catalog(FIXTURE)
    workspace = JsonlCognitiveWorkspace(tmp_path / "workspace")
    revision, = ConceptCatalogIntake(workspace).stage(
        catalog,
        (catalog.entries[0].entry_id,),
        scope="scope:ontology-catalog-review",
        objective_ref="objective:review-filter-nomination",
    )

    assert revision.state is SheetState.STAGED
    assert revision.author_ref == "actor:external-concept-catalog"
    assert revision.elements[0].kind is SheetElementKind.CONCEPT
    assert {item.kind for item in revision.elements[1:]} == {
        SheetElementKind.HYPOTHESIS
    }
    assert len(revision.elements) == 1 + len(CATALOG_FIELDS)
    assert all(item.contextual_roles == () for item in revision.elements)
    assert all(
        catalog.entries[0].source_locator in item.provenance
        for item in revision.elements
    )
    assert workspace.latest(revision.sheet_id) == revision


def test_catalog_cannot_smuggle_promotion_or_intrinsic_order() -> None:
    promoted = deepcopy(fixture_value())
    promoted["entries"][0]["promotion_authority"] = True
    with pytest.raises(ConceptCatalogError, match="promotion authority"):
        decode_concept_catalog(promoted)

    ordered = deepcopy(fixture_value())
    ordered["entries"][0]["order"] = 3
    with pytest.raises(ConceptCatalogError, match="intrinsic order"):
        decode_concept_catalog(ordered)


def test_catalog_requires_known_source_indices() -> None:
    value = deepcopy(fixture_value())
    value["entries"][0]["source_indices"] = ["999"]

    with pytest.raises(ConceptCatalogError, match="unknown sources"):
        decode_concept_catalog(value)
