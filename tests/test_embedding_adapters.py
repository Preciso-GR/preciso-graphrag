from types import SimpleNamespace
import asyncio

import pytest

import config
from core.storage.base import EmbeddingFunc


async def test_embedding_requests_share_a_limit_of_four_across_vector_stores(storage_stack):
    stores, global_config, _ = storage_stack
    embedding = global_config["embedding_func"]
    active = 0
    peak = 0
    started = asyncio.Event()
    release = asyncio.Event()
    async def embed(texts, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 4:
            started.set()
        try:
            await release.wait()
            return [[1.0] * 8 for _ in texts]
        finally:
            active -= 1
    embedding.func = embed
    payload = {str(i): {"content": f"text {i}"} for i in range(40)}
    writes = asyncio.gather(
        stores["entities_vdb"].upsert(payload),
        stores["chunks_vdb"].upsert(payload),
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert active == 4
    finally:
        release.set()
        await asyncio.wait_for(writes, timeout=2)
    assert peak == 4
    assert all(await stores["entities_vdb"].get_by_ids(list(payload)))
    assert all(await stores["chunks_vdb"].get_by_ids(list(payload)))


async def test_embedding_failure_releases_concurrency_slot():
    async def embed(texts, **kwargs):
        if texts == ["fail"]:
            raise ConnectionError("provider unavailable")
        return [[1.0, 0.0]]
    embedding = EmbeddingFunc(2, 128, embed, max_concurrent_requests=1)
    with pytest.raises(ConnectionError):
        await embedding(["fail"])
    assert await asyncio.wait_for(embedding(["success"]), timeout=2) == [[1.0, 0.0]]


def test_embedding_concurrency_is_configurable_and_validated(monkeypatch):
    async def embed(texts, **kwargs):
        return []
    monkeypatch.setenv("GRAPHRAG_EMBEDDING_CONCURRENCY", "2")
    assert EmbeddingFunc(2, 128, embed).max_concurrent_requests == 2
    monkeypatch.setenv("GRAPHRAG_EMBEDDING_CONCURRENCY", "0")
    with pytest.raises(ValueError, match="concurrency"):
        EmbeddingFunc(2, 128, embed)


async def test_ollama_uses_async_batch_endpoint_and_configured_host(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        async def embed(self, **kwargs):
            calls.append(kwargs)
            return {"embeddings": [[1.0, 0.0], [0.0, 1.0]]}
        async def close(self):
            calls.append("closed")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://embedding-host:11434")
    monkeypatch.setattr(config.importlib, "import_module", lambda name: SimpleNamespace(AsyncClient=Client))
    assert await config._ollama_embed(["first", "second"], model="test") == [[1.0, 0.0], [0.0, 1.0]]
    assert calls == [{"host": "http://embedding-host:11434"}, {"model": "test", "input": ["first", "second"]}, "closed"]


@pytest.mark.parametrize("context, input_type", [("query", "search_query"), ("document", "search_document")])
async def test_cohere_distinguishes_query_and_document_embeddings(monkeypatch, context, input_type):
    import sys
    calls = []
    class Client:
        def __init__(self, key):
            assert key == "test-key"
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            calls.append("closed")
        async def embed(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(embeddings=[[1.0, 0.0]])
    monkeypatch.setenv("COHERE_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "cohere", SimpleNamespace(AsyncClient=Client))
    assert await config._cohere_embed(["text"], context=context, model="test") == [[1.0, 0.0]]
    assert calls[0]["input_type"] == input_type
    assert calls[-1] == "closed"


async def test_openai_requests_configured_dimension_and_closes_client(monkeypatch):
    import sys
    calls = []
    class Client:
        def __init__(self, **kwargs):
            self.embeddings = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            calls.append("closed")
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 0.0])])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "DEFAULT_EMBEDDING_DIM", 2)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=Client))
    assert await config._openai_embed(["text"], model="text-embedding-3-small") == [[1.0, 0.0]]
    assert calls == [{"model": "text-embedding-3-small", "input": ["text"], "dimensions": 2}, "closed"]


async def test_ollama_legacy_client_fallback_remains_async(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def embeddings(self, *, model, prompt):
            calls.append(prompt)
            return {"embedding": [1.0, 0.0]}
    monkeypatch.setattr(config.importlib, "import_module", lambda name: SimpleNamespace(AsyncClient=Client))
    assert await config._ollama_embed(["first", "second"]) == [[1.0, 0.0], [1.0, 0.0]]
    assert calls == ["first", "second"]


@pytest.mark.parametrize("vectors", [[[1.0]], [[1.0, float("nan")]], [[0.0, 0.0]], []])
async def test_invalid_embedding_response_is_rejected_and_marks_runtime_unavailable(vectors):
    async def embed(*args, **kwargs):
        return vectors
    embedding = EmbeddingFunc(embedding_dim=2, max_token_size=128, func=embed)
    with pytest.raises(ValueError, match="embedding"):
        await embedding(["text"])
    assert embedding.runtime_error is not None


async def test_zero_embedding_does_not_mutate_index_and_valid_retry_succeeds(storage_stack):
    stores, global_config, _ = storage_stack
    embedding = global_config["embedding_func"]

    async def zero(texts, **kwargs):
        return [[0.0] * 8 for _ in texts]

    embedding.func = zero
    store = stores["chunks_vdb"]
    with pytest.raises(ValueError, match="nonzero"):
        await store.upsert({"one": {"content": "evidence"}})
    assert await store.get_by_id("one") is None

    async def valid(texts, **kwargs):
        return [[1.0] * 8 for _ in texts]

    embedding.func = valid
    await store.upsert({"one": {"content": "evidence"}})
    assert await store.get_by_id("one") is not None
    assert embedding.runtime_error is None


async def test_hanging_embedding_times_out_and_releases_slot():
    cancelled = asyncio.Event()

    async def embed(texts, **kwargs):
        if texts == ["hang"]:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return [[1.0, 0.0]]

    embedding = EmbeddingFunc(2, 128, embed, max_concurrent_requests=1, request_timeout=0.02)
    with pytest.raises(TimeoutError):
        await embedding(["hang"])
    assert cancelled.is_set()
    assert embedding.runtime_error is not None
    assert await embedding(["success"]) == [[1.0, 0.0]]


async def test_waiting_for_embedding_slot_has_a_deadline():
    started, release = asyncio.Event(), asyncio.Event()

    async def embed(texts, **kwargs):
        started.set()
        await release.wait()
        return [[1.0, 0.0]]

    embedding = EmbeddingFunc(2, 128, embed, max_concurrent_requests=1, request_timeout=2)
    active = asyncio.create_task(embedding(["active"]))
    try:
        await started.wait()
        embedding.request_timeout = 0.02
        with pytest.raises(TimeoutError):
            await embedding(["queued"])
    finally:
        release.set()
        await active


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_embedding_timeout_must_be_positive_and_finite(timeout):
    with pytest.raises(ValueError, match="timeout"):
        EmbeddingFunc(2, 128, lambda: None, request_timeout=timeout)


async def test_startup_probe_times_out_without_blocking_event_loop(monkeypatch):
    cancelled = False

    async def hang(*args, **kwargs):
        nonlocal cancelled
        try:
            await asyncio.Event().wait()
        finally:
            cancelled = True

    monkeypatch.setenv("GRAPHRAG_EMBEDDING_PROBE_TIMEOUT", "0.02")
    monkeypatch.setattr(config, "_ollama_embed", hang)
    embedding = EmbeddingFunc(2, 128, hang, model_name="test")
    await config.probe_ollama_embedding(embedding)
    assert cancelled
    assert "TimeoutError" in embedding.initialization_error
    assert embedding.embedding_dim == 2


async def test_bounded_workers_preserve_order_and_do_not_create_batch_backlog(storage_stack):
    stores, cfg, _ = storage_stack
    embedding = cfg["embedding_func"]
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def embed(texts, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            started.set()
        await release.wait()
        return [[float(text), *([1.0] * 7)] for text in texts]

    embedding.func = embed
    before = len(asyncio.all_tasks())
    write = asyncio.create_task(stores["chunks_vdb"].upsert({str(i): {"content": str(i)} for i in range(800)}))
    try:
        await started.wait()
        assert len(asyncio.all_tasks()) - before == 5
    finally:
        release.set()
        await write
    vectors = await stores["chunks_vdb"].get_vectors_by_ids(["0", "100", "799"])
    assert {key: value[0] for key, value in vectors.items()} == {"0": 0.0, "100": 100.0, "799": 799.0}


async def test_worker_failure_cancels_siblings_before_retry(storage_stack):
    stores, cfg, _ = storage_stack
    active = 0
    all_started = asyncio.Event()

    async def embed(texts, **kwargs):
        nonlocal active
        active += 1
        if active == 4:
            all_started.set()
        try:
            await all_started.wait()
            if texts[0] == "0":
                raise ConnectionError("provider failed")
            await asyncio.Event().wait()
        finally:
            active -= 1

    cfg["embedding_func"].func = embed
    with pytest.raises(ConnectionError):
        await stores["chunks_vdb"].upsert({str(i): {"content": str(i)} for i in range(40)})
    assert active == 0
    assert await stores["chunks_vdb"].get_by_id("0") is None
