import os

import networkx as nx
import pytest

from core.file_io import atomic_artifact_path
from core.storage.graph_store import NetworkXStorage
from core.utils import load_json, write_json


def test_json_serialization_failure_preserves_previous_file(tmp_path):
    path = tmp_path / "evidence.json"
    write_json({"old": {"content": "safe evidence"}}, str(path))
    original = path.read_bytes()
    with pytest.raises(ValueError):
        write_json({"bad": float("nan")}, str(path))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


def test_failed_replace_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "evidence.json"
    write_json({"old": {}}, str(path))
    original = path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        write_json({"new": {}}, str(path))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))


def test_failed_fsync_does_not_publish(tmp_path, monkeypatch):
    path = tmp_path / "evidence.json"
    write_json({"old": {}}, str(path))
    original = path.read_bytes()

    def fail(*args):
        raise OSError("sync failed")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="sync failed"):
        write_json({"new": {}}, str(path))
    assert path.read_bytes() == original


def test_publication_occurs_after_writer_completes(tmp_path):
    path = tmp_path / "evidence.json"
    write_json({"old": {}}, str(path))
    with atomic_artifact_path(path) as temporary:
        temporary.write_text('{"new": {}}')
        assert load_json(str(path)) == {"old": {}}
    assert load_json(str(path)) == {"new": {}}


def test_partial_graph_write_preserves_previous_graph(tmp_path, monkeypatch):
    path = tmp_path / "graph.graphml"
    graph = nx.Graph()
    graph.add_node("old")
    NetworkXStorage.write_nx_graph(graph, str(path))
    original = path.read_bytes()

    def interrupted(graph, destination):
        destination.write_bytes(b"<partial")
        raise OSError("interrupted")

    monkeypatch.setattr(nx, "write_graphml", interrupted)
    with pytest.raises(OSError):
        NetworkXStorage.write_nx_graph(graph, str(path))
    assert path.read_bytes() == original


async def test_partial_vector_write_preserves_index_and_restores_client_path(storage_stack, monkeypatch):
    stores, _, working_dir = storage_stack
    store = stores["chunks_vdb"]
    await store.upsert({"old": {"content": "safe evidence"}})
    await store.index_done_callback()
    path = working_dir / "vdb_chunks.json"
    original = path.read_bytes()
    original_client_path = store._client.storage_file

    def interrupted():
        from pathlib import Path
        Path(store._client.storage_file).write_text("partial")
        raise OSError("interrupted")

    monkeypatch.setattr(store._client, "save", interrupted)
    with pytest.raises(RuntimeError, match="persist"):
        await store.index_done_callback()
    assert path.read_bytes() == original
    assert store._client.storage_file == original_client_path
    assert not list(working_dir.glob(".*.tmp"))
