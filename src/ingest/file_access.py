"""File input boundaries shared by ingestion and reconciliation tools."""

from __future__ import annotations

import os
from pathlib import Path

from ingest.validator import _positive_limit


def resolve_input_file(file_path: str, global_config: dict, *, allow_reconciled: bool = False) -> Path:
    root = Path(global_config.get("input_dir") or os.getenv("GRAPHRAG_INPUT_DIR", "extractions")).expanduser().resolve()
    candidate = Path(file_path).expanduser()
    if not candidate.is_absolute():
        # Preserve the documented `extractions/name.json` form as well as
        # root-relative names when the configured root has that name.
        candidate = (root.parent if candidate.parts and candidate.parts[0] == root.name else root) / candidate
    resolved = candidate.resolve()
    roots = [root]
    if allow_reconciled:
        roots.append(Path(global_config.get("reconciliation_dir") or Path(global_config.get("working_dir", ".")) / "reconciled").resolve())
    if not any(resolved.is_relative_to(allowed) for allowed in roots):
        raise ValueError("input file must be inside the configured extraction directory")
    return resolved


def read_extraction_text(path: Path) -> str:
    if path.suffix.lower() not in {".json", ".md", ".txt"}:
        raise ValueError("unsupported extraction file extension")
    limit = _positive_limit("GRAPHRAG_MAX_INGEST_BYTES", 25 * 1024 * 1024)
    with path.open("rb") as source:
        # Enforce the limit on the actual read, not only a racy stat() result.
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"extraction file exceeds the {limit} byte limit")
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("extraction file must use UTF-8") from exc
