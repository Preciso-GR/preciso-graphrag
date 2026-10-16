# Changelog

## 0.3.0rc1 — unreleased

- Add optional built-in Granite Small English R2 embeddings with pinned artifact
  verification, one CPU thread, asynchronous offloading, and strict input limits.
- Add guided per-project setup, provider checks, saved settings, and noninteractive
  server launch through the `preciso-graphrag` command.
- Detect supported Ollama models and retain their digest and task-prefix identity.
- Add optional macOS Keychain credentials and environment-variable alternatives.
- Preview Codex registration and preserve unrelated or conflicting entries.
- Prepare uv's package cache during setup and verify offline dependency resolution
  before adding the Codex entry.

This version has not been published to PyPI or GitHub Releases. Existing collections
retain their configured model. Built-in model files download only after confirmation.

## 0.2.0rc1 — 2026-10-16

First published GitHub prerelease of the core-only GraphRAG MCP server.

- Track document contributions and support revision-checked document replacement
  and deletion.
- Support persistent graph isolation, removal, labels, merges, and disconnections.
- Preserve ingestion results across MCP entry points.
- Centralize ingestion coordination and agent summary maintenance in core modules.
- Reject stale summary submissions and restore graph, vector, and queue state
  when a summary update fails.
- Provide a minimal multi-stage Docker build, offline backup tools, and operating
  documentation.

Verification: 252 tests passed locally and in the locked Linux arm64 container
before packaging. MCP document and summary workflows passed with offline
embeddings. GitHub CI for the preceding commit failed before starting any jobs;
hosted CI success has not been established.

This is a release candidate for private, single-collection MCP use. Shared-service
access control, representative retrieval evaluation, resource budgets, and wider
platform verification remain open. See [production readiness](docs/production-readiness.md).

Back up existing graph data before upgrading. Ledger-enabled workspaces must not
be written by older runtimes. Legacy graphs need a fresh rebuild from complete,
reviewed extractions before destructive document maintenance.
