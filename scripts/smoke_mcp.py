"""Verify a real MCP handshake and persistent ingestion across server restarts.

Run `python -m scripts.smoke_mcp -- <server command and arguments>`.
Use an empty, disposable graph directory. No provider calls are needed with
GRAPHRAG_EMBEDDING_PROVIDER=fallback; this is a protocol test, not a quality eval.
"""

import argparse
import asyncio
from datetime import timedelta
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def result_dict(result):
    if result.isError:
        raise RuntimeError(str(result.content))
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def smoke(command):
    params = StdioServerParameters(command=command[0], args=command[1:], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert "get_server_status" in {tool.name for tool in tools.tools}
            payload = {
                "document_id": "mcp-smoke", "entities": [], "relationships": [],
                "chunks": [{"chunk_id": "one", "content": "Alice maintains the local document index."}],
            }
            result = result_dict(await session.call_tool("ingest_graph_tool", {"payload": payload}))
            assert result["status"] == "success", result
    # Starting a second session proves that volume data survives process exit.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
            await session.initialize()
            status = result_dict(await session.call_tool("get_server_status"))
            assert status["graph"]["documents_ingested"] == 1, status
            assert status["graph"]["chunks"] == 1, status
            result = result_dict(await session.call_tool("query_graph_tool", {"query": "Alice maintains the local document index.", "mode": "mix"}))
            assert result["status"] == "success", result
            assert result["raw_data"]["data"]["chunks"], result
    print("MCP handshake, ingestion, restart persistence, and query passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a server command after --")
    asyncio.run(smoke(command))
