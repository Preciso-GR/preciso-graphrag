import json

import pytest

from config import _fallback_embed, build_global_config
from core.storage.base import EmbeddingFunc
from core.storage.vector_store import NanoVectorDBStorage


def open_store(tmp_path, model="model-a", revision="v1"):
    embedding = EmbeddingFunc(8, 128, _fallback_embed, model_name=model, provider="test", model_revision=revision)
    cfg = build_global_config(working_dir=str(tmp_path), embedding_func=embedding)
    return NanoVectorDBStorage("chunks", "", cfg, embedding_func=embedding, meta_fields={"content"})


async def test_same_dimension_different_model_rejected_without_writes(tmp_path):
    writer = open_store(tmp_path)
    await writer.initialize()
    await writer.upsert({"record": {"content": "real evidence"}})
    await writer.index_done_callback()
    path = tmp_path / "vdb_chunks.json"
    original = path.read_bytes()
    with pytest.raises(ValueError, match="model/dimension/revision"):
        open_store(tmp_path, model="model-b")
    with pytest.raises(ValueError, match="model/dimension/revision"):
        open_store(tmp_path, revision="v2")
    assert path.read_bytes() == original
    reader = open_store(tmp_path)
    await reader.initialize()
    assert (await reader.get_by_id("record"))["content"] == "real evidence"


async def test_legacy_index_without_verified_identity_is_rejected(tmp_path):
    writer = open_store(tmp_path, revision=None)
    await writer.initialize()
    await writer.upsert({"record": {"content": "real evidence"}})
    await writer.index_done_callback()
    path = tmp_path / "vdb_chunks.json"
    data = json.loads(path.read_text())
    data.pop("additional_data")
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="no verified embedding identity"):
        open_store(tmp_path, revision=None)
    assert path.read_bytes() == original

    manifest = {"embedding": {"provider": "test", "model": "model-a", "dimension": 8}}
    (tmp_path / "artifact_manifest.json").write_text(json.dumps(manifest))
    reader = open_store(tmp_path, revision=None)
    await reader.initialize()
    assert await reader.get_by_id("record") is not None
    assert path.read_bytes() == original  # Migration is persisted only on save.
