import json
from pathlib import Path

import pytest

from ingest.file_access import read_extraction_text, resolve_input_file
from preciso_mcp.tools import ingest_from_file_tool, reconcile_tool


def test_relative_and_documented_input_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "extractions"
    root.mkdir()
    path = root / "doc.json"
    path.write_text("{}")
    assert resolve_input_file("doc.json", {}) == path
    assert resolve_input_file("extractions/doc.json", {}) == path
    assert resolve_input_file(str(path), {}) == path


@pytest.mark.parametrize("path", ["../private.json", "/etc/passwd"])
def test_input_directory_escape_is_rejected(tmp_path, path):
    with pytest.raises(ValueError, match="configured extraction directory"):
        resolve_input_file(path, {"input_dir": str(tmp_path / "inputs")})


def test_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    outside = tmp_path / "private.json"
    outside.write_text("{}")
    (root / "link.json").symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_input_file("link.json", {"input_dir": str(root)})


def test_file_size_is_limited_before_parsing(tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_text(" " * 100)
    monkeypatch.setenv("GRAPHRAG_MAX_INGEST_BYTES", "10")
    with pytest.raises(ValueError, match="byte limit"):
        read_extraction_text(path)


async def test_file_tool_rejects_outside_file_without_reading(tmp_path, monkeypatch):
    outside = tmp_path / "private.json"
    outside.write_text("private data")

    def forbidden(*args):
        raise AssertionError("must not read an outside file")

    monkeypatch.setattr(ingest_from_file_tool, "_load_payload", forbidden)
    result = await ingest_from_file_tool.ingest_from_file(str(outside), {}, {"input_dir": str(tmp_path / "inputs")})
    assert result["status"] == "error"


async def test_reconciliation_uses_safe_output_name(tmp_path, monkeypatch):
    path = tmp_path / "base.json"
    path.write_text(json.dumps({"document_id": "../../outside_part1", "entities": [], "relationships": [], "chunks": []}))

    async def ingest(**kwargs):
        return {"status": "success"}

    monkeypatch.setattr(reconcile_tool, "ingest_extracted_json", ingest)
    cfg = {"input_dir": str(tmp_path), "working_dir": str(tmp_path / "graph")}
    result = await reconcile_tool.ingest_with_reconciliation([str(path)], {}, cfg)
    assert result["status"] == "success"
    output = Path(result["unified_file"])
    assert output.parent == tmp_path / "graph" / "reconciled"
    assert "outside" not in output.name
    assert output.exists()
    assert resolve_input_file(str(output), cfg, allow_reconciled=True) == output


async def test_invalid_utf8_file_has_error_result(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"\xff")
    result = await ingest_from_file_tool.ingest_from_file(str(path), {}, {"input_dir": str(tmp_path)})
    assert result["status"] == "error"
    assert "UTF-8" in result["message"]
