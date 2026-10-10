"""Offline, verified snapshots of the supported local artifact set."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile

from core.file_io import atomic_artifact_path
from core.session_lock import graph_directory_owner
from core.transactions import ARTIFACTS, JOURNAL
from core.utils import load_json, write_json

MANIFEST = "backup_manifest.json"


def _digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Backup artifact must be a regular file: {path.name}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def verify_backup(source):
    source = Path(source).resolve()
    if (source / MANIFEST).is_symlink():
        raise ValueError("Backup manifest must not be a symlink")
    manifest = load_json(str(source / MANIFEST))
    if not manifest or manifest.get("format_version") != 1:
        raise ValueError("Missing or unsupported backup manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files or any(name not in ARTIFACTS for name in files):
        raise ValueError("Invalid backup artifact list")
    if {p.name for p in source.iterdir()} != set(files) | {MANIFEST}:
        raise ValueError("Unexpected or missing backup files")
    for name, expected in files.items():
        if not isinstance(expected, dict) or _digest(source / name) != expected:
            raise ValueError(f"Backup checksum mismatch: {name}")
    return manifest


@contextmanager
def _fresh_directory(destination):
    """Publish only a complete directory; never intentionally replace a target."""
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        yield staging
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Destination appeared during copy: {destination}")
        os.rename(staging, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _copy(source, destination):
    # Reject links and special files before reading. O_NOFOLLOW also protects
    # the final source path component if it changes between inspection/open.
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Artifact must be a regular file: {source.name}")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Artifact must be a regular file: {source.name}")
        with atomic_artifact_path(destination) as temporary:
            with temporary.open("wb") as output:
                shutil.copyfileobj(stream, output, length=1024 * 1024)


def backup_graph(source, destination):
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError("Source graph directory does not exist")
    target = Path(destination).absolute()
    if target.resolve().is_relative_to(source):
        raise ValueError("Backup destination must be outside the graph directory")
    # Stop the server first. These nonblocking locks also reject standalone
    # mutations that use the session lock without owning a server runtime.
    with graph_directory_owner(str(source)):
        descriptor = os.open(source / ".preciso-ingestion.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Graph mutation is active; stop writers before backup") from exc
            if (source / JOURNAL).exists() or (source / JOURNAL).is_symlink():
                raise RuntimeError("Unfinished transaction; recover the graph before backup")
            files = [name for name in ARTIFACTS if (source / name).exists() or (source / name).is_symlink()]
            if not files:
                raise ValueError("No persisted graph artifacts to back up")
            with _fresh_directory(target) as staging:
                for name in files:
                    _copy(source / name, staging / name)
                manifest = {
                    "format_version": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": {name: _digest(staging / name) for name in files},
                }
                write_json(manifest, str(staging / MANIFEST))
                verify_backup(staging)
            return manifest
        finally:
            os.close(descriptor)


def restore_graph(source, destination):
    source = Path(source).resolve()
    manifest = verify_backup(source)
    if Path(destination).resolve().is_relative_to(source):
        raise ValueError("Restore destination must be outside the backup directory")
    with _fresh_directory(destination) as staging:
        for name, expected in manifest["files"].items():
            _copy(source / name, staging / name)
            if _digest(staging / name) != expected:
                raise ValueError(f"Backup changed during restore: {name}")
    return manifest
