# Guided setup for Codex

Status: version 0.3.0rc1 is published on
[PyPI](https://pypi.org/project/preciso-graphrag/0.3.0rc1/). This release candidate
targets individual macOS users with Codex CLI. Other automated client and platform
setups remain unverified.

## What the user does

From your project directory, run:

```sh
uvx --from preciso-graphrag==0.3.0rc1 preciso-graphrag setup --project /absolute/project
```

uv and Codex CLI must be installed. The setup command can resume in an isolated
uvx environment with optional provider packages after confirmation. It does not
install packages inside a running MCP server.

For a development build, use the wheel's absolute path with `--from`.
Keep that wheel available: the generated development launcher references it.
An editable source installation similarly retains its source URL. Published-package
launchers use the installed package's exact version.

1. Select local or API embeddings.
2. For local use, choose built-in Granite or a running Ollama service. Supported
   installed Ollama models are listed. If none exists, setup offers a Nomic download.
   Setup does not install Ollama. A stopped service must be started separately.
3. For built-in embeddings, review the English model name, 188.1 MiB artifact size,
   and cache directory. Confirm the download if the cached files are missing or
   corrupt. Optional Python dependencies are additional. Failed downloads offer
   retry, explicit API setup, or cancellation. Repair reuses valid artifacts.
4. For API use, select OpenAI or Cohere and a model. Confirm that the provider
   receives text and usage may incur charges. Choose macOS Keychain or environment
   credentials. Setup and server readiness checks can send the same synthetic
   sentence more than once; they do not send a document corpus during setup.
5. Confirm preparation of the Codex launcher. Setup verifies the selected provider,
   populates uv's package cache, and tests the real MCP connection online and with
   uv's offline package resolution. The built-in model uses local files only.
6. Review the proposed named Codex entry and confirm it. Setup uses the official
   `codex mcp add` command. Other entries are preserved. A conflicting entry is not
   overwritten. Repeat setup leaves an identical entry unchanged.
7. Reload Codex. Ask it to call `get_server_status` and `get_document_workflow`.
   Then give the agent access to the documents you want processed.

Codex's named entries are user-level settings and can be visible across projects.
Each entry points to a separate project collection. This is data separation, not
an access-control boundary. Do not give an agent access to unrelated collections.

## Storage

The default macOS public settings path is under
`~/Library/Application Support/PRECISO/projects/<project-path-hash>/settings.json`.
Each project has a separate graph directory and extraction input directory beside
that settings file. Model artifacts are shared under
`~/Library/Caches/PRECISO/models/granite-<revision>/`.

Use `PRECISO_CONFIG_DIR` and `PRECISO_CACHE_DIR` to select alternative roots before
setup. Public settings files have mode 0600 and are published atomically. API keys
are never written there or included in Codex command arguments. Keychain references
use a provider and project account. No plaintext credential-store fallback is used.

Environment mode accepts `GRAPHRAG_OPENAI_API_KEY` or `OPENAI_API_KEY`, and
`GRAPHRAG_COHERE_API_KEY` or `COHERE_API_KEY`. Codex must inherit the selected
environment variable. A graphical client may not inherit terminal exports; choose
Keychain when that environment cannot be provided reliably.

Saved project identity is authoritative. Conflicting provider/model/dimension or
graph-location environment settings are rejected. Existing collections never change
models automatically. New Ollama configurations apply published task prefixes and
retain the detected model digest; a changed or unavailable digest blocks startup.
Legacy manually configured Ollama collections keep their previous preprocessing.

## Server startup

The launcher uses `preciso-graphrag serve --settings /absolute/settings.json`.
It loads settings and credentials before importing runtime configuration. It never
prompts or downloads weights. uv resolves its package dependencies offline from the
cache prepared during setup. Clear that uv cache only when you can rerun setup.

The built-in provider verifies all pinned model hashes before opening stores. It
uses FastEmbed 0.9.0, a single ONNX CPU inference thread, batch size one, and one
embedding request at a time. CPU work is offloaded from the MCP event loop. Cancelled
work is drained before another embedding request can start. The runtime retains
the existing vector shape, finite-value, and nonzero-vector validation.

Inputs exceeding 8,192 Granite tokenizer tokens, including special tokens, are
rejected. The agent must produce smaller passages or descriptions and shorten
oversized queries. No text is silently truncated. Queries are checked before
keyword/cache work. The existing artifact transaction restores a failed ingestion,
including failure after earlier graph or vector updates. Normal evidence chunks
remain focused; the larger window is not a target chunk length.

The model fingerprint includes the pinned revision, artifact hashes, and explicit
preprocessing version. Incompatible populated indexes fail closed. Missing weights,
bad credentials, and unavailable providers do not cause a provider substitution.
The CLI-created runtime uses an explicit whitespace context token counter offline;
the Granite tokenizer still enforces embedding input limits independently. Existing
manual server launches retain their context-tokenizer behavior.

## Recovery

- Download refused: no new project settings are written.
- Download interrupted: rerun setup and approve retry. Valid model files are reused.
- Corrupt model: rerun setup and approve repair. Only invalid/missing files download.
- Provider unavailable: restore the selected service/credentials and rerun setup.
- Changed model: keep the original model or explicitly create a new collection.
- Codex entry conflict: inspect it in Codex. Setup preserves it and reports the conflict.
- Setup stopped after saving settings: rerun for the same project. No duplicate entry
  is added. A failed verification is not reported as a successful connection.

Setup does not provide automatic model migration, a raw PDF parser, a file watcher,
or team authorization. Real API provider calls and real Keychain writes require
credentials and were not executed by the offline test suite. Keychain is currently
an optional setup dependency. Windows/Linux automated setup is not verified.

## Verification commands

```sh
python -m pytest -q
python -m ruff check src tests scripts
python -m scripts.smoke_codex_setup
python -m scripts.smoke_local_setup --python /path/to/installed/python \
  --model-dir /path/to/verified/granite-model
```

The Codex smoke isolates configuration in a temporary Codex home and preserves an
unrelated entry. The local-provider smoke requires cached weights and uses only a
temporary graph. It verifies restart, retrieval, overlength rejection, rollback,
and recovery. See [model selection](embedding-model-selection.md) for resource and
retrieval measurements; setup does not establish production retrieval quality.

Official integration reference: [Codex MCP configuration](https://developers.openai.com/codex/mcp).
