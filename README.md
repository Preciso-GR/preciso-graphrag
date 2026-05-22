# GraphRAG MCP

This project turns extracted document knowledge into a reusable graph artifact.

The key idea is:

`documents -> extraction JSON -> knowledge graph -> downstream reuse`

MCP is only one interface into that pipeline. The main output is the graph itself, so it can be exported, stored, and reused by:

- Copilot or other MCP clients
- a simple LLM <-> GraphRAG app
- internal company search and analysis workflows
- graph visualization tools
- future graph databases or enterprise pipelines

## What This Repo Is

This repo is an ingestion and retrieval backend for GraphRAG-style workflows.

It accepts structured extraction output like:

- entities
- relationships
- source chunks

and persists that into a local graph + retrieval artifacts on disk.

The graph is not tied to a single chat session. Once created, it is stored and can be reused later.

## Core Product Intention

The intended workflow is:

1. An agent reads a source document and produces extraction JSON.
2. This repo ingests that extraction into a canonical graph artifact.
3. The graph is exported to disk.
4. Other systems use that graph for retrieval, question answering, analytics, or enterprise workflows.

So the deliverable is not just "an MCP server."

The real deliverable is:

- a generated knowledge graph
- graph metadata and chunk references
- retrieval artifacts that can power later tasks

## What Gets Exported

After ingestion, this repo persists graph artifacts inside `GRAPH_IS_HERE/`.

Important files:

- `GRAPH_IS_HERE/graph_graph.graphml`
- `GRAPH_IS_HERE/kv_store_text_chunks.json`
- `GRAPH_IS_HERE/kv_store_entity_chunks.json`
- `GRAPH_IS_HERE/kv_store_relation_chunks.json`
- `GRAPH_IS_HERE/vdb_entities.json`
- `GRAPH_IS_HERE/vdb_relationships.json`
- `GRAPH_IS_HERE/vdb_chunks.json`

What they mean:

- `graph_graph.graphml`: the main exported graph structure
- `kv_store_*.json`: persisted chunk and metadata stores
- `vdb_*.json`: vector retrieval indexes used during query

The most portable artifact today is `graph_graph.graphml`, because it can be reused by other graph-oriented tools and workflows.

## High-Level Flow

1. A source document is processed by an agent or extraction step.
2. The agent writes extraction output to `extractions/{filename}_extracted.json`.
3. Ingestion reads that file and merges it into the stored graph.
4. The graph and retrieval indexes are persisted to disk.
5. Query tools read from those saved artifacts later.

## Example Workflow

### 1. Extraction

An agent produces a file like:

`extractions/apple_10k_excerpt_extracted.json`

That file should contain:

- `document_id`
- `entities`
- `relationships`
- `chunks`

### 2. Ingestion

The ingestion layer validates the extraction and builds the graph.

This can happen through:

- MCP tool: `ingest_from_file`
- manual script: `python3 ingest_manual.py ...`

### 3. Persistence

The graph is written to disk automatically.

This means the graph survives:

- Copilot restarts
- MCP server restarts
- later query sessions

### 4. Query / Reuse

Once persisted, the graph can be used for:

- MCP-based tool calls
- local manual retrieval tests
- downstream LLM applications
- export into company-specific workflows

## MCP's Role

MCP is an access layer, not the entire system.

When configured correctly, Copilot can start this repo's MCP server and call tools such as:

- `ingest_graph_tool`
- `ingest_from_file`
- `reingest_from_file`
- `ingest_checkpoint_tool`
- `query_graph_tool`

Those tools are defined in [mcp/server.py](./mcp/server.py).

So the relationship is:

- the graph pipeline creates and stores the artifact
- MCP exposes that pipeline to Copilot and other compatible clients

## Repository Structure

- [mcp/server.py](./mcp/server.py): MCP server and tool definitions
- [ingest_manual.py](./ingest_manual.py): manual ingestion test without MCP
- [query_manual.py](./query_manual.py): manual query test without MCP
- [config.py](./config.py): global configuration
- `extractions/`: extracted JSON artifacts created upstream
- `GRAPH_IS_HERE/`: persisted graph + retrieval artifacts

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Manual Testing Without MCP

This is the simplest way to validate the core product behavior before involving Copilot.

### Ingest an Extraction File

```bash
python3 ingest_manual.py extractions/apple_10k_excerpt_extracted.json
```

Expected result:

- extraction is read successfully
- graph files are written into `GRAPH_IS_HERE/`

### Query the Persisted Graph

```bash
python3 query_manual.py "What is Tim Cook's role?" mix
```

Expected result:

- query runs against the saved graph
- relevant entities, relationships, chunks, and references are returned

## MCP Setup for Copilot CLI

GitHub Copilot CLI no longer relies on `.vscode/mcp.json` alone for MCP startup.
Use a workspace `.mcp.json` or a valid user config at `~/.copilot/mcp-config.json`.

This repo includes a workspace-level `.mcp.json`.

Minimal example:

```json
{
  "mcpServers": {
    "graphrag-mcp": {
      "type": "stdio",
      "command": "/Users/sanjayelango/Desktop/graphrag-mcp/.venv/bin/python",
      "args": ["mcp/server.py"],
      "cwd": "/Users/sanjayelango/Desktop/graphrag-mcp",
      "tools": ["*"]
    }
  }
}
```

If Copilot shows:

`Invalid MCP server configuration: mcpServers: Required`

then the file `~/.copilot/mcp-config.json` is malformed and must be fixed before Copilot can start MCP servers.

## How MCP Startup Works

When you launch Copilot CLI inside this project:

1. Copilot reads MCP config.
2. It finds the `graphrag-mcp` server definition.
3. It starts the Python process for `mcp/server.py`.
4. It discovers the tools registered by the server.
5. It can then call those tools during chat.

If config is invalid, the server never starts.

## Using the MCP Server from Copilot

After config is fixed, you can verify server visibility with:

```bash
copilot mcp list
copilot mcp get graphrag-mcp
```

Inside Copilot CLI, you can inspect MCP state with:

```text
/mcp show
/mcp show graphrag-mcp
```

Example tool requests:

```text
Use the graphrag-mcp server to run ingest_from_file on extractions/apple_10k_excerpt_extracted.json
Use the graphrag-mcp server to run query_graph_tool with query "What is Tim Cook's role?"
```

## Re-Running Ingestion

If extraction has already succeeded and only ingestion must be retried:

```text
reingest_from_file("extractions/{filename}_extracted.json")
```

This avoids re-running the upstream extraction step.

## Current Limitations

This repo already proves the core artifact flow, but it is not fully productionized yet.

### 1. Export is implicit, not a first-class feature

The graph is persisted automatically, but there is no dedicated `export_graph` MCP tool or export command yet.

### 2. Fallback embeddings are being used

The current server and manual scripts use a fallback embedding function with dummy vectors.

That means:

- graph persistence works
- graph structure is real
- retrieval plumbing works
- semantic vector quality is not production-ready yet

### 3. Single local working directory

The graph is stored in `GRAPH_IS_HERE/` today. There is not yet a polished multi-project or multi-tenant export strategy.

### 4. Limited artifact packaging

Artifacts exist on disk, but there is no packaged export flow yet such as:

- zip export
- versioned release bundle
- import/export manifest
- handoff format for enterprise systems

### 5. No external graph database integration yet

The current implementation writes `GraphML` and local JSON stores. It does not yet push to systems like Neo4j, Neptune, or RDF stores.

## What Still Needs To Be Done

To align the repo with the intended company-facing workflow, these are the next important steps:

1. Add a dedicated export workflow.
   This should explicitly export the graph, metadata, and retrieval artifacts as a reusable bundle.

2. Replace fallback embeddings with a real embedding model.
   Without this, downstream semantic retrieval quality will remain weak.

3. Define a canonical artifact contract.
   Decide what exactly a company receives: `GraphML`, chunk stores, vector indexes, manifest, version, schema.

4. Add import support for downstream systems.
   Make it easy for a simple LLM app or enterprise workflow to load a previously generated graph artifact.

5. Add graph versioning and lineage.
   Track which source files, extraction runs, and model settings produced each exported graph.

6. Add better query and validation evaluation.
   We should measure graph quality, retrieval quality, and failure cases more systematically.

7. Support configurable storage destinations.
   Instead of always using `GRAPH_IS_HERE/`, allow clean per-customer or per-project output locations.

8. Add enterprise-friendly documentation.
   Document the schema, artifact meanings, and how downstream teams consume the exported graph safely.

## Recommended Product Positioning

If you want the README to reflect the real vision, the clean positioning is:

This project is an agent-assisted knowledge graph generation and export pipeline, with MCP as one runtime interface and GraphRAG reuse as the broader product outcome.
