from __future__ import annotations

import json
from functools import partial

from config import DEFAULT_SUMMARY_LANGUAGE, PROMPTS
from core.storage.base import BaseKVStorage
from core.utils import (
    logger,
    truncate_list_by_token_size,
    use_llm_func_with_cache,
)


def _truncate_entity_identifier(
    identifier: str, limit: int, chunk_key: str, identifier_role: str
) -> str:
    if len(identifier) <= limit:
        return identifier
    preview = identifier[:20]
    logger.warning(
        "%s: %s len %d > %d chars (Name: '%s...')",
        chunk_key,
        identifier_role,
        len(identifier),
        limit,
        preview,
    )
    return identifier[:limit]


async def _summarize_descriptions(
    description_type: str,
    description_name: str,
    description_list: list[str],
    global_config: dict,
    llm_response_cache: BaseKVStorage | None = None,
) -> str:
    use_llm_func = global_config["llm_model_func"]
    if use_llm_func is None:
        return "\n".join(description_list)
    use_llm_func = partial(use_llm_func, _priority=8)
    language = global_config["addon_params"].get("language", DEFAULT_SUMMARY_LANGUAGE)
    summary_length_recommended = global_config["summary_length_recommended"]
    tokenizer = global_config["tokenizer"]
    summary_context_size = global_config["summary_context_size"]
    json_descriptions = [{"Description": desc} for desc in description_list]
    truncated_json_descriptions = truncate_list_by_token_size(
        json_descriptions,
        key=lambda x: json.dumps(x, ensure_ascii=False),
        max_token_size=summary_context_size,
        tokenizer=tokenizer,
    )
    joined_descriptions = "\n".join(
        json.dumps(desc, ensure_ascii=False) for desc in truncated_json_descriptions
    )
    use_prompt = PROMPTS["summarize_entity_descriptions"].format(
        description_type=description_type,
        description_name=description_name,
        description_list=joined_descriptions,
        summary_length=summary_length_recommended,
        language=language,
    )
    summary, _ = await use_llm_func_with_cache(
        use_prompt,
        use_llm_func,
        llm_response_cache=llm_response_cache,
        cache_type="summary",
    )
    return summary


async def _handle_entity_relation_summary(
    description_type: str,
    entity_or_relation_name: str,
    description_list: list[str],
    separator: str,
    global_config: dict,
    llm_response_cache: BaseKVStorage | None = None,
) -> tuple[str, bool]:
    if not description_list:
        return "", False
    if len(description_list) == 1:
        return description_list[0], False
    tokenizer = global_config["tokenizer"]
    summary_context_size = global_config["summary_context_size"]
    summary_max_tokens = global_config["summary_max_tokens"]
    force_llm_summary_on_merge = global_config["force_llm_summary_on_merge"]
    current_list = description_list[:]
    llm_was_used = False
    while True:
        total_tokens = 0
        for desc in current_list:
            total_tokens += len(tokenizer.encode(desc))
        if total_tokens <= summary_context_size or len(current_list) <= 2:
            if (
                len(current_list) < force_llm_summary_on_merge
                and total_tokens < summary_max_tokens
            ):
                return separator.join(current_list), llm_was_used
            final_summary = await _summarize_descriptions(
                description_type,
                entity_or_relation_name,
                current_list,
                global_config,
                llm_response_cache,
            )
            return final_summary, True
        chunks = []
        current_chunk = []
        current_tokens = 0
        for desc in current_list:
            desc_tokens = len(tokenizer.encode(desc))
            if current_tokens + desc_tokens > summary_context_size and current_chunk:
                if len(current_chunk) == 1:
                    current_chunk.append(desc)
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_tokens = 0
                else:
                    chunks.append(current_chunk)
                    current_chunk = [desc]
                    current_tokens = desc_tokens
            else:
                current_chunk.append(desc)
                current_tokens += desc_tokens
        if current_chunk:
            chunks.append(current_chunk)
        new_summaries = []
        for chunk in chunks:
            if len(chunk) == 1:
                new_summaries.append(chunk[0])
            else:
                summary = await _summarize_descriptions(
                    description_type,
                    entity_or_relation_name,
                    chunk,
                    global_config,
                    llm_response_cache,
                )
                new_summaries.append(summary)
                llm_was_used = True
        current_list = new_summaries
