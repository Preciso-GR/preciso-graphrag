from pathlib import Path

import pytest

from core.runtime_status import update_artifact_manifest
from config import _fallback_embed, build_global_config
from core.bootstrap import build_storage_instances
from core.storage.base import EmbeddingFunc
from core.storage.kv_store import JsonKVStorage
from core.utils import load_json
from preciso_mcp import server


def make_store(tmp_path):
    return JsonKVStorage(
        namespace="text_chunks", workspace="", embedding_func=None,
        global_config={"working_dir": str(tmp_path)},
    )


def test_missing_json_returns_none(tmp_path):
    assert load_json(str(tmp_path / "missing.json")) is None


@pytest.mark.parametrize("content", ['{}', '{"chunk": {"content": "evidence"}}'])
def test_valid_json_object_loads(tmp_path, content):
    path = tmp_path / "store.json"
    path.write_text(content)
    assert isinstance(load_json(str(path)), dict)


@pytest.mark.parametrize("content", [b'{broken', b'', b'null', b'[]', b'false', b'0', b'""', b'\xff'])
def test_invalid_json_is_not_treated_as_missing(tmp_path, content):
    path = tmp_path / "store.json"
    path.write_bytes(content)
    with pytest.raises(RuntimeError, match="store.json"):
        load_json(str(path))
    assert path.read_bytes() == content


def test_unreadable_json_raises_with_original_cause(tmp_path, monkeypatch):
    path = tmp_path / "store.json"
    path.write_text('{"chunk": {"content": "evidence"}}')
    original = path.read_bytes()
    read_text = Path.read_text

    def deny_read(self, *args, **kwargs):
        if self == path:
            raise PermissionError("access denied")
        return read_text(self, *args, **kwargs)

    # chmod is unreliable for privileged test runners; inject the OS error.
    monkeypatch.setattr(Path, "read_text", deny_read)
    with pytest.raises(RuntimeError, match="store.json") as error:
        load_json(str(path))
    assert isinstance(error.value.__cause__, PermissionError)
    assert path.read_bytes() == original


async def test_missing_kv_initializes_empty_without_creating_artifact(tmp_path):
    store = make_store(tmp_path)
    await store.initialize()
    assert await store.get_all_items() == {}
    assert not (tmp_path / "kv_store_text_chunks.json").exists()


async def test_valid_kv_records_load(tmp_path):
    path = tmp_path / "kv_store_text_chunks.json"
    path.write_text('{"chunk": {"content": "evidence"}}')
    store = make_store(tmp_path)
    await store.initialize()
    assert (await store.get_by_id("chunk"))["content"] == "evidence"


@pytest.mark.parametrize("content", [b'{broken', b'null', b'[]', b'{"chunk": null}', b'{"chunk": "bad"}'])
async def test_failed_kv_initialization_cannot_be_bypassed_by_retry(tmp_path, content):
    path = tmp_path / "kv_store_text_chunks.json"
    path.write_bytes(content)
    failed_store = make_store(tmp_path)
    # Retry the same instance and a sibling sharing the namespace registry.
    for store in (failed_store, failed_store, make_store(tmp_path)):
        with pytest.raises(RuntimeError, match="kv_store_text_chunks.json"):
            await store.initialize()
        assert store._data is None
        assert path.read_bytes() == content

    path.write_text('{"restored": {"content": "recovered evidence"}}')
    await failed_store.initialize()
    assert (await failed_store.get_by_id("restored"))["content"] == "recovered evidence"


async def test_bad_diagnostic_manifest_does_not_overwrite_original(tmp_path):
    path = tmp_path / "artifact_manifest.json"
    original = b'{broken'
    path.write_bytes(original)
    assert await update_artifact_manifest({}, {"working_dir": str(tmp_path)}) is None
    assert path.read_bytes() == original


async def test_server_startup_stops_on_corrupt_evidence_store(tmp_path, monkeypatch):
    path = tmp_path / "kv_store_text_chunks.json"
    original = b'{broken'
    path.write_bytes(original)
    cfg = build_global_config(
        working_dir=str(tmp_path),
        embedding_func=EmbeddingFunc(
            embedding_dim=8, max_token_size=128, func=_fallback_embed,
        ),
    )
    stores = build_storage_instances(cfg)
    monkeypatch.setattr(server, "storage_instances", stores)
    monkeypatch.setattr(server, "global_config", cfg)

    with pytest.raises(RuntimeError, match="kv_store_text_chunks.json"):
        await server.startup()
    assert path.read_bytes() == original
    assert not (tmp_path / "artifact_manifest.json").exists()
    assert stores["text_chunks"]._data is None
