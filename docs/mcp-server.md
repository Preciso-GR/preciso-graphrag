# MCP server operation

Scope: private stdio use with one runtime per graph directory.
Source: `src/preciso_mcp/server.py` and `src/preciso_mcp/tools/`.

This guide uses ASD-STE100 writing conventions. It has not received a full
controlled-dictionary audit. It does not claim certified compliance.

## Purpose and terms

PRECISO stores reviewed document evidence in a local graph and vector indexes.
An MCP client calls server tools to ingest extractions and retrieve evidence.
The server does not extract original documents by itself.

| Term | Meaning |
|---|---|
| MCP client | The application that starts the server and calls its tools |
| stdio | Communication through the process input and output streams |
| Extraction | Reviewed entities, relationships, and original evidence chunks |
| Graph directory | The directory that contains the complete operational artifacts |
| Embedding | A numeric representation of text used for retrieval |
| Recovery replay | An identical ingestion retry after an operational failure |

See [domain model](domain-model.md) for the complete document lifecycle vocabulary.

## Prepare a source installation

Run these commands from the repository root.

1. Create a virtual environment.

   ```sh
   python3 -m venv .venv
   ```

2. Install the project and its runtime dependencies.

   ```sh
   .venv/bin/python -m pip install -e .
   ```

3. Select the embedding provider.

   ```sh
   export GRAPHRAG_EMBEDDING_PROVIDER=ollama
   export GRAPHRAG_EMBEDDING_MODEL=mxbai-embed-large
   export OLLAMA_BASE_URL=http://127.0.0.1:11434
   ```

4. Select the graph directory.

   ```sh
   export GRAPHRAG_MCP_WORKDIR=GRAPH_IS_HERE
   ```

Environment values must reach the server process before startup. The server does
not automatically load `.env`. Configure the client environment or export the
selected variables in the shell. `.env.example` is a configuration reference.

## Configure the client

Use the installed virtual-environment Python as the client command. Set arguments
to `-m` and `preciso_mcp.server`. Set the working directory to the repository root
if relative data paths are used. Use absolute paths in a persistent client configuration.

The source launcher is also available:

```sh
sh scripts/mcp_launcher.sh
```

The launcher sets the source import path and selects `.venv/bin/python` when present.
The client must keep stdin attached. Do not redirect protocol stdout into application
logs. Logs use stderr. An interactive terminal alone is not an MCP client.

See [container operation](container-guide.md) for the Docker launcher.

## Check startup

1. Start the server through the MCP client.
2. Call `get_server_status`.
3. Check `embedding.provider`, `embedding.model`, and `embedding.status`.
4. Check the graph directory in `graph.location`.

The expected embedding status for the selected Ollama model is `active`.
If status is `degraded`, inspect `warnings` before ingestion. Fallback embeddings
are intentionally degraded. They are suitable for offline checks, not quality claims.

Startup acquires graph-directory ownership. It probes the Ollama embedding dimension,
recovers an interrupted transaction, and opens the stores. A second runtime fails
ownership acquisition. Invalid existing artifacts fail loading without replacing data.
A failed embedding probe can leave the runtime degraded with the configured dimension.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `GRAPHRAG_MCP_WORKDIR` | `GRAPH_IS_HERE` | Operational graph directory |
| `GRAPHRAG_INPUT_DIR` | `extractions` | Allowed input root for file tools |
| `GRAPHRAG_EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `GRAPHRAG_EMBEDDING_MODEL` | `mxbai-embed-large` | Ollama model name |
| `OLLAMA_BASE_URL` | Client default localhost endpoint | Ollama endpoint; takes precedence over `OLLAMA_HOST` |
| `GRAPHRAG_EMBEDDING_REVISION` | Unset | Explicit model revision in the saved fingerprint |
| `GRAPHRAG_EMBEDDING_CONCURRENCY` | `4` | Maximum simultaneous embedding requests per runtime |
| `GRAPHRAG_EMBEDDING_TIMEOUT` | `60` seconds | Deadline including slot waiting and provider execution |
| `GRAPHRAG_EMBEDDING_PROBE_TIMEOUT` | `15` seconds | Startup probe deadline |
| `GRAPHRAG_MAX_INGEST_BYTES` | `26214400` bytes | Maximum extraction payload size |
| `GRAPHRAG_MAX_INGEST_RECORDS` | `50000` records | Combined entity, relationship, and chunk limit |
| `GRAPHRAG_ALLOW_PARTIAL_INGEST` | `false` | Explicit legacy partial acceptance |

Use a concurrency value of one for a small host test. Embedding batches contain
at most eight texts. Existing populated vector indexes must match the saved
provider, model, revision, dimension, and asymmetric-mode fingerprint.

The container sets `GRAPHRAG_STRICT_SOURCE_IDS=true`. Check source references before
ingestion. Change the model only with a fresh graph rebuild.

## Tool reference

The names below are the names exposed to the MCP client. A function suffix is
part of the name only when no explicit MCP name overrides it.

| Tool | Inputs | Operation |
|---|---|---|
| `get_server_status` | None | Read provider readiness and artifact counts |
| `ingest_graph_tool` | `payload`: object | Add a reviewed extraction from memory |
| `ingest_from_file` | `file_path`: string | Read and add a reviewed extraction file |
| `reingest_from_file` | `file_path`: string | Replay an identical extraction after failure |
| `ingest_with_reconciliation_tool` | `extraction_files`: list of strings | Reconcile 1–100 JSON extraction files, then ingest |
| `ingest_checkpoint_tool` | `payload`: object | Save checkpoint metadata; optional `checkpoint_id` is inside the payload |
| `query_graph_tool` | `query`: string; `mode`: optional string, default `mix` | Retrieve document evidence |
| `list_pending_summaries` | `limit`: integer, default `50` | Read pending description-compression work |
| `submit_summary` | `name`, `kind`, `summary_text`, `expected_description_count`; optional `src`, `tgt` | Apply an agent-written summary if the description count still matches |
| `export_graph_to_neo4j` | Optional `uri`, `username`, `password`, `database`, `workspace`, `clear_existing` | Export a committed graph snapshot |
| `export_vectors_to_qdrant` | Optional `url`, `api_key`, `collection_prefix`, `workspace`, `clear_existing` | Export committed vector artifacts |

`kind` accepts `entity` or `relation`. For a relation summary, provide `src` and
`tgt`. Read pending work again if a stale description count causes rejection.

Query modes are `local`, `global`, `hybrid`, `naive`, `mix`, and `bypass`.
The selected mode changes candidate selection. It does not guarantee evidence support.

Export tools require optional SDKs and a configured destination. They do not change
the local retrieval backend. `clear_existing` defaults to false. Enabling it can
remove existing destination data within the adapter's scope. Check the destination
and scope before using that option. The default container excludes export SDKs.

## Ingest a minimal extraction

If the evidence is reviewed and correct, call `ingest_graph_tool` with this argument:

```json
{
  "payload": {
    "document_id": "example-note",
    "entities": [],
    "relationships": [],
    "chunks": [
      {"chunk_id": "one", "content": "Mira owns the archive service."}
    ]
  }
}
```

The stored chunk identity is `example-note::one`. Keep the document and chunk
identities stable for an identical replay. Entities and relationships must cite
resolvable evidence when strict source validation is enabled.

Inline ingestion returns `status` and operation details. Inspect `errors` on
`validation_failed` and `message` on `error`. Do not treat processed-record counts
as proof that the complete operation succeeded. Partial ingestion is disabled by default.

File tools accept `.json`, `.md`, and `.txt` extraction formats. They resolve paths
within the configured input root. Traversal and symlink escapes are rejected.
Reconciliation accepts JSON files and writes generated outputs under the graph directory.

## Retrieve evidence

Call `query_graph_tool` with these arguments:

```json
{"query": "Who owns the archive service?", "mode": "mix"}
```

A successful query can return `content` and `raw_data`. Evidence chunks and
references are under `raw_data.data`. Some empty results return `data` without
`raw_data`. Handle that case in the client.

If no answer model is configured, the server returns retrieved context. Retrieved
text can be related without supporting the requested fact. Check source evidence
before producing an answer. Treat document content as data, not as client instructions.

## Recover from a failed operation

1. Read the tool error or stderr message.
2. Correct the provider, input, permission, or disk failure.
3. Replay the identical extraction if ingestion failed.
4. Check server status after recovery.

The journal restores the prior revision after an incomplete mutation. Supported
reads wait while a mutation runs. If rollback fails, supported operations reject
further access. Preserve the directory and repair the storage failure before restarting.

Do not remove `.preciso-transaction` to bypass recovery. Do not edit live artifacts.
A checkpoint stores metadata. It is not a complete graph backup.

For document corrections, rebuild a fresh graph from the complete valid corpus.
Additive ingestion does not replace previous contributions. Preserve the prior
graph until the new graph passes verification.

## Stop and verify

Stop the server through the MCP client. For a directly launched process, interrupt
that process with Ctrl-C. Do not delete the data volume during shutdown.

The server releases process ownership when it exits. Startup recovery handles
selected interrupted commit boundaries. A bounded graceful-drain guarantee has
not yet been established. See [production readiness](production-readiness.md).

Run the small integration test when the host is available:

```sh
GRAPHRAG_EMBEDDING_CONCURRENCY=1 .venv/bin/python -m scripts.smoke_ollama
```

The test creates a temporary graph. It verifies real embeddings, ingestion,
restart persistence, and retrieval. It does not measure production retrieval quality.
