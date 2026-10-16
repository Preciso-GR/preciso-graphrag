"""Exercise document maintenance through a real MCP connection, offline.

Run: python -m scripts.smoke_lifecycle
Uses a temporary workspace and deterministic embeddings. No model downloads,
provider calls, or user graph files are needed. This checks behavior, not quality.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts.smoke_mcp import result_dict


def extraction(index: int, *, corrected: bool = False) -> dict:
    text = f"Company {index} reported revenue of USD {20 if corrected else 10} million for 2025."
    return {
        "document_id": f"report-{index}", "file_path": f"report-{index}.md",
        "chunks": [{"chunk_id": "corrected" if corrected else "one", "content": text}],
        "entities": [{"entity_name": f"COMPANY_{index}", "entity_type": "company",
                      "description": text, "source_id": "corrected" if corrected else "one"}],
        "relationships": [],
    }


@asynccontextmanager
async def connection(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
            await session.initialize()
            yield session


async def call(session, name: str, **arguments):
    result = result_dict(await session.call_tool(name, arguments))
    assert result.get("status") == "success", result
    return result


async def smoke():
    with tempfile.TemporaryDirectory(prefix="preciso-lifecycle-") as directory:
        env = dict(os.environ)
        env.update(GRAPHRAG_MCP_WORKDIR=directory, GRAPHRAG_EMBEDDING_PROVIDER="fallback",
                   GRAPHRAG_EMBEDDING_CONCURRENCY="1", GRAPHRAG_STRICT_SOURCE_IDS="true",
                   OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        params = StdioServerParameters(command=sys.executable, args=["-m", "preciso_mcp.server"], env=env)
        async with connection(params) as session:
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"get_document_workflow", "manage_documents", "manage_graph", "read_evidence"} <= names
            workflow = await call(session, "get_document_workflow")
            assert "replace" in workflow["document_actions"]
            for index in range(10):
                await call(session, "manage_documents", action="create", payload=extraction(index), dry_run=False)
            for index in range(10, 13):
                await call(session, "manage_documents", action="create", payload=extraction(index), dry_run=False)
            replay = await call(session, "manage_documents", action="create", payload=extraction(0), dry_run=False)
            assert replay["replay"]
            listing = await call(session, "manage_documents", action="list")
            assert len(listing["documents"]) == 13
            invalid = result_dict(await session.call_tool("manage_documents", {
                "action": "create", "payload": {"document_id": "invalid"}, "dry_run": False}))
            assert invalid["error_code"] == "validation_failed"
            preview = await call(session, "manage_documents", action="replace", payload=extraction(0, corrected=True))
            await call(session, "manage_documents", action="replace", payload=extraction(0, corrected=True),
                       dry_run=False, expected_revision=preview["revision"])
            stale = result_dict(await session.call_tool("manage_documents", {
                "action": "delete", "document_id": "report-1", "dry_run": False,
                "expected_revision": preview["revision"]}))
            assert stale["error_code"] == "revision_conflict"
            preview = await call(session, "manage_documents", action="delete", document_id="report-1")
            await call(session, "manage_documents", action="delete", document_id="report-1", dry_run=False,
                       expected_revision=preview["revision"])
            preview = await call(session, "manage_graph", action="isolate", node_id="COMPANY_0")
            await call(session, "manage_graph", action="isolate", node_id="COMPANY_0", dry_run=False,
                       expected_revision=preview["revision"])
            hidden = result_dict(await session.call_tool("read_evidence", {"chunk_id": "report-0::corrected"}))
            assert hidden["error_code"] == "not_found"
        async with connection(params) as session:
            graph = await call(session, "manage_graph", action="inspect")
            assert "COMPANY_0" in graph["edits"]["isolated"]
            assert "COMPANY_0" not in {node["id"] for node in graph["nodes"]}
            listing = await call(session, "manage_documents", action="list")
            assert len(listing["documents"]) == 12
            preview = await call(session, "manage_graph", action="restore", node_id="COMPANY_0")
            await call(session, "manage_graph", action="restore", node_id="COMPANY_0", dry_run=False,
                       expected_revision=preview["revision"])
            passage = await call(session, "read_evidence", chunk_id="report-0::corrected")
            assert "USD 20 million" in passage["content"]
            old = result_dict(await session.call_tool("read_evidence", {"chunk_id": "report-0::one"}))
            assert old["error_code"] == "not_found"
            query = await call(session, "query_graph_tool", query=passage["content"], mode="mix")
            chunks = query["raw_data"]["data"]["chunks"]
            assert any(chunk["content"] == passage["content"] for chunk in chunks), chunks
    print("MCP lifecycle passed: 10+3 documents, replay, invalid input, replacement, deletion, stale revision, isolation, restart, restoration, evidence, query.")


if __name__ == "__main__":
    asyncio.run(smoke())
