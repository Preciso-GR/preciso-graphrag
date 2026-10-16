"""Ingestion adapters must retain the core outcome used by agent workflows."""
from __future__ import annotations

import copy
import json

import pytest

from preciso_mcp import server
from preciso_mcp.tools import ingest_from_file_tool, reconcile_tool


@pytest.mark.parametrize("entry", ["inline", "file", "replay", "reconciled"])
@pytest.mark.parametrize("outcome", [
    {"status": "error", "error_code": "revision_conflict", "revision": 7,
     "message": "Use document replacement", "details": {"retryable": False}},
    {"status": "success", "document_id": "report", "revision": 7, "replay": True,
     "entities_merged": 2, "relationships_merged": 1, "chunks_ingested": 3,
     "ingestion_counts": {
         "entities": {"added": 0, "merged": 0, "skipped_duplicate": 2},
         "relationships": {"added": 0, "merged": 0, "skipped_duplicate": 1},
         "chunks": {"added": 0, "merged": 0, "skipped_duplicate": 3}},
     "file_path": "original-report.md", "extension_metadata": {"retained": True}},
    {"status": "partial_success", "revision": 8, "replay": False,
     "errors": ["One claim was invalid"], "warnings": [],
     "summary_events": [{"kind": "entity", "name": "ACME"}]},
], ids=["revision-conflict", "duplicate-replay", "committed-partial-result"])
async def test_ingestion_adapters_preserve_core_outcomes(entry, outcome, tmp_path, monkeypatch):
    payload = {"document_id": "report", "entities": [], "relationships": [], "chunks": []}
    path = tmp_path / "extraction.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    core_result = copy.deepcopy(outcome)

    async def ingest(*args, **kwargs):
        return core_result

    config = {"input_dir": str(tmp_path), "working_dir": str(tmp_path / "graph")}
    if entry == "inline":
        monkeypatch.setattr(server, "ingest_extracted_json", ingest)
        result = await server.ingest_graph_tool(payload)
    elif entry == "reconciled":
        monkeypatch.setattr(reconcile_tool, "ingest_extracted_json", ingest)
        result = await reconcile_tool.ingest_with_reconciliation([str(path)], {}, config)
        assert result["files_reconciled"] == 1
        assert result["unified_file"]
    else:
        monkeypatch.setattr(ingest_from_file_tool, "ingest_extracted_json", ingest)
        tool = (ingest_from_file_tool.reingest_from_file if entry == "replay"
                else ingest_from_file_tool.ingest_from_file)
        result = await tool(str(path), {}, config)
        assert result["file_path"] == str(path)

    for field, value in outcome.items():
        if field == "file_path" and entry in {"file", "replay"}:
            assert result["source_file_path"] == value
        else:
            assert result[field] == value
    assert core_result == outcome, "The adapter must not mutate the core result"


async def test_file_ingestion_reports_actual_replay_and_revision_conflict(storage_stack, monkeypatch):
    stores, config, directory = storage_stack
    config["input_dir"] = str(directory)
    monkeypatch.setenv("GRAPHRAG_STRICT_SOURCE_IDS", "true")
    path = directory / "report.json"
    payload = {"document_id": "report", "file_path": "original.md",
               "entities": [], "relationships": [],
               "chunks": [{"chunk_id": "one", "content": "ACME reported USD 10 million."}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    first = await ingest_from_file_tool.ingest_from_file(str(path), stores, config)
    assert first["status"] == "success"
    assert first["revision"] == 1 and first["replay"] is False
    assert first["chunks_stored"] == 1
    assert first["source_file_path"] == "original.md"

    replay = await ingest_from_file_tool.reingest_from_file(str(path), stores, config)
    assert replay["status"] == "success"
    assert replay["revision"] == 1 and replay["replay"] is True
    assert replay["document_id"] == "report"
    assert replay["chunks_stored"] == 0
    assert replay["ingestion_counts"]["chunks"]["skipped_duplicate"] == 1

    payload["chunks"][0]["content"] = "ACME reported USD 20 million."
    path.write_text(json.dumps(payload), encoding="utf-8")
    conflict = await ingest_from_file_tool.ingest_from_file(str(path), stores, config)
    assert conflict["status"] == "error"
    assert conflict["error_code"] == "revision_conflict" and conflict["revision"] == 1
    assert (await stores["text_chunks"].get_by_id("report::one"))["content"] == "ACME reported USD 10 million."


async def test_reconciliation_reports_actual_replay_and_revision_conflict(storage_stack):
    stores, config, directory = storage_stack
    config["input_dir"] = str(directory)
    path = directory / "base.json"
    payload = {"document_id": "report_part1", "entities": [], "relationships": [],
               "chunks": [{"chunk_id": "one", "content": "Original evidence."}]}
    path.write_text(json.dumps(payload), encoding="utf-8")

    first = await reconcile_tool.ingest_with_reconciliation([str(path)], stores, config)
    assert first["status"] == "success"
    assert first["document_id"] == "report"
    assert first["revision"] == 1 and first["replay"] is False
    replay = await reconcile_tool.ingest_with_reconciliation([str(path)], stores, config)
    assert replay["status"] == "success"
    assert replay["revision"] == 1 and replay["replay"] is True
    assert replay["ingestion_counts"]["chunks"]["skipped_duplicate"] == 1

    payload["chunks"][0]["content"] = "Changed evidence."
    path.write_text(json.dumps(payload), encoding="utf-8")
    conflict = await reconcile_tool.ingest_with_reconciliation([str(path)], stores, config)
    assert conflict["status"] == "error"
    assert conflict["error_code"] == "revision_conflict" and conflict["revision"] == 1
    assert conflict["message"]
    assert (await stores["text_chunks"].get_by_id("report::one"))["content"] == "Original evidence."


@pytest.mark.parametrize("entry", ["inline", "file", "reconciled"])
async def test_explicit_partial_ingestion_reports_that_data_was_committed(entry, storage_stack, monkeypatch):
    stores, config, directory = storage_stack
    config.update(input_dir=str(directory), allow_partial_ingest=True)
    payload = {"document_id": "partial", "relationships": [],
               "chunks": [{"chunk_id": "one", "content": "Retained evidence."}],
               "entities": [{"entity_name": "GHOST", "entity_type": "ORG", "source_id": "one"}]}
    path = directory / "partial.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    if entry == "inline":
        monkeypatch.setattr(server, "storage_instances", stores)
        monkeypatch.setattr(server, "global_config", config)
        result = await server.ingest_graph_tool(payload)
    elif entry == "reconciled":
        result = await reconcile_tool.ingest_with_reconciliation([str(path)], stores, config)
    else:
        result = await ingest_from_file_tool.ingest_from_file(str(path), stores, config)
    assert result["status"] == "partial_success"
    assert result["revision"] == 1
    assert result["errors"]
    assert await stores["graph"].get_node("GHOST") is None
    assert (await stores["text_chunks"].get_by_id("partial::one"))["content"] == "Retained evidence."
