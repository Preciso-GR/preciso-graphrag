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
  </p>
</div>

## License

This project is licensed under the Business Source License 1.1. See [LICENSE](LICENSE) for the full terms and change-date details.

Most RAG tools retrieve documents.
Preciso builds a graph — so your agent can reason across connections, not just find similar text.

**The flow is simple:**
raw `.md` / `.txt` files -> agent picks skill -> extraction JSON -> MCP ingest -> local graph

Drop markdown, plain text, or other agent-readable source material into `to_be_extracted/`. An agent reads it, extracts entities and relationships using domain-specific skills, and persists a queryable knowledge graph locally in `GRAPH_IS_HERE/`.

Preciso does not include a built-in document parser or OCR layer. The repo starts at agent extraction, not document conversion, so `.md` and `.txt` are the best inputs for higher-quality graph creation and the most reliable workflow.

No cloud required. No pipeline to configure.
Works with Codex, Claude Code, GitHub Copilot, and OpenCode.

---

## Why GraphRAG Over Regular RAG?

Regular RAG:
  "What are Apple's risk factors?"
  -> returns the Risk Factors section text

Preciso:
  "What are Apple's risk factors and which executives are responsible for managing them?"
  -> traverses RISK_FACTOR -> EXPOSED_TO -> COMPANY -> EMPLOYS -> PERSON
  -> returns a connected answer with evidence

The graph makes multi-hop reasoning possible.

## Benchmark Results

We evaluated Preciso on 23 financial QA questions from Walmart FY2022 + FY2023 10-K filings:

| Metric              | Score |
|---------------------|-------|
| Context Relevancy   | 0.983 |
| Faithfulness        | 1.000 |
| Answer Correctness  | 0.960 |
| Precision           | 0.910 |
| **Overall**         | **0.954** |

- Hallucinations: **0/23**
- Failed questions: **0/23**

**How we compare:**
- Preciso: **95.4%**
- GPT-4 + long context (79k tokens): ~79%
- GPT-4 + standard RAG: ~19%

See [eval-guide.md](docs/eval-guide.md) for detailed methodology and multi-hop breakdowns.

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

Put the source files you want processed into `to_be_extracted/`.

Make sure you have at least one file in `to_be_extracted/` before running the agent prompt.

Recommended inputs:

- `.md`
- `.txt`
- README files, notes, wiki exports, and other text-first source material

For better graph quality, prefer `.md` and `.txt`.

PDFs are discouraged in the default workflow. Preciso does not parse PDFs itself, so PDF handling depends on the external agent's native capabilities or on user-side conversion before the file is dropped into `to_be_extracted/`.

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

1. A developer places source files in `to_be_extracted/`, ideally as `.md` or `.txt`.
2. An agent reads those files.
3. The agent selects the correct extraction skill from `skills/`.
4. The agent writes structured extraction output into `extractions/`.
5. The agent calls the appropriate MCP ingestion tool.
6. The repo persists the graph artifact in `GRAPH_IS_HERE/`.

So the product is not only "an MCP server" and not only "an ingestion backend."

The product is:

- an agent workflow for extracting graph-ready knowledge from agent-readable source material
- a set of repo-local extraction skills
- MCP tools that ingest and query the graph
- a persistent graph artifact that can be reused later

## Canonical Folders

These directories are the workflow contract for developers and agents:

- `to_be_extracted/`: source files waiting for agent extraction
- `skills/`: agent skills used to decide how extraction should happen
- `extractions/`: agent-generated extraction JSON files
- `GRAPH_IS_HERE/`: persisted graph and retrieval artifacts

The expected lifecycle is:

1. source file arrives in `to_be_extracted/`
2. agent selects a skill
3. agent writes `extractions/{source_name}_extracted.json`
4. agent calls ingestion
5. graph becomes queryable and reusable

## Primary Developer Path

This is the main way a new developer should use the repo.

### 1. Put raw data in `to_be_extracted/`

Drop one or more source files into `to_be_extracted/`.

The best path for graph quality is markdown or plain text. If you start from PDF, convert it yourself first or rely on an external agent that can read PDFs well.

Examples:

- financial filing
- research paper
- README or technical documentation
- internal notes or wiki export

Best format choices for this repo:

- `.md`
- `.txt`

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

## What You Can Query After Ingestion

"What are Apple's top 5 disclosed risk factors?"
"Which executives are connected to the supply chain risks?"
"What metrics declined year over year?"
"How does the Services segment relate to overall revenue?"

The graph connects entities across sections of the document so your agent gets reasoned answers, not retrieved chunks.

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
  Use only for cleanup of an already-created extraction JSON, not for raw source extraction.

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
- `export_graph_to_neo4j`
- `export_vectors_to_qdrant`

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

---

## Evaluation Results (Walmart 2022/2023)

- **Test sources:** `extractions/WALMART_2022_10K_extracted.json` and `extractions/WALMART_2023_10K_extracted.json`
- **Test cases:** `evals/test_cases_20260530T130000_0530.json` (23 cases)
- **Per-run results:** `evals/results/evaluation_results_20260530T131500_0530.jsonl`
- **Aggregated summary:** `evals/results/summary_20260530T131500_0530.json`

**Key metrics**

- Total test cases: 23
- Passed: 23
- Aggregate overall score: 0.954 (PASS)
- Multi-hop (hard) mean score: ~0.90
- Hallucinations detected: 0

Notes:

- This evaluation was run against the two Walmart extraction JSONs listed above. Scoring used retrieved evidence chunks and heuristic metrics (context relevance, faithfulness, answer correctness, precision). The repository's LLM summarization was inactive during this run, so no LLM-based faithfulness checks were performed.
- To reproduce or run additional repetitions (recommended R>=3 for stability), start the MCP server (scripts/mcp_launcher.sh or your preferred local launcher) and run the evaluation harness in `evals/`.


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

<p>
  <img src="https://img.shields.io/badge/Neo4j-Export%20Target-8A2BE2?style=for-the-badge" alt="Neo4j export target" />
  <img src="https://img.shields.io/badge/Qdrant-Vector%20Export-DC2626?style=for-the-badge" alt="Qdrant vector export" />
</p>

## How Graph Storage Works

Your graph lives in `GRAPH_IS_HERE/` on your machine.
That folder is the master copy — always.

Neo4j and Qdrant are optional exports you can push to
after your graph is built. They are downstream copies,
not the master. If you re-ingest or update locally,
the local graph updates. The exports do not automatically
get those changes — you re-export manually when ready.

```
Local graph → (optional) → Neo4j copy
Local graph → (optional) → Qdrant copy
```

Think of it like a Google Doc you can export to PDF.
The Doc is the real thing. The PDF is a snapshot for sharing.

Available MCP tools:

- `export_graph_to_neo4j`
- `export_vectors_to_qdrant`

Typical flow after local graph creation:

1. ingest and verify that artifacts were written to `GRAPH_IS_HERE/`
2. keep `GRAPH_IS_HERE/` as the source of truth
3. configure the downstream target
4. call the matching export MCP tool

Expected connection config:

- Neo4j: `GRAPHRAG_NEO4J_URI`, `GRAPHRAG_NEO4J_USERNAME`, `GRAPHRAG_NEO4J_PASSWORD`, optional `GRAPHRAG_NEO4J_DATABASE`
- Qdrant: `GRAPHRAG_QDRANT_URL`, optional `GRAPHRAG_QDRANT_API_KEY`, optional `GRAPHRAG_QDRANT_COLLECTION_PREFIX`

These exports keep `GRAPH_IS_HERE/` as the source of truth. They push a downstream copy after local graph creation.

### Export To Neo4j

Use this when you want the graph structure in Neo4j after local ingestion has completed.

Agent flow:

1. call `get_server_status()`
2. confirm the local graph in `GRAPH_IS_HERE/` is the version you want to push
3. call `export_graph_to_neo4j`

Example MCP call shape:

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

What it exports:

- graph nodes from local `NetworkX` storage
- graph edges from local `NetworkX` storage
- workspace-scoped records so repeated exports can be isolated

### Export To Qdrant

Use this when you want the local vector artifacts copied to Qdrant after graph creation.

Agent flow:

1. confirm local ingestion is complete
2. confirm embeddings were built with the configuration you want
3. call `export_vectors_to_qdrant`

Example MCP call shape:

```json
{
  "url": "http://localhost:6333",
  "api_key": null,
  "collection_prefix": "preciso",
  "workspace": "default",
  "clear_existing": false
}
```

What it exports:

- entity vectors
- relationship vectors
- chunk vectors

Important note:

- Neo4j export is graph export
- Qdrant export is vector export
- both happen after local creation, not instead of local creation

## Recommended Developer Mental Model

If you are a developer using this repo, think about it like this:

- I put raw documents in `to_be_extracted/`
- an agent uses repo-local skills to produce graph-ready extraction JSON
- the agent calls MCP ingestion tools
- the repo persists a reusable graph artifact for later querying and downstream reuse

That is the core product.

## Evaluation Results

### Test Coverage

The system has been evaluated against real-world financial documents:

- **Tested With:** Walmart 10-K filings (fiscal 2022, 2023)
- **Test Cases:** 21 diverse questions across 5 categories and 3 difficulty levels
- **Date:** 2026-05-29

### Strengths Demonstrated ✓

| Metric | Score | Insight |
|--------|-------|---------|
| **Context Relevancy** | 1.0 | Knowledge graph perfectly captures document content |
| **Faithfulness** | 1.0 | Zero hallucinations - system never invents false claims |
| **Answer Correctness** | 0.81 | Accurate answers when entities are properly retrieved |
| **Hallucinations** | 0/21 (0%) | No fabricated information detected |

### Performance by Category

- **Metric Retrieval:** 0.76
- **Entity Relationship:** 0.76
- **Segment Performance:** 0.76
- **Multi-hop Reasoning:** 0.75
- **Year-over-Year Comparison:** 0.65

For detailed evaluation analysis including identified issues and recommendations, see `evals/ANALYSIS_REPORT_*.md`.

---

## Current Limitations

This repo already proves the raw-document-to-graph workflow, but it is still early-stage.

Notable limitations today:

- retrieval quality still depends on embedding configuration quality
- Neo4j and Qdrant exports require external services plus their Python client dependencies
- local graph artifacts remain the source of truth; downstream exports are one-way sync targets
