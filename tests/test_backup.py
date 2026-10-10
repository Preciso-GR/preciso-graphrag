import fcntl
import os

import pytest

from config import build_global_config
from core.backup import MANIFEST, backup_graph, restore_graph, verify_backup
from core.bootstrap import build_storage_instances, initialize_storage_instances
from core.session_lock import graph_directory_owner
from core.transactions import ArtifactTransaction
from core.utils import write_json
from ingest.pipeline import ingest_extracted_json
from tests.test_pipeline_e2e import make_payload
from tests.test_transactions import artifact_bytes


async def test_backup_restore_reopens_graph_vectors_and_evidence(storage_stack, tmp_path):
    stores, cfg, root = storage_stack
    assert (await ingest_extracted_json(make_payload(), stores, cfg))["status"] == "success"
    before = artifact_bytes(root)
    backup, restored = tmp_path.parent / f"{tmp_path.name}-snapshot", tmp_path.parent / f"{tmp_path.name}-restore"
    manifest = backup_graph(root, backup)
    assert manifest == verify_backup(backup)
    restore_graph(backup, restored)
    assert artifact_bytes(restored) == before
    assert artifact_bytes(root) == before
    reopened = build_storage_instances(build_global_config(working_dir=str(restored), embedding_func=cfg["embedding_func"]))
    await initialize_storage_instances(reopened)
    assert await reopened["graph"].has_node("APPLE")
    assert await reopened["text_chunks"].get_by_id("doc_e2e::chunk-1") is not None
    query = make_payload()["chunks"][0]["content"]
    recovered = await reopened["chunks_vdb"].query(query, top_k=1)
    assert recovered
    assert recovered[0]["chunk_id"] == "doc_e2e::chunk-1"


def source_graph(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    write_json({"one": {"content": "evidence"}}, str(root / "kv_store_text_chunks.json"))
    return root


def test_corrupt_backup_rejected_before_restore(tmp_path):
    source = source_graph(tmp_path)
    snapshot = tmp_path / "snapshot"
    backup_graph(source, snapshot)
    (snapshot / "kv_store_text_chunks.json").write_text('{}')
    with pytest.raises(ValueError, match="checksum"):
        restore_graph(snapshot, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_active_runtime_and_mutation_rejected(tmp_path):
    source = source_graph(tmp_path)
    with graph_directory_owner(str(source)):
        with pytest.raises(RuntimeError, match="runtime"):
            backup_graph(source, tmp_path / "snapshot")
    descriptor = os.open(source / ".preciso-ingestion.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="mutation"):
            backup_graph(source, tmp_path / "snapshot")
    finally:
        os.close(descriptor)
    assert not (tmp_path / "snapshot").exists()


def test_pending_transaction_requires_recovery(tmp_path):
    source = source_graph(tmp_path)
    transaction = ArtifactTransaction(source)
    transaction.begin()
    with pytest.raises(RuntimeError, match="recover"):
        backup_graph(source, tmp_path / "snapshot")
    assert transaction.journal.exists()
    transaction.rollback()
    backup_graph(source, tmp_path / "snapshot")


@pytest.mark.parametrize("name", ["../escape.json", "unexpected.json"])
def test_manifest_rejects_unlisted_artifact_names(tmp_path, name):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    write_json({"format_version": 1, "files": {name: {}}}, str(snapshot / MANIFEST))
    with pytest.raises(ValueError, match="artifact list"):
        restore_graph(snapshot, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_symlink_source_is_not_copied(tmp_path):
    source = source_graph(tmp_path)
    (source / "vdb_chunks.json").symlink_to(source / "kv_store_text_chunks.json")
    with pytest.raises(ValueError, match="regular file"):
        backup_graph(source, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()
    assert not list(tmp_path.glob('.snapshot-*'))


def test_existing_destination_is_preserved(tmp_path):
    source = source_graph(tmp_path)
    snapshot = tmp_path / "snapshot"
    backup_graph(source, snapshot)
    with pytest.raises(FileExistsError):
        backup_graph(source, snapshot)
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "keep").write_text('user data')
    with pytest.raises(FileExistsError):
        restore_graph(snapshot, restored)
    assert (restored / "keep").read_text() == 'user data'


def test_copy_failure_does_not_publish_partial_backup(tmp_path, monkeypatch):
    import core.backup as module
    source = source_graph(tmp_path)
    before = artifact_bytes(source)
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(module.shutil, "copyfileobj", fail)
    with pytest.raises(OSError, match="disk full"):
        backup_graph(source, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()
    assert not list(tmp_path.glob('.snapshot-*'))
    assert artifact_bytes(source) == before


def test_snapshot_inside_source_is_rejected(tmp_path):
    source = source_graph(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        backup_graph(source, source / "snapshot")


def test_changed_backup_during_copy_does_not_publish_restore(tmp_path, monkeypatch):
    import core.backup as module
    source = source_graph(tmp_path)
    snapshot = tmp_path / "snapshot"
    backup_graph(source, snapshot)
    copy = module._copy
    def corrupt(source, destination):
        copy(source, destination)
        destination.write_text('{}')
    monkeypatch.setattr(module, "_copy", corrupt)
    with pytest.raises(ValueError, match="changed during restore"):
        restore_graph(snapshot, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_cli_round_trip_and_error_exit(tmp_path):
    import subprocess
    import sys
    source = source_graph(tmp_path)
    for args in (
        ["backup", str(source), str(tmp_path / "snapshot")],
        ["verify", str(tmp_path / "snapshot")],
        ["restore", str(tmp_path / "snapshot"), str(tmp_path / "restored")],
    ):
        result = subprocess.run([sys.executable, "-m", "preciso_mcp.backup_cli", *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert '"status": "success"' in result.stdout
    result = subprocess.run([sys.executable, "-m", "preciso_mcp.backup_cli", "restore", str(tmp_path / "snapshot"), str(tmp_path / "restored")], capture_output=True, text=True)
    assert result.returncode == 1
    assert "already exists" in result.stderr
