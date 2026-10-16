"""Document lifecycle operations against the offline storage stack."""

from __future__ import annotations

import copy

from core.bootstrap import build_storage_instances, initialize_storage_instances
from core.transactions import ARTIFACTS
from core.utils import compute_mdhash_id
from ingest.pipeline import ingest_extracted_json


def document_payload(
    document_id: str,
    *,
    chunk_text: str,
    entity_description: str,
    relation_description: str = "ACME partners with BETA.",
) -> dict:
    return {
        "document_id": document_id,
        "file_path": f"{document_id}.md",
        "timestamp": 1_700_000_000,
        "chunks": [{"chunk_id": "chunk-1", "content": chunk_text}],
        "entities": [
            {
                "entity_name": "ACME",
                "entity_type": "ORG",
                "description": entity_description,
                "source_id": "chunk-1",
            },
            {
                "entity_name": "BETA",
                "entity_type": "ORG",
                "description": f"BETA mentioned by {document_id}.",
                "source_id": "chunk-1",
            },
        ],
        "relationships": [
            {
                "src_id": "ACME",
                "tgt_id": "BETA",
                "description": relation_description,
                "source_id": "chunk-1",
            }
        ],
    }


async def lifecycle(stores, config, action, **kwargs):
    from core.documents import document_operation

    return await document_operation(stores, config, action, **kwargs)


async def committed_create(stores, config, payload):
    return await lifecycle(
        stores,
        config,
        "create",
        document_id=payload["document_id"],
        payload=payload,
        dry_run=False,
    )


async def workspace_revision(stores, config):
    result = await lifecycle(stores, config, "list")
    assert result["status"] == "success", result
    return result["revision"]


async def test_create_and_identical_replay_are_idempotent(storage_stack):
    stores, config, _ = storage_stack
    payload = document_payload(
        "lifecycle-replay", chunk_text="ACME evidence.", entity_description="ACME is a company."
    )

    first = await committed_create(stores, config, payload)
    second = await committed_create(stores, config, copy.deepcopy(payload))

    assert first["status"] == second["status"] == "success"
    assert second["replay"] is True
    chunks = await stores["text_chunks"].get_all_items()
    assert list(key for key in chunks if key.startswith("lifecycle-replay::")) == [
        "lifecycle-replay::chunk-1"
    ]
    listed = await lifecycle(stores, config, "list")
    assert listed["revision"] == second["revision"]
    assert len(listed["documents"]) == 1
    assert "payload" not in listed["documents"][0]


async def test_replace_and_delete_preserve_other_document_contributions(storage_stack):
    stores, config, _ = storage_stack
    first = document_payload(
        "lifecycle-first", chunk_text="Original first evidence.", entity_description="First ACME fact."
    )
    second = document_payload(
        "lifecycle-second", chunk_text="Second evidence.", entity_description="Second ACME fact.",
        relation_description="Second document supports ACME and BETA.",
    )
    assert (await committed_create(stores, config, first))["status"] == "success"
    assert (await committed_create(stores, config, second))["status"] == "success"

    replacement = document_payload(
        "lifecycle-first", chunk_text="Corrected first evidence.",
        entity_description="Corrected ACME fact.", relation_description="Corrected relationship fact.",
    )
    revision = await workspace_revision(stores, config)
    preview = await lifecycle(
        stores,
        config,
        "replace",
        document_id="lifecycle-first",
        payload=replacement,
        expected_revision=revision,
    )
    assert preview["status"] == "success", preview
    assert preview["revision"] == revision
    assert "First ACME fact." in (await stores["graph"].get_node("ACME"))["description"]

    replaced = await lifecycle(
        stores,
        config,
        "replace",
        document_id="lifecycle-first",
        payload=replacement,
        expected_revision=preview["revision"],
        dry_run=False,
    )
    assert replaced["status"] == "success", replaced

    node = await stores["graph"].get_node("ACME")
    assert "Corrected ACME fact." in node["description"]
    assert "Second ACME fact." in node["description"]
    assert "First ACME fact." not in node["description"]
    assert await stores["text_chunks"].get_by_id("lifecycle-first::chunk-1") is not None
    assert "Corrected first evidence." in (
        await stores["text_chunks"].get_by_id("lifecycle-first::chunk-1")
    )["content"]

    revision = await workspace_revision(stores, config)
    deleted = await lifecycle(
        stores,
        config,
        "delete",
        document_id="lifecycle-first",
        expected_revision=revision,
        dry_run=False,
    )
    assert deleted["status"] == "success", deleted
    node = await stores["graph"].get_node("ACME")
    edge = await stores["graph"].get_edge("ACME", "BETA")
    assert "Second ACME fact." in node["description"]
    assert "Corrected ACME fact." not in node["description"]
    assert "Second document supports ACME and BETA." in edge["description"]
    assert "Corrected relationship fact." not in edge["description"]
    assert await stores["text_chunks"].get_by_id("lifecycle-first::chunk-1") is None
    assert await stores["text_chunks"].get_by_id("lifecycle-second::chunk-1") is not None


async def test_delete_last_contributor_removes_orphan_graph_and_vectors(storage_stack):
    stores, config, _ = storage_stack
    payload = document_payload(
        "lifecycle-last", chunk_text="Only source evidence.", entity_description="Only ACME fact."
    )
    assert (await committed_create(stores, config, payload))["status"] == "success"
    revision = await workspace_revision(stores, config)

    result = await lifecycle(
        stores,
        config,
        "delete",
        document_id="lifecycle-last",
        expected_revision=revision,
        dry_run=False,
    )

    assert result["status"] == "success", result
    assert await stores["graph"].get_node("ACME") is None
    assert await stores["graph"].get_node("BETA") is None
    assert await stores["graph"].get_edge("ACME", "BETA") is None
    assert await stores["text_chunks"].get_by_id("lifecycle-last::chunk-1") is None
    assert await stores["chunks_vdb"].get_by_id(
        compute_mdhash_id("lifecycle-last::chunk-1", prefix="vchunk-")
    ) is None


async def test_destructive_commit_requires_current_workspace_revision(storage_stack):
    stores, config, _ = storage_stack
    first = document_payload(
        "lifecycle-revision-one", chunk_text="One.", entity_description="One ACME fact."
    )
    second = document_payload(
        "lifecycle-revision-two", chunk_text="Two.", entity_description="Two ACME fact."
    )
    await committed_create(stores, config, first)
    stale_revision = await workspace_revision(stores, config)
    await committed_create(stores, config, second)

    result = await lifecycle(
        stores,
        config,
        "delete",
        document_id="lifecycle-revision-one",
        expected_revision=stale_revision,
        dry_run=False,
    )

    assert result["status"] == "error"
    assert result["error_code"] == "revision_conflict"
    assert await stores["text_chunks"].get_by_id("lifecycle-revision-one::chunk-1") is not None


async def test_legacy_untracked_store_rejects_destructive_edit_without_changes(storage_stack):
    stores, config, _ = storage_stack
    legacy = document_payload(
        "legacy-untracked", chunk_text="Legacy content.", entity_description="Legacy ACME fact."
    )
    # Model a legacy adapter set that has no contribution ledger.
    legacy_stores = {name: store for name, store in stores.items() if name != "documents"}
    assert (await ingest_extracted_json(legacy, legacy_stores, config))["status"] == "success"
    before = copy.deepcopy(await stores["text_chunks"].get_all_items())

    result = await lifecycle(
        stores,
        config,
        "delete",
        document_id="legacy-untracked",
        expected_revision=await workspace_revision(stores, config),
        dry_run=False,
    )

    assert result["status"] == "error"
    assert result["error_code"] == "legacy_untracked"
    assert await stores["text_chunks"].get_all_items() == before
    assert await stores["graph"].get_node("ACME") is not None


async def test_changed_additive_ingest_of_tracked_document_is_rejected(storage_stack):
    stores, config, _ = storage_stack
    initial = document_payload(
        "lifecycle-additive-conflict", chunk_text="Original.", entity_description="Original ACME fact."
    )
    changed = document_payload(
        "lifecycle-additive-conflict", chunk_text="Changed.", entity_description="Changed ACME fact."
    )
    assert (await committed_create(stores, config, initial))["status"] == "success"

    result = await ingest_extracted_json(changed, stores, config)

    assert result["status"] == "error"
    assert result["error_code"] == "revision_conflict"
    assert "Original." in (await stores["text_chunks"].get_by_id(
        "lifecycle-additive-conflict::chunk-1"
    ))["content"]


async def test_document_ledger_survives_storage_reopen(storage_stack):
    stores, config, _ = storage_stack
    payload = document_payload(
        "lifecycle-reopen", chunk_text="Persisted content.", entity_description="Persisted ACME fact."
    )
    assert (await committed_create(stores, config, payload))["status"] == "success"

    reopened = build_storage_instances(config)
    await initialize_storage_instances(reopened)
    await reopened["documents"].reload_from_disk()
    listed = await lifecycle(reopened, config, "list")

    assert listed["status"] == "success", listed
    assert [item["document_id"] for item in listed["documents"]] == ["lifecycle-reopen"]


async def test_document_registry_is_in_transaction_artifact_set():
    assert any("documents" in artifact for artifact in ARTIFACTS)


async def test_failed_rebuild_rolls_back_ledger_and_derived_stores(storage_stack, monkeypatch):
    stores, config, root = storage_stack
    first = document_payload(
        "lifecycle-rollback-one", chunk_text="Stable evidence.", entity_description="Stable ACME fact."
    )
    second = document_payload(
        "lifecycle-rollback-two", chunk_text="Second evidence.", entity_description="Second ACME fact."
    )
    assert (await committed_create(stores, config, first))["status"] == "success"
    assert (await committed_create(stores, config, second))["status"] == "success"
    before_documents = copy.deepcopy(await stores["documents"].get_all_items())
    before_chunks = copy.deepcopy(await stores["text_chunks"].get_all_items())
    before_node = copy.deepcopy(await stores["graph"].get_node("ACME"))
    artifact_bytes = {
        name: (root / name).read_bytes()
        for name in ARTIFACTS
        if (root / name).is_file()
    }

    async def fail_write(data):
        raise OSError("injected evidence write failure")

    monkeypatch.setattr(stores["text_chunks"], "upsert", fail_write)
    revision = await workspace_revision(stores, config)
    result = await lifecycle(
        stores,
        config,
        "delete",
        document_id="lifecycle-rollback-one",
        expected_revision=revision,
        dry_run=False,
    )

    assert result["status"] == "error", result
    assert await stores["documents"].get_all_items() == before_documents
    assert await stores["text_chunks"].get_all_items() == before_chunks
    assert await stores["graph"].get_node("ACME") == before_node
    assert {
        name: (root / name).read_bytes()
        for name in ARTIFACTS
        if (root / name).is_file()
    } == artifact_bytes


async def test_vector_only_legacy_store_blocks_replace_and_delete(storage_stack):
    stores, config, _ = storage_stack
    await stores["chunks_vdb"].upsert(
        {
            "legacy-vector-only": {
                "content": "Legacy indexed evidence without graph or text records.",
                "full_doc_id": "legacy-vector-doc",
                "file_path": "legacy.md",
                "chunk_id": "legacy-vector-doc::chunk-1",
            }
        }
    )
    await stores["chunks_vdb"].index_done_callback()

    replacement = {
        "document_id": "legacy-vector-doc",
        "file_path": "legacy.md",
        "chunks": [],
        "entities": [],
        "relationships": [],
    }
    replace_result = await lifecycle(
        stores,
        config,
        "replace",
        document_id="legacy-vector-doc",
        payload=replacement,
        expected_revision=0,
        dry_run=False,
    )
    delete_result = await lifecycle(
        stores,
        config,
        "delete",
        document_id="legacy-vector-doc",
        expected_revision=0,
        dry_run=False,
    )

    assert replace_result["status"] == "error"
    assert replace_result["error_code"] == "legacy_untracked"
    assert delete_result["status"] == "error"
    assert delete_result["error_code"] == "legacy_untracked"
    assert (await stores["chunks_vdb"].get_by_id("legacy-vector-only"))["content"].startswith("Legacy indexed")

