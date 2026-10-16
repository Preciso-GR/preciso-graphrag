"""Stale agent summaries must be rejected after a lifecycle rebuild."""

from __future__ import annotations

from config import GRAPH_FIELD_SEP, SUMMARY_MARKER
from core.documents import document_operation
from ingest.pipeline import ingest_extracted_json
from preciso_mcp.tools.pending_summaries_tool import list_pending_summaries, submit_summary


def payload(document_id: str, description: str) -> dict:
    return {
        "document_id": document_id,
        "file_path": f"{document_id}.md",
        "chunks": [{"chunk_id": "chunk-1", "content": f"Evidence for {description}"}],
        "entities": [
            {
                "entity_name": "ACME",
                "entity_type": "ORG",
                "description": description,
                "source_id": "chunk-1",
            }
        ],
        "relationships": [],
    }


def entity_item(result: dict) -> dict:
    return next(item for item in result["items"] if item["kind"] == "entity" and item["name"] == "ACME")


async def test_rebuild_invalidates_prior_summary_content_token_even_when_count_matches(storage_stack):
    stores, config, _ = storage_stack
    config["raw_tail_size"] = 1
    first = payload("summary-lifecycle-one", "Old ACME fact.")
    second = payload("summary-lifecycle-two", "Second ACME fact.")
    assert (await ingest_extracted_json(first, stores, config))["status"] == "success"
    assert (await ingest_extracted_json(second, stores, config))["status"] == "success"

    listed = await list_pending_summaries(stores, config)
    stale_item = entity_item(listed)
    stale_token = stale_item["content_token"]
    count_before = stale_item["description_count"]
    submitted = await submit_summary(
        stores,
        config,
        name="ACME",
        kind="entity",
        summary_text="Old summary based on the original facts.",
        expected_description_count=count_before,
        expected_content_token=stale_token,
    )
    assert submitted["status"] == "success", submitted
    assert SUMMARY_MARKER in (await stores["graph"].get_node("ACME"))["description"]

    replacement = payload("summary-lifecycle-one", "Corrected ACME fact.")
    documents = await document_operation(stores, config, "list")
    replaced = await document_operation(
        stores,
        config,
        "replace",
        document_id="summary-lifecycle-one",
        payload=replacement,
        expected_revision=documents["revision"],
        dry_run=False,
    )
    assert replaced["status"] == "success", replaced

    node = await stores["graph"].get_node("ACME")
    assert len(node["description"].split(GRAPH_FIELD_SEP)) == count_before
    assert SUMMARY_MARKER not in node["description"]
    assert "Old summary based on the original facts." not in node["description"]
    assert "Corrected ACME fact." in node["description"]

    stale_list = await list_pending_summaries(stores, config)
    current_item = entity_item(stale_list)
    assert current_item["description_count"] == count_before
    assert current_item["content_token"] != stale_token
    assert current_item["content_token_required"] is True

    rejected_old_token = await submit_summary(
        stores,
        config,
        name="ACME",
        kind="entity",
        summary_text="Stale agent summary.",
        expected_description_count=count_before,
        expected_content_token=stale_token,
    )
    assert rejected_old_token["status"] == "error"
    assert rejected_old_token["error_code"] == "stale_summary"

    rejected_missing_token = await submit_summary(
        stores,
        config,
        name="ACME",
        kind="entity",
        summary_text="Agent summary without a generation token.",
        expected_description_count=count_before,
    )
    assert rejected_missing_token["status"] == "error"
    assert rejected_missing_token["error_code"] == "stale_summary"

    current = await list_pending_summaries(stores, config)
    fresh_item = entity_item(current)
    accepted = await submit_summary(
        stores,
        config,
        name="ACME",
        kind="entity",
        summary_text="Summary of the corrected and current facts.",
        expected_description_count=fresh_item["description_count"],
        expected_content_token=fresh_item["content_token"],
    )
    assert accepted["status"] == "success", accepted
    final_description = (await stores["graph"].get_node("ACME"))["description"]
    assert "Summary of the corrected and current facts." in final_description
    assert "Old summary based on the original facts." not in final_description
