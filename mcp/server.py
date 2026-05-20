from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import build_global_config
from core.query import kg_query
from core.storage.base import EmbeddingFunc
from core.storage.graph_store import NetworkXStorage
from core.storage.kv_store import JsonKVStorage
from core.storage.base import QueryParam
from core.storage.vector_store import NanoVectorDBStorage
from core.utils import BasicTokenizer
from ingest.pipeline import ingest_extracted_json
from mcp.server.fastmcp import FastMCP


async def _fallback_embed(texts, **kwargs):
    return [[0.0] * 8 for _ in texts]


def build_storage_instances(global_config: dict, workspace: str = "") -> dict:
    embedding_func = global_config["embedding_func"]
    shared_kwargs = {"workspace": workspace, "global_config": global_config}
    return {
        "graph": NetworkXStorage(
            namespace="graph",
            embedding_func=None,
            **shared_kwargs,
        ),
        "text_chunks": JsonKVStorage(
            namespace="text_chunks",
            embedding_func=None,
            **shared_kwargs,
        ),
        "entity_chunks": JsonKVStorage(
            namespace="entity_chunks",
            embedding_func=None,
            **shared_kwargs,
        ),
        "relation_chunks": JsonKVStorage(
            namespace="relation_chunks",
            embedding_func=None,
            **shared_kwargs,
        ),
        "llm_cache": JsonKVStorage(
            namespace="llm_cache",
            embedding_func=None,
            **shared_kwargs,
        ),
        "checkpoints": JsonKVStorage(
            namespace="checkpoints",
            embedding_func=None,
            **shared_kwargs,
        ),
        "entities_vdb": NanoVectorDBStorage(
            namespace="entities",
            embedding_func=embedding_func,
            meta_fields={"entity_name", "source_id", "content", "file_path", "entity_type"},
            **shared_kwargs,
        ),
        "relationships_vdb": NanoVectorDBStorage(
            namespace="relationships",
            embedding_func=embedding_func,
            meta_fields={"src_id", "tgt_id", "source_id", "content", "file_path", "keywords", "description", "weight"},
            **shared_kwargs,
        ),
        "chunks_vdb": NanoVectorDBStorage(
            namespace="chunks",
            embedding_func=embedding_func,
            meta_fields={"full_doc_id", "content", "file_path", "chunk_id"},
            **shared_kwargs,
        ),
    }


async def initialize_storage_instances(storage_instances: dict) -> None:
    for storage in storage_instances.values():
        await storage.initialize()


tokenizer = BasicTokenizer()
global_config = build_global_config(
    tokenizer=tokenizer,
    embedding_func=EmbeddingFunc(
        embedding_dim=8,
        max_token_size=8192,
        func=_fallback_embed,
        model_name="fallback",
    ),
)
storage_instances = build_storage_instances(global_config)
mcp = FastMCP("graphrag-mcp")


@mcp.tool()
async def ingest_graph_tool(payload: dict) -> dict:
    return await ingest_extracted_json(payload, storage_instances, global_config)


@mcp.tool()
async def ingest_checkpoint_tool(payload: dict) -> dict:
    try:
        checkpoints = storage_instances["checkpoints"]
        checkpoint_id = str(payload.get("checkpoint_id") or "checkpoint")
        await checkpoints.upsert({checkpoint_id: {"payload": payload}})
        await checkpoints.index_done_callback()
        return {"status": "success", "checkpoint_id": checkpoint_id}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool()
async def query_graph_tool(query: str, mode: str = "mix") -> dict:
    try:
        result = await kg_query(
            query=query,
            knowledge_graph_inst=storage_instances["graph"],
            entities_vdb=storage_instances["entities_vdb"],
            relationships_vdb=storage_instances["relationships_vdb"],
            text_chunks_db=storage_instances["text_chunks"],
            query_param=QueryParam(mode=mode, include_references=True),
            global_config=global_config,
            hashing_kv=storage_instances.get("llm_cache"),
            chunks_vdb=storage_instances["chunks_vdb"],
        )
        if result is None:
            return {"status": "success", "message": "no results", "data": {}}
        return {
            "status": "success",
            "message": "query complete",
            "content": result.content,
            "raw_data": result.raw_data,
            "is_streaming": result.is_streaming,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def startup() -> None:
    await initialize_storage_instances(storage_instances)


if __name__ == "__main__":
    import asyncio

    asyncio.run(startup())
    mcp.run()
