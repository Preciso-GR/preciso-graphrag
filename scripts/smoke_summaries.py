"""Check agent summary maintenance over MCP with temporary offline data.

Run: python -m scripts.smoke_summaries
No model calls or user graph files are required.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile

from mcp import StdioServerParameters

from scripts.smoke_lifecycle import call, connection
from scripts.smoke_mcp import result_dict


def extraction(index: int, *, corrected: bool = False) -> dict:
    description = f"ACME fact {index}{' corrected' if corrected else ''}."
    return {
        "document_id": f"summary-{index}", "file_path": f"summary-{index}.md",
        "chunks": [{"chunk_id": "one", "content": f"{description} BETA works with ACME."}],
        "entities": [
            {"entity_name": "ACME", "entity_type": "company", "description": description, "source_id": "one"},
            {"entity_name": "BETA", "entity_type": "company", "description": f"BETA fact {index}.", "source_id": "one"},
        ],
        "relationships": [{"src_id": "ACME", "tgt_id": "BETA", "source_id": "one",
                           "description": f"ACME and BETA cooperate in source {index}."}],
    }


def entity_item(result: dict) -> dict:
    return next(item for item in result["items"] if item["kind"] == "entity" and item["name"] == "ACME")


def submission(item: dict, text: str) -> dict:
    return {"name": item["name"], "kind": item["kind"], "src": item["src"], "tgt": item["tgt"],
            "summary_text": text, "expected_description_count": item["description_count"],
            "expected_content_token": item["content_token"]}


async def smoke():
    with tempfile.TemporaryDirectory(prefix="preciso-summary-") as directory:
        env = dict(os.environ)
        env.update(GRAPHRAG_MCP_WORKDIR=directory, GRAPHRAG_EMBEDDING_PROVIDER="fallback",
                   GRAPHRAG_EMBEDDING_CONCURRENCY="1", GRAPHRAG_RAW_TAIL_SIZE="1",
                   GRAPHRAG_STRICT_SOURCE_IDS="true", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        params = StdioServerParameters(command=sys.executable, args=["-m", "preciso_mcp.server"], env=env)
        async with connection(params) as session:
            for index in range(2):
                await call(session, "ingest_graph_tool", payload=extraction(index))
            pending = await call(session, "list_pending_summaries")
            original = entity_item(pending)
            relation = next(item for item in pending["items"] if item["kind"] == "relation")
            for item in (original, relation):
                await call(session, "submit_summary", **submission(item, "Reviewed summary of older facts."))
            remaining = await call(session, "list_pending_summaries")
            assert original["key"] not in {item["key"] for item in remaining["items"]}
            assert relation["key"] not in {item["key"] for item in remaining["items"]}
        async with connection(params) as session:
            persisted = await call(session, "list_pending_summaries")
            assert original["key"] not in {item["key"] for item in persisted["items"]}
            assert relation["key"] not in {item["key"] for item in persisted["items"]}
            preview = await call(session, "manage_documents", action="replace", payload=extraction(0, corrected=True))
            await call(session, "manage_documents", action="replace", payload=extraction(0, corrected=True),
                       expected_revision=preview["revision"], dry_run=False)
            pending = await call(session, "list_pending_summaries")
            current = entity_item(pending)
            assert current["content_token_required"] is True
            assert current["content_token"] != original["content_token"]
            stale = result_dict(await session.call_tool("submit_summary", submission(original, "Outdated summary.")))
            assert stale["status"] == "error" and stale["error_code"] == "stale_summary", stale
            await call(session, "submit_summary", **submission(current, "Reviewed corrected facts."))
    print("MCP summaries passed: entity/relation submission, pending queue, restart, replacement, stale rejection, fresh submission.")


if __name__ == "__main__":
    asyncio.run(smoke())
