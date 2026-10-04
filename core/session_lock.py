"""A cross-session guard for mutations of one graph-artifact directory."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from core.storage.shared_storage import get_storage_keyed_lock


@asynccontextmanager
async def ingestion_session_lock(working_dir: str, workspace: str = ""):
    """Serialize ingestions sharing an artifact directory, including processes.

    Storage-level locks protect individual reads and writes.  They cannot protect
    a complete read/merge/write ingestion transaction, where two sessions could
    otherwise both begin from the same graph snapshot and the later save wins.
    """
    artifact_dir = Path(working_dir) / workspace if workspace else Path(working_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lock_path = artifact_dir / ".preciso-ingestion.lock"
    in_process_lock = get_storage_keyed_lock(f"ingestion-session:{artifact_dir.resolve()}")

    async with in_process_lock:
        # fcntl is available on Preciso's supported POSIX hosts.  Using
        # LOCK_NB plus a short await keeps another process from blocking the
        # event loop while it completes its ingestion.
        import fcntl

        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.05)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


@asynccontextmanager
async def graph_read_session(config: dict, workspace: str = ""):
    """Do not expose intermediate graph changes to supported read operations."""
    if "working_dir" not in config:
        yield  # Pure in-memory test/custom adapters have no local artifact set.
        return
    from core.transactions import ensure_artifacts_available

    async with ingestion_session_lock(config["working_dir"], workspace):
        ensure_artifacts_available(config, workspace)
        yield


@contextmanager
def graph_directory_owner(working_dir: str):
    """Reject a second MCP server with stale in-memory views of the same files."""
    import fcntl

    root = Path(working_dir)
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root / ".preciso-runtime.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another MCP runtime owns this graph directory") from exc
        yield
    finally:
        os.close(descriptor)
