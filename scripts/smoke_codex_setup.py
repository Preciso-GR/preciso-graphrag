"""Check registration/idempotency with the real Codex CLI in temporary user config."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from preciso_mcp.setup_cli import connect_codex


def main():
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("Install Codex CLI to run this manual integration check")
    with tempfile.TemporaryDirectory(prefix="preciso-codex-setup-") as directory:
        root = Path(directory)
        home = root / "codex"
        home.mkdir()
        project = root / "project"
        project.mkdir()
        # CODEX_HOME is used for its documented purpose: isolate this test's
        # Codex configuration. The real user's configuration is never read.
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
            subprocess.run([codex, "mcp", "add", "unrelated", "--", "echo", "preserve-me"], check=True, capture_output=True)
            command = [sys.executable, "-m", "preciso_mcp.cli", "serve", "--settings", str(root / "settings.json")]
            with patch("preciso_mcp.setup_cli.confirm", return_value=True):
                connect_codex(project, command)
            before = (home / "config.toml").read_bytes()
            connect_codex(project, command)
            assert (home / "config.toml").read_bytes() == before
            entries = json.loads(subprocess.check_output([codex, "mcp", "list", "--json"], text=True))
            assert len(entries) == 2
            assert next(e for e in entries if e["name"] == "unrelated")["transport"]["args"] == ["preserve-me"]
            owned = next(e for e in entries if e["name"].startswith("preciso-"))
            assert owned["transport"]["command"] == command[0]
            assert owned["transport"]["args"] == command[1:]
    print("Codex setup passed: real CLI registration, existing-entry preservation, repeat setup without changes.")


if __name__ == "__main__":
    main()
