"""Offline boundaries for local inference and project onboarding."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

from core import local_embeddings as local
from preciso_mcp import setup_cli as setup
from preciso_mcp import user_settings as settings


def project_data(tmp_path, provider="fastembed"):
    return {"schema_version": 1, "project": str(tmp_path), "provider": provider,
            "model": local.MODEL if provider == "fastembed" else "test-model", "dimension": 384,
            "model_dir": str(tmp_path / "model"), "workdir": str(tmp_path / "graph"),
            "input_dir": str(tmp_path / "inputs")}


def test_settings_reject_secret_fields_and_preserve_previous_file(tmp_path):
    path = tmp_path / "settings.json"
    data = project_data(tmp_path)
    settings.save_settings(path, data)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="fields"):
        settings.save_settings(path, {**data, "api_key": "do-not-persist"})
    assert path.read_bytes() == original
    assert path.stat().st_mode & 0o777 == 0o600


def test_project_storage_is_stable_and_separate(tmp_path, monkeypatch):
    monkeypatch.setenv("PRECISO_CONFIG_DIR", str(tmp_path / "settings"))
    assert settings.project_settings_path(tmp_path / "one") == settings.project_settings_path(tmp_path / "one")
    assert settings.project_settings_path(tmp_path / "one") != settings.project_settings_path(tmp_path / "two")


def test_saved_provider_does_not_silently_follow_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPHRAG_EMBEDDING_PROVIDER", "ollama")
    with pytest.raises(ValueError, match="conflicts"):
        settings.apply_settings(project_data(tmp_path))


def test_keychain_key_not_in_saved_settings(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(settings.os, "environ", dict(os.environ))
    data = {**project_data(tmp_path, "openai"), "credential_mode": "keychain"}
    monkeypatch.setattr(settings, "macos_keychain", lambda: SimpleNamespace(get_password=lambda *a: "private-key"))
    for key in ["GRAPHRAG_EMBEDDING_PROVIDER", "GRAPHRAG_EMBEDDING_DIM", "GRAPHRAG_MCP_WORKDIR", "GRAPHRAG_INPUT_DIR",
                "GRAPHRAG_EMBEDDING_CONCURRENCY", "PRECISO_REQUIRE_PROVIDER", "GRAPHRAG_OPENAI_EMBEDDING_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GRAPHRAG_OPENAI_API_KEY", "old-value")
    settings.apply_settings(data)
    assert os.environ["GRAPHRAG_OPENAI_API_KEY"] == "private-key"
    path = tmp_path / "settings.json"
    settings.save_settings(path, data)
    assert "private-key" not in path.read_text()


def test_missing_model_never_downloads_implicitly(tmp_path):
    with pytest.raises(ValueError, match="incomplete"):
        local.verify_model(tmp_path)


def test_altered_artifact_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "FILES", {"model.onnx": "not-the-real-hash"})
    (tmp_path / "model.onnx").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity"):
        local.verify_model(tmp_path)


async def test_batch_length_checked_before_any_inference(tmp_path):
    provider = local.GraniteEmbedding(tmp_path)
    called = []
    provider.tokenizer = SimpleNamespace(encode=lambda text: SimpleNamespace(ids=range(len(text))))
    provider.model = SimpleNamespace(embed=lambda *a, **k: called.append(a))
    with pytest.raises(ValueError, match="No text was truncated"):
        await provider(["short", "x" * (local.TOKEN_LIMIT + 1)])
    assert called == []


async def test_cancellation_does_not_allow_overlapping_cpu_work(tmp_path):
    provider = local.GraniteEmbedding(tmp_path)
    provider.model = object()
    started, release = threading.Event(), threading.Event()
    calls = []

    def embed(texts):
        calls.append(texts)
        if len(calls) == 1:
            started.set()
            release.wait(2)
        return [[1.0]]

    provider._embed = embed
    first = asyncio.create_task(provider(["first"]))
    while not started.is_set():
        await asyncio.sleep(0)
    first.cancel()
    second = asyncio.create_task(provider(["second"]))
    await asyncio.sleep(0.01)
    assert len(calls) == 1
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    await second
    assert len(calls) == 2


def test_launcher_retains_optional_packages_and_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(setup, "package_source", lambda: "preciso-graphrag==test")
    local_command = setup.launch_command(tmp_path / "settings.json", "fastembed")
    assert "fastembed==0.9.0" in local_command
    assert "--offline" in local_command
    cloud = setup.launch_command(tmp_path / "settings.json", "openai", "keychain")
    assert "keyring>=25,<26" in cloud and "openai>=1.0.0" in cloud
    assert not any("API_KEY=" in arg for arg in cloud)


def test_model_repair_redownloads_only_missing_or_corrupt_files(tmp_path, monkeypatch):
    import hashlib
    import sys
    good = b"reviewed-model"
    hashes = {name: hashlib.sha256(good).hexdigest() for name in ["good", "corrupt", "missing"]}
    monkeypatch.setattr(local, "FILES", hashes)
    (tmp_path / "good").write_bytes(good)
    (tmp_path / "corrupt").write_bytes(b"bad")
    requests = []
    def download(repository, filename, **kwargs):
        requests.append((filename, kwargs["force_download"]))
        (tmp_path / filename).write_bytes(good)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(hf_hub_download=download))
    local.download_model(tmp_path)
    assert requests == [("corrupt", True), ("missing", False)]


def test_codex_existing_different_entry_not_overwritten(tmp_path, monkeypatch):
    import hashlib
    slug = tmp_path.name.lower()[:24]
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    name = "preciso-" + slug + "-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8]
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps([{"name": name, "transport": {"command": "other", "args": []}}]))

    monkeypatch.setattr(setup.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(setup.subprocess, "run", run)
    with pytest.raises(ValueError, match="not overwritten"):
        setup.connect_codex(tmp_path, ["uvx", "serve"])
    assert len(calls) == 1


def test_setup_refuses_noninteractive_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    with pytest.raises(ValueError, match="interactive terminal"):
        setup.setup_project(tmp_path)


def test_model_download_refusal_keeps_settings_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("PRECISO_CONFIG_DIR", str(tmp_path / "configuration"))
    monkeypatch.setenv("PRECISO_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup, "ensure_dependencies", lambda *a: True)
    monkeypatch.setattr(setup, "confirm", lambda *a: False)
    setup.setup_project(tmp_path, "fastembed", "codex")
    assert not settings.project_settings_path(tmp_path).exists()
    assert not (tmp_path / "cache").exists()


def test_probe_failure_does_not_write_keychain_or_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PRECISO_CONFIG_DIR", str(tmp_path / "configuration"))
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(setup, "ensure_dependencies", lambda *a: True)
    written = []
    def configure(data):
        data.update(model="test-model", credential_mode="keychain")
        return "secret", SimpleNamespace(set_password=lambda *a: written.append(a))
    monkeypatch.setattr(setup, "configure_api", configure)
    monkeypatch.setattr(setup, "confirm", lambda *a: True)
    monkeypatch.setattr(setup, "probe_settings", lambda *a: (_ for _ in ()).throw(ValueError("failed")))
    with pytest.raises(ValueError, match="failed"):
        setup.setup_project(tmp_path, "openai", "codex")
    assert written == []
    assert not settings.project_settings_path(tmp_path).exists()


async def test_query_rejects_overlength_before_keywords_or_vector_search(storage_stack):
    from core.query import kg_query
    from core.storage.base import QueryParam
    stores, config, directory = storage_stack
    provider = local.GraniteEmbedding(directory)
    provider.model = object()
    provider.tokenizer = SimpleNamespace(encode=lambda text: SimpleNamespace(ids=range(len(text))))
    config["embedding_func"].func = provider
    with pytest.raises(ValueError, match="No text was truncated"):
        await kg_query(query="x" * (local.TOKEN_LIMIT + 1), knowledge_graph_inst=stores["graph"],
                       entities_vdb=stores["entities_vdb"], relationships_vdb=stores["relationships_vdb"],
                       text_chunks_db=stores["text_chunks"], chunks_vdb=stores["chunks_vdb"],
                       query_param=QueryParam(mode="mix"), global_config=config)


async def test_failed_local_startup_does_not_open_stores(monkeypatch):
    from preciso_mcp import server
    async def initialize():
        raise ValueError("model missing")
    monkeypatch.setattr(server, "storage_instances", {})
    monkeypatch.setattr(server, "DEFAULT_EMBEDDING_PROVIDER", "fastembed")
    monkeypatch.setattr(server, "build_default_embedding_func", lambda **k: SimpleNamespace(func=SimpleNamespace(initialize=initialize)))
    monkeypatch.setattr(server, "build_storage_instances", lambda *a: pytest.fail("Opened storage before provider readiness"))
    with pytest.raises(ValueError, match="model missing"):
        await server.initialize_runtime()


def test_codex_change_during_preview_is_not_overwritten(tmp_path, monkeypatch):
    import hashlib
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", tmp_path.name.lower())[:24]
    name = "preciso-" + slug + "-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8]
    outputs = iter([[], [{"name": name}]])
    monkeypatch.setattr(setup.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(next(outputs))))
    monkeypatch.setattr(setup, "confirm", lambda *a: True)
    with pytest.raises(ValueError, match="changed during"):
        setup.connect_codex(tmp_path, ["uvx", "serve"])
