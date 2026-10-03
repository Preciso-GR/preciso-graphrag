from types import SimpleNamespace

import pytest

import config
from core.storage.base import EmbeddingFunc


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


@pytest.mark.parametrize("vectors", [[[1.0]], [[1.0, float("nan")]], []])
async def test_invalid_embedding_response_is_rejected_and_marks_runtime_unavailable(vectors):
    async def embed(*args, **kwargs):
        return vectors
    embedding = EmbeddingFunc(embedding_dim=2, max_token_size=128, func=embed)
    with pytest.raises(ValueError, match="embedding"):
        await embedding(["text"])
    assert embedding.runtime_error is not None
