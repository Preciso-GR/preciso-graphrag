"""Offline retrieval benchmark; run with `python -m scripts.benchmark_retrieval`.

Synthetic vectors isolate local lookup/scoring overhead from model and network
latency. All artifacts live in a temporary directory; no user graph is opened.
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import logging
import statistics
import tempfile
import time

import numpy as np

from config import build_global_config
from core.query import select_evidence_chunks_by_vector
from core.storage.base import EmbeddingFunc
from core.storage.vector_store import NanoVectorDBStorage
from core.utils import compute_mdhash_id


async def benchmark(args):
    rng = np.random.default_rng(42)

    async def embed(texts, **kwargs):
        return rng.standard_normal((len(texts), args.dimension)).astype(np.float32)

    with tempfile.TemporaryDirectory(prefix="preciso-retrieval-benchmark-") as workdir:
        config = build_global_config(
            working_dir=workdir,
            embedding_func=EmbeddingFunc(args.dimension, 8192, embed, model_name="synthetic"),
        )
        store = NanoVectorDBStorage(
            namespace="chunks", workspace="", global_config=config,
            embedding_func=config["embedding_func"], meta_fields={"chunk_id", "content"},
        )
        await store.initialize()
        await store.upsert({
            compute_mdhash_id(f"chunk-{i}", prefix="vchunk-"): {
                "chunk_id": f"chunk-{i}", "content": f"Evidence {i}",
            }
            for i in range(args.records)
        })
        indices = np.linspace(0, args.records - 1, args.candidates, dtype=int)
        candidates = [{"chunk_id": f"chunk-{i}", "content": f"Evidence {i}"} for i in indices]
        ids = [compute_mdhash_id(c["chunk_id"], prefix="vchunk-") for c in candidates]
        query_vector = rng.standard_normal(args.dimension).tolist()

        async def lookup():
            result = await store.get_by_ids(ids)
            assert [row["id"] for row in result] == ids

        async def rank():
            result = await select_evidence_chunks_by_vector(
                "synthetic query", candidates, store, top_k=8,
                min_similarity=-1.0, query_embedding=query_vector,
            )
            assert len(result) == min(8, args.candidates)

        timings = {}
        for name, operation in (("bulk_lookup", lookup), ("evidence_selection", rank)):
            await operation()  # warm up
            durations = []
            for _ in range(args.repeats):
                started = time.perf_counter()
                await operation()
                durations.append((time.perf_counter() - started) * 1000)
            timings[name] = {"median_ms": round(statistics.median(durations), 3)}
        if args.profile:
            profiler = cProfile.Profile()
            profiler.enable()
            await lookup()
            await rank()
            profiler.disable()
            profiler.dump_stats(args.profile)
        return {
            "records": args.records, "candidates": args.candidates,
            "dimension": args.dimension, "repeats": args.repeats,
            "timings": timings,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=10000)
    parser.add_argument("--candidates", type=int, default=500)
    parser.add_argument("--dimension", type=int, default=256)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--profile")
    args = parser.parse_args()
    if min(args.records, args.candidates, args.dimension, args.repeats) <= 0:
        parser.error("all counts must be positive")
    if args.candidates > args.records:
        parser.error("candidates cannot exceed records")
    logging.disable(logging.INFO)
    print(json.dumps(asyncio.run(benchmark(args)), indent=2))


if __name__ == "__main__":
    main()
