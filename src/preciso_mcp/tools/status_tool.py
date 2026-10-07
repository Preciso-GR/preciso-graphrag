from __future__ import annotations

from core.runtime_status import build_runtime_status
from core.session_lock import graph_read_session


async def get_server_status(storage_instances: dict, global_config: dict) -> dict:
    workspace = getattr(storage_instances.get("graph"), "workspace", "")
    async with graph_read_session(global_config, workspace):
        # Status reads do not rewrite the manifest or scan the graph twice.
        return await build_runtime_status(storage_instances, global_config)
