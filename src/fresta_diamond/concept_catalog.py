"""Unvalidated external concept catalogs and workspace-only intake."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetLink,
    SheetRevision,
    SheetState,
)


CONCEPT_CATALOG_SCHEMA = "fresta://unvalidated-concept-catalog@1"
CONCEPT_CATALOG_AUTHORITY = "UNVALIDATED_CONCEPT_CATALOG"
CONCEPT_ENTRY_AUTHORITY = "UNVALIDATED_CONCEPT_NOMINATION"
CATALOG_FIELDS = (
    "structural_definition",
    "application_domain",
    "filtration_role",
    "incompleteness_relation",
    "systemic_consequence",
)
_INTRINSIC_ORDER_KEYS = {"order", "orders", "order_profile", "contextual_roles"}


class ConceptCatalogError(RuntimeError):
    """An external catalog crossed or corrupted its unvalidated boundary."""


@dataclass(frozen=True)
class ConceptCatalogSource:
    source_index: str
    reference: str


@dataclass(frozen=True)
class ConceptCatalogEntry:
    entry_id: str
    source_locator: str
    canonical_name_candidate: str
    proposed_fields: Mapping[str, str]
    source_indices_raw: str
    source_indices: tuple[str, ...]
    authority: str = CONCEPT_ENTRY_AUTHORITY
    promotion_authority: bool = False


@dataclass(frozen=True)
class ConceptCatalog:
    catalog_id: str
    source: Mapping[str, str]
    cautions: tuple[str, ...]
    sources: tuple[ConceptCatalogSource, ...]
    entries: tuple[ConceptCatalogEntry, ...]
    authority: str = CONCEPT_CATALOG_AUTHORITY

    def entry(self, entry_id: str) -> ConceptCatalogEntry:
        try:
            return next(item for item in self.entries if item.entry_id == entry_id)
        except StopIteration as exc:
            raise ConceptCatalogError(f"Unknown catalog entry: {entry_id}") from exc


def load_concept_catalog(path: str | Path) -> ConceptCatalog:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise ConceptCatalogError("Could not read concept catalog") from exc
    if not isinstance(raw, Mapping):
        raise ConceptCatalogError("Concept catalog must be an object")
    return decode_concept_catalog(raw)


def decode_concept_catalog(value: Mapping[str, Any]) -> ConceptCatalog:
    if value.get("schema") != CONCEPT_CATALOG_SCHEMA:
        raise ConceptCatalogError("Unsupported concept catalog schema")
    if value.get("authority") != CONCEPT_CATALOG_AUTHORITY:
        raise ConceptCatalogError("Concept catalog authority was altered")
    if _contains_intrinsic_order(value):
        raise ConceptCatalogError("Concept catalog assigns an intrinsic order")
    source = value.get("source")
    if not isinstance(source, Mapping):
        raise ConceptCatalogError("Concept catalog source must be an object")
    decoded_source = {
        key: _text(source, key)
        for key in (
            "filename", "sha256", "concept_sheet", "concept_range",
            "source_sheet", "source_range", "extraction_method",
        )
    }
    sources = tuple(
        ConceptCatalogSource(
            source_index=_text(item, "source_index"),
            reference=_text(item, "reference"),
        )
        for item in _mapping_sequence(value, "sources")
    )
    source_ids = {item.source_index for item in sources}
    if len(source_ids) != len(sources):
        raise ConceptCatalogError("Concept catalog contains duplicate sources")
    entries = tuple(_decode_entry(item, source_ids) for item in _mapping_sequence(
        value, "entries"
    ))
    entry_ids = {item.entry_id for item in entries}
    if not entries or len(entry_ids) != len(entries):
        raise ConceptCatalogError("Concept catalog entries are empty or duplicated")
    return ConceptCatalog(
        catalog_id=_text(value, "catalog_id"),
        source=decoded_source,
        cautions=_text_sequence(value, "cautions"),
        sources=sources,
        entries=entries,
    )


@dataclass(frozen=True)
class ConceptCatalogIntake:
    workspace: JsonlCognitiveWorkspace

    def stage(
        self,
        catalog: ConceptCatalog,
        entry_ids: tuple[str, ...],
        *,
        scope: str,
        objective_ref: str,
    ) -> tuple[SheetRevision, ...]:
        if not entry_ids or len(set(entry_ids)) != len(entry_ids):
            raise ConceptCatalogError("Catalog intake requires unique entries")
        if not scope.strip() or not objective_ref.strip():
            raise ConceptCatalogError("Catalog intake scope and objective are required")
        revisions = tuple(
            self._revision(catalog, catalog.entry(entry_id), scope, objective_ref)
            for entry_id in entry_ids
        )
        for revision in revisions:
            self.workspace.save(revision)
        return revisions

    @staticmethod
    def _revision(
        catalog: ConceptCatalog,
        entry: ConceptCatalogEntry,
        scope: str,
        objective_ref: str,
    ) -> SheetRevision:
        base_provenance = (
            f"catalog:{catalog.catalog_id}",
            entry.source_locator,
        ) + tuple(f"catalog-source:{item}" for item in entry.source_indices)
        elements = [SheetElement(
            element_id=f"{entry.entry_id}:name",
            kind=SheetElementKind.CONCEPT,
            content=f"Candidate concept name: {entry.canonical_name_candidate}",
            scope=scope,
            provenance=base_provenance,
        )]
        for field in CATALOG_FIELDS:
            elements.append(SheetElement(
                element_id=f"{entry.entry_id}:{field}",
                kind=SheetElementKind.HYPOTHESIS,
                content=f"Proposed {field}: {entry.proposed_fields[field]}",
                scope=scope,
                provenance=base_provenance,
            ))
        links = tuple(
            SheetLink(
                link_id=f"{entry.entry_id}:source:{source_index}",
                source_element_id=None,
                target_ref=f"catalog-source:{source_index}",
                relation="nominated-from-unlocalized-document-index",
            )
            for source_index in entry.source_indices
        )
        return SheetRevision(
            sheet_id=f"catalog:{catalog.catalog_id}:{entry.entry_id}",
            revision_number=1,
            title=f"Unvalidated concept nomination: {entry.canonical_name_candidate}",
            state=SheetState.STAGED,
            elements=tuple(elements),
            links=links,
            objective_ref=objective_ref,
            author_ref="actor:external-concept-catalog",
        )


def _decode_entry(
    value: Mapping[str, Any],
    known_sources: set[str],
) -> ConceptCatalogEntry:
    if value.get("authority") != CONCEPT_ENTRY_AUTHORITY:
        raise ConceptCatalogError("Concept entry authority was altered")
    if value.get("promotion_authority") is not False:
        raise ConceptCatalogError("Concept catalog entry claims promotion authority")
    if value.get("validation_refs") not in ([], ()):
        raise ConceptCatalogError("Concept catalog entry contains validation refs")
    if value.get("derivation_seals") not in ([], ()):
        raise ConceptCatalogError("Concept catalog entry contains derivation seals")
    fields = value.get("proposed_fields")
    if not isinstance(fields, Mapping) or set(fields) != set(CATALOG_FIELDS):
        raise ConceptCatalogError("Concept catalog entry has invalid proposed fields")
    source_indices = _text_sequence(value, "source_indices")
    missing = sorted(set(source_indices) - known_sources)
    if not source_indices or missing:
        raise ConceptCatalogError(
            f"Concept catalog entry references unknown sources: {missing}"
        )
    return ConceptCatalogEntry(
        entry_id=_text(value, "entry_id"),
        source_locator=_text(value, "source_locator"),
        canonical_name_candidate=_text(value, "canonical_name_candidate"),
        proposed_fields={field: _text(fields, field) for field in CATALOG_FIELDS},
        source_indices_raw=_text(value, "source_indices_raw"),
        source_indices=source_indices,
    )


def _contains_intrinsic_order(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(_INTRINSIC_ORDER_KEYS & set(value)) or any(
            _contains_intrinsic_order(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_intrinsic_order(item) for item in value)
    return False


def _mapping_sequence(
    value: Mapping[str, Any], key: str
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise ConceptCatalogError(f"{key} must be a sequence")
    if any(not isinstance(item, Mapping) for item in raw):
        raise ConceptCatalogError(f"{key} contains a non-object")
    return tuple(raw)


def _text_sequence(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise ConceptCatalogError(f"{key} must be a sequence")
    result = tuple(_nonempty_text(item, key) for item in raw)
    if len(result) != len(set(result)):
        raise ConceptCatalogError(f"{key} contains duplicates")
    return result


def _text(value: Mapping[str, Any], key: str) -> str:
    return _nonempty_text(value.get(key), key)


def _nonempty_text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConceptCatalogError(f"{key} must be non-empty text")
    return value.strip()
