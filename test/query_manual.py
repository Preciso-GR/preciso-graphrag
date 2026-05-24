#!/usr/bin/env python
"""
Manual query CLI script.
Test graph retrieval quality against GRAPH_IS_HERE without MCP client connectivity.

Usage:
    python query_manual.py "What is Tim Cook's role?"
    python query_manual.py "What is Tim Cook's role?" local
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import build_default_embedding_func, build_global_config
from core.query import kg_query
from core.storage.base import QueryParam
from core.storage.graph_store import NetworkXStorage
from core.storage.kv_store import JsonKVStorage
from core.storage.vector_store import NanoVectorDBStorage
from core.utils import BasicTokenizer


def build_storage_instances(global_config: dict, workspace: str = "") -> dict:
    embedding_func = global_config["embedding_func"]
    shared_kwargs = {"workspace": workspace, "global_config": global_config}
    return {
        "graph": NetworkXStorage(namespace="graph", embedding_func=None, **shared_kwargs),
        "text_chunks": JsonKVStorage(namespace="text_chunks", embedding_func=None, **shared_kwargs),
        "entity_chunks": JsonKVStorage(namespace="entity_chunks", embedding_func=None, **shared_kwargs),
        "relation_chunks": JsonKVStorage(namespace="relation_chunks", embedding_func=None, **shared_kwargs),
        "llm_cache": JsonKVStorage(namespace="llm_cache", embedding_func=None, **shared_kwargs),
        "checkpoints": JsonKVStorage(namespace="checkpoints", embedding_func=None, **shared_kwargs),
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


async def query_graph_manual(query: str, mode: str) -> None:
    working_dir = Path("GRAPH_IS_HERE")
    if not working_dir.exists():
        print("GRAPH_IS_HERE does not exist yet. Run ingest_manual.py first.")
        sys.exit(1)

    tokenizer = BasicTokenizer()
    global_config = build_global_config(
        working_dir=str(working_dir),
        tokenizer=tokenizer,
        embedding_func=build_default_embedding_func(),
    )
    storage_instances = build_storage_instances(global_config)
    await initialize_storage_instances(storage_instances)

    query_param = QueryParam(
        mode=mode,
        include_references=True,
        only_need_context=True,
        response_type="Short Answer",
    )
    result = await kg_query(
        query=query,
        knowledge_graph_inst=storage_instances["graph"],
        entities_vdb=storage_instances["entities_vdb"],
        relationships_vdb=storage_instances["relationships_vdb"],
        text_chunks_db=storage_instances["text_chunks"],
        query_param=query_param,
        global_config=global_config,
        hashing_kv=storage_instances.get("llm_cache"),
        chunks_vdb=storage_instances["chunks_vdb"],
    )

    if result is None:
        print("No query result returned.")
        sys.exit(1)

    raw_data = result.raw_data or {}
    data = raw_data.get("data", {})
    metadata = raw_data.get("metadata", {})
    processing_info = metadata.get("processing_info", {})
    references = data.get("references", [])

    print(f"Query: {query}")
    print(f"Mode: {mode}")
    print()
    print("Retrieved Context:")
    print(result.content or "[empty]")
    print()
    print("Retrieval Summary:")
    print(f"  Entities Returned: {len(data.get('entities', []))}")
    print(f"  Relationships Returned: {len(data.get('relationships', []))}")
    print(f"  Chunks Returned: {len(data.get('chunks', []))}")
    if processing_info:
        print("  Processing Info:")
        print(json.dumps(processing_info, indent=2))

    if references:
        print()
        print("References:")
        for reference in references:
            ref_id = reference.get("reference_id", "?")
            file_path = reference.get("file_path", "unknown_source")
            print(f"  [{ref_id}] {file_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python query_manual.py "<query>" [mode]')
        print('Example: python query_manual.py "What is Tim Cook\'s role?"')
        print('Modes: local | global | hybrid | naive | mix | bypass')
        sys.exit(1)

    query = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "mix"
    asyncio.run(query_graph_manual(query, mode))


if __name__ == "__main__":
    main()
