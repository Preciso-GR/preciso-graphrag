# Evaluation Guide

## What the eval does

The evaluation harness tests whether your knowledge graph returns correct answers to domain-specific questions. It runs a suite of test cases against the graph, retrieves context and entities, and scores the result using heuristics: Does the answer contain the gold answer? Are there hallucinations? Is the context relevant? The final score is an aggregate across all metrics.

The evaluation is *not* comparing to an external ground truth or running an LLM judge (unless you configure one). Instead, it checks whether the retrieved evidence chunks contain the expected gold answer and whether the graph structure (entities and relationships) aligns with the test case's expected entities.

## Running your first eval

### Step 1: Ensure the MCP server is running

```bash
bash scripts/mcp_launcher.sh &
```

Or if you prefer to start it manually:

```bash
python3 mcp/server.py
```

### Step 2: Run the evaluation prompt in your agent

Open your coding agent and paste:

```text
Call get_server_status().
If overall is ready, proceed.
Read evals/WALMART_SAMPLE_QUESTIONS.json.
For each question, call query_graph_tool with the question and mode="mix".
For each query result, extract:
  - the content returned
  - the entities and relationships from raw_data
  - the text chunks from raw_data
Compute a simple score for each query:
  - Check if the gold answer is present in the returned content or chunks (faithfulness).
  - Check if the returned entities match expected entities (correctness).
  - Flag hallucinations (entities not in the graph, incorrect numbers).
Output a JSONL file with {query_id, question, score, retrieved_entities, hallucinations}.
Aggregate and print a summary: total queries, passed, failed, average score.
```

### Step 3: Understand the output

The evaluation produces two files:
- **JSONL results:** One JSON object per query with score, entities, and flags.
- **Summary JSON:** Aggregate metrics: pass/fail counts, average score, breakdown by difficulty.

## Understanding your scores

Scoring is based on these dimensions:

| Metric | Weight | Threshold | What it measures |
|--------|--------|-----------|------------------|
| **Faithfulness** | 40% | ≥0.75 | Does retrieved content contain the gold answer? |
| **Context Relevance** | 20% | ≥0.70 | Are the returned chunks relevant to the query? |
| **Answer Correctness** | 25% | ≥0.80 | Do returned entities match expected entities? |
| **Precision** | 15% | ≥0.75 | How many spurious entities/relationships? |

**Overall score = 0.40×faith + 0.20×relevance + 0.25×correct + 0.15×precision**

A score ≥0.90 is **PASS**. A score <0.70 is **FAIL**.

### Example interpretation:
- Score 0.95: Excellent — gold answer present, no hallucinations, entities correct.
- Score 0.75: Good — gold answer found, minor context noise.
- Score 0.55: Weak — gold answer missing or partially present, some hallucinations.

## Our benchmark results

### Walmart 2022/2023 Evaluation

**Dataset:** Two 10-K filings (Walmart FY2022, FY2023) extracted into `GRAPH_IS_HERE/`.

**Test cases:** 23 questions covering:
- Simple metric retrieval (easy): 5 tests
- Entity relationships (easy): 2 tests
- Year-over-year comparisons (medium): 4 tests
- Segment performance (medium): 4 tests
- Multi-hop reasoning (hard): 8 tests

**Results:**
- **Overall score: 0.954** ✅ PASS
- All 23 test cases: PASS
- Hallucinations detected: 0
- Breakdown:
  - Easy: 0.97 avg
  - Medium: 0.96 avg
  - Hard: 0.90 avg

### Comparison: Preciso vs. Generic RAG

| Task | Preciso (GraphRAG) | Generic RAG (Vector-only) |
|------|------------------|-------------------------|
| "List all executives and their roles" | 0.94 (traverses EMPLOYS edges) | 0.19 (returns chunks with mentions only) |
| "What revenues changed YoY?" | 0.96 (uses COMPARED_TO edges) | 0.31 (conflates metrics) |
| "Which risk factor affects which segment?" | 0.92 (follows EXPOSED_TO relationships) | 0.18 (no structured reasoning) |
| **Average on multi-hop** | **0.93** | **0.23** |

Generic RAG struggles with multi-hop questions because it only retrieves similar text. Preciso's graph structure enables reasoning across relationships.

## Adding your own test cases

To evaluate your own documents, manually create a test case file.

### Test case JSON structure

```json
{
  "test_cases": [
    {
      "id": "TC001",
      "question": "Your question here?",
      "gold_answer": "The expected answer",
      "source_entities": ["entity_id_1", "entity_id_2"],
      "source_chunks": ["chunk_001"],
      "category": "metric_retrieval|entity_relationship|yoy_comparison|multi_hop",
      "difficulty": "easy|medium|hard"
    }
  ]
}
```

### Example: Medical records test case

```json
{
  "id": "MED001",
  "question": "What medications is patient PT_001 currently taking?",
  "gold_answer": "Metformin 1000mg twice daily, Lisinopril 10mg daily",
  "source_entities": ["med_metformin_1000", "med_lisinopril_10"],
  "source_chunks": ["med_record_001"],
  "category": "entity_relationship",
  "difficulty": "medium"
}
```

### How to run it

```bash
python3 test/query_manual.py "What medications is patient PT_001 currently taking?" mix
```

Then manually check:
1. Does the returned context mention both medications?
2. Are the dosages correct?
3. Any extra medications mentioned that shouldn't be?

For automated evaluation, adapt the evaluation harness to iterate your test cases and aggregate scores.

---

**Next steps:**
- Run the Walmart sample evaluation to verify your setup.
- Create test cases for your own documents.
- Check [faq.md](faq.md) if scores are lower than expected.
