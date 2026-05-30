# Getting Started in 5 Minutes

## What you need

- **Python 3.11+**
- **Ollama running locally** (for embeddings) — [install here](https://ollama.ai)
- **Claude Code, Codex, or GitHub Copilot** (or any supported agent)

## Step 1: Clone and install

```bash
git clone https://github.com/yourusername/preciso-graphrag
cd preciso-graphrag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Drop a document

Place any document into `to_be_extracted/`. Supported formats:
- PDF (plain text extraction)
- Markdown
- Plain text
- Financial filings (10-K, 10-Q, etc.)
- Research papers
- Codebase documentation

For example:
```bash
cp your_document.txt to_be_extracted/
```

## Step 3: Run this prompt in your agent

Open your coding agent (Claude Code, Copilot, etc.) in this repo root and paste:

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

The agent will:
1. Extract structured knowledge (entities, relationships) from your document.
2. Validate the extraction.
3. Ingest it into a local knowledge graph.
4. Confirm success.

## Step 4: Query your graph

Once ingestion is done, test a query. Open a terminal and run:

```bash
python3 test/query_manual.py "What are the company's risk factors?" mix
```

Expected output: A structured response with entities, relationships, and evidence chunks from your document.

Example (Walmart filing):
```
Entities:
  - walmart_inc (company)
  - supply_chain_risk (risk_factor)

Relationships:
  - walmart_inc EXPOSED_TO supply_chain_risk

Context:
  "Walmart's supply chain is exposed to various risks including disruptions..."
```

## What just happened

You've built a knowledge graph from unstructured text. Instead of retrieving similar chunks (like regular RAG), the system extracted entities and relationships and stored them as a queryable graph. When you ask a question, it traverses the graph to find connected answers — so multi-hop reasoning works: "Who is responsible for managing supply chain risks?" → finds PERSON MANAGES RISK_FACTOR connections and returns executive names.

This is GraphRAG: reasoning across connections, not just searching for similar text.

---

**Next steps:**
- Read [skills-guide.md](skills-guide.md) to learn how to customize extraction for your domain.
- Check [eval-guide.md](eval-guide.md) to validate your graph quality.
- See [faq.md](faq.md) for troubleshooting.
