from __future__ import annotations

import os
from pathlib import Path
from typing import Any

GRAPH_FIELD_SEP = "<SEP>"
DEFAULT_MAX_ENTITY_TOKENS = 4_000
DEFAULT_MAX_RELATION_TOKENS = 4_000
DEFAULT_MAX_TOTAL_TOKENS = 16_000
DEFAULT_RELATED_CHUNK_NUMBER = 8
DEFAULT_KG_CHUNK_PICK_METHOD = "WEIGHT"
DEFAULT_SUMMARY_LANGUAGE = "English"
DEFAULT_MAX_FILE_PATHS = 8
DEFAULT_FILE_PATH_MORE_PLACEHOLDER = "more_paths"
DEFAULT_ENTITY_NAME_MAX_LENGTH = 255
DEFAULT_TOP_K = 20
DEFAULT_CHUNK_TOP_K = 20
DEFAULT_HISTORY_TURNS = 3
DEFAULT_SOURCE_IDS_LIMIT_METHOD = "KEEP"
SOURCE_IDS_LIMIT_METHOD_KEEP = "KEEP"
SOURCE_IDS_LIMIT_METHOD_FIFO = "FIFO"
VALID_SOURCE_IDS_LIMIT_METHODS = {
    SOURCE_IDS_LIMIT_METHOD_KEEP,
    SOURCE_IDS_LIMIT_METHOD_FIFO,
}

PROMPTS = {
    "summarize_entity_descriptions": (
        "Summarize the following {description_type} information for "
        "{description_name} in {language}. Keep the most important facts and "
        "target about {summary_length} tokens.\n{description_list}"
    ),
    "rag_response": (
        "You are a financial graph retrieval assistant.\n"
        "Use the provided context to answer in {response_type}.\n"
        "Additional user guidance: {user_prompt}\n\n"
        "{context_data}"
    ),
    "kg_query_context": (
        "-----Entities-----\n{entities_str}\n\n"
        "-----Relationships-----\n{relations_str}\n\n"
        "-----Text Chunks-----\n{text_chunks_str}\n\n"
        "-----References-----\n{reference_list_str}"
    ),
    "fail_response": "No relevant graph context could be constructed for the query.",
}


def build_global_config(
    *,
    working_dir: str | None = None,
    llm_model_func: Any = None,
    embedding_func: Any = None,
    tokenizer: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_dir = Path(working_dir or os.getenv("GRAPHRAG_MCP_WORKDIR", "./graphrag_mcp_data"))
    config: dict[str, Any] = {
        "working_dir": str(base_dir),
        "llm_model_func": llm_model_func,
        "embedding_func": embedding_func,
        "tokenizer": tokenizer,
        "embedding_batch_num": 8,
        "vector_db_storage_cls_kwargs": {
            "cosine_better_than_threshold": 0.2,
        },
        "enable_llm_cache": True,
        "enable_llm_cache_for_entity_extract": True,
        "summary_context_size": 8_000,
        "summary_max_tokens": 1_024,
        "summary_length_recommended": 256,
        "force_llm_summary_on_merge": 3,
        "embedding_token_limit": None,
        "max_entity_tokens": DEFAULT_MAX_ENTITY_TOKENS,
        "max_relation_tokens": DEFAULT_MAX_RELATION_TOKENS,
        "max_total_tokens": DEFAULT_MAX_TOTAL_TOKENS,
        "related_chunk_number": DEFAULT_RELATED_CHUNK_NUMBER,
        "kg_chunk_pick_method": DEFAULT_KG_CHUNK_PICK_METHOD,
        "max_source_ids_per_entity": 64,
        "max_source_ids_per_relation": 64,
        "source_ids_limit_method": DEFAULT_SOURCE_IDS_LIMIT_METHOD,
        "max_file_paths": DEFAULT_MAX_FILE_PATHS,
        "file_path_more_placeholder": DEFAULT_FILE_PATH_MORE_PLACEHOLDER,
        "max_graph_nodes": 1000,
        "min_rerank_score": 0.0,
        "addon_params": {"language": DEFAULT_SUMMARY_LANGUAGE},
        "system_prompt_template": PROMPTS["rag_response"],
    }
    if extra:
        config.update(extra)
    return config
