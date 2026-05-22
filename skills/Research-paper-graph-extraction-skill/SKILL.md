---
name: research-paper-graph-extraction
description: >
  Use this skill whenever a user wants to extract and connect knowledge from academic
  research papers, scientific literature, or multi-paper corpora for graph-based ingestion.
  Triggers include: PDFs of research papers, arXiv links, literature reviews, citation networks,
  hypothesis graphs, experiment comparisons, method lineages, or any academic/scientific text.
  Also trigger when the user says: "map citations in these papers", "connect findings across studies",
  "build a literature graph", "link hypotheses", "trace the origin of this method", "compare results
  across papers", "which papers cite each other", "extract contributions from this paper", or
  "I want to query my paper collection".
  This skill handles multi-paper corpora (a folder of papers) as well as single papers.
  Use this instead of general-graph-extraction whenever the source is academic/scientific literature.
---

# Research Paper Graph Extraction Skill

## Why This Skill Exists

Researchers and analysts reading literature face a specific problem: insights are scattered across dozens of papers, methods evolve across years, and contradictions between studies are hard to surface. This skill builds a graph that makes a paper collection *queryable* — like having a research assistant who has read everything and can answer:

- "Which papers first introduced attention mechanisms?"
- "What datasets did papers in 2022-2023 benchmark on?"
- "Which findings from Paper A were contradicted by Paper B?"
- "What methods does Method X build upon?"
- "Which authors published together across these papers?"

---

## Extraction Output Format

Write to `extractions/{source_filename}_extracted.json`.

For a single paper:
```json
{
  "source": "attention_is_all_you_need.pdf",
  "domain": "research",
  "domain_subtype": "single_paper",
  "extracted_at": "2024-10-01T00:00:00Z",
  "entities": [...],
  "relationships": [...],
  "metadata": {
    "title": "Attention Is All You Need",
    "authors": ["Vaswani et al."],
    "year": 2017,
    "venue": "NeurIPS",
    "doi": "...",
    "arxiv_id": "1706.03762",
    "field": "Machine Learning"
  }
}
```

For multi-paper corpora, produce one extraction file per paper, then run ingestion for each. The graph engine will link papers via shared citations, methods, datasets, and authors.

---

## Entity Types for Research Papers

### Core Academic Entities

| Type | Description | Example |
|------|-------------|---------|
| `PAPER` | A published or preprint work | "Attention Is All You Need" |
| `AUTHOR` | Named researcher | Ashish Vaswani |
| `INSTITUTION` | University, lab, company | Google Brain, MIT CSAIL |
| `METHOD` | Named technique or algorithm | Transformer, BERT, LoRA |
| `DATASET` | Named evaluation dataset | ImageNet, SQuAD, MMLU |
| `METRIC` | Evaluation measure | BLEU score, F1, Perplexity |
| `FINDING` | A stated result or claim | "Transformer outperforms RNN on WMT14" |
| `HYPOTHESIS` | An untested or proposed claim | "Sparse attention approximates full attention" |
| `CONCEPT` | An abstract idea or term | Self-attention, inductive bias, fine-tuning |
| `TASK` | An NLP/ML/scientific task | Machine translation, question answering |
| `VENUE` | Publication venue | NeurIPS, ICML, Nature, arXiv |
| `LIMITATION` | An acknowledged weakness | "Quadratic complexity in sequence length" |

---

## Entity Schema

```json
{
  "id": "transformer_2017",
  "type": "PAPER",
  "label": "Attention Is All You Need",
  "properties": {
    "year": 2017,
    "venue": "NeurIPS",
    "arxiv_id": "1706.03762",
    "citation_count": 95000,
    "abstract_summary": "Proposes Transformer architecture relying entirely on attention, removing recurrence and convolutions.",
    "contributions": [
      "Multi-head self-attention mechanism",
      "Positional encoding scheme",
      "Encoder-decoder Transformer architecture"
    ]
  }
}
```

For `FINDING` entities, always include `evidence_type`:
```json
{
  "id": "transformer_bleu_wmt14",
  "type": "FINDING",
  "label": "Transformer achieves 28.4 BLEU on WMT14 En-De",
  "properties": {
    "value": "28.4 BLEU",
    "dataset": "WMT 2014 English-to-German",
    "evidence_type": "empirical",
    "paper": "transformer_2017",
    "section": "Results"
  }
}
```

`evidence_type` values: `empirical`, `theoretical`, `ablation`, `observational`, `claimed`

---

## Relationship Types for Research Literature

| Relationship | Usage |
|-------------|-------|
| `AUTHORED_BY` | Paper → Author |
| `AFFILIATED_WITH` | Author → Institution |
| `PUBLISHED_IN` | Paper → Venue |
| `CITES` | Paper → Paper (source cites target) |
| `EXTENDS` | Method/Paper → Prior method/paper |
| `PROPOSES` | Paper → Method/Concept |
| `EVALUATES_ON` | Paper → Dataset |
| `REPORTS_METRIC` | Paper → Metric (with value) |
| `ACHIEVES` | Paper/Method → Finding |
| `CONTRADICTS` | Finding → Finding (conflicting results) |
| `SUPPORTS` | Finding → Hypothesis (evidence for) |
| `ADDRESSES` | Paper → Task |
| `INTRODUCES` | Paper → Concept/Dataset (first use) |
| `IMPROVES_OVER` | Method/Paper → Baseline method/paper |
| `HAS_LIMITATION` | Paper/Method → Limitation |
| `CO_AUTHORED_WITH` | Author ↔ Author |

### Relationship Schema

```json
{
  "source": "bert_2018",
  "target": "transformer_2017",
  "type": "EXTENDS",
  "properties": {
    "context": "BERT uses the Transformer encoder and extends it with masked language modeling pretraining",
    "aspect": "pretraining objective"
  }
}
```

Always include `"context"` on relationships — one sentence from the paper text justifying the connection.

---

## Multi-Paper Corpus Strategy

When given multiple papers (a folder, a bibliography, a literature review):

### Step 1 — Build the Paper Index First
Extract all `PAPER` entities with metadata before diving into content. This lets you link citations correctly.

### Step 2 — Extract Per-Paper, Then Cross-Link
For each paper:
1. Extract its entities and internal relationships
2. Identify all citations → create `CITES` relationships to other papers in the corpus
3. Flag unresolved citations (papers not in corpus) with `"in_corpus": false`

### Step 3 — Surface Cross-Paper Connections
After individual extractions, make one pass to find:
- **Shared methods**: Paper A and Paper B both evaluate `METHOD_X` → add `EVALUATES_ON` from both
- **Contradictions**: Paper A reports 92% F1 on dataset D; Paper B reports 84% F1 → add `CONTRADICTS` between findings
- **Method lineages**: Method A → Method B → Method C chain via `EXTENDS`
- **Author networks**: Authors who appear in multiple papers → `CO_AUTHORED_WITH`

---

## Extraction Precision Rules for Research

1. **Separate findings from claims**: If the paper reports an empirical result, it's a `FINDING`. If the paper proposes something unverified, it's a `HYPOTHESIS`.
2. **Metric values must include context**: `"28.4 BLEU"` alone is meaningless — always attach dataset, year, and comparison baseline.
3. **Contribution vs. claim**: Mark contributions (things the paper introduces or proves) separately from claims (things the paper asserts without full proof).
4. **Citation directionality**: `CITES` is directed. Paper A citing Paper B means A → B (A depends on B's work).
5. **Don't merge methods carelessly**: "Self-attention" in two different papers may refer to slightly different mechanisms — use paper-scoped IDs like `self_attention_vaswani_2017`.

---

## Special: Hypothesis & Argument Graphs

For theory-heavy papers (philosophy of science, formal methods, economics), extract the argument structure:

```json
{
  "entities": [
    { "id": "h1", "type": "HYPOTHESIS", "label": "Scaling laws hold for all modalities",
      "properties": { "status": "proposed", "paper": "scaling_laws_2020" } },
    { "id": "f1", "type": "FINDING", "label": "Language model loss decreases as power law of compute",
      "properties": { "evidence_type": "empirical", "paper": "scaling_laws_2020" } }
  ],
  "relationships": [
    { "source": "f1", "target": "h1", "type": "SUPPORTS",
      "properties": { "strength": "strong", "context": "Consistent across 7 orders of magnitude of compute" } }
  ]
}
```

---

## Step-by-Step Agent Workflow

```
1. READ paper(s) — abstract, introduction, related work, methods, results, conclusion
2. EXTRACT metadata block (title, authors, year, venue, DOI/arXiv)
3. PASS 1 — Named entity extraction:
   - Methods, datasets, metrics, tasks proposed or used
   - Authors and institutions
   - Prior works cited (for CITES relationships)
4. PASS 2 — Finding and hypothesis extraction:
   - Main results from abstract and results sections
   - Ablations as secondary findings
   - Limitations from limitations/conclusion sections
5. PASS 3 — Relationship extraction:
   - EXTENDS, IMPROVES_OVER for method lineage
   - CONTRADICTS for conflicting results vs. prior work
   - SUPPORTS for findings supporting hypotheses
6. For multi-paper corpora: Cross-link after individual extractions
7. VALIDATE: entity IDs consistent, no orphan relationships
8. WRITE to extractions/{filename}_extracted.json
9. CALL ingest_from_file MCP tool
```

---

## Example: Research Paper Extraction

**Input (abstract excerpt):**
> "We present BERT, a language representation model designed to pre-train deep bidirectional representations by jointly conditioning on both left and right context. BERT achieves state-of-the-art results on eleven NLP tasks, including pushing GLUE to 80.4% (+7.6% absolute improvement)."

**Output:**
```json
{
  "entities": [
    {
      "id": "bert_2018",
      "type": "PAPER",
      "label": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
      "properties": { "year": 2018, "venue": "NAACL" }
    },
    {
      "id": "bert_method",
      "type": "METHOD",
      "label": "BERT (Bidirectional Encoder Representations from Transformers)",
      "properties": { "approach": "masked language modeling + next sentence prediction" }
    },
    {
      "id": "glue_benchmark",
      "type": "DATASET",
      "label": "GLUE Benchmark",
      "properties": {}
    },
    {
      "id": "bert_glue_result",
      "type": "FINDING",
      "label": "BERT achieves 80.4% on GLUE",
      "properties": {
        "value": "80.4%",
        "dataset": "GLUE",
        "improvement": "+7.6% absolute",
        "evidence_type": "empirical"
      }
    }
  ],
  "relationships": [
    { "source": "bert_2018", "target": "bert_method", "type": "PROPOSES", "properties": {} },
    { "source": "bert_2018", "target": "glue_benchmark", "type": "EVALUATES_ON", "properties": {} },
    { "source": "bert_method", "target": "bert_glue_result", "type": "ACHIEVES", "properties": {} },
    { "source": "bert_2018", "target": "transformer_2017", "type": "EXTENDS",
      "properties": { "context": "Uses Transformer encoder with bidirectional pretraining" } }
  ]
}
```

---

## After Extraction

- Run `ingest_from_file("extractions/{filename}_extracted.json")` via MCP
- If ingestion fails, use `reingest_from_file(...)` — no re-extraction needed
- Sample queries after ingestion:
  - `"Which papers cite the Transformer paper?"`
  - `"What methods were evaluated on SQuAD?"`
  - `"Which findings contradict each other?"`
  - `"What are the limitations of BERT?"`
  - `"Who are the most prolific authors in this corpus?"`
  - `"Trace the lineage of the attention mechanism"`