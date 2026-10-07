"""Compare lexical fallback and local Ollama on a small evidence retrieval pilot."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


async def evaluate(fixture, provider):
    # Import after CLI configuration, so config reads the selected model/host.
    from config import build_default_embedding_func, build_global_config, probe_ollama_embedding
    from core.bootstrap import build_storage_instances, initialize_storage_instances
    from core.query import kg_query
    from core.storage.base import EmbeddingFunc, QueryParam
    from core.utils import BasicTokenizer
    from config import _fallback_embed
    from ingest.pipeline import ingest_extracted_json

    if provider == "ollama":
        embedding = build_default_embedding_func(probe=False)
        await probe_ollama_embedding(embedding)
        if embedding.initialization_error:
            raise RuntimeError(embedding.initialization_error)
    else:
        embedding = EmbeddingFunc(8, 8192, _fallback_embed, model_name="fallback", provider="fallback", model_revision="lexical-v1")

    with tempfile.TemporaryDirectory(prefix=f"preciso-pilot-{provider}-") as root:
        config = build_global_config(working_dir=root, tokenizer=BasicTokenizer(), embedding_func=embedding)
        stores = build_storage_instances(config)
        await initialize_storage_instances(stores)
        result = await ingest_extracted_json({
            "document_id": fixture["document_id"], "entities": [], "relationships": [],
            "chunks": fixture["chunks"],
        }, stores, config)
        if result["status"] != "success":
            raise RuntimeError(result)
        rows = []
        for case in fixture["questions"]:
            start = time.perf_counter()
            response = await kg_query(
                query=case["query"], knowledge_graph_inst=stores["graph"],
                entities_vdb=stores["entities_vdb"], relationships_vdb=stores["relationships_vdb"],
                text_chunks_db=stores["text_chunks"], chunks_vdb=stores["chunks_vdb"],
                query_param=QueryParam(mode="mix", top_k=2, chunk_top_k=2, only_need_context=True, include_references=True),
                global_config=config,
            )
            chunks = ((response.raw_data or {}).get("data", {}).get("chunks", []) if response else [])
            ids = [item["chunk_id"] for item in chunks]
            gold = {f'{fixture["document_id"]}::{key}' for key in case["required"]}
            found = set(ids)
            rows.append({
                "id": case["id"], "retrieved": ids, "required": sorted(gold),
                "recall": len(gold & found) / len(gold) if gold else None,
                "complete_evidence": gold <= found if gold else None,
                "unsupported_returned_evidence": bool(found) if not gold else None,
                "valid_chunk_ids": found <= {f'{fixture["document_id"]}::{chunk["chunk_id"]}' for chunk in fixture["chunks"]},
                "query_seconds": round(time.perf_counter() - start, 4),
            })
        answerable = [row for row in rows if row["recall"] is not None]
        return {
            "provider": provider, "embedding": embedding.index_identity(),
            "embedding_concurrency": embedding.max_concurrent_requests,
            "vector_similarity_threshold": stores["chunks_vdb"].cosine_better_than_threshold,
            "mode": "mix", "chunk_top_k": 2,
            "mean_evidence_recall": sum(row["recall"] for row in answerable) / len(answerable),
            "complete_evidence_cases": sum(row["complete_evidence"] for row in answerable),
            "answerable_cases": len(answerable), "queries": rows,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--output", default="evals/results/core-retrieval-pilot.json")
    args = parser.parse_args()
    os.environ.update(GRAPHRAG_EMBEDDING_PROVIDER="ollama", GRAPHRAG_EMBEDDING_MODEL="mxbai-embed-large",
                      GRAPHRAG_EMBEDDING_CONCURRENCY="1", GRAPHRAG_EMBEDDING_TIMEOUT="120",
                      GRAPHRAG_EMBEDDING_PROBE_TIMEOUT="120")
    path = Path(__file__).resolve().parents[1] / "evals/fixtures/core_retrieval_pilot.json"
    content = path.read_bytes()
    fixture = json.loads(content)
    results = [asyncio.run(evaluate(fixture, "fallback"))]
    if not args.offline_only:
        results.append(asyncio.run(evaluate(fixture, "ollama")))
    report = {"fixture_sha256": hashlib.sha256(content).hexdigest(), "scope": fixture["scope"],
              "limitations": "Six synthetic cases; no held-out set, graph edges, generated answers, or memory measurement. Timings include query work only.",
              "results": results}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
