"""Durable replacement of one local artifact without truncating its predecessor."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


@contextmanager
def atomic_artifact_path(destination: str | Path) -> Iterator[Path]:
    """Publish a completed temporary artifact; failures leave the old file intact.

    The writer must close its handles before leaving this context. The temporary
    file lives beside the destination so os.replace stays on one filesystem.
    This protects one artifact, not a transaction across several artifacts.
    """
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        if path.exists():
            temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        yield temporary
        with temporary.open("rb") as artifact:
            os.fsync(artifact.fileno())
        os.replace(temporary, path)
        # Supported targets are POSIX. Persist the directory entry as well as
        # file contents; propagate failure rather than claiming durable success.
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
