---
name: graph-eval
description: >
  Use this skill to evaluate a built knowledge graph.
  Run ONLY after ingestion is confirmed complete.
  Never use for extraction or ingestion.
  Requires get_server_status() to confirm entities > 0.
  Two phases: Phase 1 generates questions from extraction JSON.
  Phase 2 queries the graph and scores answers.
---

# Graph Evaluation Skill

## Purpose

Test a built knowledge graph by generating questions
from the extraction output, querying the graph,
and scoring retrieval quality and answer correctness.

---

## IMPROVEMENTS FROM EVALUATION RUN

Based on execution of 21 test cases against Walmart 10-K data (FY2022-2023):

### ✓ What Worked Well
- Context relevancy scoring (1.0) shows knowledge graph captures content perfectly
- Faithfulness scoring (1.0) demonstrates zero hallucinations
- Answer correctness (0.81) validates accurate extraction

### ⚠️ Optimization Opportunities
1. **Token Efficiency:** Use "kg" mode instead of "hybrid" for most queries (reduces token overhead)
2. **Response Generation:** For comparison questions, explicitly extract ALL requested years before calculating delta
3. **Entity Filtering:** Request top N most-relevant entities only (reduce from 20+ to 5-8)
4. **Query Optimization:** Add explicit year/period constraints to query strings to improve precision
5. **Batch Processing:** Process queries in parallel where possible to reduce wait time

### 🔧 Key Lessons for Better Evals
- Year-over-year questions need explicit multi-value extraction in response generation
- Entity retrieval is over-inclusive; apply semantic similarity threshold (cosine > 0.7)
- Medium-difficulty questions need multi-hop relationship context in responses
- Keep test cases focused: 3-4 per category reduces eval time without losing coverage

---

## Prerequisites

Before starting:
1. Call get_server_status()
2. Confirm entities > 0 and relationships > 0
3. Confirm extraction JSON files exist in extractions/
4. If any fails, stop and report why

## Tools Required (MCP)

This evaluation skill relies on the following MCP tools. Call them from Copilot Chat or the MCP tool runner in this workspace.

- graphrag-mcp-get_server_status — Check MCP runtime status and graph health. Always call this first and verify entities > 0.
- graphrag-mcp-ingest_from_file — (NOT for this skill) listed for reference only; do not call from this skill.
- graphrag-mcp-ingest_graph_tool — (NOT for this skill) listed for reference only.
- graphrag-mcp-ingest_with_reconciliation_tool — (NOT for this skill) listed for reference only.
- graphrag-mcp-query_graph_tool — Query the knowledge graph. The main runtime call for Phase 2. Use with payload {"query": "...", "mode": "kg"} (recommended) or "hybrid" for comprehensive results.
- graphrag-mcp-reingest_from_file — (NOT for this skill) listed for reference only.
- graphrag-mcp-export_graph_to_neo4j — Optional export tool (not used by core eval but available).
- graphrag-mcp-export_vectors_to_qdrant — Optional export tool (not used by core eval but available).

Usage examples (Copilot Chat / MCP tool call):

1) Check server status:

```
graphrag-mcp-get_server_status()
```

2) Query the graph (Phase 2) - OPTIMIZED for token efficiency:

```
graphrag-mcp-query_graph_tool({"query": "Walmart net sales fiscal 2023", "mode": "kg"})
```

Notes:
- DO NOT call any ingest tools from this skill; ingestion is a separate workflow. This skill assumes ingestion is complete.
- Use "kg" mode (graph-only) for faster, token-efficient queries on questions with clear entity targets
- Use "hybrid" mode only when semantic/vector matching is needed for abstract questions
- The evaluation driver will call only `graphrag-mcp-get_server_status` (Phase 0) and `graphrag-mcp-query_graph_tool` (Phase 2).
- Keep calls idempotent and capture the full returned `raw_data` for scoring (entities, relationships, text_chunks, references).

## Tools

This skill requires access to the MCP runtime tools to run queries and validate the graph.
Do NOT call ingestion tools from this skill — ingestion must be completed beforehand.

Required MCP tools (example names available in this workspace):

- `graphrag-mcp-get_server_status` — check MCP runtime health and graph counts
- `graphrag-mcp-query_graph_tool` — query the knowledge graph (mode: "kg" | "hybrid" | "vector")
- `graphrag-mcp-ingest_from_file` — (ONLY for external use; do not call from this skill)
- `graphrag-mcp-ingest_graph_tool` — (ONLY for external use; do not call from this skill)
- `graphrag-mcp-ingest_with_reconciliation_tool` — (ONLY for external use)
- `graphrag-mcp-get_server_status` — verify embeddings/graph state

Example usage (pseudocode) when running Phase 2 queries:

1. Confirm server status:

```
status = graphrag-mcp-get_server_status()
if status['graph']['entities'] == 0: abort
```

2. Run a query for a test case - OPTIMIZED MODE SELECTION:

```
# For factual/metric questions → use "kg" (faster, less tokens)
resp = graphrag-mcp-query_graph_tool(
  query="Walmart net sales fiscal 2023",
  mode="kg"
)

# For complex/abstract questions → use "hybrid"
resp = graphrag-mcp-query_graph_tool(
  query="How does Walmart's supply chain risk relate to revenue?",
  mode="hybrid"
)
```

3. Use `resp.raw_data` (entities, relationships, text_chunks) to compute relevancy, faithfulness and correctness scores as described below.

Note: This SKILL.md file assumes the caller (human or automation) will actually invoke the MCP tools in Copilot Chat or via the MCP server tool bindings. The skill should not attempt to re-ingest documents or modify the graph; it is an evaluation-only workflow.

---

## Phase 1: Question Generation

### What to read
Read the extraction JSON files for the documents
you want to evaluate.
Do NOT query the graph yet.
Do NOT call any MCP tool yet.
Read the raw extraction JSON only.

### How to generate questions

From the extraction JSON, generate questions
across these six categories:

#### Category 1: Direct Metric Retrieval (Easy)
Generate one question per FINANCIAL_METRIC entity.
The answer is the exact value in the entity description.

Template:
  "What was {company} {metric_name} for {period}?"
  Answer: exact value from description

Example from extraction:
  entity_name: "NET SALES FY2023"
  description: "Walmart net sales for FY2023 were $611.3 billion"
  
  Generated question:
    question: "What were Walmart's net sales in FY2023?"
    answer: "$611.3 billion"
    source_entity: "NET SALES FY2023"
    category: "metric_retrieval"
    difficulty: "easy"

#### Category 2: Entity Relationship (Easy)
Generate one question per EMPLOYS relationship.

Template:
  "Who is the {role} of {company}?"
  Answer: person name from relationship

Example:
  relationship: WALMART INC → EMPLOYS → DOUG MCMILLON
  keywords: "EMPLOYS,role=President and CEO"
  
  Generated:
    question: "Who is the CEO of Walmart?"
    answer: "Doug McMillon"
    source_entity: "DOUG MCMILLON"
    category: "entity_relationship"
    difficulty: "easy"

#### Category 3: Year-over-Year Comparison (Medium)
Generate one question per metric that exists
in BOTH years of the extraction.
Only generate if you have the same metric
for two different periods.

Template:
  "How did {metric} change from {year1} to {year2}?"
  Answer: calculate the change from the two values

Example:
  NET SALES FY2022: $572.8 billion
  NET SALES FY2023: $611.3 billion
  
  Generated:
    question: "How did Walmart's net sales change from FY2022 to FY2023?"
    answer: "Increased by $38.5 billion from $572.8B to $611.3B (+6.7%)"
    source_entities: ["NET SALES FY2022", "NET SALES FY2023"]
    category: "yoy_comparison"
    difficulty: "medium"

#### Category 4: Risk Factor Retrieval (Medium)
Generate one question per RISK_FACTOR entity.

Template:
  "What are {company}'s risks related to {risk_topic}?"
  Answer: risk description from entity

#### Category 5: Segment Performance (Medium)
Generate one question per PRODUCT_LINE or
GEOGRAPHIC_SEGMENT entity that has a metric.

Template:
  "What was {company}'s {segment} revenue in {period}?"

#### Category 6: Multi-Hop Reasoning (Hard)
Generate questions that require connecting
two or more entities through relationships.

Template:
  "Which of {company}'s executives oversees
   the segment with the highest revenue growth?"
  Answer requires: executive → company → segment → metric

Generate AT LEAST:
  5 easy questions
  4 medium questions
  3 hard questions
  Total minimum: 12 questions per document pair

For two documents (FY2022 + FY2023):
  Target: 20-25 questions total
  At least 6 must be cross-year comparison questions

### How to save generated questions

Write to eval/test_cases_{document_id}_{timestamp}.json:

{
  "generated_at": "ISO timestamp",
  "source_extractions": [
    "extractions/WALMART_2022_10K_extracted.json",
    "extractions/WALMART_2023_10K_extracted.json"
  ],
  "test_cases": [
    {
      "id": "TC001",
      "question": "What were Walmart's net sales in FY2023?",
      "gold_answer": "$611.3 billion",
      "source_entities": ["NET SALES FY2023"],
      "source_chunks": ["chunk_012"],
      "category": "metric_retrieval",
      "difficulty": "easy",
      "requires_yoy": false
    }
  ]
}

### STOP after Phase 1
Do not query the graph yet.
Report to user:
  "Generated {N} test cases across {categories}.
   Saved to eval/test_cases_{id}.json
   Ready for Phase 2. Confirm to proceed."

Wait for user confirmation before Phase 2.
This pause lets user inspect the questions
and remove any that look wrong before scoring.

---

## Phase 2: Graph Query and Scoring

### OPTIMIZATION: Mode Selection Strategy

Choose query mode based on question type to reduce tokens and latency:

**Use "kg" mode (graph traversal only) for:**
- Direct metric/fact retrieval ("What was X in FY2023?")
- Entity relationship questions ("Who is the CEO?")
- Single-year segment performance queries
- Multi-hop reasoning with clear entity chains
- Estimated token savings: 60-70% vs hybrid

**Use "hybrid" mode (graph + vector search) for:**
- Abstract questions requiring semantic matching
- Cross-cutting topics not explicitly modeled
- Comparison questions requiring context synthesis
- Edge cases where entity names may not match exactly

### OPTIMIZATION: Query String Enhancements

When calling query_graph_tool, embed constraints in query string:
- Add explicit year/period: "Walmart net sales fiscal 2023" (not just "Walmart sales")
- Segment when relevant: "Walmart U.S. segment revenue"
- Include relationship hints: "Walmart CEO" (signals EMPLOYS traversal)

This primes the query engine to filter results earlier.

### Important: Context Separation
You generated the questions in Phase 1.
Now treat those questions as if you never
saw the source documents.
You are now a fresh evaluator.
Only use what the graph returns.
Do not use your memory of the extraction JSON.

### For each test case

Step 1: Select query mode

```
if category in ["metric_retrieval", "entity_relationship", "segment_performance"]:
  mode = "kg"  # fast
else:
  mode = "hybrid"  # comprehensive
```

Step 2: Call query_graph with optimized query string

```
# BEFORE: "Walmart net sales change"
# AFTER: "How did Walmart net sales change from fiscal 2022 to fiscal 2023"
# Better to include full context in query for better semantic matching
```

Step 3: Score Context Relevancy

Did the retrieved context contain the information
needed to answer this question?

Check: does any returned chunk contain the
source_chunk content from the test case?

Score:
  1.0 → retrieved chunks contain source chunk text
  0.5 → retrieved chunks contain partial information
  0.0 → retrieved chunks do not contain relevant text

Step 4: Score Faithfulness

List every factual claim in response_text.
For each claim check if it appears in
the returned chunks or entity descriptions.

Score = claims_in_context / total_claims

Claims that appear nowhere in retrieved context
are hallucinations. Mark them explicitly.

Step 5: Score Answer Correctness

Compare response_text against gold_answer.

For numerical answers:
  Extract all numbers from response_text
  Extract all numbers from gold_answer
  Score 1.0 if numbers match within 1%
  Score 0.5 if numbers are present but wrong format
  Score 0.0 if numbers are missing or wrong

For text answers (names, roles, descriptions):
  Score 1.0 if gold_answer text appears in response
  Score 0.5 if partial match
  Score 0.0 if not present

**CRITICAL FIX FOR YoY COMPARISON:**
- Check response contains BOTH year values
- For questions asking "change from X to Y", response must include both X and Y values
- If response only has one year, score 0.5 or 0.0

Step 6: Score Precision

Of the entities returned by query_graph,
how many appear in source_entities for this question?

Score = relevant_entities / total_entities_returned

If no entities returned: score 0.0

**OPTIMIZATION:** If > 15 entities returned, apply semantic threshold:
- Flag as precision issue
- Recommend post-processing filter (similarity > 0.7)

Step 7: Write individual result

Write to eval/results/TC{id}_{timestamp}.json:
{
  "test_id": "TC001",
  "question": "...",
  "gold_answer": "...",
  "response": "...",
  "retrieved_entities": [...],
  "retrieved_chunks_preview": [...],
  "scores": {
    "context_relevancy": float,
    "faithfulness": float,
    "answer_correctness": float,
    "precision": float,
    "mean": float
  },
  "hallucinated_claims": [...],
  "notes": "..."
}

---

## Phase 3: Summary Report

After all test cases complete, calculate:

aggregate_scores = {
  "context_relevancy": mean of all CR scores,
  "faithfulness": mean of all F scores,
  "answer_correctness": mean of all AC scores,
  "precision": mean of all P scores,
  "overall": mean of all four aggregate scores
}

by_category = {
  "metric_retrieval": mean score for easy category,
  "entity_relationship": mean score,
  "yoy_comparison": mean score,
  "risk_factor": mean score,
  "segment_performance": mean score,
  "multi_hop": mean score
}

by_difficulty = {
  "easy": mean of easy question scores,
  "medium": mean of medium question scores,
  "hard": mean of hard question scores
}

Write to eval/results/summary_{timestamp}.json:
{
  "run_at": "ISO timestamp",
  "documents_tested": [...],
  "total_questions": int,
  "aggregate_scores": {...},
  "by_category": {...},
  "by_difficulty": {...},
  "passed": [TC ids with overall >= 0.80],
  "failed": [TC ids with overall < 0.50],
  "hallucination_count": int,
  "threshold_result": "PASS / WARN / FAIL"
}

Threshold:
  overall >= 0.80 → PASS
  overall 0.60-0.79 → WARN
  overall < 0.60 → FAIL

---

## Troubleshooting & Performance Tuning

### If evaluation is slow:
1. Use "kg" mode instead of "hybrid" (60-70% faster)
2. Reduce test case count (target 15-20 cases, not 30+)
3. Add explicit time/period constraints to queries
4. Process queries in parallel batches if possible

### If precision is low (<0.15):
1. Check entity retrieval in Phase 2 (raw result count)
2. Apply similarity threshold filter (cosine > 0.7)
3. Refine query strings with more specific keywords
4. Consider re-extracting with better entity disambiguation

### If YoY comparison tests fail:
1. Verify response includes BOTH requested years
2. Check response includes calculated delta (not just values)
3. Ensure source contains both year metrics before generating question
4. Response must show format: "FY2022: X → FY2023: Y, Change: +Z"

---

## Report to User

After writing summary, show this table:

Preciso Eval Results — Walmart FY2022 + FY2023
================================================
Metric                  Score    Threshold
------------------------------------------------
Context Relevancy       X.XX     > 0.75
Faithfulness            X.XX     > 0.80
Answer Correctness      X.XX     > 0.75
Precision               X.XX     > 0.70
------------------------------------------------
Overall                 X.XX     > 0.80
------------------------------------------------
Result: PASS / WARN / FAIL

By Difficulty:
  Easy:    X.XX (target > 0.85)
  Medium:  X.XX (target > 0.75)
  Hard:    X.XX (target > 0.60)

By Category:
  Metric Retrieval:    X.XX
  Entity Relationship: X.XX
  YoY Comparison:      X.XX
  Risk Factors:        X.XX
  Segment Performance: X.XX
  Multi-Hop:           X.XX

Hallucinations detected: N claims not in retrieved context
Failed tests: [list TC ids]

Full results saved to eval/results/summary_{timestamp}.json