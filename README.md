# GraphRAG MCP

GraphRAG MCP is an agent-driven workflow for turning raw documents into a reusable knowledge graph artifact.

The intended flow is:

`raw files -> agent chooses skill -> extraction JSON -> MCP ingestion -> persistent graph artifact`

The end user does not start with extraction JSON. The end user starts by dropping source material into `to_be_extracted/`, then an agent such as Codex or Claude Code performs extraction using the skills in this repo and calls the ingestion tools.

MCP is one runtime interface inside that workflow. The real product output is the persisted graph artifact.

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

1. inspect files in `to_be_extracted/`
2. choose the right skill from `skills/`
3. read and extract the document
4. write extraction JSON to `extractions/`
5. call the matching MCP ingestion tool

Example agent request:

```text
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

- `ingest_graph_tool`
- `ingest_from_file`
- `reingest_from_file`
- `ingest_with_reconciliation_tool`
- `query_graph_tool`

The relationship is:

- skills produce the extraction payload
- MCP tools ingest and query that payload
- the graph artifact is the durable output

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## MCP Setup

This repo includes a workspace `.mcp.json` for local development. It points at this checkout's virtualenv and server entrypoint.

If another developer clones the repo elsewhere, they must update the path values to match their machine or create an equivalent user-level MCP config.

Minimal structure:

```json
{
  "mcpServers": {
    "graphrag-mcp": {
      "type": "stdio",
      "command": "/path/to/repo/.venv/bin/python",
      "args": ["mcp/server.py"],
      "cwd": "/path/to/repo",
      "tools": ["*"]
    }
  }
}
```

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

## What Gets Persisted

The graph is stored in `GRAPH_IS_HERE/` and is reusable across sessions.

The most portable artifact today is:

- `GRAPH_IS_HERE/graph_graph.graphml`

The JSON stores and vector DB files support retrieval and query workflows inside this repo.

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

- the local MCP config is still path-based and must be adapted per machine
- export is implicit through persisted files rather than a dedicated export command
- the default retrieval setup depends on local embedding configuration quality
- multi-project packaging and developer onboarding can still be simplified further
