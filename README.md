<div align="center">
  <h1>Preciso GraphRAG</h1>
  <p><strong>Precise graph connections from your documents.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Codex-Agent-111111?style=for-the-badge&logo=openai&logoColor=white" alt="Codex agent support" />
    <img src="https://img.shields.io/badge/Claude%20Code-Agent-C8102E?style=for-the-badge" alt="Claude Code agent support" />
    <img src="https://img.shields.io/badge/OpenCode-Agent-FFFFFF?style=for-the-badge&logoColor=C8102E&color=C8102E" alt="OpenCode agent support" />
    <img src="https://img.shields.io/badge/Copilot-Agent-7F1D1D?style=for-the-badge&logo=github&logoColor=white" alt="Copilot agent support" />
  </p>
  <p>
    <img src="https://img.shields.io/badge/Workflow-Agent--First-FFFFFF?style=for-the-badge&logoColor=C8102E&color=C8102E" alt="Agent-first workflow" />
    <img src="https://img.shields.io/badge/Output-Local%20Graph%20Artifact-C8102E?style=for-the-badge" alt="Local graph artifact" />
    <img src="https://img.shields.io/badge/Neo4j-Export%20Target-8A2BE2?style=for-the-badge" alt="Neo4j export target" />
    <img src="https://img.shields.io/badge/Qdrant-Vector%20Export-DC2626?style=for-the-badge" alt="Qdrant vector export" />
  </p>
</div>

Preciso GraphRAG is an agent-driven workflow for turning raw documents into a reusable knowledge graph artifact.

It is designed to feel sharp, direct, and dependable: drop documents in, let the agent choose the right skill, then persist a graph artifact locally in a red-and-white, local-first workflow.

The intended flow is:

`raw files -> agent chooses skill -> extraction JSON -> MCP ingestion -> persistent graph artifact`

The end user does not start with extraction JSON. The end user starts by dropping source material into `to_be_extracted/`, then an agent such as Codex or Claude Code performs extraction using the skills in this repo and calls the ingestion tools.

MCP is one runtime interface inside that workflow. The real product output is the persisted graph artifact.

## Red-White Workflow

Preciso GraphRAG is built around a simple local contract:

- red side: raw source documents arrive in `to_be_extracted/`
- white side: the agent extracts structured knowledge into `extractions/`
- final pass: MCP ingests that extraction and persists the graph in `GRAPH_IS_HERE/`

The branding is simple on purpose: bold input, clean extraction, precise graph output.

## New User In 3 Minutes

### 1. Clone and install dependencies

```bash
git clone <your-fork-or-this-repo-url>
cd graphrag-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment expectations:

- use Python 3 with a local virtualenv in `.venv`
- the agent should be opened from this repo root
- `.mcp.json` uses a repo-local launcher that prefers `.venv/bin/python`
- if you want better retrieval quality, configure your preferred embedding runtime separately

### 2. Drop files into `to_be_extracted/`

Put the raw documents you want processed into `to_be_extracted/`.

### 3. Open Codex, Claude Code, or Copilot in this repo and use this prompt

```text
Call get_server_status().
If overall is ready, proceed.
If overall is degraded, explain what is degraded, what still works, and ask whether to proceed or fix first.
Read the files in to_be_extracted/.
Choose the most appropriate extraction skill from the skills folder for each file.
Extract entities, relationships, and chunks into extractions/{source_name}_extracted.json.
Validate that every source_id maps to a real chunk_id and that all relationships reference defined entities.
If the extraction looks clean, call ingest_from_file for each generated extraction file.
If you find duplicate entities, orphaned relationships, or conflicts, use the reconciliation skill before ingestion.
Then confirm the graph artifacts written to GRAPH_IS_HERE/ and summarize what was ingested.
```

That is the fastest supported developer onboarding path.

## Core Product Idea

This repo is built around six steps:

1. A developer places source files in `to_be_extracted/`.
2. An agent reads those files.
3. The agent selects the correct extraction skill from `skills/`.
4. The agent writes structured extraction output into `extractions/`.
5. The agent calls the appropriate MCP ingestion tool.
6. The repo persists the graph artifact in `GRAPH_IS_HERE/`.

So the product is not only "an MCP server" and not only "an ingestion backend."

The product is:

- an agent workflow for extracting graph-ready knowledge from raw documents
- a set of repo-local extraction skills
- MCP tools that ingest and query the graph
- a persistent graph artifact that can be reused later

## Canonical Folders

These directories are the workflow contract for developers and agents:

- `to_be_extracted/`: raw user inputs waiting for extraction
- `skills/`: agent skills used to decide how extraction should happen
- `extractions/`: agent-generated extraction JSON files
- `GRAPH_IS_HERE/`: persisted graph and retrieval artifacts

The expected lifecycle is:

1. raw file arrives in `to_be_extracted/`
2. agent selects a skill
3. agent writes `extractions/{source_name}_extracted.json`
4. agent calls ingestion
5. graph becomes queryable and reusable

## Primary Developer Path

This is the main way a new developer should use the repo.

### 1. Put raw data in `to_be_extracted/`

Drop one or more source files into `to_be_extracted/`.

Examples:

- financial filing
- research paper
- README or technical documentation
- internal notes or wiki export

### 2. Ask an agent to run the workflow

Use a coding agent that can read files and follow repo-local instructions.

The agent should:

1. call `get_server_status()`
2. if overall is degraded, explain warnings and ask before proceeding
3. inspect files in `to_be_extracted/`
4. choose the right skill from `skills/`
5. read and extract the document
6. write extraction JSON to `extractions/`
7. validate chunk/entity/relationship consistency
8. call the matching MCP ingestion tool
9. verify graph artifacts in `GRAPH_IS_HERE/`

Example agent request:

```text
Call get_server_status().
If overall is ready, proceed.
If overall is degraded, explain what is degraded, what still works, and ask whether to proceed or fix first.
Read the files in to_be_extracted/.
Choose the appropriate extraction skill from the skills folder.
Extract entities, relationships, and chunks into extractions/.
Then call the appropriate ingestion tool so the graph is built in GRAPH_IS_HERE/.
```

### 3. Confirm graph artifacts were created

After ingestion, the graph is persisted in `GRAPH_IS_HERE/`.

Important artifacts:

- `GRAPH_IS_HERE/graph_graph.graphml`
- `GRAPH_IS_HERE/kv_store_text_chunks.json`
- `GRAPH_IS_HERE/kv_store_entity_chunks.json`
- `GRAPH_IS_HERE/kv_store_relation_chunks.json`
- `GRAPH_IS_HERE/vdb_entities.json`
- `GRAPH_IS_HERE/vdb_relationships.json`
- `GRAPH_IS_HERE/vdb_chunks.json`
- `GRAPH_IS_HERE/artifact_manifest.json`

## Skill Selection

The agent should choose a skill based on the source material.

Available extraction skills:

- `skills/Financial-Graph-Extraction/SKILL.md`
  Use for 10-Ks, 10-Qs, earnings calls, analyst reports, and other financial material.
- `skills/Research-paper-graph-extraction-skill/SKILL.md`
  Use for research papers, scientific literature, and academic corpora.
- `skills/General-graph-extraction-skill/SKILL.md`
  Use for codebases, READMEs, wikis, internal docs, and general non-financial content.
- `skills/Reconciliation-Subagent-Skill/SKILL.md`
  Use only for cleanup of an already-created extraction JSON, not for raw-document extraction.

The agent is expected to decide the skill before producing `extractions/{source}_extracted.json`.

## MCP's Role

MCP is the tool interface the agent uses after extraction.

It is responsible for:

- ingesting extracted JSON into the graph
- retrying ingestion if needed
- querying the persisted graph
- supporting reconciliation-based ingestion flows

Important tools exposed by the server in [mcp/server.py](./mcp/server.py):

- `get_server_status`
- `ingest_graph_tool`
- `ingest_from_file`
- `reingest_from_file`
- `ingest_with_reconciliation_tool`
- `query_graph_tool`

The relationship is:

- skills produce the extraction payload
- MCP tools ingest and query that payload
- the graph artifact is the durable output

## Runtime Status Tool (get_server_status)

This tool is the runtime truth surface for agents. Call it before any extraction or ingestion.

Status contract:

- reports embedding mode/provider/model/dimension and status
- reports local graph storage type and artifact location
- reports entity/relationship counts from local stores
- reports LLM configuration status
- returns `warnings` for degraded states
- returns an overall `overall`: `ready` or `degraded`

If status is `degraded`, the agent must explain what is degraded, what still works, and ask whether to proceed.

Example (healthy):

```json
{
  "overall": "ready",
  "warnings": [],
  "embedding": {
    "mode": "local",
    "provider": "ollama",
    "model": "mxbai-embed-large",
    "dimension": 768,
    "status": "active"
  },
  "graph": {
    "storage": "networkx",
    "location": "/path/to/GRAPH_IS_HERE",
    "graph_file": "/path/to/GRAPH_IS_HERE/graph_graph.graphml",
    "entities": 142,
    "relationships": 281,
    "documents_ingested": 1,
    "chunks": 96
  },
  "llm": {
    "configured": true,
    "provider": "custom",
    "model": "custom_llm",
    "status": "active"
  },
  "updated_at": 1770000000
}
```

Example (degraded embeddings + no LLM):

```json
{
  "overall": "degraded",
  "warnings": [
    "Fallback embeddings are active; graph creation still works, but vector similarity quality is reduced.",
    "LLM summarization is not configured; extraction and graph creation still work, but summary generation is skipped."
  ],
  "embedding": {
    "mode": "fallback",
    "provider": "fallback",
    "model": "fallback",
    "dimension": 8,
    "status": "degraded"
  },
  "graph": {
    "storage": "networkx",
    "location": "/path/to/GRAPH_IS_HERE",
    "graph_file": "/path/to/GRAPH_IS_HERE/graph_graph.graphml",
    "entities": 0,
    "relationships": 0,
    "documents_ingested": 0,
    "chunks": 0
  },
  "llm": {
    "configured": false,
    "provider": "none",
    "model": null,
    "status": "inactive"
  },
  "updated_at": 1770000000
}
```

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## MCP Setup

This repo includes a workspace `.mcp.json` for local development.

It is agent-first and assumes:

- `.venv` exists at the repo root
- the agent is opened from the repo root
- the launcher will use `.venv/bin/python`

Minimal structure:

```json
{
  "mcpServers": {
    "graphrag-mcp": {
      "type": "stdio",
      "command": "/bin/sh",
      "args": ["scripts/mcp_launcher.sh"],
      "cwd": ".",
      "tools": ["*"]
    }
  }
}
```

If you want a direct fallback, replace `command` with the absolute path to your own `.venv/bin/python`.

## Manual Fallback Path

Advanced users can still drive the handoff manually after extraction.

This is useful when:

- an agent already wrote extraction JSON
- you want to inspect or repair extraction output by hand
- you want to retry ingestion without re-running extraction

### Ingest an existing extraction file

```bash
python3 test/ingest_manual.py extractions/reconciled_apple_10k_2024_1779725404.json
```

### Query the persisted graph

```bash
python3 test/query_manual.py "What is Tim Cook's role?" mix
```

### Run reconciliation demo flow

```bash
python3 test/reconcile_manual.py
```

## Internal Extraction Contract

Extraction JSON is still required as the handoff between extraction and ingestion, but it is not the main user-facing entrypoint.

The repo expects a JSON object with:

- `document_id`
- `entities`
- `relationships`
- `chunks`

The extraction skills in `skills/` already define the expected schema and output filename pattern:

- `extractions/{source_filename}_extracted.json`

Recommended execution contract for agents:

- treat each raw input file in `to_be_extracted/` as one extraction unit unless the user asks otherwise
- write one extraction JSON per source file
- call `get_server_status()` first
- if overall is `degraded`, explain what is degraded, what still works, and ask before continuing
- validate before ingestion
- use the reconciliation skill only when cleanup is needed

## What Gets Persisted

The graph is stored in `GRAPH_IS_HERE/` and is reusable across sessions.

The most portable artifact today is:

- `GRAPH_IS_HERE/graph_graph.graphml`

The JSON stores and vector DB files support retrieval and query workflows inside this repo.

The manifest is a lightweight summary of the artifact bundle:

- working directory and graph storage type
- embedding provider/model/dimension and fallback mode
- document/entity/relationship counts (when available)
- generation/update timestamps

## Downstream Export Adapters (Optional)

Local persistence in `GRAPH_IS_HERE/` is the source of truth. Downstream exports are optional, post-creation adapters:

- Neo4j export means graph export (nodes + edges)
- Qdrant export means vector export (embeddings + metadata)

Exports are one-way from the local artifact bundle to downstream systems. They are not required for ingestion or querying.

## Recommended Developer Mental Model

If you are a developer using this repo, think about it like this:

- I put raw documents in `to_be_extracted/`
- an agent uses repo-local skills to produce graph-ready extraction JSON
- the agent calls MCP ingestion tools
- the repo persists a reusable graph artifact for later querying and downstream reuse

That is the core product.

## Current Limitations

This repo already proves the raw-document-to-graph workflow, but it is still early-stage.

Notable limitations today:

- Neo4j and Qdrant are not implemented yet as downstream export adapters
- export is still local-first rather than a dedicated push command
- retrieval quality still depends on embedding configuration quality
