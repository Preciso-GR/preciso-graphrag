"""Small interactive onboarding flow. Server startup never invokes this module's UI."""
from __future__ import annotations

import asyncio
import getpass
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from preciso_mcp.user_settings import (
    KEY_ENV, credential_account, load_settings, macos_keychain,
    project_settings_path, save_settings,
)

DEPENDENCIES = {"fastembed": ["fastembed==0.9.0"], "ollama": [],
                "openai": ["openai>=1.0.0"], "cohere": ["cohere>=4.0.0"]}


def confirm(message):
    return input(message + " [y/N] ").strip().lower() in {"y", "yes"}


def ollama_endpoint():
    endpoint = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    if "://" not in endpoint:
        endpoint = "http://" + endpoint
    return endpoint


def installed_ollama_models():
    try:
        with urllib.request.urlopen(ollama_endpoint() + "/api/tags", timeout=3) as response:
            payload = json.loads(response.read(1024 * 1024))
        return {item["name"]: item["digest"] for item in payload["models"]
                if item["name"].split(":")[0] in {"nomic-embed-text", "mxbai-embed-large"}}
    except Exception:
        raise ValueError("Ollama is not reachable. Start it or choose built-in local embeddings.") from None


def ensure_ollama_models():
    """Start an installed local service only after interactive consent."""
    try:
        return installed_ollama_models()
    except ValueError:
        pass
    endpoint = urllib.parse.urlsplit(ollama_endpoint())
    if (endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
            or endpoint.path not in {"", "/"} or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment):
        raise ValueError("The configured Ollama service is unavailable. Start that service and rerun setup; no local service was started.")
    executable = shutil.which("ollama")
    if not executable:
        raise ValueError("Ollama is not installed. Install it, or choose built-in Granite embeddings.")
    if not confirm("Ollama is stopped. Start it in the background? It will keep running after setup."):
        raise ValueError("Ollama was not started. Start it manually or choose built-in embeddings. Settings were not changed.")
    try:
        process = subprocess.Popen([executable, "serve"],
                                   env=dict(os.environ, OLLAMA_HOST=ollama_endpoint()),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        raise ValueError("Ollama could not be started. Run 'ollama serve' to inspect the problem, then rerun setup.") from None
    ready = False
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                models = installed_ollama_models()
                ready = True
                return models
            except ValueError:
                if process.poll() is not None:
                    break
                time.sleep(0.5)
    finally:
        if not ready and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
    raise ValueError("Ollama did not become ready. Run 'ollama serve' to inspect the problem, then rerun setup. Settings were not changed.")


def choose_client():
    value = input("Connect agent: 1 Codex, 2 Claude Code, 3 Both [1]: ").strip() or "1"
    if value not in {"1", "2", "3"}:
        raise ValueError("Choose Codex, Claude Code, or both")
    return {"1": "codex", "2": "claude", "3": "both"}[value]


def package_source():
    dist = importlib.metadata.distribution("preciso-graphrag")
    direct = dist.read_text("direct_url.json")
    if direct:
        data = json.loads(direct)
        # Development checkouts and downloaded wheels remain reproducible too.
        if data.get("url", "").startswith("file:"):
            return data["url"]
    return "preciso-graphrag==" + dist.version


def launch_command(settings_path, provider, credential_mode=None, *, offline=True):
    uvx = shutil.which("uvx")
    if not uvx:
        raise ValueError("Install uv before automated setup; its uvx command launches PRECISO for your agent.")
    command = [uvx, "--from", package_source()]
    if offline:
        command.append("--offline")
    requirements = list(DEPENDENCIES[provider])
    if credential_mode == "keychain":
        requirements.append("keyring>=25,<26")
    for requirement in requirements:
        command.extend(["--with", requirement])
    return command + ["preciso-graphrag", "serve", "--settings", str(settings_path)]


def ensure_dependencies(project, provider, client="codex"):
    module = {"fastembed": "fastembed", "openai": "openai", "cohere": "cohere"}.get(provider)
    missing_provider = module and importlib.util.find_spec(module) is None
    missing_keyring = provider in KEY_ENV and importlib.util.find_spec("keyring") is None
    if missing_provider or missing_keyring:
        command = launch_command(project_settings_path(project), provider, "keychain" if provider in KEY_ENV else None, offline=False)
        command[-3:] = ["setup", "--project", str(project), "--provider", provider, "--client", client]
        print("Selected provider needs optional Python packages:\n" + shlex.join(command))
        if not confirm("Install these packages in uvx's isolated environment and resume setup?"):
            return False
        subprocess.run(command, check=True)
        return False  # Resumed setup owns the remaining work.
    return True


def choose_api():
    value = input("API provider: 1 OpenAI, 2 Cohere [1]: ").strip() or "1"
    if value not in {"1", "2"}:
        raise ValueError("Choose API provider 1 or 2")
    return {"1": "openai", "2": "cohere"}[value]


def choose_provider():
    value = input("Embeddings: 1 Local (recommended), 2 API [1]: ").strip() or "1"
    if value == "2":
        return choose_api()
    if value != "1":
        raise ValueError("Choose local or API embeddings")
    try:
        models = installed_ollama_models()
        print("Ollama is running." + (" Installed supported models: " + ", ".join(models) if models else " No supported models installed."))
    except ValueError:
        models = None
        print("No running Ollama detected. Built-in embeddings do not require it.")
    if models is not None or shutil.which("ollama"):
        value = input("Local runtime: 1 Built-in Granite (recommended), 2 Ollama [1]: ").strip() or "1"
        if value == "2":
            return "ollama"
        if value != "1":
            raise ValueError("Choose built-in or Ollama embeddings")
    return "fastembed"


def configure_api(data):
    provider = data["provider"]
    default = "text-embedding-3-small" if provider == "openai" else "embed-english-v3.0"
    if not data.get("model"):
        data["dimension"] = 1536 if provider == "openai" else 1024
    data["model"] = input(f"Embedding model [{data.get('model') or default}]: ").strip() or data.get("model") or default
    print("The API provider will receive document text and queries. Usage can incur charges.")
    mode = input("Credentials: 1 macOS Keychain, 2 Environment variable [1]: ").strip() or "1"
    if mode == "1":
        try:
            keychain = macos_keychain()
            previous = keychain.get_password("preciso-graphrag", credential_account(data))
        except Exception:
            print("Keychain unavailable. Install the setup extra for Keychain, or use an environment variable.")
            if not confirm("Use an environment variable instead?"):
                raise ValueError("No secure credential storage selected")
            mode = "2"
        else:
            secret = getpass.getpass("API key (hidden; blank keeps existing key): ").strip() or previous
            if not secret:
                raise ValueError("An API key is required")
            data["credential_mode"] = "keychain"
            return secret, keychain
    if mode != "2":
        raise ValueError("Choose Keychain or an environment variable")
    data["credential_mode"] = "environment"
    if not (os.getenv(KEY_ENV[provider]) or os.getenv(provider.upper() + "_API_KEY")):
        raise ValueError(f"Set {KEY_ENV[provider]} in the environment, then rerun setup")
    return None, None


def probe_settings(data, secret=None):
    # Never save a new key merely to test it. Pass it via the child's environment.
    with tempfile.TemporaryDirectory(prefix="preciso-provider-check-") as temporary:
        path = Path(temporary) / "settings.json"
        candidate = dict(data)
        if secret is not None:
            candidate["credential_mode"] = "environment"
        save_settings(path, candidate)
        env = dict(os.environ)
        if secret is not None:
            env[KEY_ENV[data["provider"]]] = secret
        result = subprocess.run([sys.executable, "-m", "preciso_mcp.cli", "check", "--settings", str(path)],
                                capture_output=True, text=True, env=env, timeout=120)
        if result.returncode:
            raise ValueError("Embedding connection check failed. Check the provider/model/credentials and retry. No provider was substituted.")
        return json.loads(result.stdout)["dimension"]


async def verify_mcp(command):
    from datetime import timedelta
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async with stdio_client(StdioServerParameters(command=command[0], args=command[1:], env=dict(os.environ))) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=120)) as session:
            await session.initialize()
            result = await session.call_tool("get_server_status")
            data = result.structuredContent
            if data is None:
                data = json.loads(next(item.text for item in result.content if item.type == "text"))
            if result.isError or data["embedding"]["status"] != "active":
                raise ValueError("MCP provider is not active")


def connection_name(project):
    slug = re.sub(r"[^a-z0-9-]", "-", project.name.lower())[:24] or "project"
    return "preciso-" + slug + "-" + hashlib.sha256(str(project).encode()).hexdigest()[:8]


def version_upgrade(previous, command):
    """Only a package version can change; preserve provider, paths, and flags."""
    if not isinstance(previous, list) or len(previous) != len(command):
        return False
    old, new = list(previous), list(command)
    try:
        index = new.index("--from") + 1
        for value in (old[index], new[index]):
            if not isinstance(value, str) or not re.fullmatch(r"preciso-graphrag==[0-9][0-9A-Za-z.]*", value):
                return False
        old[index] = new[index]
    except (ValueError, IndexError):
        return False
    return old == new


def connect_codex(project, command):
    codex = shutil.which("codex")
    if not codex:
        print("Codex CLI was not found. Saved settings are ready; install Codex CLI and rerun setup.")
        return
    name = connection_name(project)
    listed = subprocess.run([codex, "mcp", "list", "--json"], capture_output=True, text=True, check=True)
    entries = json.loads(listed.stdout)
    existing = next((entry for entry in entries if entry["name"] == name), None)
    if existing:
        transport = existing.get("transport", {})
        if transport.get("command") == command[0] and transport.get("args") == command[1:]:
            print("Codex already has this PRECISO connection. No change needed.")
            return
        previous = [transport.get("command"), *transport.get("args", [])]
        if not version_upgrade(previous, command) or transport.get("env") or transport.get("env_vars"):
            raise ValueError("A different Codex entry already uses this project name. It was not overwritten.")
    change = [codex, "mcp", "add", name, "--", *command]
    print("Proposed Codex MCP entry (contains no API key):\n" + shlex.join(change))
    print("Codex stores this named entry in user configuration; separate collections are not access control.")
    if not confirm(("Update this managed entry's package version" if existing else "Add this entry") + " while preserving other Codex servers?"):
        print("Connection not added. Rerun setup when ready.")
        return
    # Re-read after approval to avoid overwriting an entry added during the prompt.
    current = json.loads(subprocess.run([codex, "mcp", "list", "--json"], capture_output=True, text=True, check=True).stdout)
    if next((entry for entry in current if entry["name"] == name), None) != existing:
        raise ValueError("Codex configuration changed during setup. Rerun to inspect it.")
    subprocess.run(change, check=True, capture_output=True, text=True)
    print("Codex connection added. Restart or reload Codex to discover the server.")


def claude_entries(project):
    """Read entries only; official Claude CLI owns all writes."""
    config_dir = os.getenv("CLAUDE_CONFIG_DIR")
    user_path = Path(config_dir).expanduser() / ".claude.json" if config_dir else Path.home() / ".claude.json"
    try:
        user = json.loads(user_path.read_text()) if user_path.exists() else {}
        shared_path = project / ".mcp.json"
        shared = json.loads(shared_path.read_text()) if shared_path.exists() else {}
        local = user.get("projects", {}).get(str(project), {}).get("mcpServers", {})
        entries = [local, shared.get("mcpServers", {}), user.get("mcpServers", {})]
        if not all(isinstance(entry, dict) for entry in entries):
            raise ValueError("Invalid MCP server mapping")
        return entries
    except (ValueError, AttributeError, OSError):
        raise ValueError("Claude Code configuration could not be read. Repair its JSON or permissions, then rerun setup. No entry was changed.") from None


def connect_claude(project, command):
    claude = shutil.which("claude")
    if not claude:
        print("Claude Code CLI was not found. Saved settings are ready; install Claude Code CLI and rerun setup.")
        return
    name = connection_name(project)
    entries = claude_entries(project)
    existing = next((entry[name] for entry in entries if name in entry), None)
    expected = {"type": "stdio", "command": command[0], "args": command[1:]}
    if existing is not None:
        normalized = dict(existing) if isinstance(existing, dict) else {}
        if normalized.get("env") == {}:
            normalized.pop("env")  # Claude CLI writes an empty env map by default.
        if normalized == expected:
            print("Claude Code already has this PRECISO connection. No change needed.")
            return
        previous = [existing.get("command"), *existing.get("args", [])] if isinstance(existing, dict) else []
        if (entries[0].get(name) != existing or not version_upgrade(previous, command)
                or set(normalized) - set(expected) or normalized.get("type", "stdio") != "stdio"):
            raise ValueError("A different Claude Code entry already uses this project name. It was not overwritten.")
    change = [claude, "mcp", "add", "--transport", "stdio", "--scope", "local", name, "--", *command]
    print("Proposed Claude Code MCP entry (contains no API key):\n" + shlex.join(change))
    print("Claude Code local scope keeps this connection private to the selected project.")
    if not confirm(("Update this managed entry's package version" if existing else "Add this entry") + " while preserving other Claude Code servers?"):
        print("Claude Code connection not added. Rerun setup when ready.")
        return
    if claude_entries(project) != entries:
        raise ValueError("Claude Code configuration changed during setup. Rerun to inspect it.")
    if existing is not None:
        subprocess.run([claude, "mcp", "remove", "--scope", "local", name], cwd=project, check=True, capture_output=True, text=True)
    try:
        subprocess.run(change, cwd=project, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        if existing is not None:
            try:
                subprocess.run([claude, "mcp", "add", "--transport", "stdio", "--scope", "local", name,
                                "--", *previous], cwd=project, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError:
                raise ValueError("Claude Code update and restoration failed. Project graph/settings are preserved; repair Claude Code CLI and rerun setup to restore its connection.") from None
        raise
    print("Claude Code connection added. Restart or reload Claude Code, then inspect /mcp.")


def setup_project(project, provider=None, client=None):
    if not sys.stdin.isatty():
        raise ValueError("Setup requires an interactive terminal. Server startup uses the noninteractive serve command.")
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Select an existing project directory")
    client = client or choose_client()
    if client == "both":
        print("Both agents will share this project collection. Use one agent's MCP server at a time; stop it before switching agents.")
    settings_path = project_settings_path(project)
    existing = load_settings(settings_path) if settings_path.exists() else None
    if existing and provider is not None and provider != existing["provider"]:
        raise ValueError("This project already has a provider. Use a new collection for a model change.")
    provider = existing["provider"] if existing else provider or choose_provider()
    if not ensure_dependencies(project, provider, client):
        return
    data = dict(existing) if existing else {"schema_version": 1, "project": str(project), "provider": provider,
            "dimension": 384, "workdir": str(settings_path.parent / "graph"),
            "input_dir": str(settings_path.parent / "extractions")}
    secret = keychain = None
    if provider == "fastembed":
        from core.local_embeddings import MODEL, MODEL_BYTES, default_model_directory, download_model, verify_model
        data.update(model=MODEL, model_dir=data.get("model_dir", str(default_model_directory())))
        while True:
            try:
                verify_model(Path(data["model_dir"]))
                break
            except ValueError:
                print(f"Model: {MODEL}\nDownload: {MODEL_BYTES / 1024**2:.1f} MiB, plus optional Python packages.\nCache: {data['model_dir']}")
                if not confirm("Download or repair this pinned model?"):
                    print("Download cancelled. No project settings were changed.")
                    return
                try:
                    download_model(Path(data["model_dir"]))
                    break
                except Exception:
                    choice = input("Download failed. Retry [r], choose API [a], cancel [c]: ").strip().lower()
                    if choice == "a":
                        return setup_project(project, choose_api(), client)
                    if choice != "r":
                        return
    elif provider == "ollama":
        models = ensure_ollama_models()
        if existing and models.get(existing["model"]) != existing.get("ollama_digest"):
            raise ValueError("The saved Ollama model changed. Keep its original revision or create a new collection.")
        if not models:
            print("No supported model found. Suggested download: nomic-embed-text (approximately 274 MB).")
            if not confirm("Download it through the running Ollama service?"):
                return
            import ollama
            ollama.Client(host=ollama_endpoint()).pull("nomic-embed-text")
            models = installed_ollama_models()
        names = sorted(models)
        if existing:
            name = existing["model"]
        else:
            for index, name in enumerate(names, 1):
                print(f"{index}. {name}")
            selection = int(input("Choose installed model [1]: ").strip() or "1")
            if not 1 <= selection <= len(names):
                raise ValueError("Invalid installed model selection")
            name = names[selection - 1]
        data.update(model=name, ollama_digest=models[name])
    else:
        secret, keychain = configure_api(data)
        if existing and data["model"] != existing["model"]:
            raise ValueError("Changing models needs a new collection. Existing settings were preserved.")
        if not confirm("Test the API with one synthetic sentence (a small usage charge may apply)?"):
            return
    dimension = probe_settings(data, secret)
    if existing and dimension != existing["dimension"]:
        raise ValueError("Provider dimensions changed. Existing settings were preserved.")
    data["dimension"] = dimension
    command = launch_command(settings_path, provider, data.get("credential_mode"))
    if keychain is not None:
        keychain.set_password("preciso-graphrag", credential_account(data), secret)
    save_settings(settings_path, data)
    Path(data["input_dir"]).mkdir(parents=True, exist_ok=True)
    if not confirm("Prepare and verify the agent launcher (uv may download Python packages)?"):
        print("Settings saved. Agent connections were not changed. Rerun setup to finish the connection.")
        return
    # Populate uv's tool cache now. Later Codex starts resolve offline, without
    # waiting on package-index availability. The model/API can still use its
    # explicitly selected provider; --offline applies to uv, not the server.
    warm_command = launch_command(settings_path, provider, data.get("credential_mode"), offline=False)
    asyncio.run(verify_mcp(warm_command))
    asyncio.run(verify_mcp(command))
    print(f"Provider and MCP connection verified.\nSettings: {settings_path}\nCollection: {data['workdir']}")
    for target, connect in (("codex", connect_codex), ("claude", connect_claude)):
        if client in {target, "both"}:
            connect(project, command)
