"""Run the MCP integration check with local Ollama and a disposable graph.

This test verifies real embedding calls and persistence. It is not a retrieval
quality benchmark. Use --dry-run to inspect configuration without starting Ollama.
"""

import argparse
import asyncio
import json
import math
import os
import sys
import tempfile

from scripts.smoke_mcp import smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="mxbai-embed-large")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be finite and positive")

    command = [sys.executable, "-m", "preciso_mcp.server"]
    settings = {
        "GRAPHRAG_EMBEDDING_PROVIDER": "ollama",
        "GRAPHRAG_EMBEDDING_MODEL": args.model,
        "OLLAMA_BASE_URL": args.host,
        "GRAPHRAG_EMBEDDING_TIMEOUT": str(args.timeout),
        "GRAPHRAG_EMBEDDING_PROBE_TIMEOUT": str(args.timeout),
        "GRAPHRAG_STRICT_SOURCE_IDS": "true",
    }
    if args.dry_run:
        print(json.dumps({"command": command, "settings": settings,
                          "graph": "new temporary directory; removed after test"}, indent=2))
        return

    # A cold model load can use the full provider deadline. Allow additional
    # time for MCP startup, filesystem work, and protocol response delivery.
    with tempfile.TemporaryDirectory(prefix="preciso-ollama-smoke-") as graph:
        env = dict(os.environ)
        env.update(settings, GRAPHRAG_MCP_WORKDIR=graph)
        embedding = asyncio.run(smoke(
            command, timeout=args.timeout + 30, expected_provider="ollama",
            expected_model=args.model, env=env,
        ))
        print(json.dumps({"embedding": embedding, "result": "passed"}, indent=2))


if __name__ == "__main__":
    main()
