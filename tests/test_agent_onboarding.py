"""Consent, provider startup, and client-registration boundaries."""
import json
from types import SimpleNamespace

import pytest

from preciso_mcp import setup_cli as setup
from preciso_mcp.user_settings import project_settings_path


@pytest.mark.parametrize(("answer", "expected"), [("", "codex"), ("1", "codex"), ("2", "claude"), ("3", "both")])
def test_client_choices(monkeypatch, answer, expected):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert setup.choose_client() == expected


def test_invalid_client_rejected(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "4")
    with pytest.raises(ValueError, match="Choose Codex"):
        setup.choose_client()


def unavailable():
    raise ValueError("not reachable")


def test_running_ollama_does_not_prompt_or_spawn(monkeypatch):
    monkeypatch.setattr(setup, "installed_ollama_models", lambda: {"nomic": "digest"})
    monkeypatch.setattr(setup, "confirm", lambda _: pytest.fail("Prompted for an already running service"))
    monkeypatch.setattr(setup.subprocess, "Popen", lambda *a, **k: pytest.fail("Spawned a second service"))
    assert setup.ensure_ollama_models() == {"nomic": "digest"}


def test_start_refusal_does_not_spawn(monkeypatch):
    monkeypatch.setattr(setup, "installed_ollama_models", unavailable)
    monkeypatch.setattr(setup, "ollama_endpoint", lambda: "http://127.0.0.1:11434")
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/bin/ollama")
    monkeypatch.setattr(setup, "confirm", lambda _: False)
    monkeypatch.setattr(setup.subprocess, "Popen", lambda *a, **k: pytest.fail("Started without consent"))
    with pytest.raises(ValueError, match="not started"):
        setup.ensure_ollama_models()


@pytest.mark.parametrize("endpoint", ["https://localhost:11434", "http://remote.example:11434", "http://localhost:11434/api"])
def test_unavailable_nonlocal_or_invalid_endpoint_never_starts(monkeypatch, endpoint):
    monkeypatch.setattr(setup, "installed_ollama_models", unavailable)
    monkeypatch.setattr(setup, "ollama_endpoint", lambda: endpoint)
    monkeypatch.setattr(setup, "confirm", lambda _: pytest.fail("Offered an inappropriate local start"))
    with pytest.raises(ValueError, match="no local service"):
        setup.ensure_ollama_models()


def test_ollama_start_waits_for_readiness_and_preserves_endpoint(monkeypatch):
    responses = iter([None, None, {"nomic": "digest"}])
    def models():
        result = next(responses)
        if result is None:
            raise ValueError("not ready")
        return result
    monkeypatch.setattr(setup, "installed_ollama_models", models)
    monkeypatch.setattr(setup, "ollama_endpoint", lambda: "http://127.0.0.1:12345")
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/bin/ollama")
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    monkeypatch.setattr(setup.time, "sleep", lambda _: None)
    spawned = []
    process = SimpleNamespace(poll=lambda: None)
    def popen(command, **kwargs):
        spawned.append((command, kwargs))
        return process
    monkeypatch.setattr(setup.subprocess, "Popen", popen)
    assert setup.ensure_ollama_models() == {"nomic": "digest"}
    assert spawned[0][0] == ["/bin/ollama", "serve"]
    assert spawned[0][1]["env"]["OLLAMA_HOST"] == "http://127.0.0.1:12345"
    assert spawned[0][1]["start_new_session"] is True


def test_start_timeout_cleans_up_only_started_process(monkeypatch):
    monkeypatch.setattr(setup, "installed_ollama_models", unavailable)
    monkeypatch.setattr(setup, "ollama_endpoint", lambda: "http://localhost:11434")
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/bin/ollama")
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    times = iter([0, 21])
    monkeypatch.setattr(setup.time, "monotonic", lambda: next(times))
    calls = []
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: calls.append("terminate"), wait=lambda **k: calls.append("wait"))
    monkeypatch.setattr(setup.subprocess, "Popen", lambda *a, **k: process)
    with pytest.raises(ValueError, match="did not become ready"):
        setup.ensure_ollama_models()
    assert calls == ["terminate", "wait"]


@pytest.mark.parametrize(("client", "expected"), [("codex", ["codex"]), ("claude", ["claude"]), ("both", ["codex", "claude"])])
def test_setup_registers_only_selected_clients(tmp_path, monkeypatch, client, expected):
    monkeypatch.setenv("PRECISO_CONFIG_DIR", str(tmp_path / "configuration"))
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup, "ensure_dependencies", lambda *a: True)
    monkeypatch.setattr(setup, "ensure_ollama_models", lambda: {"nomic-embed-text:latest": "digest"})
    monkeypatch.setattr(setup, "probe_settings", lambda *a: 768)
    monkeypatch.setattr(setup, "launch_command", lambda *a, **k: ["uvx", "serve"])
    monkeypatch.setattr("builtins.input", lambda _: "1")
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    async def verified(command):
        return None
    monkeypatch.setattr(setup, "verify_mcp", verified)
    registered = []
    monkeypatch.setattr(setup, "connect_codex", lambda *a: registered.append("codex"))
    monkeypatch.setattr(setup, "connect_claude", lambda *a: registered.append("claude"))
    setup.setup_project(tmp_path, "ollama", client)
    assert registered == expected
    assert project_settings_path(tmp_path).exists()


def test_dependency_resume_retains_client_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.importlib.util, "find_spec", lambda _: None)
    monkeypatch.setattr(setup, "launch_command", lambda *a, **k: ["uvx", "preciso-graphrag", "serve", "--settings", "settings.json"])
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    called = []
    monkeypatch.setattr(setup.subprocess, "run", lambda command, **k: called.append(command))
    assert setup.ensure_dependencies(tmp_path, "fastembed", "both") is False
    assert called[0][-2:] == ["--client", "both"]


def claude_config(tmp_path, monkeypatch, project, entries):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    path = tmp_path / ".claude.json"
    path.write_text(json.dumps({"projects": {str(project): {"mcpServers": entries}}, "unrelated": "preserve"}))
    monkeypatch.setattr(setup.shutil, "which", lambda _: "claude")
    return path


@pytest.mark.parametrize("extra", [{}, {"env": {}}])
def test_claude_identical_registration_is_noop(tmp_path, monkeypatch, extra):
    project = tmp_path / "project"
    project.mkdir()
    name = setup.connection_name(project)
    path = claude_config(tmp_path, monkeypatch, project, {name: {"type": "stdio", "command": "uvx", "args": ["serve"], **extra}})
    before = path.read_bytes()
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: pytest.fail("Rewrote existing entry"))
    setup.connect_claude(project, ["uvx", "serve"])
    assert path.read_bytes() == before


def test_claude_conflict_never_overwritten(tmp_path, monkeypatch):
    name = setup.connection_name(tmp_path)
    path = claude_config(tmp_path, monkeypatch, tmp_path, {name: {"command": "other"}})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="not overwritten"):
        setup.connect_claude(tmp_path, ["uvx", "serve"])
    assert path.read_bytes() == before


def test_claude_configuration_change_during_preview_is_rejected(tmp_path, monkeypatch):
    path = claude_config(tmp_path, monkeypatch, tmp_path, {})
    def confirm(_):
        path.write_text(json.dumps({"mcpServers": {"new": {"command": "other"}}}))
        return True
    monkeypatch.setattr(setup, "confirm", confirm)
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: pytest.fail("Wrote after config changed"))
    with pytest.raises(ValueError, match="changed during"):
        setup.connect_claude(tmp_path, ["uvx", "serve"])


def test_claude_registration_uses_project_scope_and_preserves_other_servers(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    path = claude_config(tmp_path, monkeypatch, project, {"other": {"command": "echo"}})
    before = path.read_bytes()
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    calls = []
    monkeypatch.setattr(setup.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    setup.connect_claude(project, ["uvx", "serve"])
    command, kwargs = calls[0]
    assert command[:8] == ["claude", "mcp", "add", "--transport", "stdio", "--scope", "local", setup.connection_name(project)]
    assert kwargs["cwd"] == project
    assert path.read_bytes() == before  # All writes are delegated to the real CLI.


def test_launcher_upgrade_cannot_change_model_or_settings():
    old = ["uvx", "--from", "preciso-graphrag==0.3.0rc1", "serve", "--settings", "/one"]
    new = ["uvx", "--from", "preciso-graphrag==0.3.0rc2", "serve", "--settings", "/one"]
    assert setup.version_upgrade(old, new)
    assert not setup.version_upgrade(old, [*new[:-1], "/another"])
    assert not setup.version_upgrade(old, ["other", *new[1:]])


def test_failed_claude_version_update_restores_previous_launcher(tmp_path, monkeypatch):
    import subprocess
    old = ["uvx", "--from", "preciso-graphrag==0.3.0rc1", "serve", "--settings", "/same"]
    new = [v.replace("rc1", "rc2") for v in old]
    name = setup.connection_name(tmp_path)
    claude_config(tmp_path, monkeypatch, tmp_path,
                  {name: {"type": "stdio", "command": old[0], "args": old[1:], "env": {}}})
    monkeypatch.setattr(setup, "confirm", lambda _: True)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(setup.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        setup.connect_claude(tmp_path, new)
    assert len(calls) == 3
    assert calls[-1][-len(old):] == old
