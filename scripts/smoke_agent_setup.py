"""Check both installed agent CLIs with isolated configuration; never start an LLM."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from preciso_mcp.setup_cli import connect_claude, connect_codex, connection_name


def main():
    codex, claude = shutil.which("codex"), shutil.which("claude")
    if not codex or not claude:
        raise SystemExit("Install Codex CLI and Claude Code CLI for this integration check")
    with tempfile.TemporaryDirectory(prefix="preciso-agent-setup-") as directory:
        root = Path(directory).resolve()
        project = root / "project"
        project.mkdir()
        codex_home, claude_home = root / "codex", root / "claude"
        codex_home.mkdir()
        claude_home.mkdir()
        with patch.dict(os.environ, {"CODEX_HOME": str(codex_home), "CLAUDE_CONFIG_DIR": str(claude_home)}):
            subprocess.run([codex, "mcp", "add", "unrelated", "--", "echo", "preserve"], check=True, capture_output=True)
            subprocess.run([claude, "mcp", "add", "--scope", "local", "unrelated", "--", "echo", "preserve"],
                           cwd=project, check=True, capture_output=True)
            old = ["uvx", "--from", "preciso-graphrag==0.3.0rc1", "--offline", "preciso-graphrag",
                   "serve", "--settings", str(root / "settings.json")]
            new = [arg.replace("==0.3.0rc1", "==0.3.0rc2") for arg in old]
            with patch("preciso_mcp.setup_cli.confirm", return_value=True):
                for connect in (connect_codex, connect_claude):
                    connect(project, old)
                paths = [codex_home / "config.toml", claude_home / ".claude.json"]
                before = [p.read_bytes() for p in paths]
                for connect in (connect_codex, connect_claude):
                    connect(project, old)
                assert [p.read_bytes() for p in paths] == before, "Repeat setup rewrote configuration"
                for connect in (connect_codex, connect_claude):
                    connect(project, new)
            entries = json.loads(subprocess.check_output([codex, "mcp", "list", "--json"], text=True))
            assert len(entries) == 2
            assert next(e for e in entries if e["name"] == "unrelated")["transport"]["args"] == ["preserve"]
            assert next(e for e in entries if e["name"] == connection_name(project))["transport"]["args"] == new[1:]
            data = json.loads((claude_home / ".claude.json").read_text())
            servers = data["projects"][str(project)]["mcpServers"]
            assert len(servers) == 2
            assert servers["unrelated"]["args"] == ["preserve"]
            assert servers[connection_name(project)]["args"] == new[1:]
    print("Both real CLIs passed: registration, preservation, repeat setup, and explicit package-version upgrade.")


if __name__ == "__main__":
    main()
