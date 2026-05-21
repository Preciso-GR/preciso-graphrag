#!/usr/bin/env python
"""
Manual ingestion CLI script.
Test extraction → graph creation without depending on MCP client connectivity.

Usage:
    python ingest_manual.py extractions/apple_10k_excerpt_extracted.json
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import build_global_config
from core.storage.base import EmbeddingFunc
from core.storage.graph_store import NetworkXStorage
from core.storage.kv_store import JsonKVStorage
from core.storage.vector_store import NanoVectorDBStorage
from core.utils import BasicTokenizer
from ingest.pipeline import ingest_extracted_json


async def _fallback_embed(texts, **kwargs):
    """Simple fallback embedding function."""
    return [[0.0] * 8 for _ in texts]


def build_storage_instances(global_config: dict, workspace: str = "") -> dict:
    """Build all storage backends (same as server.py)."""
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
    """Initialize all storage backends."""
    for storage in storage_instances.values():
        await storage.initialize()


async def ingest_file_manual(file_path: str) -> None:
    """
    Manually ingest extraction file into graph.
    
    Args:
        file_path: Path to extraction JSON file (e.g., extractions/apple_10k_excerpt_extracted.json)
    """
    # Check file exists
    extraction_file = Path(file_path)
    if not extraction_file.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    print(f"📂 Reading extraction file: {file_path}")
    
    # Load extraction JSON
    try:
        with open(extraction_file, "r") as f:
            payload = json.load(f)
        print(f"✅ Loaded extraction JSON")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)
    
    # Initialize config and storage
    print("⚙️  Initializing config and storage...")
    tokenizer = BasicTokenizer()
    global_config = build_global_config(
        working_dir="GRAPH_IS_HERE",
        tokenizer=tokenizer,
        embedding_func=EmbeddingFunc(
            embedding_dim=8,
            max_token_size=8192,
            func=_fallback_embed,
            model_name="fallback",
        ),
    )
    
    storage_instances = build_storage_instances(global_config)
    await initialize_storage_instances(storage_instances)
    print(f"✅ Storage initialized in: {Path(global_config['working_dir']).resolve()}")
    
    # Extract payload details
    document_id = payload.get("document_id", "unknown")
    entities = payload.get("entities", [])
    relationships = payload.get("relationships", [])
    chunks = payload.get("chunks", [])
    
    print(f"\n📊 Extraction Summary:")
    print(f"   Document ID: {document_id}")
    print(f"   Entities: {len(entities)}")
    print(f"   Relationships: {len(relationships)}")
    print(f"   Chunks: {len(chunks)}")
    
    # Ingest into graph
    print(f"\n🔄 Ingesting into graph...")
    result = await ingest_extracted_json(payload, storage_instances, global_config)
    
    print(f"\n📈 Ingestion Result:")
    print(f"   Status: {result.get('status', 'unknown')}")
    print(f"   Entities Added: {result.get('entities_added', 0)}")
    print(f"   Relationships Added: {result.get('relationships_added', 0)}")
    print(f"   Chunks Stored: {result.get('chunks_stored', 0)}")
    if "message" in result:
        print(f"   Message: {result['message']}")
    
    if result.get("status") == "success":
        print(f"\n✅ Ingestion successful!")
        print(f"🗂️  Graph stored in: GRAPH_IS_HERE/")
        
        # Graph stats (already printed from ingestion log)
        print(f"\n✨ Your graph is ready to query!")
        print(f"   Location: {Path(global_config['working_dir']).resolve()}")
        print(f"\n💡 Next: Try querying the graph with a client or the server")
    else:
        print(f"\n❌ Ingestion failed!")
        if "errors" in result:
            print(f"Errors: {result['errors']}")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python ingest_manual.py <extraction_file_path>")
        print("Example: python ingest_manual.py extractions/apple_10k_excerpt_extracted.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    asyncio.run(ingest_file_manual(file_path))


if __name__ == "__main__":
    main()
