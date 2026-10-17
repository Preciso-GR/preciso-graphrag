# Manual source-checkout connection

Codex users should use [guided setup](../../docs/simple-setup.md). It registers
the server with `codex mcp add`; it does not read this JSON example.

`claude-code.source.json` shows the repository launcher for clients that accept
the `mcpServers` JSON format. It is not a universal MCP activation file.

For Claude Code, copy it to `.mcp.json` in the checkout root, replace the launcher
argument with the absolute path to `scripts/mcp_launcher.sh`, and complete the
client's project-server approval. Install the project in `.venv` first and configure
the embedding provider as described in [manual setup](../../docs/getting-started.md).
The launcher opens the checkout's graph, not a guided-setup project collection.

Other clients can use the same command and arguments in their own configuration
format. Do not copy machine paths, credentials, or generated client settings into
Git. The Python distribution does not include this example.
