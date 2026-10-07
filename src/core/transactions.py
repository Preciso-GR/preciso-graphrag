"""Recoverable mutations of the local artifact set, without a second database."""

from __future__ import annotations

import fcntl
import os
import shutil
from pathlib import Path

from core.file_io import atomic_artifact_path
from core.session_lock import ingestion_session_lock
from core.utils import load_json, logger, write_json

ARTIFACTS = (
    "graph_graph.graphml", "vdb_entities.json", "vdb_relationships.json", "vdb_chunks.json",
    "kv_store_text_chunks.json", "kv_store_entity_chunks.json", "kv_store_relation_chunks.json",
    "kv_store_pending_summaries.json", "kv_store_llm_cache.json", "kv_store_checkpoints.json",
    "artifact_manifest.json",
)
JOURNAL = ".preciso-transaction"
_unavailable_directories: set[str] = set()


def ensure_artifacts_available(config: dict, workspace: str = "") -> None:
    if str(artifact_directory(config, workspace).resolve()) in _unavailable_directories:
        raise RuntimeError("Storage recovery failed; stop this runtime and restore/recover the data before restarting")


def artifact_directory(config: dict, workspace: str = "") -> Path:
    root = Path(config["working_dir"])
    return root / workspace if workspace else root


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _recover(root: Path) -> None:
    journal = root / JOURNAL
    if not journal.exists():
        return
    if journal.is_symlink() or not journal.is_dir():
        raise RuntimeError("Invalid transaction journal; preserve the data directory for recovery")
    manifest = load_json(str(journal / "manifest.json"))
    if manifest is None:
        # No mutation starts until the complete preparation record is durable.
        shutil.rmtree(journal)
        _sync_directory(root)
        return
    names = manifest.get("previous_files")
    state = manifest.get("state")
    if not isinstance(names, list) or any(name not in ARTIFACTS for name in names) or state not in {"prepared", "committed"}:
        raise RuntimeError("Invalid transaction recovery record; restore a verified backup")
    if state == "prepared":
        for name in ARTIFACTS:
            destination = root / name
            if name in names:
                backup = journal / name
                if not backup.is_file() or backup.is_symlink():
                    raise RuntimeError(f"Transaction backup `{name}` is missing or invalid")
                # Retain the backup throughout rollback. A second crash can
                # restart the restoration from the same complete recovery set.
                with atomic_artifact_path(destination) as temporary:
                    temporary.unlink()
                    os.link(backup, temporary)
            else:
                destination.unlink(missing_ok=True)
        _sync_directory(root)
    # Rename before deletion. Otherwise a crash during recursive deletion can
    # leave a prepared journal with missing backups after a completed rollback.
    garbage = root / f"{JOURNAL}.complete"
    if garbage.exists():
        shutil.rmtree(garbage)
    os.replace(journal, garbage)
    _sync_directory(root)
    shutil.rmtree(garbage)


def recover_artifacts(config: dict, workspace: str = "") -> None:
    """Recover before loading stores; never roll back another active session."""
    root = artifact_directory(config, workspace)
    if not (root / JOURNAL).exists():
        return
    descriptor = os.open(root / ".preciso-ingestion.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Graph mutation is active; retry initialization after it completes") from exc
        _recover(root)
    finally:
        os.close(descriptor)


class ArtifactTransaction:
    def __init__(self, root: Path):
        self.root = root
        self.journal = root / JOURNAL
        self.previous_files: list[str] = []

    def begin(self) -> None:
        _recover(self.root)
        self.journal.mkdir(mode=0o700)
        try:
            for name in ARTIFACTS:
                path = self.root / name
                if path.exists():
                    if path.is_symlink() or not path.is_file():
                        raise RuntimeError(f"Invalid artifact path `{name}`")
                    # Existing writers replace files atomically. Hard links
                    # therefore preserve prior bytes without copying the corpus.
                    os.link(path, self.journal / name)
                    self.previous_files.append(name)
            write_json({"state": "prepared", "previous_files": self.previous_files}, str(self.journal / "manifest.json"))
            _sync_directory(self.root)
        except BaseException:
            # No application mutation has occurred during preparation.
            shutil.rmtree(self.journal)
            raise

    def commit(self) -> None:
        write_json({"state": "committed", "previous_files": self.previous_files}, str(self.journal / "manifest.json"))
        try:
            _recover(self.root)
        except OSError as exc:
            # The committed marker is durable. Cleanup can resume at startup.
            logger.warning("Committed transaction cleanup deferred: %s", exc)

    def rollback(self) -> None:
        # Reset the marker before restoration if commit publication failed.
        manifest = load_json(str(self.journal / "manifest.json"))
        if manifest is None or manifest.get("state") != "prepared":
            write_json({"state": "prepared", "previous_files": self.previous_files}, str(self.journal / "manifest.json"))
        _recover(self.root)


async def _reload_stores(stores: dict) -> None:
    for store in stores.values():
        reload = getattr(store, "reload_from_disk", None)
        if reload is not None:
            await reload()


async def run_artifact_mutation(operation, stores: dict, config: dict) -> dict:
    if "working_dir" not in config:
        if any(hasattr(store, "_file_name") or hasattr(store, "_client_file_name") or hasattr(store, "_graphml_xml_file") for store in stores.values()):
            raise ValueError("Local storage mutations require a working directory")
        return await operation()  # Custom memory-only adapters have no files.
    workspace = getattr(stores.get("graph"), "workspace", "")
    async with ingestion_session_lock(config["working_dir"], workspace):
        ensure_artifacts_available(config, workspace)
        transaction = ArtifactTransaction(artifact_directory(config, workspace))
        transaction.begin()

        async def rollback():
            try:
                transaction.rollback()
                await _reload_stores(stores)
            except BaseException:
                _unavailable_directories.add(str(transaction.root.resolve()))
                raise

        try:
            result = await operation()
            if result.get("status") == "partial_success" and not config.get("allow_partial_ingest", False):
                result = {
                    "status": "validation_failed", "errors": result.get("errors", []),
                    "message": "Extraction rejected; no changes were committed",
                }
            if result.get("status") in {"success", "partial_success"}:
                transaction.commit()
                return result
        except BaseException:
            await rollback()
            raise
        await rollback()
        return result
