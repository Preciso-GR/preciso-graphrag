from __future__ import annotations

from ingest.pipeline import ingest_extracted_json


async def ingest_graph(payload: dict, storage_instances: dict, global_config: dict) -> dict:
    return await ingest_extracted_json(payload, storage_instances, global_config)
