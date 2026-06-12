<div align="center">
  <h1>Preciso</h1>
  <p><strong>Precise knowledge graphs from your documents.</strong></p>
  <p><em>Named after Bruno Fernandes. Every pass lands exactly where it needs to.</em></p>

  <p>
    <img src="https://img.shields.io/badge/Codex-Agent-111111?style=for-the-badge&logo=openai&logoColor=white" alt="Codex agent support" />
    <img src="https://img.shields.io/badge/Claude%20Code-Agent-C8102E?style=for-the-badge" alt="Claude Code agent support" />
    <img src="https://img.shields.io/badge/OpenCode-Agent-FFFFFF?style=for-the-badge&logoColor=C8102E&color=C8102E" alt="OpenCode agent support" />
    <img src="https://img.shields.io/badge/Copilot-Agent-7F1D1D?style=for-the-badge&logo=github&logoColor=white" alt="Copilot agent support" />
  </p>
  <p>
    <img src="https://img.shields.io/badge/Local--First-FFFFFF?style=for-the-badge&logoColor=C8102E&color=C8102E" alt="Local-first workflow" />
    <img src="https://img.shields.io/badge/Python-3.11%2B-111111?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/License-BSL%201.1-blue?style=for-the-badge" alt="BSL 1.1 License" />
  </p>
</div>

---

Most RAG tools retrieve documents. Preciso builds a **knowledge graph** — so your agent can reason across connections, not just find similar text.

```
raw .md / .txt files → agent picks skill → extraction JSON → MCP ingest → local graph
```

Drop source files into `to_be_extracted/`. An agent reads them, extracts entities and relationships using domain-specific skills, and persists a queryable knowledge graph locally in `GRAPH_IS_HERE/`. No cloud required. No pipeline to configure.

---

## Table of Contents

- [Why GraphRAG?](#why-graphrag-over-regular-rag)
- [Benchmark Results](#benchmark-results)
- [Quickstart](#quickstart-3-minutes)
- [How It Works](#how-it-works)
- [Skill Selection](#skill-selection)
- [MCP Tools](#mcp-tools)
- [Querying the Graph](#what-you-can-query-after-ingestion)
- [Downstream Exports](#downstream-exports-optional)
- [Manual Fallback](#manual-fallback-path)
- [License](#license)

---

## Why GraphRAG Over Regular RAG?

**Regular RAG:**
```
"What are Apple's risk factors?"
→ returns the Risk Factors section text
```

**Preciso:**
```
"What are Apple's risk factors and which executives are responsible for managing them?"
→ traverses RISK_FACTOR → EXPOSED_TO → COMPANY → EMPLOYS → PERSON
→ returns a connected answer with evidence
```

The graph makes multi-hop reasoning possible.

---

## Benchmark Results

Evaluated on 23 financial QA questions from Walmart FY2022 + FY2023 10-K filings:

| Metric             | Score    |
|--------------------|----------|
| Context Relevancy  | 0.983    |
| Faithfulness       | **1.000**|
| Answer Correctness | 0.960    |
| Precision          | 0.910    |
| **Overall**        | **0.954**|

- **Hallucinations:** 0 / 23
- **Failed questions:** 0 / 23

**How Preciso compares:**

| System                           | Score  |
|----------------------------------|--------|
| **Preciso**                      | **95.4%** |
| GPT-4 + long context (79k tokens)| ~79%   |
| GPT-4 + standard RAG             | ~19%   |

See [eval-guide.md](docs/eval-guide.md) for detailed methodology and multi-hop breakdowns.

---

## Quickstart (3 Minutes)

### 1. Clone and install

```bash
git clone <your-fork-or-this-repo-url>
cd graphrag-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Preciso expects Python 3.11+, a local virtualenv at `.venv`, and the agent opened from the repo root. `.mcp.json` uses a repo-local launcher that prefers `.venv/bin/python`.

### 2. Drop files into `to_be_extracted/`

Best input formats:
- `.md`
- `.txt`
- README files, wiki exports, notes, and other text-first source material

> PDFs are discouraged by default. Preciso does not parse PDFs itself — convert them to `.md` or `.txt` first, or rely on an external agent with native PDF support.

### 3. Run the agent prompt

Open Codex, Claude Code, GitHub Copilot, or OpenCode in this repo and run:

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

---

## How It Works

Preciso is built around a six-step contract between your agent, the repo-local skills, and the MCP server:

1. Developer places source files in `to_be_extracted/`
2. Agent reads those files
3. Agent selects the correct extraction skill from `skills/`
4. Agent writes structured extraction output to `extractions/`
5. Agent calls the appropriate MCP ingestion tool
6. Repo persists the graph artifact in `GRAPH_IS_HERE/`

### Red-White Workflow

| Stage       | Directory         | Description                                      |
|-------------|-------------------|--------------------------------------------------|
| 🔴 Red side | `to_be_extracted/`| Raw source documents arrive here                 |
| ⚪ White side| `extractions/`    | Agent writes structured extraction JSON here     |
| Final pass  | `GRAPH_IS_HERE/`  | MCP ingests extraction and persists the graph    |

### Canonical Folders

```
to_be_extracted/     ← source files waiting for agent extraction
skills/              ← domain-specific extraction skills
extractions/         ← agent-generated extraction JSON files
GRAPH_IS_HERE/       ← persisted graph and retrieval artifacts
```

---

## Skill Selection

The agent selects a skill based on the source material type:

| Skill | Path | Use For |
|-------|------|---------|
| Financial extraction | `skills/Financial-Graph-Extraction/SKILL.md` | 10-Ks, 10-Qs, earnings calls, analyst reports |
| Research paper extraction | `skills/Research-paper-graph-extraction-skill/SKILL.md` | Research papers, scientific literature, academic corpora |
| General extraction | `skills/General-graph-extraction-skill/SKILL.md` | Codebases, READMEs, wikis, internal docs |
| Reconciliation | `skills/Reconciliation-Subagent-Skill/SKILL.md` | Cleanup of existing extraction JSON only — not for raw sources |

---

## MCP Tools

MCP is the tool interface the agent uses after extraction. It is responsible for ingesting extracted JSON, querying the graph, and optional downstream exports.

### Core tools

| Tool | Description |
|------|-------------|
| `get_server_status` | Runtime health check — call before any extraction or ingestion |
| `ingest_graph_tool` | Ingest extraction payload into the graph |
| `ingest_from_file` | Ingest from a named extraction JSON file |
| `reingest_from_file` | Re-ingest an existing extraction file |
| `ingest_with_reconciliation_tool` | Ingest with conflict resolution |
| `query_graph_tool` | Query the persisted graph |
| `export_graph_to_neo4j` | Export graph structure to Neo4j |
| `export_vectors_to_qdrant` | Export vector artifacts to Qdrant |

### `get_server_status` — runtime truth surface

Call this before any extraction or ingestion. It returns the current state of embeddings, graph storage, and LLM config.

**Healthy response:**
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
  }
}
```

**Degraded response:**
```json
{
  "overall": "degraded",
  "warnings": [
    "Fallback embeddings are active; graph creation still works, but vector similarity quality is reduced.",
    "LLM summarization is not configured; extraction and graph creation still work, but summary generation is skipped."
  ],
  "embedding": { "mode": "fallback", "status": "degraded" },
  "llm": { "configured": false, "status": "inactive" }
}
```

If `overall` is `degraded`, the agent must explain what is degraded, what still works, and ask before continuing.

---

## What You Can Query After Ingestion

```
"What are Apple's top 5 disclosed risk factors?"
"Which executives are connected to the supply chain risks?"
"What metrics declined year over year?"
"How does the Services segment relate to overall revenue?"
```

The graph connects entities across document sections so your agent gets reasoned answers, not retrieved chunks.

---

## Graph Artifacts

After ingestion, the graph is persisted in `GRAPH_IS_HERE/` and is reusable across sessions:

```
GRAPH_IS_HERE/
├── graph_graph.graphml              ← most portable artifact
├── kv_store_text_chunks.json
├── kv_store_entity_chunks.json
├── kv_store_relation_chunks.json
├── vdb_entities.json
├── vdb_relationships.json
├── vdb_chunks.json
└── artifact_manifest.json
```

---

## Downstream Exports (Optional)

<p>
  <img src="https://img.shields.io/badge/Neo4j-Export%20Target-8A2BE2?style=for-the-badge" alt="Neo4j export target" />
  <img src="https://img.shields.io/badge/Qdrant-Vector%20Export-DC2626?style=for-the-badge" alt="Qdrant vector export" />
</p>

`GRAPH_IS_HERE/` is always the source of truth. Neo4j and Qdrant are optional downstream copies — not replacements.

```
Local graph (master) → (optional) → Neo4j copy
Local graph (master) → (optional) → Qdrant copy
```

Think of it like a Google Doc you export to PDF. The Doc is the real thing. The PDF is a snapshot for sharing.

### Export to Neo4j

```json
{
  "uri": "bolt://localhost:7687",
  "username": "neo4j",
  "password": "your-password",
  "database": "neo4j",
  "workspace": "default",
  "clear_existing": false
}
```

Required env vars: `GRAPHRAG_NEO4J_URI`, `GRAPHRAG_NEO4J_USERNAME`, `GRAPHRAG_NEO4J_PASSWORD`, optionally `GRAPHRAG_NEO4J_DATABASE`

### Export to Qdrant

```json
{
  "url": "http://localhost:6333",
  "api_key": null,
  "collection_prefix": "preciso",
  "workspace": "default",
  "clear_existing": false
}
```

Required env vars: `GRAPHRAG_QDRANT_URL`, optionally `GRAPHRAG_QDRANT_API_KEY`, `GRAPHRAG_QDRANT_COLLECTION_PREFIX`

> Neo4j exports graph structure. Qdrant exports vector artifacts. Both happen after local creation, not instead of it.

---

## Manual Fallback Path

For advanced users who want to drive ingestion manually after extraction:

```bash
# Ingest an existing extraction file
python3 test/ingest_manual.py extractions/reconciled_apple_10k_2024_1779725404.json

# Query the persisted graph
python3 test/query_manual.py "What is Tim Cook's role?" mix

# Run reconciliation demo flow
python3 test/reconcile_manual.py
```

---

## MCP Setup

This repo includes a workspace `.mcp.json` for local development:

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

If you want a direct fallback, replace `command` with the absolute path to your `.venv/bin/python`.

---

## Extraction Contract

Extraction JSON must include:

```json
{
  "document_id": "...",
  "entities": [...],
  "relationships": [...],
  "chunks": [...]
}
```

Output filename pattern: `extractions/{source_filename}_extracted.json`

---

## Current Limitations

- Retrieval quality depends on embedding configuration quality
- Neo4j and Qdrant exports require external services plus their Python client dependencies
- Local graph artifacts remain the source of truth; downstream exports are one-way sync targets
- PDF handling requires user-side conversion or an external agent with native PDF support ( claude code and Codex doesnt neet conversion )

---

## License

This project is licensed under the **Business Source License 1.1**. See [LICENSE](LICENSE) for full terms and change-date details.
