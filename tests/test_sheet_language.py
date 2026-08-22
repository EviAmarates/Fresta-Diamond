from __future__ import annotations

import pytest

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.sheet_language import (
    CANONICAL_WORKING_LANGUAGE,
    WORKING_REPRESENTATION_AUTHORITY,
    CanonicalWorkingRepresentation,
    WorkingClaim,
    WorkingQuestion,
    WorkingRelation,
    canonical_working_json,
    decode_working_json,
    decode_working_representation,
    dual_language_elements,
    encode_working_representation,
)


def representation() -> CanonicalWorkingRepresentation:
    return CanonicalWorkingRepresentation(
        object_ref="object:automobile",
        objective="Explain bounded functional identity.",
        claims=(WorkingClaim(
            claim_id="claim:energy",
            content="Energy is transformed into movement.",
            dependency_refs=("crystal:motor",),
            provenance=("sheet-revision:energy:sha256:" + "a" * 64,),
            confidence=0.9,
        ),),
        relations=(WorkingRelation(
            relation_id="relation:components-function",
            source_ref="concept:components",
            predicate="sustain",
            target_ref="concept:functional-identity",
            constraint_refs=("constraint:bounded-system",),
        ),),
        open_questions=(WorkingQuestion(
            question_id="question:failure",
            content="Which component failures break functional identity?",
            dependency_refs=("claim:energy",),
        ),),
    )


def test_canonical_working_representation_round_trips_exactly() -> None:
    working = representation()

    assert decode_working_representation(
        encode_working_representation(working)
    ) == working
    encoded = canonical_working_json(working)
    assert decode_working_json(encoded) == working
    assert canonical_working_json(decode_working_json(encoded)) == encoded


def test_dual_language_sheet_preserves_human_and_canonical_views(
    tmp_path,
) -> None:
    working = representation()
    human, canonical = dual_language_elements(
        element_prefix="automobile",
        scope="scope:automobile",
        human_language="pt-PT",
        human_text="O automóvel transforma energia em movimento.",
        working=working,
        provenance=("document:automobile",),
    )
    revision = SheetRevision(
        sheet_id="dual-automobile",
        revision_id="dual-automobile:1",
        revision_number=1,
        title="Dual automobile sheet",
        state=SheetState.DRAFT,
        elements=(human, canonical),
    )
    workspace = JsonlCognitiveWorkspace(tmp_path)
    workspace.save(revision)
    restored = workspace.latest(revision.sheet_id)

    assert restored.elements[0].language == "pt-PT"
    assert restored.elements[0].kind is SheetElementKind.NOTE
    assert restored.elements[1].language == CANONICAL_WORKING_LANGUAGE
    assert restored.elements[1].kind is (
        SheetElementKind.WORKING_REPRESENTATION
    )
    assert decode_working_json(restored.elements[1].content) == working


def test_confidence_remains_unvalidated_and_authority_cannot_be_forged() -> None:
    working = representation()
    assert working.claims[0].confidence == 0.9
    assert working.authority == WORKING_REPRESENTATION_AUTHORITY
    forged = encode_working_representation(working)
    forged["authority"] = "VALIDATED"

    with pytest.raises(PermissionError, match="cannot grant authority"):
        decode_working_representation(forged)
    with pytest.raises(ValueError, match="between zero and one"):
        WorkingClaim("claim:bad", "Bad confidence", confidence=1.1)
