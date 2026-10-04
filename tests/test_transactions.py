import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest

from core.session_lock import graph_directory_owner, graph_read_session
from core.transactions import ARTIFACTS, ArtifactTransaction, JOURNAL, recover_artifacts, run_artifact_mutation
from core.utils import load_json, write_json
from ingest.pipeline import ingest_extracted_json
from tests.test_pipeline_e2e import make_payload


def artifact_bytes(root):
    return {name: (root / name).read_bytes() for name in ARTIFACTS if (root / name).exists()}


async def test_failed_save_restores_all_files_and_memory(storage_stack, monkeypatch):
    stores, cfg, root = storage_stack
    assert (await ingest_extracted_json(make_payload(), stores, cfg))["status"] == "success"
    before = artifact_bytes(root)
    node = dict(await stores["graph"].get_node("APPLE"))
    payload = make_payload()
    payload["document_id"] = "failed-document"

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(stores["entities_vdb"]._client, "save", fail)
    result = await ingest_extracted_json(payload, stores, cfg)
    assert result["status"] == "error"
    assert artifact_bytes(root) == before
    assert dict(await stores["graph"].get_node("APPLE")) == node
    assert await stores["text_chunks"].get_by_id("failed-document::chunk-1") is None
    assert not (root / JOURNAL).exists()
    assert (await ingest_extracted_json(payload, stores, cfg))["status"] == "success"


async def test_cancellation_restores_memory_and_releases_session(storage_stack):
    stores, cfg, root = storage_stack
    baseline = artifact_bytes(root)
    started = asyncio.Event()

    async def mutate():
        await stores["text_chunks"].upsert({"bad": {"content": "uncommitted"}})
        await stores["text_chunks"].index_done_callback()
        await stores["graph"].upsert_node("uncommitted", {"kind": "test"})
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(run_artifact_mutation(mutate, stores, cfg))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert artifact_bytes(root) == baseline
    assert await stores["text_chunks"].get_by_id("bad") is None
    assert not await stores["graph"].has_node("uncommitted")
    assert not (root / JOURNAL).exists()
    async with graph_read_session(cfg):
        pass


@pytest.mark.parametrize("committed", [False, True])
def test_real_process_kill_recovers_transaction(tmp_path, committed):
    path = tmp_path / "kv_store_text_chunks.json"
    write_json({"old": {}}, str(path))
    code = '''
import os, signal, sys
from pathlib import Path
from core.transactions import ArtifactTransaction
from core.utils import write_json
root = Path(sys.argv[1])
transaction = ArtifactTransaction(root)
transaction.begin()
write_json({"new": {}}, str(root / "kv_store_text_chunks.json"))
write_json({"added": {}}, str(root / "kv_store_entity_chunks.json"))
if sys.argv[2] == "True":
    write_json({"state": "committed", "previous_files": transaction.previous_files}, str(transaction.journal / "manifest.json"))
os.kill(os.getpid(), signal.SIGKILL)
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), str(committed)], capture_output=True)
    assert result.returncode == -9, result.stderr
    recover_artifacts({"working_dir": str(tmp_path)})
    assert load_json(str(path)) == ({"new": {}} if committed else {"old": {}})
    assert (tmp_path / "kv_store_entity_chunks.json").exists() == committed
    assert not (tmp_path / JOURNAL).exists()


def test_recovery_can_resume_after_interrupted_rollback(tmp_path, monkeypatch):
    first = tmp_path / "kv_store_text_chunks.json"
    second = tmp_path / "kv_store_entity_chunks.json"
    for path in (first, second):
        write_json({"old": {}}, str(path))
    transaction = ArtifactTransaction(tmp_path)
    transaction.begin()
    assert first.stat().st_ino == (transaction.journal / first.name).stat().st_ino
    for path in (first, second):
        write_json({"new": {}}, str(path))
    replace = os.replace

    def interrupted(source, destination):
        if Path(destination) == second:
            raise OSError("recovery interrupted")
        return replace(source, destination)

    monkeypatch.setattr(os, "replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        recover_artifacts({"working_dir": str(tmp_path)})
    assert (tmp_path / JOURNAL / first.name).exists()
    monkeypatch.setattr(os, "replace", replace)
    recover_artifacts({"working_dir": str(tmp_path)})
    assert all(load_json(str(path)) == {"old": {}} for path in (first, second))


def test_second_runtime_is_rejected_and_owner_released(tmp_path):
    with graph_directory_owner(str(tmp_path)):
        with pytest.raises(RuntimeError, match="Another MCP runtime"):
            with graph_directory_owner(str(tmp_path)):
                pass
    with graph_directory_owner(str(tmp_path)):
        pass


async def test_read_waits_until_mutation_has_committed(storage_stack):
    stores, cfg, _ = storage_stack
    started, release = asyncio.Event(), asyncio.Event()

    async def mutate():
        await stores["text_chunks"].upsert({"record": {"content": "committed evidence"}})
        started.set()
        await release.wait()
        await stores["text_chunks"].index_done_callback()
        return {"status": "success"}

    async def read():
        async with graph_read_session(cfg):
            return await stores["text_chunks"].get_by_id("record")

    writer = asyncio.create_task(run_artifact_mutation(mutate, stores, cfg))
    await asyncio.wait_for(started.wait(), 2)
    reader = asyncio.create_task(read())
    await asyncio.sleep(0)
    assert not reader.done()
    release.set()
    await writer
    assert (await reader)["content"] == "committed evidence"


async def test_invalid_semantic_record_rolls_back_complete_document_by_default(storage_stack):
    stores, cfg, root = storage_stack
    payload = make_payload()
    payload["entities"].append({"entity_name": "invalid"})
    baseline = artifact_bytes(root)
    result = await ingest_extracted_json(payload, stores, cfg)
    assert result["status"] == "validation_failed"
    assert artifact_bytes(root) == baseline
    assert await stores["text_chunks"].get_all_items() == {}
    assert not await stores["graph"].has_node("APPLE")


async def test_failed_rollback_blocks_further_reads_and_mutations(storage_stack, monkeypatch):
    stores, cfg, root = storage_stack

    async def rejected():
        await stores["text_chunks"].upsert({"bad": {"content": "uncommitted"}})
        return {"status": "error"}

    def failed_rollback(self):
        raise OSError("cannot restore storage")

    monkeypatch.setattr(ArtifactTransaction, "rollback", failed_rollback)
    with pytest.raises(OSError):
        await run_artifact_mutation(rejected, stores, cfg)
    assert (root / JOURNAL).exists()
    with pytest.raises(RuntimeError, match="Storage recovery failed"):
        async with graph_read_session(cfg):
            pass
    with pytest.raises(RuntimeError, match="Storage recovery failed"):
        await run_artifact_mutation(rejected, stores, cfg)
