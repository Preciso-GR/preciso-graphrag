"""Query-cache keys must represent every input sent to the response model."""

from __future__ import annotations

import pytest
from functools import partial

import core.query as query_module
from core.storage.base import QueryContextResult, QueryParam
from core.utils import use_llm_func_with_cache


class MemoryCache:
    def __init__(self):
        self.global_config = {"enable_llm_cache": True}
        self.data = {}

    async def get_by_id(self, key):
        return self.data.get(key)

    async def upsert(self, data):
        self.data.update(data)


@pytest.mark.asyncio
async def test_query_cache_varies_with_rendered_prompt_and_history(monkeypatch):
    async def fake_context(*_args, **_kwargs):
        return QueryContextResult(context="graph context", raw_data={})

    calls = []

    async def model(query, **kwargs):
        calls.append((query, kwargs["system_prompt"], kwargs["history_messages"]))
        return f"response-{len(calls)}"

    monkeypatch.setattr(query_module, "_build_query_context", fake_context)
    cache = MemoryCache()
    config = {"enable_llm_cache": True}

    async def run(system_prompt, history):
        return await query_module.kg_query(
            query="What changed?",
            knowledge_graph_inst=None,
            entities_vdb=None,
            relationships_vdb=None,
            text_chunks_db=None,
            chunks_vdb=None,
            query_param=QueryParam(
                mode="local",
                ll_keywords=["changed"],
                conversation_history=history,
                model_func=model,
            ),
            global_config=config,
            hashing_kv=cache,
            system_prompt=system_prompt,
        )

    await run("Answer precisely using: {context_data}", [])
    await run("Answer cautiously using: {context_data}", [])
    await run(
        "Answer cautiously using: {context_data}",
        [{"role": "user", "content": "Earlier question"}],
    )

    assert len(calls) == 3


@pytest.fixture
def fixed_context(monkeypatch):
    async def context(*args, **kwargs):
        return QueryContextResult(context="evidence", raw_data={})
    monkeypatch.setattr(query_module, "_build_query_context", context)


async def run_query(model, cache, **kwargs):
    return await query_module.kg_query(
        "question", None, None, None, None,
        QueryParam(mode="local", ll_keywords=["fixed"], model_func=model, **kwargs),
        {}, hashing_kv=cache, system_prompt="Use {context_data}",
    )


async def test_query_cache_isolates_models_and_bound_settings(fixed_context):
    calls = []
    async def model(*args, model_name, **kwargs):
        calls.append(model_name)
        return f"answer {model_name}"
    cache = MemoryCache()
    first = await run_query(partial(model, model_name="A"), cache)
    second = await run_query(partial(model, model_name="B"), cache)
    repeated = await run_query(partial(model, model_name="B"), cache)
    assert [first.content, second.content, repeated.content] == ["answer A", "answer B", "answer B"]
    assert calls == ["A", "B"]


async def test_keyword_cache_isolates_models_and_token_limits():
    calls = []
    async def model(*args, model_name, max_tokens=None, **kwargs):
        calls.append((model_name, max_tokens))
        return f"{model_name}:{max_tokens}"
    cache = MemoryCache()
    cache.global_config["enable_llm_cache_for_entity_extract"] = True
    for name, limit in (("A", 10), ("B", 10), ("B", 20), ("B", 20)):
        result, _ = await use_llm_func_with_cache(
            "same prompt", partial(model, model_name=name),
            llm_response_cache=cache, max_tokens=limit, cache_type="keywords",
        )
        assert result == f"{name}:{limit}"
    assert calls == [("A", 10), ("B", 10), ("B", 20)]


async def test_stream_request_does_not_return_cached_nonstream_answer(fixed_context):
    async def chunks():
        yield "streamed answer"
    async def model(*args, stream=False, **kwargs):
        return chunks() if stream else "plain answer"
    cache = MemoryCache()
    await run_query(model, cache)
    result = await run_query(model, cache, stream=True)
    assert result.is_streaming
    assert [chunk async for chunk in result.response_iterator] == ["streamed answer"]


async def test_valid_answer_words_are_not_removed(fixed_context):
    answer = "The user asked which model answers the question. " * 4
    async def model(*args, **kwargs):
        return answer
    result = await run_query(model, MemoryCache())
    assert result.content == answer
