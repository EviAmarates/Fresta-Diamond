from fresta_diamond.meta_memory import MetaMemoryStore
from .test_identity import _meta


def test_meta_memory_is_versioned_and_restart_readable(tmp_path) -> None:
    store = MetaMemoryStore(tmp_path / "meta")
    first = store.save(_meta())
    assert first.version_ref == "meta-analysis:meta:identity@1"

    restarted = MetaMemoryStore(tmp_path / "meta")
    loaded = restarted.latest("meta:identity")
    assert loaded.content_hash == first.content_hash
    assert loaded.report.phi_open is True


def test_meta_memory_preserves_lineage(tmp_path) -> None:
    store = MetaMemoryStore(tmp_path / "meta")
    first = store.save(_meta())
    second = store.save(_meta())

    assert first.version == 1
    assert second.version == 2
    assert len(store.history("meta:identity")) == 2
