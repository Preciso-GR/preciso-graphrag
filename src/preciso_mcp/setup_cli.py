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
        raise ValueError("Install uv before automated setup; its uvx command launches PRECISO for Codex.")
    command = [uvx, "--from", package_source()]
    if offline:
        command.append("--offline")
    requirements = list(DEPENDENCIES[provider])
    if credential_mode == "keychain":
        requirements.append("keyring>=25,<26")
    for requirement in requirements:
        command.extend(["--with", requirement])
    return command + ["preciso-graphrag", "serve", "--settings", str(settings_path)]


def ensure_dependencies(project, provider):
    module = {"fastembed": "fastembed", "openai": "openai", "cohere": "cohere"}.get(provider)
    missing_provider = module and importlib.util.find_spec(module) is None
    missing_keyring = provider in KEY_ENV and importlib.util.find_spec("keyring") is None
    if missing_provider or missing_keyring:
        command = launch_command(project_settings_path(project), provider, "keychain" if provider in KEY_ENV else None, offline=False)
        command[-3:] = ["setup", "--project", str(project), "--provider", provider]
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


def connect_codex(project, command):
    codex = shutil.which("codex")
    if not codex:
        print("Codex CLI was not found. Saved settings are ready; install Codex CLI and rerun setup.")
        return
    slug = re.sub(r"[^a-z0-9-]", "-", project.name.lower())[:24] or "project"
    name = "preciso-" + slug + "-" + hashlib.sha256(str(project).encode()).hexdigest()[:8]
    listed = subprocess.run([codex, "mcp", "list", "--json"], capture_output=True, text=True, check=True)
    entries = json.loads(listed.stdout)
    existing = next((entry for entry in entries if entry["name"] == name), None)
    if existing:
        transport = existing.get("transport", {})
        if transport.get("command") == command[0] and transport.get("args") == command[1:]:
            print("Codex already has this PRECISO connection. No change needed.")
            return
        raise ValueError("A different Codex entry already uses this project name. It was not overwritten.")
    change = [codex, "mcp", "add", name, "--", *command]
    print("Proposed Codex MCP entry (contains no API key):\n" + shlex.join(change))
    print("Codex stores this named entry in user configuration; separate collections are not access control.")
    if not confirm("Add this entry while preserving other Codex servers?"):
        print("Connection not added. Rerun setup when ready.")
        return
    # Re-read after approval to avoid overwriting an entry added during the prompt.
    current = json.loads(subprocess.run([codex, "mcp", "list", "--json"], capture_output=True, text=True, check=True).stdout)
    if any(entry["name"] == name for entry in current):
        raise ValueError("Codex configuration changed during setup. Rerun to inspect it.")
    subprocess.run(change, check=True, capture_output=True, text=True)
    print("Codex connection added. Restart or reload Codex to discover the server.")


def setup_project(project, provider=None):
    if not sys.stdin.isatty():
        raise ValueError("Setup requires an interactive terminal. Server startup uses the noninteractive serve command.")
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Select an existing project directory")
    settings_path = project_settings_path(project)
    existing = load_settings(settings_path) if settings_path.exists() else None
    if existing and provider is not None and provider != existing["provider"]:
        raise ValueError("This project already has a provider. Use a new collection for a model change.")
    provider = existing["provider"] if existing else provider or choose_provider()
    if not ensure_dependencies(project, provider):
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
                        return setup_project(project, choose_api())
                    if choice != "r":
                        return
    elif provider == "ollama":
        models = installed_ollama_models()
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
            if models.get(name) != existing.get("ollama_digest"):
                raise ValueError("The saved Ollama model changed. Keep its original revision or create a new collection.")
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
    if not confirm("Prepare and verify the Codex launcher (uv may download Python packages)?"):
        print("Settings saved. Codex was not changed. Rerun setup to finish the connection.")
        return
    # Populate uv's tool cache now. Later Codex starts resolve offline, without
    # waiting on package-index availability. The model/API can still use its
    # explicitly selected provider; --offline applies to uv, not the server.
    warm_command = launch_command(settings_path, provider, data.get("credential_mode"), offline=False)
    asyncio.run(verify_mcp(warm_command))
    asyncio.run(verify_mcp(command))
    print(f"Provider and MCP connection verified.\nSettings: {settings_path}\nCollection: {data['workdir']}")
    connect_codex(project, command)
