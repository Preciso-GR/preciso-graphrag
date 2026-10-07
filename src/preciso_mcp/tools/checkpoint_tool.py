from __future__ import annotations

import time

from core.utils import compute_mdhash_id, logger
from core.transactions import run_artifact_mutation


async def ingest_checkpoint(payload: dict, storage_instances: dict, global_config: dict) -> dict:
    return await run_artifact_mutation(lambda: _ingest_checkpoint(payload, storage_instances, global_config), storage_instances, global_config)


async def _ingest_checkpoint(payload: dict, storage_instances: dict, global_config: dict) -> dict:
    try:
        checkpoints = storage_instances["checkpoints"]
        checkpoint_id = str(
            payload.get("checkpoint_id")
            or compute_mdhash_id(f"{time.time()}:{payload}", prefix="ckpt-")
        )
        await checkpoints.upsert(
            {
                checkpoint_id: {
                    "payload": payload,
                    "saved_at": int(time.time()),
                }
            }
        )
        await checkpoints.index_done_callback()
        return {
            "status": "success",
            "message": "checkpoint saved",
            "checkpoint_id": checkpoint_id,
        }
    except Exception as exc:
        logger.exception("ingest_checkpoint failed")
        return {"status": "error", "message": str(exc)}
