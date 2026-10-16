"""Noninteractive server entry point. Interactive onboarding is a separate command."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import runpy


async def probe_provider():
    # User settings must be applied before importing config's environment defaults.
    import numpy as np
    from config import build_default_embedding_func
    embedding = build_default_embedding_func(probe=False)
    if embedding.provider == "fastembed":
        await embedding.func.initialize()
    # Probe the raw provider once to learn its actual dimension. No corpus is sent.
    vectors = np.asarray(await embedding.func(["PRECISO embedding connection check."], context="document"))
    if vectors.ndim != 2 or vectors.shape[0] != 1 or not vectors.shape[1] or not np.isfinite(vectors).all() or not np.linalg.norm(vectors):
        raise ValueError("Provider returned invalid embedding vectors")
    return {"status": "success", "dimension": int(vectors.shape[1])}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="preciso-graphrag")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="Choose embeddings and connect a project to Codex")
    setup.add_argument("--project", type=Path, default=Path.cwd())
    setup.add_argument("--provider", choices=["fastembed", "ollama", "openai", "cohere"])
    for name in ("serve", "check"):
        command = commands.add_parser(name)
        command.add_argument("--settings", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            from preciso_mcp.setup_cli import setup_project
            return setup_project(args.project, args.provider)
        from preciso_mcp.user_settings import apply_settings, load_settings
        data = load_settings(args.settings)
        apply_settings(data)
        if data["provider"] == "ollama":
            from preciso_mcp.setup_cli import installed_ollama_models
            current = installed_ollama_models()
            if current.get(data["model"]) != data.get("ollama_digest"):
                raise ValueError("The selected Ollama model is unavailable or changed; rerun setup. Existing indexes are preserved.")
        if args.command == "check":
            print(json.dumps(asyncio.run(probe_provider())))
        else:
            os.environ.setdefault("GRAPHRAG_DISABLE_TIKTOKEN", "1")
            runpy.run_module("preciso_mcp.server", run_name="__main__")
    except (Exception, KeyboardInterrupt) as exc:
        # Provider exceptions can include request details. Never print secrets.
        if args.command == "setup" or isinstance(exc, (ValueError, FileNotFoundError)):
            message = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else "Setup did not complete. Retry or choose another provider."
        else:
            message = "Provider or configuration unavailable. Run setup/check to recover. No provider was substituted."
        parser.exit(1, message + "\n")


if __name__ == "__main__":
    main()
