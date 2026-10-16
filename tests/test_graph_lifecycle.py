"""Persistent graph edits and evidence access through the document ledger."""

from __future__ import annotations

import copy

from core.bootstrap import build_storage_instances, initialize_storage_instances
from core.documents import document_operation, graph_operation, read_evidence
from core.utils import compute_mdhash_id
from ingest.pipeline import ingest_extracted_json


def payload(document_id: str, *, prefix: str = "first", include_c: bool = True) -> dict:
    entities = [
        {"entity_name": "ACME", "entity_type": "ORG", "description": f"{prefix} ACME fact.", "source_id": "chunk-1"},
        {"entity_name": "BETA", "entity_type": "ORG", "description": f"{prefix} BETA fact.", "source_id": "chunk-2"},
    ]
    relationships = [
        {"src_id": "ACME", "tgt_id": "BETA", "description": f"{prefix} ACME relates to BETA.", "source_id": "chunk-1"}
    ]
    if include_c:
        entities.append(
            {"entity_name": "GAMMA", "entity_type": "ORG", "description": f"{prefix} GAMMA fact.", "source_id": "chunk-1"}
        )
        relationships.append(
            {"src_id": "ACME", "tgt_id": "GAMMA", "description": f"{prefix} ACME relates to GAMMA.", "source_id": "chunk-1"}
        )
    return {
        "document_id": document_id,
        "file_path": f"{document_id}.md",
        "timestamp": 1_700_000_000,
        "chunks": [
            {"chunk_id": "chunk-1", "content": f"{prefix} shared passage about ACME and GAMMA."},
            {"chunk_id": "chunk-2", "content": f"{prefix} separate passage about BETA."},
        ],
        "entities": entities,
        "relationships": relationships,
    }


async def revision(stores, config):
    result = await graph_operation(stores, config, "inspect")
    assert result["status"] == "success", result
    return result["revision"]


async def commit_graph(stores, config, action, **kwargs):
    preview = await graph_operation(stores, config, action, **kwargs)
    assert preview["status"] == "success", preview
    return await graph_operation(
        stores,
        config,
        action,
        **kwargs,
        expected_revision=preview["revision"],
        dry_run=False,
    )


def chunk_vector_id(chunk_id: str) -> str:
    return compute_mdhash_id(chunk_id, prefix="vchunk-")


async def test_isolate_withholds_shared_passage_vectors_and_read_evidence_then_restore(storage_stack):
    stores, config, _ = storage_stack
    source = payload("graph-isolation")
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    first_id = "graph-isolation::chunk-1"
    second_id = "graph-isolation::chunk-2"
    assert (await read_evidence(stores, config, first_id))["status"] == "success"
    stores["chunks_vdb"].cosine_better_than_threshold = 0.0
    before_vector_query = await stores["chunks_vdb"].query("shared passage", top_k=10)
    assert chunk_vector_id(first_id) in {row["id"] for row in before_vector_query}

    isolated = await commit_graph(stores, config, "isolate", node_id="ACME")

    assert isolated["revision"] == 2
    assert await stores["graph"].get_node("ACME") is None
    # GAMMA is not isolated, but its only claim shares the withheld passage.
    assert await stores["graph"].get_node("GAMMA") is None
    assert await stores["graph"].get_node("BETA") is not None
    assert await stores["graph"].get_edge("ACME", "BETA") is None
    assert await stores["text_chunks"].get_by_id(first_id) is None
    assert await stores["chunks_vdb"].get_by_id(chunk_vector_id(first_id)) is None
    hidden_vector_query = await stores["chunks_vdb"].query("shared passage", top_k=10)
    assert chunk_vector_id(first_id) not in {row["id"] for row in hidden_vector_query}
    assert (await stores["text_chunks"].get_by_id(second_id)) is not None
    hidden = await read_evidence(stores, config, first_id)
    assert hidden["status"] == "error" and hidden["error_code"] == "not_found"
    assert (await read_evidence(stores, config, second_id))["status"] == "success"

    restored = await commit_graph(stores, config, "restore", node_id="ACME")

    assert restored["status"] == "success", restored
    assert await stores["graph"].get_node("ACME") is not None
    assert await stores["graph"].get_node("GAMMA") is not None
    assert await stores["graph"].get_edge("ACME", "BETA") is not None
    assert (await read_evidence(stores, config, first_id))["status"] == "success"
    restored_vector_query = await stores["chunks_vdb"].query("shared passage", top_k=10)
    assert chunk_vector_id(first_id) in {row["id"] for row in restored_vector_query}


async def test_isolation_is_reapplied_to_new_documents_and_survives_reopen(storage_stack):
    stores, config, _ = storage_stack
    original = payload("graph-persistent-edit", include_c=False)
    assert (await ingest_extracted_json(original, stores, config))["status"] == "success"
    assert (await commit_graph(stores, config, "isolate", node_id="ACME"))["status"] == "success"

    later = {
        "document_id": "graph-persistent-later",
        "file_path": "later.md",
        "chunks": [{"chunk_id": "later-1", "content": "Later ACME evidence."}],
        "entities": [{"entity_name": "ACME", "entity_type": "ORG", "description": "Later ACME fact.", "source_id": "later-1"}],
        "relationships": [],
    }
    assert (await ingest_extracted_json(later, stores, config))["status"] == "success"

    reopened = build_storage_instances(config)
    await initialize_storage_instances(reopened)
    for name in ("documents", "graph", "text_chunks", "chunks_vdb", "entities_vdb", "relationships_vdb"):
        await reopened[name].reload_from_disk()

    assert await reopened["graph"].get_node("ACME") is None
    assert await reopened["text_chunks"].get_by_id("graph-persistent-later::later-1") is None
    inspected = await graph_operation(reopened, config, "inspect")
    assert inspected["revision"] == 3
    assert "ACME" in inspected["edits"]["isolated"]


async def test_merge_retargets_edges_and_future_ingest_without_resurrecting_source(storage_stack):
    stores, config, _ = storage_stack
    first = {
        "document_id": "graph-merge-first",
        "file_path": "first.md",
        "chunks": [
            {"chunk_id": "c1", "content": "Alpha is the same as Beta."},
            {"chunk_id": "c2", "content": "Alpha is related to Gamma."},
        ],
        "entities": [
            {"entity_name": "ALPHA", "entity_type": "ORG", "description": "Alpha entity fact.", "source_id": "c1"},
            {"entity_name": "BETA", "entity_type": "ORG", "description": "Beta entity fact.", "source_id": "c1"},
            {"entity_name": "GAMMA", "entity_type": "ORG", "description": "Gamma entity fact.", "source_id": "c2"},
        ],
        "relationships": [
            {"src_id": "ALPHA", "tgt_id": "BETA", "description": "Alpha duplicates Beta.", "source_id": "c1"},
            {"src_id": "ALPHA", "tgt_id": "GAMMA", "description": "Alpha links Gamma.", "source_id": "c2"},
        ],
    }
    assert (await ingest_extracted_json(first, stores, config))["status"] == "success"

    merged = await commit_graph(stores, config, "merge", node_id="ALPHA", target_id="BETA")

    assert merged["status"] == "success", merged
    assert await stores["graph"].get_node("ALPHA") is None
    assert await stores["graph"].get_node("BETA") is not None
    assert await stores["graph"].get_edge("BETA", "GAMMA") is not None
    assert await stores["graph"].get_edge("ALPHA", "GAMMA") is None
    replay = await ingest_extracted_json(copy.deepcopy(first), stores, config)
    assert replay["status"] == "success" and replay["replay"] is True
    assert await stores["graph"].get_node("ALPHA") is None

    later = {
        "document_id": "graph-merge-later",
        "file_path": "later.md",
        "chunks": [{"chunk_id": "c1", "content": "Alpha still has another connection to Gamma."}],
        "entities": [
            {"entity_name": "ALPHA", "entity_type": "ORG", "description": "New Alpha fact.", "source_id": "c1"},
            {"entity_name": "GAMMA", "entity_type": "ORG", "description": "New Gamma fact.", "source_id": "c1"},
        ],
        "relationships": [
            {"src_id": "ALPHA", "tgt_id": "GAMMA", "description": "New Alpha Gamma relation.", "source_id": "c1"}
        ],
    }
    assert (await ingest_extracted_json(later, stores, config))["status"] == "success"
    assert await stores["graph"].get_node("ALPHA") is None
    assert "New Alpha fact." in (await stores["graph"].get_node("BETA"))["description"]
    assert "New Alpha Gamma relation." in (await stores["graph"].get_edge("BETA", "GAMMA"))["description"]

    assert (await commit_graph(stores, config, "isolate", node_id="BETA"))["status"] == "success"
    assert await stores["graph"].get_node("BETA") is None
    assert (await commit_graph(stores, config, "restore", node_id="BETA"))["status"] == "success"
    assert await stores["graph"].get_node("BETA") is not None
    assert (await commit_graph(stores, config, "remove", node_id="BETA"))["status"] == "success"
    assert await stores["graph"].get_node("BETA") is None
    future_alias = {
        "document_id": "graph-merge-after-remove",
        "file_path": "after-remove.md",
        "chunks": [{"chunk_id": "c1", "content": "Another Alpha fact."}],
        "entities": [{"entity_name": "ALPHA", "entity_type": "ORG", "description": "Another Alpha fact.", "source_id": "c1"}],
        "relationships": [],
    }
    assert (await ingest_extracted_json(future_alias, stores, config))["status"] == "success"
    assert await stores["graph"].get_node("ALPHA") is None
    assert await stores["graph"].get_node("BETA") is None


async def test_disconnect_removes_only_edge_and_persists_for_new_contributions(storage_stack):
    stores, config, _ = storage_stack
    source = payload("graph-remove-disconnect", include_c=False)
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    disconnected = await commit_graph(
        stores, config, "disconnect", node_id="ACME", target_id="BETA"
    )
    assert disconnected["status"] == "success", disconnected
    assert await stores["graph"].get_edge("ACME", "BETA") is None
    assert await stores["graph"].get_node("ACME") is not None
    assert await stores["graph"].get_node("BETA") is not None
    assert (await read_evidence(stores, config, "graph-remove-disconnect::chunk-1"))["status"] == "success"

    later = {
        "document_id": "graph-disconnect-later",
        "file_path": "later.md",
        "chunks": [{"chunk_id": "c1", "content": "ACME connects to BETA."}],
        "entities": [
            {"entity_name": "ACME", "entity_type": "ORG", "description": "Later ACME.", "source_id": "c1"},
            {"entity_name": "BETA", "entity_type": "ORG", "description": "Later BETA.", "source_id": "c1"},
        ],
        "relationships": [{"src_id": "ACME", "tgt_id": "BETA", "description": "Later edge.", "source_id": "c1"}],
    }
    assert (await ingest_extracted_json(later, stores, config))["status"] == "success"
    assert await stores["graph"].get_edge("ACME", "BETA") is None


async def test_remove_suppresses_active_node_but_retains_original_payload(storage_stack):
    stores, config, _ = storage_stack
    source = payload("graph-permanent-remove", include_c=False)
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    removed = await commit_graph(stores, config, "remove", node_id="ACME")
    assert removed["status"] == "success", removed
    assert await stores["graph"].get_node("ACME") is None
    assert (await stores["documents"].get_by_id("graph-permanent-remove"))["payload"] == source


async def test_generated_chunk_ids_remain_stable_when_earlier_chunks_are_withheld(storage_stack):
    stores, config, _ = storage_stack
    document_id = "graph-generated-id"
    first_text = "ACME private passage."
    second_text = "BETA public passage."
    first_raw_id = compute_mdhash_id(f"{document_id}:0:{first_text}", prefix="chunk-")
    second_raw_id = compute_mdhash_id(f"{document_id}:1:{second_text}", prefix="chunk-")
    source = {
        "document_id": document_id,
        "file_path": f"{document_id}.md",
        "chunks": [{"content": first_text}, {"content": second_text}],
        "entities": [
            {"entity_name": "ACME", "entity_type": "ORG", "description": "Private ACME fact.", "source_id": first_raw_id},
            {"entity_name": "BETA", "entity_type": "ORG", "description": "Public BETA fact.", "source_id": second_raw_id},
        ],
        "relationships": [],
    }
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    original_second_id = f"{document_id}::{second_raw_id}"
    assert (await read_evidence(stores, config, original_second_id))["status"] == "success"

    assert (await commit_graph(stores, config, "isolate", node_id="ACME"))["status"] == "success"
    assert await stores["text_chunks"].get_by_id(original_second_id) is not None
    assert (await commit_graph(stores, config, "restore", node_id="ACME"))["status"] == "success"

    restored_ids = await stores["text_chunks"].get_all_items()
    assert f"{document_id}::{first_raw_id}" in restored_ids
    assert original_second_id in restored_ids
    assert (await read_evidence(stores, config, original_second_id))["status"] == "success"


async def test_replace_updates_live_chunk_vector_and_last_delete_leaves_empty_index(storage_stack):
    stores, config, _ = storage_stack
    stores["chunks_vdb"].cosine_better_than_threshold = 0.95
    old = {
        "document_id": "graph-vector-replace",
        "file_path": "vector.md",
        "chunks": [{"chunk_id": "stable", "content": "oldzebraquartz"}],
        "entities": [{"entity_name": "ZEBRA", "entity_type": "ORG", "description": "Old fact.", "source_id": "stable"}],
        "relationships": [],
    }
    assert (await ingest_extracted_json(old, stores, config))["status"] == "success"
    vector_id = chunk_vector_id("graph-vector-replace::stable")
    old_search = await stores["chunks_vdb"].query("oldzebraquartz", top_k=10)
    assert vector_id in {row["id"] for row in old_search}

    replacement = copy.deepcopy(old)
    replacement["chunks"][0]["content"] = "newpurplephoenix"
    replacement["entities"][0]["description"] = "New fact."
    listing = await document_operation(stores, config, "list")
    replaced = await document_operation(
        stores,
        config,
        "replace",
        document_id="graph-vector-replace",
        payload=replacement,
        expected_revision=listing["revision"],
        dry_run=False,
    )
    assert replaced["status"] == "success", replaced
    new_search = await stores["chunks_vdb"].query("newpurplephoenix", top_k=10)
    assert vector_id in {row["id"] for row in new_search}
    assert all(row.get("content") == "newpurplephoenix" for row in new_search)
    assert await stores["chunks_vdb"].query("oldzebraquartz", top_k=10) == []

    listing = await document_operation(stores, config, "list")
    deleted = await document_operation(
        stores,
        config,
        "delete",
        document_id="graph-vector-replace",
        expected_revision=listing["revision"],
        dry_run=False,
    )
    assert deleted["status"] == "success", deleted
    assert await stores["chunks_vdb"].query("newpurplephoenix", top_k=10) == []


async def test_graph_edit_rebuild_failure_restores_prior_graph_and_rules(storage_stack, monkeypatch):
    stores, config, _ = storage_stack
    source = payload("graph-edit-rollback", include_c=False)
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    before_node = copy.deepcopy(await stores["graph"].get_node("ACME"))
    before_evidence = copy.deepcopy(
        await stores["text_chunks"].get_by_id("graph-edit-rollback::chunk-1")
    )

    async def fail_write(data):
        raise OSError("injected evidence write failure")

    monkeypatch.setattr(stores["text_chunks"], "upsert", fail_write)
    listing = await graph_operation(stores, config, "inspect")
    result = await graph_operation(
        stores,
        config,
        "isolate",
        node_id="ACME",
        expected_revision=listing["revision"],
        dry_run=False,
    )

    assert result["status"] == "error"
    assert await stores["graph"].get_node("ACME") == before_node
    assert await stores["text_chunks"].get_by_id("graph-edit-rollback::chunk-1") == before_evidence
    after = await graph_operation(stores, config, "inspect")
    assert "ACME" not in after["edits"].get("isolated", [])


async def test_invalid_claims_are_rejected_before_edit_projection(storage_stack):
    stores, config, _ = storage_stack
    initial = payload("graph-invalid-after-edit", include_c=False)
    assert (await ingest_extracted_json(initial, stores, config))["status"] == "success"
    assert (await commit_graph(stores, config, "isolate", node_id="ACME"))["status"] == "success"

    invalid_hidden_entity = {
        "document_id": "graph-invalid-hidden-entity",
        "file_path": "invalid-entity.md",
        "chunks": [{"chunk_id": "c1", "content": "Hidden incomplete claim."}],
        "entities": [
            {"entity_name": "ACME", "entity_type": "ORG", "source_id": "c1"},
        ],
        "relationships": [],
    }
    invalid_unknown_endpoint = {
        "document_id": "graph-invalid-unknown-endpoint",
        "file_path": "invalid-relation.md",
        "chunks": [{"chunk_id": "c1", "content": "Unknown endpoint claim."}],
        "entities": [
            {"entity_name": "ALPHA", "entity_type": "ORG", "description": "Alpha fact.", "source_id": "c1"},
        ],
        "relationships": [
            {"src_id": "ALPHA", "tgt_id": "GHOST", "description": "Invalid relation.", "source_id": "c1"},
        ],
    }

    for invalid in (invalid_hidden_entity, invalid_unknown_endpoint):
        result = await ingest_extracted_json(invalid, stores, config)
        assert result["status"] == "error", result
        assert result["error_code"] == "validation_failed"
        assert await stores["documents"].get_by_id(invalid["document_id"]) is None
        assert await stores["text_chunks"].get_by_id(f"{invalid['document_id']}::c1") is None


async def test_isolation_matches_raw_chunk_ids_that_contain_namespace_delimiters(storage_stack):
    stores, config, _ = storage_stack
    source = {
        "document_id": "graph-delimited-source",
        "file_path": "delimited.md",
        "chunks": [{"chunk_id": "foreign::chunk", "content": "Private ACME passage."}],
        "entities": [{"entity_name": "ACME", "entity_type": "ORG", "description": "Private ACME fact.", "source_id": "foreign::chunk"}],
        "relationships": [],
    }
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    evidence_id = "graph-delimited-source::foreign::chunk"
    assert (await read_evidence(stores, config, evidence_id))["status"] == "success"

    result = await commit_graph(stores, config, "isolate", node_id="ACME")

    assert result["status"] == "success", result
    assert await stores["text_chunks"].get_by_id(evidence_id) is None
    assert (await read_evidence(stores, config, evidence_id))["error_code"] == "not_found"


async def test_empty_chunk_claim_is_rejected_before_isolation_projection(storage_stack):
    stores, config, _ = storage_stack
    initial = payload("graph-empty-after-edit", include_c=False)
    assert (await ingest_extracted_json(initial, stores, config))["status"] == "success"
    assert (await commit_graph(stores, config, "isolate", node_id="ACME"))["status"] == "success"
    invalid = {
        "document_id": "graph-empty-hidden-claim",
        "file_path": "empty.md",
        "chunks": [{"chunk_id": "empty-chunk", "content": "   "}],
        # The isolated entity would be omitted by _project. The empty passage
        # still must fail validation before that projection can hide the claim.
        "entities": [{"entity_name": "ACME", "entity_type": "ORG", "description": "Hidden claim.", "source_id": "empty-chunk"}],
        "relationships": [],
    }

    result = await ingest_extracted_json(invalid, stores, config)

    assert result["status"] == "error", result
    assert result["error_code"] == "validation_failed"
    assert await stores["documents"].get_by_id(invalid["document_id"]) is None
    assert await stores["text_chunks"].get_by_id("graph-empty-hidden-claim::empty-chunk") is None


async def test_rename_dry_run_and_stale_revision_guard(storage_stack):
    stores, config, _ = storage_stack
    source = payload("graph-rename", include_c=False)
    assert (await ingest_extracted_json(source, stores, config))["status"] == "success"
    current_revision = await revision(stores, config)
    preview = await graph_operation(
        stores, config, "rename", node_id="ACME", label="Acme Corporation"
    )
    assert preview["status"] == "success" and preview["dry_run"] is True
    assert preview["revision"] == current_revision
    assert "display_name" not in await stores["graph"].get_node("ACME")

    renamed = await graph_operation(
        stores,
        config,
        "rename",
        node_id="ACME",
        label="Acme Corporation",
        expected_revision=preview["revision"],
        dry_run=False,
    )
    assert renamed["status"] == "success", renamed
    assert (await stores["graph"].get_node("ACME"))["display_name"] == "Acme Corporation"
    stale = await graph_operation(
        stores,
        config,
        "rename",
        node_id="ACME",
        label="Stale rename",
        expected_revision=preview["revision"],
        dry_run=False,
    )
    assert stale["status"] == "error" and stale["error_code"] == "revision_conflict"
    assert (await stores["graph"].get_node("ACME"))["display_name"] == "Acme Corporation"

