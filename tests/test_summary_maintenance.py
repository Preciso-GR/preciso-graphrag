"""Summary maintenance must publish graph, vectors, and pending work together."""
from __future__ import annotations

import copy

import pytest

from config import SUMMARY_MARKER
from core.summary_maintenance import list_pending_summaries, submit_summary
from core.transactions import ARTIFACTS
from tests.test_agent_summary_mode import ingest_n_docs


@pytest.mark.parametrize("kind", ["entity", "relation"])
async def test_failed_summary_publication_restores_artifacts_and_allows_retry(kind, storage_stack, monkeypatch):
    stores, config, root = storage_stack
    config["raw_tail_size"] = 1
    await ingest_n_docs(stores, config, n=3)
    listed = await list_pending_summaries(stores, config)
    item = next(row for row in listed["items"] if row["kind"] == kind)
    before_files = {name: (root / name).read_bytes() for name in ARTIFACTS if (root / name).is_file()}
    before_nodes = copy.deepcopy(await stores["graph"].get_all_nodes())
    before_edges = copy.deepcopy(await stores["graph"].get_all_edges())
    before_pending = copy.deepcopy(await stores["pending_summaries"].get_all_items())
    arguments = dict(
        name=item["name"], kind=kind, summary_text="Reviewed summary of older facts.",
        expected_description_count=item["description_count"],
        expected_content_token=item["content_token"], src=item["src"], tgt=item["tgt"],
    )

    async def fail_publication():
        raise OSError("injected pending queue publication failure")

    with monkeypatch.context() as patch:
        patch.setattr(stores["pending_summaries"], "index_done_callback", fail_publication)
        rejected = await submit_summary(stores, config, **arguments)

    assert rejected["status"] == "error"
    assert "publication failure" in rejected["message"]
    assert {name: (root / name).read_bytes() for name in ARTIFACTS if (root / name).is_file()} == before_files
    assert await stores["graph"].get_all_nodes() == before_nodes
    assert await stores["graph"].get_all_edges() == before_edges
    assert await stores["pending_summaries"].get_all_items() == before_pending

    # The same reviewed work remains valid after rollback, and can be retried.
    accepted = await submit_summary(stores, config, **arguments)
    assert accepted["status"] == "success", accepted
    assert await stores["pending_summaries"].get_by_id(item["key"]) is None
    record = (await stores["graph"].get_node(item["name"]) if kind == "entity"
              else await stores["graph"].get_edge(item["src"], item["tgt"]))
    assert SUMMARY_MARKER in record["description"]
    assert record["description"].endswith(item["content_to_summarize"]["keep_tail"][-1])
