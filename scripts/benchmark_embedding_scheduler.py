"""Count pending embedding tasks with an offline, paused provider."""

import asyncio
import json
import logging
import tempfile

from config import build_global_config
from core.storage.base import EmbeddingFunc
from core.storage.vector_store import NanoVectorDBStorage


async def benchmark():
    release, started = asyncio.Event(), asyncio.Event()
    calls = 0

    async def embed(texts, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            started.set()
        await release.wait()
        return [[1.0, 0.0] for _ in texts]

    with tempfile.TemporaryDirectory() as workdir:
        embedding = EmbeddingFunc(2, 128, embed, max_concurrent_requests=4)
        cfg = build_global_config(working_dir=workdir, embedding_func=embedding)
        store = NanoVectorDBStorage("chunks", "", cfg, embedding_func=embedding)
        await store.initialize()
        before = len(asyncio.all_tasks())
        task = asyncio.create_task(store.upsert({str(i): {"content": str(i)} for i in range(8000)}))
        try:
            await asyncio.wait_for(started.wait(), 5)
            pending = len(asyncio.all_tasks()) - before
        finally:
            release.set()
            await task
        return {"texts": 8000, "batch_size": 8, "concurrency": 4, "additional_pending_tasks": pending}


if __name__ == "__main__":
    logging.disable(logging.INFO)
    print(json.dumps(asyncio.run(benchmark()), indent=2))
