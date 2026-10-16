"""Public project settings and macOS Keychain references. Never persist API keys."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

PROVIDERS = {"fastembed", "ollama", "openai", "cohere"}
KEY_ENV = {"openai": "GRAPHRAG_OPENAI_API_KEY", "cohere": "GRAPHRAG_COHERE_API_KEY"}
FIELDS = {"schema_version", "project", "provider", "model", "dimension", "model_dir",
          "workdir", "input_dir", "credential_mode", "ollama_digest"}


def project_settings_path(project: Path) -> Path:
    root = Path(os.environ.get("PRECISO_CONFIG_DIR", "~/Library/Application Support/PRECISO")).expanduser()
    key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:20]
    return root / "projects" / key / "settings.json"


def validate_settings(data):
    if not isinstance(data, dict) or set(data) - FIELDS:
        raise ValueError("Unsupported project settings fields")
    if data.get("schema_version") != 1 or data.get("provider") not in PROVIDERS:
        raise ValueError("Unsupported project settings version or provider")
    for field in ("project", "workdir", "input_dir"):
        if not isinstance(data.get(field), str) or not Path(data[field]).is_absolute():
            raise ValueError(f"Settings require an absolute {field} path")
    if not isinstance(data.get("model"), str) or not data["model"].strip():
        raise ValueError("Missing embedding model")
    dimension = data.get("dimension")
    if type(dimension) is not int or not 0 < dimension <= 65536:
        raise ValueError("Invalid embedding dimension")
    if data.get("credential_mode") not in {None, "environment", "keychain"}:
        raise ValueError("Unsupported credential storage")
    if data["provider"] == "fastembed":
        from core.local_embeddings import MODEL
        if data["model"] != MODEL or not Path(data.get("model_dir", "")).is_absolute():
            raise ValueError("Unsupported built-in model or model directory")
    return data


def load_settings(path: Path):
    return validate_settings(json.loads(path.read_text()))


def save_settings(path: Path, data):
    from core.file_io import atomic_artifact_path
    validate_settings(data)
    with atomic_artifact_path(path) as temporary:
        temporary.chmod(0o600)
        temporary.write_text(json.dumps(data, indent=2) + "\n")


def credential_account(data):
    return data["provider"] + ":" + hashlib.sha256(data["project"].encode()).hexdigest()[:20]


def macos_keychain():
    if sys.platform != "darwin":
        raise RuntimeError("Automatic secure credential storage currently supports macOS only")
    try:
        from keyring.backends.macOS import Keyring
        return Keyring()
    except Exception:
        raise RuntimeError("macOS Keychain is unavailable. Choose environment-variable credentials.") from None


def apply_settings(data):
    """Saved identity is authoritative. Reject conflicting environment overrides."""
    from core.local_embeddings import MODEL

    provider = data["provider"]
    mapping = {"GRAPHRAG_EMBEDDING_PROVIDER": provider, "GRAPHRAG_EMBEDDING_DIM": str(data["dimension"]),
               "GRAPHRAG_MCP_WORKDIR": data["workdir"], "GRAPHRAG_INPUT_DIR": data["input_dir"],
               "GRAPHRAG_EMBEDDING_CONCURRENCY": "1", "PRECISO_REQUIRE_PROVIDER": "1"}
    model_variable = {"openai": "GRAPHRAG_OPENAI_EMBEDDING_MODEL", "cohere": "GRAPHRAG_COHERE_EMBEDDING_MODEL"}.get(provider, "GRAPHRAG_EMBEDDING_MODEL")
    mapping[model_variable] = data["model"]
    if provider == "fastembed":
        if data["model"] != MODEL:
            raise ValueError("Saved local model is unsupported")
        mapping["GRAPHRAG_LOCAL_MODEL_DIR"] = data["model_dir"]
    if provider == "ollama":
        mapping["GRAPHRAG_OLLAMA_TASK_PREFIXES"] = "v1"
        mapping["GRAPHRAG_EMBEDDING_REVISION"] = data.get("ollama_digest", "unknown") + ":prefix-v1"
    for key, value in mapping.items():
        if key in os.environ and os.environ[key] != value:
            raise ValueError(f"Environment setting {key} conflicts with saved project settings; rerun setup explicitly")
        os.environ[key] = value
    if provider in KEY_ENV:
        variable = KEY_ENV[provider]
        if data.get("credential_mode") == "keychain":
            try:
                secret = macos_keychain().get_password("preciso-graphrag", credential_account(data))
            except Exception:
                raise RuntimeError("Could not read the API key from macOS Keychain") from None
            if not secret:
                raise ValueError("No API key found in macOS Keychain; rerun setup")
            os.environ[variable] = secret
        elif not (os.getenv(variable) or os.getenv(provider.upper() + "_API_KEY")):
            raise ValueError(f"Set {variable} before starting PRECISO")
