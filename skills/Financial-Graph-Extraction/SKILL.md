---
name: financial-graph-extraction
description: >
  Use this skill whenever a user wants to extract entities and relationships from
  financial documents for graph-based ingestion in this repo. Triggers include: 10-K or
  10-Q filings, earnings call transcripts, analyst reports, investor presentations,
  SEC filings, financial news articles, risk disclosures, balance sheets, income
  statements, MD&A sections, or any structured/unstructured financial text.
  Also trigger when the user says things like "build a graph from this report",
  "map the relationships in this filing", "connect entities in this earnings call",
  "I want to query this financial doc", or "extract for graph-rag".
  This skill enforces HIGH PRECISION extraction — financial data must be factually exact,
  numerically grounded, and relationship-typed with financial semantics. Always use this
  over the general extraction skill when the source material is financial in nature.
  Output must follow the GraphRAG ingestion schema: document_id + entities + relationships + chunks,
  with chunk-based source_id values.
---

# Financial Graph Extraction Skill

## Why This Skill Exists

Financial analysts read enormous volumes of documents — 10-Ks, earnings transcripts, research notes — to surface connections between companies, people, risks, and metrics. This skill turns that reading into a structured knowledge graph that an agent can query with precision.

Financial extraction demands **higher fidelity than general text** because:
- Numbers, dates, and percentages must be exact (no approximation)
- Entity disambiguation matters (Apple Inc. ≠ Apple the fruit; Tim Cook as CEO ≠ Tim Cook as person)
- Relationships carry financial weight (subsidiary, acquired, guarantees, competes with)
- Temporal context is critical (Q3 2024 revenue ≠ Q3 2023 revenue)

---

## Extraction Output Format (Repo-Compatible)

Always write to `extractions/{source_filename}_extracted.json`.

This repo **requires** `document_id`, `entities`, `relationships`, and `chunks`.

```json
{
  "document_id": "apple_10k_2024",
  "file_path": "apple_10k_2024.pdf",
  "timestamp": 1727740800,
  "entities": [...],
  "relationships": [...],
  "chunks": [...]
}
```

### Chunks (Required)
Chunks are the evidence base. Every entity and relationship must point to a chunk via `source_id`.

```json
{
  "chunk_id": "chunk_003",
  "content": "Net sales increased 2 percent or $7.8 billion during 2024 compared to 2023.",
  "chunk_order_index": 3,
  "file_path": "apple_10k_2024.pdf"
}
```

---

## Entity Types for Financial Documents

Extract the following entity types with strict typing:

### Core Entity Types

| Type | Description | Example |
|------|-------------|---------|
| `COMPANY` | Legal corporate entity | Apple Inc., Foxconn Technology Group |
| `PERSON` | Named individual with role | Tim Cook (CEO), Luca Maestri (CFO) |
| `FINANCIAL_METRIC` | Quantitative figure | Revenue $394.3B, Net Income $97B, EPS $6.16 |
| `PRODUCT_LINE` | Named revenue segment | iPhone, Mac, Services, Wearables |
| `GEOGRAPHIC_SEGMENT` | Revenue or ops region | Americas, Greater China, Europe |
| `RISK_FACTOR` | Disclosed risk | Supply chain concentration, FX exposure, litigation |
| `LEGAL_ENTITY` | Subsidiary or JV | Apple Operations International Ltd |
| `REGULATION` | Named law or standard | ASC 606, GDPR, Sarbanes-Oxley |
| `TRANSACTION` | M&A, investment, divestiture | Acquired Beats Electronics for $3B |
| `DATE_PERIOD` | Fiscal period | FY2024, Q3 2024, YE September 28 2024 |

### Entity Schema (Required Fields)

```json
{
  "entity_name": "apple_inc",
  "entity_type": "COMPANY",
  "description": "Apple Inc. (AAPL) is a consumer electronics company with FY end in September.",
  "source_id": "chunk_001",
  "file_path": "apple_10k_2024.pdf"
}
```

For `FINANCIAL_METRIC`, keep **all numeric detail inside `description`** so ingestion preserves it:

```json
{
  "entity_name": "net_sales_fy2024",
  "entity_type": "FINANCIAL_METRIC",
  "description": "Total net sales were $391,035 million for FY2024 (YoY +2.0%; source section MD&A).",
  "source_id": "chunk_003",
  "file_path": "apple_10k_2024.pdf"
}
```

---

## Relationship Types for Financial Documents

Relationships use `src_id` and `tgt_id` (entity_name values). Encode relationship type and qualifiers in `keywords`.

### Relationship Type Keywords (Controlled Vocabulary)

| Keyword | Usage |
|---------|-------|
| `EMPLOYS` | Company → Person (with role) |
| `SUBSIDIARY_OF` | Legal entity → Parent company |
| `ACQUIRED` | Company → Target (with date, value) |
| `COMPETES_WITH` | Company ↔ Company |
| `SUPPLIES_TO` | Supplier → Customer |
| `REPORTED_METRIC` | Company → Financial metric |
| `OPERATES_IN` | Company → Geographic segment |
| `EXPOSED_TO` | Company/Segment → Risk factor |
| `GOVERNED_BY` | Company/Practice → Regulation |
| `ISSUED` | Company → Debt/Equity instrument |
| `AUDITED_BY` | Company → Audit firm |
| `MENTIONS` | Document section → Any entity |

### Relationship Schema (Required Fields)

```json
{
  "src_id": "apple_inc",
  "tgt_id": "tim_cook",
  "description": "Tim Cook served as Chief Executive Officer of Apple Inc. (since 2011; FY2024).",
  "keywords": "EMPLOYS,role=Chief Executive Officer,period=FY2024",
  "source_id": "chunk_014",
  "weight": 1.0,
  "file_path": "apple_10k_2024.pdf"
}
```

Always attach `period` or `as_of` in `description` or `keywords` for relationships that change over time.

---

## Precision Rules (Non-Negotiable)

1. **Exact numbers**: Copy figures verbatim from the source. Never round unless the source rounds.
2. **Units always present**: Put units directly in `description` (e.g., `$391,035 million`).
3. **Period always present**: Every metric must reference a fiscal period in `description` or `keywords`.
4. **Disambiguate entities**: If "the Company" refers to Apple Inc., resolve it. Don't leave pronouns.
5. **No inference beyond the text**: If the document does not say X acquired Y, don't add that relationship.
6. **Source section tagging**: Add `source_section=...` in `keywords` or `description`.
7. **Conflicting data**: If two sections report different values for the same metric, create separate entities (e.g., `net_sales_fy2024_mda`, `net_sales_fy2024_financials`) and mark `conflict=true` in `keywords`.
8. **Evidence linkage**: Every entity and relationship must use a `source_id` that matches a real `chunk_id` in `chunks`.

---

## Analyst-Oriented Extraction Focus

When processing financial documents, prioritize connections analysts actually query:

### Tier 1 — Always Extract
- Executive team (name, title, compensation, tenure)
- Revenue by segment (product line + geography)
- Key metrics: revenue, gross margin, operating income, net income, EPS, FCF
- Debt structure: long-term debt, credit facilities, maturities
- Top risks disclosed in Risk Factors section
- Auditor and audit opinion
- Related-party transactions

### Tier 2 — Extract When Present
- Customer concentration (if any customer > 10% revenue)
- Supplier/manufacturing dependencies
- Pending litigation with materiality estimates
- Off-balance-sheet arrangements
- Goodwill and intangibles by acquisition
- Share repurchase programs

### Tier 3 — Extract for Deep Analysis
- Non-GAAP reconciliation items
- Geographic revenue breakdowns
- Employee headcount and changes
- Capital expenditure breakdown
- Lease obligations schedule

---

## Step-by-Step Agent Workflow

```
1. READ the document in full (or in chunked passes for long filings)
2. IDENTIFY document type (10-K, 10-Q, earnings transcript, etc.)
3. CHUNK the text into evidence blocks (sections, paragraphs, or tables)
   - Assign chunk_id like chunk_001, chunk_002...
4. EXTRACT metadata for document_id + file_path
5. PASS 1 — Entity extraction:
   - Scan for all named companies, people, metrics, segments, risks
   - Assign entity_name (snake_case, unique within the file)
   - Set source_id to the chunk_id that contains the evidence
6. PASS 2 — Relationship extraction:
   - For each entity pair, determine if a typed relationship exists in the text
   - Encode relationship type in keywords (EMPLOYS, ACQUIRED, etc.)
   - Attach period/as_of in description or keywords
7. PASS 3 — Validation:
   - All entities have entity_name, entity_type, description, source_id
   - All relationships have src_id, tgt_id, description, source_id
   - No entity_name is duplicated
   - No relationship references an undefined entity_name
   - Every source_id matches an existing chunk_id
8. WRITE to extractions/{filename}_extracted.json
9. CALL ingest_from_file MCP tool with the output path
```

---

## Common Financial Document Patterns

### 10-K Structure Mapping
```
Item 1 (Business)        → COMPANY, PRODUCT_LINE, GEOGRAPHIC_SEGMENT, COMPETES_WITH
Item 1A (Risk Factors)   → RISK_FACTOR, EXPOSED_TO
Item 7 (MD&A)            → FINANCIAL_METRIC, REPORTED_METRIC, trends
Item 8 (Financial Stmts) → FINANCIAL_METRIC (authoritative source)
Item 9A (Controls)       → REGULATION, GOVERNED_BY
Proxy Statement          → PERSON, EMPLOYS, compensation
```

### Earnings Call Transcript Pattern
- Speaker turns → `PERSON` entities with `EMPLOYS` linking to company
- Guidance → `FINANCIAL_METRIC` with `period=FY2025E` in description/keywords (E = estimate)
- Analyst questions → tag `source_section=Q&A` in keywords

---

## Example Extraction (Apple 10-K Excerpt)

**Input text:**
> "Apple's net sales increased 2 percent or $7.8 billion during 2024 compared to 2023. iPhone net sales decreased 1 percent or $2.0 billion during 2024 compared to 2023."

**Output:**
```json
{
  "document_id": "apple_10k_2024",
  "file_path": "apple_10k_2024.pdf",
  "timestamp": 1727740800,
  "chunks": [
    {
      "chunk_id": "chunk_003",
      "content": "Apple's net sales increased 2 percent or $7.8 billion during 2024 compared to 2023. iPhone net sales decreased 1 percent or $2.0 billion during 2024 compared to 2023.",
      "chunk_order_index": 3,
      "file_path": "apple_10k_2024.pdf"
    }
  ],
  "entities": [
    {
      "entity_name": "apple_inc",
      "entity_type": "COMPANY",
      "description": "Apple Inc. is the reporting company referenced in the 2024 filing.",
      "source_id": "chunk_003",
      "file_path": "apple_10k_2024.pdf"
    },
    {
      "entity_name": "iphone",
      "entity_type": "PRODUCT_LINE",
      "description": "iPhone product line referenced in the net sales discussion.",
      "source_id": "chunk_003",
      "file_path": "apple_10k_2024.pdf"
    },
    {
      "entity_name": "net_sales_fy2024_change",
      "entity_type": "FINANCIAL_METRIC",
      "description": "Net sales increased 2% or $7.8B during 2024 compared to 2023 (source_section=MD&A).",
      "source_id": "chunk_003",
      "file_path": "apple_10k_2024.pdf"
    },
    {
      "entity_name": "iphone_net_sales_fy2024_change",
      "entity_type": "FINANCIAL_METRIC",
      "description": "iPhone net sales decreased 1% or $2.0B during 2024 compared to 2023 (source_section=MD&A).",
      "source_id": "chunk_003",
      "file_path": "apple_10k_2024.pdf"
    }
  ],
  "relationships": [
    {
      "src_id": "apple_inc",
      "tgt_id": "net_sales_fy2024_change",
      "description": "Apple Inc. reported a net sales increase in 2024 compared to 2023.",
      "keywords": "REPORTED_METRIC,period=FY2024_vs_FY2023,source_section=MD&A",
      "source_id": "chunk_003",
      "weight": 1.0,
      "file_path": "apple_10k_2024.pdf"
    },
    {
      "src_id": "iphone",
      "tgt_id": "iphone_net_sales_fy2024_change",
      "description": "iPhone net sales decreased in 2024 compared to 2023.",
      "keywords": "REPORTED_METRIC,period=FY2024_vs_FY2023,source_section=MD&A",
      "source_id": "chunk_003",
      "weight": 1.0,
      "file_path": "apple_10k_2024.pdf"
    }
  ]
}
```

---

## After Extraction

- Run `ingest_from_file("extractions/{filename}_extracted.json")` via MCP
- If ingestion fails but extraction file exists, use `reingest_from_file(...)` — no re-extraction needed
- Sample queries to verify the graph:
  - `"What was Apple's revenue in FY2024?"`
  - `"Who are Apple's top executives and their compensation?"`
  - `"What are the top 5 risk factors disclosed?"`
  - `"Which segments saw revenue decline?"`

---

## Multi-Document and Large Document Handling

### When to work alone (default)

Work alone when:
- Single document under 50 pages
- Under 15 sections
- Straightforward flat structure

Alone workflow:
  Read fully → extract → write → ingest_from_file → done

---

### When to spawn subagents

Spawn subagents when:
- Single document over 50 pages OR over 15 sections
- Multiple documents given at once (2 or more files)
- You notice context is filling up mid-document

---

### Orchestrator workflow (you are the orchestrator)

Step 1: Read first 50 lines of the document only.
        Count section headers (## and ### markers).
        Estimate total length.

Step 2: Divide sections into groups.
        Each group: 10 to 12 sections maximum.
        Each group: under 3000 tokens if possible.
        Name groups: part1, part2, part3...

Step 3: Spawn one subagent per group.
        Give each subagent:
          - The text content of their assigned sections only
          - This same skill file as their instructions
          - Their output filename:
            extractions/{original_filename}_part{n}_extracted.json
          - This strict rule:
            "DO NOT call ingest_from_file or any ingest tool.
             Write your output file and report complete."

Step 4: Wait for ALL subagents to finish before proceeding.
        Do not call any tool until every subagent reports complete.

Step 5: Call ingest_with_reconciliation with all part files:
        ingest_with_reconciliation([
          "extractions/{filename}_part1_extracted.json",
          "extractions/{filename}_part2_extracted.json",
          ...all part files...
        ])

Step 6: Wait for response.

Step 7: Report final summary to user:
        - Files reconciled: N
        - Duplicate entities merged: N
        - Total entities added: N
        - Total relationships added: N
        - Unified file location: extractions/reconciled_{filename}_{ts}.json

---

### Subagent rule (when you are a subagent)

You are a subagent if:
- Your assigned output filename contains _part
- You were given a specific section range to process
- You were told not to call ingest tools

When you are a subagent:
  - Extract ONLY your assigned sections
  - Do not reference or look up other sections
  - Do not call ingest_from_file
  - Do not call ingest_with_reconciliation
  - Do not call any MCP ingest tool
  - Write your output file to the filename you were given
  - When done, report exactly:
    "Extraction complete: {your_output_filename}
     Entities extracted: {count}
     Relationships extracted: {count}"
  - Stop. Do nothing else.

---

### Entity registry rule for subagents

When you are a subagent you only see your sections.
If you encounter a pronoun or reference like
"the Company", "its subsidiary", "the aforementioned entity"
and you cannot resolve it from your sections alone:

  Create the entity anyway with description:
  "Referenced in document. Details in another section."

The reconciler will merge it with the fully-described
version from another subagent's output.

Do not skip entities because they lack full context.
Extract what you can. The reconciler fixes the rest.
