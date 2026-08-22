"""Auditable dual human/canonical working representations for sheets."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from typing import Any, Mapping

from fresta_diamond.cognitive_workspace import (
    SheetElement,
    SheetElementKind,
)


WORKING_REPRESENTATION_SCHEMA = "fresta://canonical-working-representation@1"
WORKING_REPRESENTATION_AUTHORITY = "UNVALIDATED_WORKSPACE_REPRESENTATION"
CANONICAL_WORKING_LANGUAGE = "fresta-canonical@1"


@dataclass(frozen=True)
class WorkingClaim:
    claim_id: str
    content: str
    dependency_refs: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    confidence: float | None = None

    def __post_init__(self) -> None:
        _required(self.claim_id, "Working claim ID")
        _required(self.content, "Working claim content")
        _refs(self.dependency_refs, "Working claim dependencies")
        _refs(self.provenance, "Working claim provenance")
        if self.confidence is not None and (
            not isfinite(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Working claim confidence must be between zero and one")


@dataclass(frozen=True)
class WorkingRelation:
    relation_id: str
    source_ref: str
    predicate: str
    target_ref: str
    constraint_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.relation_id, "Working relation ID"),
            (self.source_ref, "Working relation source"),
            (self.predicate, "Working relation predicate"),
            (self.target_ref, "Working relation target"),
        ):
            _required(value, name)
        _refs(self.constraint_refs, "Working relation constraints")


@dataclass(frozen=True)
class WorkingQuestion:
    question_id: str
    content: str
    dependency_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.question_id, "Working question ID")
        _required(self.content, "Working question content")
        _refs(self.dependency_refs, "Working question dependencies")


@dataclass(frozen=True)
class CanonicalWorkingRepresentation:
    object_ref: str
    objective: str
    claims: tuple[WorkingClaim, ...] = ()
    relations: tuple[WorkingRelation, ...] = ()
    open_questions: tuple[WorkingQuestion, ...] = ()
    authority: str = WORKING_REPRESENTATION_AUTHORITY

    def __post_init__(self) -> None:
        _required(self.object_ref, "Working representation object ref")
        _required(self.objective, "Working representation objective")
        if self.authority != WORKING_REPRESENTATION_AUTHORITY:
            raise PermissionError(
                "Canonical working representation cannot grant authority"
            )
        _unique(tuple(item.claim_id for item in self.claims), "claim IDs")
        _unique(tuple(item.relation_id for item in self.relations), "relation IDs")
        _unique(
            tuple(item.question_id for item in self.open_questions),
            "question IDs",
        )


def encode_working_representation(
    value: CanonicalWorkingRepresentation,
) -> dict[str, Any]:
    return {
        "schema": WORKING_REPRESENTATION_SCHEMA,
        "object_ref": value.object_ref,
        "objective": value.objective,
        "authority": value.authority,
        "claims": [{
            "claim_id": item.claim_id,
            "content": item.content,
            "dependency_refs": list(item.dependency_refs),
            "provenance": list(item.provenance),
            "confidence": item.confidence,
        } for item in value.claims],
        "relations": [{
            "relation_id": item.relation_id,
            "source_ref": item.source_ref,
            "predicate": item.predicate,
            "target_ref": item.target_ref,
            "constraint_refs": list(item.constraint_refs),
        } for item in value.relations],
        "open_questions": [{
            "question_id": item.question_id,
            "content": item.content,
            "dependency_refs": list(item.dependency_refs),
        } for item in value.open_questions],
    }


def decode_working_representation(
    value: Mapping[str, Any],
) -> CanonicalWorkingRepresentation:
    if value.get("schema") != WORKING_REPRESENTATION_SCHEMA:
        raise ValueError("Unknown canonical working representation schema")
    return CanonicalWorkingRepresentation(
        object_ref=_text(value, "object_ref"),
        objective=_text(value, "objective"),
        authority=_text(value, "authority"),
        claims=tuple(WorkingClaim(
            claim_id=_text(item, "claim_id"),
            content=_text(item, "content"),
            dependency_refs=_text_tuple(item, "dependency_refs"),
            provenance=_text_tuple(item, "provenance"),
            confidence=_optional_confidence(item.get("confidence")),
        ) for item in _objects(value, "claims")),
        relations=tuple(WorkingRelation(
            relation_id=_text(item, "relation_id"),
            source_ref=_text(item, "source_ref"),
            predicate=_text(item, "predicate"),
            target_ref=_text(item, "target_ref"),
            constraint_refs=_text_tuple(item, "constraint_refs"),
        ) for item in _objects(value, "relations")),
        open_questions=tuple(WorkingQuestion(
            question_id=_text(item, "question_id"),
            content=_text(item, "content"),
            dependency_refs=_text_tuple(item, "dependency_refs"),
        ) for item in _objects(value, "open_questions")),
    )


def canonical_working_json(value: CanonicalWorkingRepresentation) -> str:
    return json.dumps(
        encode_working_representation(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def decode_working_json(value: str) -> CanonicalWorkingRepresentation:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Canonical working JSON is required")
    decoded = json.loads(value)
    if not isinstance(decoded, Mapping):
        raise TypeError("Canonical working JSON must contain one object")
    return decode_working_representation(decoded)


def dual_language_elements(
    *,
    element_prefix: str,
    scope: str,
    human_language: str,
    human_text: str,
    working: CanonicalWorkingRepresentation,
    provenance: tuple[str, ...] = (),
) -> tuple[SheetElement, SheetElement]:
    for value, name in (
        (element_prefix, "Dual element prefix"),
        (scope, "Dual element scope"),
        (human_language, "Human language"),
        (human_text, "Human text"),
    ):
        _required(value, name)
    _refs(provenance, "Dual element provenance")
    return (
        SheetElement(
            element_id=f"{element_prefix}:human",
            kind=SheetElementKind.NOTE,
            content=human_text,
            scope=scope,
            provenance=provenance,
            language=human_language,
        ),
        SheetElement(
            element_id=f"{element_prefix}:working",
            kind=SheetElementKind.WORKING_REPRESENTATION,
            content=canonical_working_json(working),
            scope=scope,
            provenance=provenance,
            language=CANONICAL_WORKING_LANGUAGE,
        ),
    )


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _refs(values: tuple[str, ...], name: str) -> None:
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{name} contain an empty ref")
    _unique(values, name)


def _unique(values: tuple[str, ...], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Canonical working {name} must be unique")


def _text(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{key} must be non-empty text")
    return result


def _text_tuple(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    result = tuple(raw)
    _refs(result, key)
    return result


def _objects(
    value: Mapping[str, Any],
    key: str,
) -> tuple[Mapping[str, Any], ...]:
    raw = value.get(key)
    if not isinstance(raw, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, Mapping) for item in raw):
        raise TypeError(f"{key} must contain objects")
    return tuple(raw)


def _optional_confidence(value: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("Working claim confidence must be numeric")
    return float(value)
