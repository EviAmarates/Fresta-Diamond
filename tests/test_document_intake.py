import json

import pytest

from fresta_diamond.application import DiamondApplication
from fresta_diamond.document_intake import read_document
from fresta_diamond.sheet_decomposition import SheetDecompositionService
from fresta_diamond.command_service import DiamondCommandService

from .test_application import PERMISSIONS, response_bundle


def test_document_intake_is_content_addressed_and_utf8_exact(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("Nota bounded.\n", encoding="utf-8", newline="")

    source = read_document(path)

    assert source.source_ref == f"document:{source.content_sha256}"
    assert source.content == "Nota bounded.\n"
    assert source.byte_length == len(source.content.encode("utf-8"))
    assert source.path == str(path.resolve())


def test_document_intake_rejects_binary_and_oversized_sources(tmp_path) -> None:
    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="UTF-8"):
        read_document(binary)

    large = tmp_path / "large.txt"
    large.write_text("12345", encoding="utf-8")
    with pytest.raises(ValueError, match="byte limit"):
        read_document(large, max_bytes=4)


def test_document_intake_rejects_empty_or_non_file_sources(tmp_path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        read_document(empty)

    with pytest.raises(ValueError, match="regular file"):
        read_document(tmp_path / "missing.txt")


def test_application_materializes_document_into_lossless_bounded_sheets(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    content = "Primeira nota.\n" * 20
    path.write_text(content, encoding="utf-8", newline="")
    app = DiamondApplication(
        tmp_path / "data",
        lambda *_args, **_kwargs: {"content": "unused"},
        required_permissions=("llm.test",),
    )

    source = app.ingest_document(path)
    outcome = app.materialize_document(
        source,
        scope="scope:document",
        title="Imported notes",
        max_child_content_tokens=4,
        objective="Inspect imported notes",
    )

    assert len(outcome.leaf_refs) > 1
    assert SheetDecompositionService(app.workspace).reconstruct(outcome) == content
    assert all(ref.revision_id.endswith(":revision:1") for ref in outcome.leaf_refs)


def test_document_leaf_batch_uses_normal_learn_pipeline_and_returns_pending(
    tmp_path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("A bounded document note. " * 20, encoding="utf-8")
    app = DiamondApplication(
        tmp_path / "data",
        lambda _grant, **_kwargs: {
            "content": json.dumps(response_bundle()),
            "model": "document-test",
        },
        required_permissions=PERMISSIONS,
        max_attention_tokens=1_000,
        max_response_tokens=200,
    )
    decomposition = app.materialize_document(
        app.ingest_document(path),
        scope="scope:document",
        title="Imported notes",
        max_child_content_tokens=4,
        objective="Learn bounded document notes",
    )

    outcome = app.learn_document_leaves(
        decomposition,
        objective="Learn bounded document notes",
        max_leaves=1,
    )

    assert len(outcome.outcomes) == 1
    assert outcome.processed_leaf_refs == (
        decomposition.leaf_refs[0].revision_id,
    )
    assert outcome.pending_leaf_refs
    assert len(app.learning_commits()) == 1
    resumed = app.resume_document_learning(
        outcome.checkpoint.checkpoint_id,
        decomposition,
        max_leaves=1,
    )
    assert resumed.processed_leaf_refs == (outcome.pending_leaf_refs[0],)
    assert len(app.learning_commits()) == 2
    restored = app.load_document_decomposition(outcome.checkpoint.checkpoint_id)
    assert SheetDecompositionService(app.workspace).reconstruct(restored) == (
        path.read_text(encoding="utf-8")
    )


def test_document_resume_command_replays_only_pending_leaves(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("A bounded note. " * 20, encoding="utf-8")
    app = DiamondApplication(
        tmp_path / "data",
        lambda _grant, **_kwargs: {
            "content": json.dumps(response_bundle()),
            "model": "document-replay",
        },
        required_permissions=PERMISSIONS,
        max_attention_tokens=1_000,
        max_response_tokens=200,
    )
    decomposition = app.materialize_document(
        app.ingest_document(path),
        scope="scope:document",
        title="Imported notes",
        max_child_content_tokens=4,
        objective="Learn bounded document notes",
    )
    first = app.learn_document_leaves(
        decomposition,
        objective="Learn bounded document notes",
        max_leaves=1,
    )
    commands = DiamondCommandService(app)

    resumed = commands.execute_line(
        f"/document resume {first.checkpoint.checkpoint_id} --max-leaves 1"
    )

    assert resumed.model_call_count >= 1
    assert resumed.payload["processed_leaf_refs"] == (
        first.pending_leaf_refs[0],
    )
    assert resumed.payload["pending_leaf_refs"]
    assert len(app.learning_commits()) == 2
