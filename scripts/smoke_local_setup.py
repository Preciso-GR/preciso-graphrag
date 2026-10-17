"""Real installed Granite MCP check. Uses cached weights and disposable data only."""
import argparse
import asyncio
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.local_embeddings import MODEL
from core.transactions import ARTIFACTS
from preciso_mcp.user_settings import save_settings
from scripts.smoke_mcp import result_dict, smoke


async def verify(python, model_dir):
    with tempfile.TemporaryDirectory(prefix="preciso-setup-smoke-") as temporary:
        root = Path(temporary)
        path = root / "settings.json"
        save_settings(path, {"schema_version": 1, "project": str(root), "provider": "fastembed",
                            "model": MODEL, "dimension": 384, "model_dir": str(model_dir.resolve()),
                            "workdir": str(root / "graph"), "input_dir": str(root / "inputs")})
        command = [python, "-m", "preciso_mcp.cli", "serve", "--settings", str(path)]
        env = dict(os.environ, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                   TOKENIZERS_PARALLELISM="false", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        await smoke(command, env=env, expected_provider="fastembed", expected_model=MODEL)
        params = StdioServerParameters(command=command[0], args=command[1:], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                before = {name: (root / "graph" / name).read_bytes() for name in ARTIFACTS if (root / "graph" / name).is_file()}
                huge = "archive " * 9000
                payload = {"document_id": "oversized", "chunks": [{"chunk_id": "one", "content": "ACME owns the archive."}],
                           "entities": [{"entity_name": "ACME", "entity_type": "company", "description": huge, "source_id": "one"}],
                           "relationships": []}
                bad = await session.call_tool("ingest_graph_tool", {"payload": payload})
                if not bad.isError:
                    assert result_dict(bad)["status"] not in {"success", "partial_success"}
                after = {name: (root / "graph" / name).read_bytes() for name in ARTIFACTS if (root / "graph" / name).is_file()}
                assert before == after, "Rejected overlength ingestion changed persisted artifacts"
                bad_query = await session.call_tool("query_graph_tool", {"query": huge})
                assert bad_query.isError or result_dict(bad_query)["status"] == "error"
                result = result_dict(await session.call_tool("query_graph_tool", {"query": "Alice maintains the local document index."}))
                assert result["status"] == "success", result
        print("Installed local setup passed: active Granite, restart, retrieval, overlength rejection, rollback, recovery.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(verify(args.python, args.model_dir))
