---
name: graph-eval
description: >
  AGENT-BASED evaluation framework for knowledge graphs.
  Automatically generates test questions, queries the graph,
  calculates metrics, and produces evaluation reports.
  Run ONLY after ingestion. Full pipeline execution.
  Handles embedding mismatches. Production-ready.
---

# Graph Evaluation Skill — Agent-Based Full Pipeline

## Purpose

**Automated evaluation framework** that executes end-to-end:
- Generates test questions from extraction JSON
- Executes queries directly against knowledge graph via MCP
- Auto-calculates metrics (relevancy, faithfulness, correctness, precision)
- Produces evaluation reports with pass/fail determinations
- Detects and reports embedding/vector DB issues

This is an **agent-only** workflow (not for manual execution).

---

## Agent Workflow Overview

```
┌─────────────────────────────────────────┐
│ STEP 0: PRE-FLIGHT CHECK                │
│ - Call get_server_status()              │
│ - Verify entities > 0                   │
│ - Detect embedding dimension mismatches │
│ - Abort if critical issues found        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ STEP 1: QUESTION GENERATION             │
│ - Read extraction JSON files            │
│ - Generate 20-25 test questions         │
│ - Assign difficulty/category            │
│ - Save test_cases.json                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ STEP 2: PARALLEL QUERY EXECUTION        │
│ - For each test case:                   │
│   • Select query mode (kg/hybrid)       │
│   • Call query_graph_tool (MCP)         │
│   • Capture retrieved entities/chunks   │
│   • Store raw response                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ STEP 3: AUTO METRIC CALCULATION         │
│ - Context Relevancy (0-1)               │
│ - Faithfulness (0-1)                    │
│ - Answer Correctness (0-1)              │
│ - Precision (0-1)                       │
│ - Write individual TC result JSON       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ STEP 4: REPORT GENERATION               │
│ - Aggregate scores by metric            │
│ - Group by category & difficulty        │
│ - Detect hallucinations                 │
│ - Produce summary + tables              │
│ - PASS/WARN/FAIL determination          │
└─────────────────────────────────────────┘
```

---

## Step 0: Pre-Flight Check

### Vector DB / Embedding Dimension Mismatch Handling

**Problem:** You may see `.dim-mismatch-XXXX.bak` files in `GRAPH_IS_HERE/` indicating vector DB state corruption.

**Agent Action:**

```python
# BEFORE running queries, check:
status = call(graphrag_mcp_get_server_status)

if status['error']:
    ABORT: "MCP server not running"
    
if status['graph']['entities'] == 0:
    ABORT: "No entities ingested. Run ingestion first."
    
if status['has_dimension_mismatch']:
    WARN: "Dimension mismatch detected in vector DB"
    ACTION: Clear backup files and reingest
    → Delete: vdb_*.dim-mismatch-*.bak
    → Call: mcp_reingest_from_file() if needed
    
if status['entities'] > 0 and status['relationships'] > 0:
    PROCEED: "Graph ready for evaluation"
```

**Key:** Do not attempt queries if vector dimension mismatch exists; reingest first.

---

## Agent Implementation Guide

### Required MCP Tools (Agent Must Call)

```
1. graphrag-mcp-get_server_status
   - Check graph health, entity counts
   - Detect embedding mismatches
   - Called once at start (Step 0)

2. graphrag-mcp-query_graph_tool
   - Execute queries during evaluation loop
   - Called once per test case (Step 2)
   - Payload: {"query": "...", "mode": "kg|hybrid|global"}
   - Returns: entities[], relationships[], text_chunks[], references[]

3. (Optional) graphrag-mcp-reingest_from_file
   - Called only if dimension mismatch detected
   - Recovers vector DB state
```

### Agent Pseudocode — Full Pipeline

```python
def evaluate_knowledge_graph(extraction_files, output_dir):
    """
    Automated eval agent. Execute all steps sequentially.
    """
    
    # STEP 0: PRE-FLIGHT
    print("▶ Step 0: Pre-flight validation...")
    status = call_mcp(graphrag_mcp_get_server_status)
    
    if status.entities == 0:
        return ERROR("No entities. Ingest first.")
    
    if status.has_dim_mismatch:
        print("⚠ Dimension mismatch detected. Recovering...")
        call_mcp(graphrag_mcp_reingest_from_file, extraction_files[0])
        status = call_mcp(graphrag_mcp_get_server_status)
    
    print(f"✓ Graph ready: {status.entities} entities, {status.relationships} relationships")
    
    # STEP 1: GENERATE QUESTIONS
    print("▶ Step 1: Generating test questions...")
    test_cases = generate_test_questions(extraction_files)
    save_json(f"{output_dir}/test_cases_{timestamp}.json", test_cases)
    print(f"✓ Generated {len(test_cases)} questions")
    
    # STEP 2: EXECUTE QUERIES
    print("▶ Step 2: Executing queries...")
    results_jsonl = f"{output_dir}/evaluation_results_{timestamp}.jsonl"
    
    with open(results_jsonl, 'w') as f:
        for i, tc in enumerate(test_cases, 1):
        # Determine query mode based on question type
        mode = "kg" if tc["difficulty"] == "easy" else "hybrid"
        if "compare" in tc["question"].lower():
            mode = "global"  # YoY uses global mode
        
        print(f"  [{i}/{len(test_cases)}] {tc['id']}: {tc['question'][:60]}...")
        
        # Call MCP query tool
            response = call_mcp(
            graphrag_mcp_query_graph_tool,
            query=tc["question"],
            mode=mode
        )
        
        # Store raw response
            result = execute_and_score_test_case(tc, response, mode)
            f.write(json.dumps(result) + '\n')
    
    print(f"✓ Executed queries, results streamed to {results_jsonl}")
    
    # STEP 3: CALCULATE METRICS
    print("▶ Step 3: Calculating metrics...")
    print("✓ Metrics calculated and streamed to JSONL")
    
    # STEP 4: GENERATE REPORT
    print("▶ Step 4: Generating evaluation report...")
    summary = generate_summary_report(results_jsonl)
    save_json(f"{output_dir}/results/summary_{timestamp}.json", summary)
    
    print("\n" + "="*60)
    print_report_table(summary)
    print("="*60)
    
    if summary["threshold_result"] == "PASS":
        print("✓ EVALUATION PASSED")
    else:
        print("⚠ EVALUATION WARNING / FAILED")
    
    return summary
```

---

## Step 1: Test Question Generation

Agent reads extraction JSON files and generates test cases programmatically.

### Question Template Library

**EASY (Direct Lookup)**
```
metric_retrieval:
  template: "What was {company} {metric} for {period}?"
  gold_answer: {value from entity}

entity_relationship:
  template: "Who is the {role} of {company}?"
  gold_answer: {person name from EMPLOYS relationship}
```

**MEDIUM (Aggregation/Filtering)**
```
segment_performance:
  template: "What was {company}'s {segment} revenue in {period}?"
  gold_answer: {metric value}

risk_factor:
  template: "What are {company}'s {risk_type} risks?"
  gold_answer: {risk description}

yoy_comparison:
  template: "How did {metric} change from {year1} to {year2}?"
  gold_answer: "Changed from {X} to {Y}, delta {+/- Z} ({pct}%)"
  NOTE: Response MUST include BOTH years + delta
```

**HARD (Multi-Hop)**
```
multi_hop:
  template: "Which of {company}'s {segment} executives has {attribute}?"
  gold_answer: {person name}
  NOTE: Requires entity → relationship → entity → relationship chain
```

### Generation Rules

Agent should:
- Read all extraction JSON in `extractions/`
- Extract all `FINANCIAL_METRIC`, `RISK_FACTOR`, `PRODUCT_LINE`, `GEOGRAPHIC_SEGMENT`, `PERSON`, `EMPLOYS` entities
- Generate at least:
  - 5-6 easy questions (metric_retrieval, entity_relationship)
  - 4-5 medium questions (segment, risk, yoy)
  - 3-4 hard questions (multi-hop)
  - **Total: 15-20 questions per extraction pair**

### Test Case JSON Schema

```json
{
  "generated_at": "2026-05-30T12:00:00Z",
  "source_extractions": ["extractions/WALMART_2022_10K_extracted.json"],
  "total_cases": 18,
  "test_cases": [
    {
      "id": "TC001",
      "question": "What were Walmart's net sales in FY2023?",
      "gold_answer": "$611.3 billion",
      "source_entities": ["NET SALES FY2023"],
      "source_chunks": ["chunk_012"],
      "category": "metric_retrieval",
      "difficulty": "easy",
      "requires_yoy": false,
      "query_hints": "financial metric, net sales, fiscal 2023"
    },
    {
      "id": "TC010",
      "question": "How did Walmart's net sales change from FY2022 to FY2023?",
      "gold_answer": "Increased from $572.8B to $611.3B (+$38.5B, +6.7%)",
      "source_entities": ["NET SALES FY2022", "NET SALES FY2023"],
      "source_chunks": ["chunk_008", "chunk_012"],
      "category": "yoy_comparison",
      "difficulty": "medium",
      "requires_yoy": true,
      "query_hints": "comparison, year-over-year, fiscal 2022 2023"
    }
  ]
}
```

Save to: `evals/test_cases_{timestamp}.json`

---

## Step 2: Direct Query Execution & Metrics Calculation

Agent loops through test cases and **immediately calculates metrics** for each query result.

### Query Mode Selection (Automatic)

```python
def select_query_mode(test_case):
    question = test_case["question"].lower()
    
    # YoY comparisons need relationship edge traversal
    if any(x in question for x in ["compare", "change", "yoy", "year over"]):
        return "global"
    
    # Entity relationships use graph traversal
    if test_case["category"] in ["entity_relationship", "segment_performance"]:
        return "kg"
    
    # Multi-hop reasoning
    if test_case["category"] == "multi_hop":
        return "hybrid"
    
    # Default: fast path
    return "kg"
```

### Metric Calculation Functions

**1. Context Relevancy Score (0-1)**

```python
def score_context_relevancy(test_case, query_response):
    """
    Did retrieved chunks contain information to answer question?
    """
    source_chunks = set(test_case.get("source_chunks", []))
    retrieved_chunks = set(c.get("id") for c in query_response["text_chunks"])
    
    if not source_chunks:
        # No source chunks specified; check if ANY chunks were returned
        return 1.0 if len(retrieved_chunks) > 0 else 0.0
    
    overlap = len(source_chunks & retrieved_chunks)
    partial_match = len([c for c in query_response["text_chunks"] 
                        if any(s in c.get("content", "") 
                               for s in test_case["gold_answer"].split()[:5])])
    
    if overlap > 0:
        return 1.0
    elif partial_match > 0:
        return 0.7
    else:
        return 0.0
```

**2. Faithfulness Score (0-1)**

```python
def score_faithfulness(test_case, query_response):
    """
    What % of claims in response are backed by retrieved context?
    Detects hallucinations.
    """
    # For now, if response is not provided yet, estimate from chunks
    # This will be calculated after LLM response is generated
    
    retrieved_text = " ".join([c.get("content", "") 
                               for c in query_response["text_chunks"]])
    
    # Check if gold answer values appear in retrieved context
    gold_values = extract_key_facts(test_case["gold_answer"])
    backed_values = sum(1 for v in gold_values if v in retrieved_text)
    
    if len(gold_values) == 0:
        return 1.0
    
    return backed_values / len(gold_values)
```

**3. Answer Correctness Score (0-1)**

```python
def score_answer_correctness(test_case, query_response):
    """
    Does the gold answer match what the query returned?
    """
    retrieved_entities = query_response.get("entities", [])
    retrieved_text = " ".join([c.get("content", "") 
                               for c in query_response["text_chunks"]])
    
    gold_answer = test_case["gold_answer"].lower()
    
    # For numerical answers: check if numbers match
    gold_numbers = extract_numbers(gold_answer)
    text_numbers = extract_numbers(retrieved_text)
    
    if gold_numbers:
        matches = [n for n in text_numbers if is_close(n, gold_numbers[0], pct=0.01)]
        return 1.0 if matches else 0.0
    
    # For text answers: check substring presence
    if gold_answer in retrieved_text.lower():
        return 1.0
    elif any(part in retrieved_text.lower() for part in gold_answer.split()):
        return 0.5
    else:
        return 0.0
```

**4. Precision Score (0-1)**

```python
def score_precision(test_case, query_response):
    """
    Of entities returned, how many are relevant to the question?
    """
    source_entities = set(test_case.get("source_entities", []))
    retrieved_entities = set(e.get("entity_name") for e in query_response.get("entities", []))
    
    if len(retrieved_entities) == 0:
        return 0.0
    
    # Direct match
    relevant = len(source_entities & retrieved_entities)
    
    # Semantic match (entity type alignment)
    semantic_relevant = sum(1 for e in query_response.get("entities", [])
                           if is_semantically_relevant(e, test_case))
    
    total_relevant = max(relevant, semantic_relevant)
    
    # Penalize over-retrieval
    if len(retrieved_entities) > 15:
        return total_relevant / (len(retrieved_entities) * 1.5)  # 1.5x penalty
    
    return min(1.0, total_relevant / len(retrieved_entities))
```

### Full Query + Metrics Loop (Streaming to JSONL)

```python
def execute_evaluation_suite(test_cases, mcp_tools, output_jsonl):
    """
    Execute all test cases, stream results to JSONL.
    Returns aggregated metrics for final summary.
    """
    results_list = []
    
    with open(output_jsonl, 'a') as f:
        for i, test_case in enumerate(test_cases, 1):
            result = execute_and_score_test_case(test_case, mcp_tools)
            results_list.append(result)
            
            # Append to JSONL immediately (streaming)
            f.write(json.dumps(result) + '\n')
            
            # Progress indicator
            status_char = "✓" if result["scores"]["mean"] >= 0.80 else "✗"
            print(f"  [{i}/{len(test_cases)}] {status_char} {result['id']}")
    
    return results_list

def execute_and_score_test_case(test_case, mcp_tools):
    """
    Execute one test case: query → collect chunks → calculate metrics
    """
    # 1. Call MCP query tool
    mode = select_query_mode(test_case)
    response = mcp_tools.call(
        "graphrag-mcp-query_graph_tool",
        query=test_case["question"],
        mode=mode
    )
    
    if response["status"] != "success":
        return {
            "id": test_case["id"],
            "question": test_case["question"],
            "gold_answer": test_case["gold_answer"],
            "scores": {
                "context_relevancy": 0.0,
                "faithfulness": 0.0,
                "answer_correctness": 0.0,
                "precision": 0.0,
                "mean": 0.0
            },
            "error": response.get("message", "Query failed"),
            "status": "ERROR"
        }
    
    # 2. Calculate metrics
    scores = {
        "context_relevancy": score_context_relevancy(test_case, response),
        "faithfulness": score_faithfulness(test_case, response),
        "answer_correctness": score_answer_correctness(test_case, response),
        "precision": score_precision(test_case, response)
    }
    
    # 3. Aggregate
    scores["mean"] = mean(scores.values())
    
    # 4. Detect hallucinations
    hallucinations = detect_hallucinations(test_case, response, scores)
    
    # 5. Package result
    result = {
        "id": test_case["id"],
        "category": test_case.get("category"),
        "difficulty": test_case.get("difficulty"),
        "question": test_case["question"],
        "gold_answer": test_case["gold_answer"],
        "query_mode": mode,
        "retrieved_entities_count": len(response.get("entities", [])),
        "retrieved_chunks_count": len(response.get("text_chunks", [])),
        "scores": scores,
        "hallucinations": hallucinations,
        "status": "PASS" if scores["mean"] >= 0.80 else "FAIL"
    }
    
    return result
```

**Output format:** `evals/results/evaluation_results_{timestamp}.jsonl`

**Each line is a complete test result:**
```jsonl
{"id":"TC001","category":"metric_retrieval","difficulty":"easy","question":"What were Walmart's net sales in FY2023?","gold_answer":"$611.3 billion","query_mode":"kg","retrieved_entities_count":3,"retrieved_chunks_count":2,"scores":{"context_relevancy":1.0,"faithfulness":1.0,"answer_correctness":1.0,"precision":0.95,"mean":0.9875},"hallucinations":[],"status":"PASS"}
{"id":"TC002","category":"entity_relationship","difficulty":"easy","question":"Who is the CEO of Walmart?","gold_answer":"Doug McMillon","query_mode":"kg","retrieved_entities_count":2,"retrieved_chunks_count":1,"scores":{"context_relevancy":1.0,"faithfulness":1.0,"answer_correctness":1.0,"precision":0.9,"mean":0.975},"hallucinations":[],"status":"PASS"}
{"id":"TC003","category":"yoy_comparison","difficulty":"medium","question":"How did Walmart's net sales change from FY2022 to FY2023?","gold_answer":"Increased from $572.8B to $611.3B (+$38.5B, +6.7%)","query_mode":"global","retrieved_entities_count":4,"retrieved_chunks_count":3,"scores":{"context_relevancy":0.95,"faithfulness":0.95,"answer_correctness":0.9,"precision":0.85,"mean":0.9125},"hallucinations":[],"status":"PASS"}
```

**Advantages:**
- ✓ Append incrementally (can resume if interrupted)
- ✓ Stream process with `jq` or pandas
- ✓ Single file for archival/version control
- ✓ Load all results: `df = pd.read_json('results.jsonl', lines=True)`
- ✓ Aggregate easily: `df.groupby('category')['scores.mean'].mean()`

---

## Step 4: Automated Summary Report Generation

Agent aggregates all individual test results and produces final report.

### Aggregation Function

```python
def generate_summary_report(scored_results):
    """
    Aggregate individual test scores into summary statistics.
    """
    
    # By Metric
    metrics = ["context_relevancy", "faithfulness", "answer_correctness", "precision"]
        metrics = ["context_relevancy", "faithfulness", "answer_correctness", "precision"]
        aggregate_scores = {
            m: mean([r["scores"][m] for r in results]) 
            for m in metrics
        }
    aggregate_scores["overall"] = mean(aggregate_scores.values())
    
    # By Category
        categories = set(r.get("category") for r in results)
    by_category = {
            cat: mean([r["scores"]["mean"] for r in results 
                   if r.get("category") == cat])
                for cat in categories
            }
    
    # By Difficulty
        difficulties = set(r.get("difficulty") for r in results)
    by_difficulty = {
            diff: mean([r["scores"]["mean"] for r in results 
                    if r.get("difficulty") == diff])
                for diff in difficulties
            }
    
    # Test Status
        passed = [r["id"] for r in results if r["scores"]["mean"] >= 0.80]
        failed = [r["id"] for r in results if r["scores"]["mean"] < 0.50]
    
    # Hallucinations
        hallucination_count = sum(
            len(r.get("hallucinations", [])) for r in results
        )
    
    # Threshold Determination
        if aggregate_scores["overall"] >= 0.80:
            threshold_result = "PASS"
        elif aggregate_scores["overall"] >= 0.60:
            threshold_result = "WARN"
        else:
            threshold_result = "FAIL"
    
    return {
            "run_at": datetime.now().isoformat(),
            "results_file": jsonl_file,
            "total_questions": len(results),
            "documents_tested": extract_docs(results),
            "aggregate_scores": aggregate_scores,
            "by_category": by_category,
            "by_difficulty": by_difficulty,
            "passed": passed,
            "failed": failed,
            "hallucination_count": hallucination_count,
            "threshold_result": threshold_result,
            "query_modes_used": extract_query_modes(results)
        }
```

### Summary Report JSON

```json
{
  "run_at": "2026-05-30T13:45:22Z",
  "total_questions": 18,
    "results_file": "evals/results/evaluation_results_20260530T134500_0530.jsonl",
  "documents_tested": [
    "WALMART_2022_10K_extracted.json",
    "WALMART_2023_10K_extracted.json"
  ],
  "aggregate_scores": {
    "context_relevancy": 0.92,
    "faithfulness": 0.88,
    "answer_correctness": 0.85,
    "precision": 0.81,
    "overall": 0.87
  },
  "by_category": {
    "metric_retrieval": 0.94,
    "entity_relationship": 0.91,
    "yoy_comparison": 0.78,
    "risk_factor": 0.85,
    "segment_performance": 0.82,
    "multi_hop": 0.68
  },
  "by_difficulty": {
    "easy": 0.93,
    "medium": 0.83,
    "hard": 0.70
  },
  "passed": ["TC001", "TC002", "TC003", "TC004", "TC005", "TC006", "TC007", "TC008", "TC009", "TC010", "TC011", "TC012", "TC013", "TC014", "TC015"],
  "failed": ["TC016"],
  "hallucination_count": 1,
  "threshold_result": "PASS",
  "query_modes_used": {
    "kg": 10,
    "hybrid": 5,
    "global": 3
  }
}
```

**Files generated:**
- `evals/results/evaluation_results_{timestamp}.jsonl` ← all test results (one JSON per line)
- `evals/results/summary_{timestamp}.json` ← aggregated metrics + report

**Example: Query test results from JSONL:**
```bash
# See all failed tests
jq 'select(.status=="FAIL")' evals/results/evaluation_results_*.jsonl

# Get average score by category
jq -s 'group_by(.category) | map({category: .[0].category, avg: (map(.scores.mean) | add/length)})' evals/results/evaluation_results_*.jsonl

# Load in Python
import pandas as pd
df = pd.read_json('evals/results/evaluation_results_*.jsonl', lines=True)
print(df.groupby('category')['scores'].apply(lambda x: x.apply(lambda y: y['mean']).mean()))
```

### Report Output (Console)

```
╔════════════════════════════════════════════════════════════════╗
║           PRECISO GRAPH EVALUATION REPORT                      ║
║              Walmart FY2022 + FY2023                           ║
╚════════════════════════════════════════════════════════════════╝

EXECUTION SUMMARY
─────────────────────────────────────────────────────────────────
Total Questions:       18
Documents Tested:      2
Query Modes:           kg: 10, hybrid: 5, global: 3
Duration:              ~45 seconds
Status:                ✓ COMPLETE

AGGREGATE SCORES (Threshold)
─────────────────────────────────────────────────────────────────
Metric                      Score    Target    Result
─────────────────────────────────────────────────────────────────
Context Relevancy           0.92     > 0.75    ✓ PASS
Faithfulness                0.88     > 0.80    ✓ PASS
Answer Correctness          0.85     > 0.75    ✓ PASS
Precision                   0.81     > 0.70    ✓ PASS
─────────────────────────────────────────────────────────────────
OVERALL SCORE               0.87     > 0.80    ✓✓ PASS
─────────────────────────────────────────────────────────────────

PERFORMANCE BY DIFFICULTY
─────────────────────────────────────────────────────────────────
Easy (Metric + Entity):     0.93 / 1.0  (6 questions)   ✓ EXCELLENT
Medium (Aggregation):       0.83 / 1.0  (8 questions)   ✓ GOOD
Hard (Multi-Hop):           0.70 / 1.0  (4 questions)   ⚠ FAIR
─────────────────────────────────────────────────────────────────

PERFORMANCE BY CATEGORY
─────────────────────────────────────────────────────────────────
Metric Retrieval            0.94 ✓
Entity Relationship         0.91 ✓
YoY Comparison              0.78 ⚠  (needs 2-year extraction)
Risk Factor                 0.85 ✓
Segment Performance         0.82 ✓
Multi-Hop Reasoning         0.68 ⚠  (requires chain traversal)
─────────────────────────────────────────────────────────────────

ISSUES & RECOMMENDATIONS
─────────────────────────────────────────────────────────────────
Hallucinations:            1 claim not in context
  - TC016: "Doug McMillon is CEO since 2014" (date not in extraction)

Tests Passed:              17/18 (94%)
Tests Failed:              1/18 (6%)

Precision Issues:          2 tests returned > 15 entities
  - TC009: 22 entities (apply similarity threshold > 0.7)
  - TC014: 18 entities (recommend entity filtering)

RECOMMENDATIONS
─────────────────────────────────────────────────────────────────
✓ Knowledge graph quality is EXCELLENT

Consider:
  1. For multi-hop questions, results improve with relationship
     pre-filtering (reduce candidate set before traversal)
  2. YoY comparison mode ("global") performs slightly lower —
     may indicate sparse COMPARED_TO edges in graph
  3. Entity over-retrieval (>15 results) — apply semantic
     similarity threshold (cosine > 0.7) in query post-processing

Next Steps:
  → Ingest additional reference documents
  → Tune entity disambiguation in extraction phase
  → Consider relationship type pre-filtering for complex queries

═══════════════════════════════════════════════════════════════════
```

---

## Troubleshooting & Recovery

### Issue: Embedding Dimension Mismatch

**Symptom:** Files like `vdb_entities.json.dim-mismatch-1780127123.bak` exist in `GRAPH_IS_HERE/`

**Agent Recovery:**
1. Call `get_server_status()` — confirm the issue
2. Stop MCP server
3. Delete all `.dim-mismatch-*.bak` files
4. Restart MCP server
5. Call `reingest_from_file()` on original extraction JSON
6. Verify with `get_server_status()` → entities > 0
7. Retry evaluation

### Issue: Query Returns 0 Entities

**Symptom:** One or more queries return empty entity lists

**Root Cause:** Entity not in graph or query string mismatch

**Agent Action:**
- Log query string and gold_answer
- Verify entity exists in extraction JSON
- Try alternate query string (e.g., "Walmart" → "WMT")
- Mark test case as "INCONCLUSIVE" not "FAIL"
- Report entity extraction gaps to ingestion phase

### Issue: Low Precision (> 20 entities returned)

**Symptom:** Tests return more than 15 entities consistently

**Agent Action:**
- Apply post-query filtering: keep top 8 by semantic similarity
- Reduce token usage by capping entity results
- Log "precision_issue" flag in summary
- Recommend entity disambiguation in extraction

### Issue: YoY Comparison Tests Consistently Fail

**Symptom:** Category `yoy_comparison` scores < 0.60

**Root Cause:** Response doesn't include BOTH years + delta

**Agent Action:**
- Verify query response includes both year values
- Check gold_answer format includes delta calculation
- Ensure extraction JSON has metrics for BOTH fiscal years
- Re-generate test case if source data incomplete

---

## Performance Targets

| Metric | Target | Comment |
|--------|--------|---------|
| Overall Score | ≥ 0.80 | PASS threshold |
| Context Relevancy | ≥ 0.85 | Should be near-perfect |
| Faithfulness | ≥ 0.80 | No hallucinations acceptable |
| Answer Correctness | ≥ 0.80 | Accurate extraction validated |
| Precision | ≥ 0.70 | Avoid massive over-retrieval |
| Easy Questions | ≥ 0.90 | Direct lookups should excel |
| Medium Questions | ≥ 0.75 | Aggregation queries |
| Hard Questions | ≥ 0.60 | Multi-hop reasoning is challenging |

---

## Agent Checklist

Before running evaluation:

- [ ] Extraction JSON files exist in `extractions/`
- [ ] MCP server is running
- [ ] `get_server_status()` returns entities > 0
- [ ] No embedding dimension mismatches
- [ ] Output directories writable (`evals/results/`)
- [ ] Timestamp generation available (ISO format)

During execution:

- [ ] Generate test cases first
- [ ] Validate test case count (15-20 recommended)
- [ ] For each query, capture full response (entities, chunks, relationships)
- [ ] Calculate all 4 metrics for each test
- [ ] Write individual TC results immediately (don't batch)
- [ ] Detect hallucinations as you go

After execution:

- [ ] Aggregate scores match individual scores
- [ ] Summary JSON includes all required fields
- [ ] Console report displays pass/fail determinations
- [ ] Failed test cases documented with root cause
- [ ] Recommendations section populated
- [ ] Files saved to correct output paths

---

## Summary

**This is a production-grade, agent-only evaluation framework that:**

✓ Handles embedding mismatches gracefully  
✓ Generates questions programmatically from extractions  
✓ Executes queries with automatic mode selection  
✓ Calculates 4 metrics per query automatically  
✓ Aggregates results into comprehensive reports  
✓ Detects hallucinations and precision issues  
✓ Provides actionable recommendations  
✓ Works fully autonomously (no manual intervention)

**To invoke:** Call the agent and pass extraction file paths + output directory.

**Output:** Full evaluation suite saved to `evals/results/`