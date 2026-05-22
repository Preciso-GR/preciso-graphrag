---
name: general-graph-extraction
description: >
  Use this skill whenever a user wants to extract entities and relationships from
  non-financial documents to build a queryable knowledge graph. Triggers include:
  codebases and technical documentation, internal wikis, product specs, README files,
  meeting notes, support tickets, HR or policy documents, onboarding materials,
  knowledge bases, Notion/Confluence exports, API docs, and general text corpora.
  Also trigger when the user says "map dependencies in my codebase", "graph this doc",
  "extract knowledge from this wiki", "connect these notes", "build a graph from my repo",
  or "index this for querying". Use the financial-graph-extraction skill instead when
  the document is a financial filing, earnings report, or analyst document.
---

# General Graph Extraction Skill

## What This Skill Does

This skill guides an agent to read a document or codebase and produce a structured JSON extraction — entities and relationships — that can be ingested into a knowledge graph via the `ingest_from_file` MCP tool.

Unlike financial extraction (which enforces strict numerical precision), general extraction prioritizes **semantic richness and connection density** — the goal is to enable natural-language queries like:
- "What does the AuthService depend on?"
- "Which modules are owned by the payments team?"
- "What broke when we changed the database schema?"
- "Who are the experts on the recommendation engine?"

---

## Extraction Output Format

Write to `extractions/{source_filename}_extracted.json`.

```json
{
  "source": "backend_readme.md",
  "domain": "general",
  "domain_subtype": "codebase",
  "extracted_at": "2024-10-01T00:00:00Z",
  "entities": [...],
  "relationships": [...],
  "metadata": {
    "document_type": "README",
    "project": "my-backend-service",
    "language": "Python"
  }
}
```

---

## Domain Subtypes and Entity Profiles

Choose the right entity profile based on what you're processing:

### 1. Codebase / Technical Docs

| Entity Type | Examples |
|-------------|---------|
| `MODULE` | `auth_service`, `payment_processor` |
| `FUNCTION` | `validate_token()`, `create_order()` |
| `CLASS` | `UserRepository`, `InvoiceBuilder` |
| `API_ENDPOINT` | `POST /api/v2/orders` |
| `DATABASE_TABLE` | `users`, `transactions` |
| `CONFIG_KEY` | `MAX_RETRY_COUNT`, `DB_URL` |
| `DEPENDENCY` | `numpy`, `FastAPI`, `Redis` |
| `TEAM` | `Platform Team`, `Payments Squad` |
| `CONCEPT` | `idempotency`, `circuit breaker` |

Relevant relationship types: `IMPORTS`, `CALLS`, `OWNS`, `DEPENDS_ON`, `DOCUMENTS`, `IMPLEMENTS`, `EXTENDS`, `STORES_IN`, `EXPOSES`

### 2. Internal Wiki / Knowledge Base

| Entity Type | Examples |
|-------------|---------|
| `PERSON` | Sanjay Elango (author/owner) |
| `TEAM` | Backend Infrastructure |
| `PROCESS` | Deployment Pipeline, Oncall Rotation |
| `TOOL` | Datadog, PagerDuty, Terraform |
| `CONCEPT` | SLA definition, retry policy |
| `DOCUMENT` | Runbook: DB failover |
| `DECISION` | ADR-042: Use Postgres over MySQL |

Relevant relationship types: `OWNS`, `WRITTEN_BY`, `REFERENCES`, `SUPERSEDES`, `IMPLEMENTS`, `USES`, `DESCRIBES`, `DECIDES`

### 3. Meeting Notes / Tickets

| Entity Type | Examples |
|-------------|---------|
| `PERSON` | Named attendees/assignees |
| `ACTION_ITEM` | "Fix token expiry bug by Friday" |
| `DECISION` | "We'll use Redis for session storage" |
| `BLOCKER` | "Waiting on security review" |
| `PROJECT` | Project Phoenix |
| `DATE` | 2024-10-15 (target date) |

Relevant relationship types: `ASSIGNED_TO`, `BLOCKS`, `RELATES_TO`, `DECIDED_IN`, `DUE_BY`

---

## Universal Entity Schema

```json
{
  "id": "auth_service",
  "type": "MODULE",
  "label": "Authentication Service",
  "properties": {
    "language": "Python",
    "path": "services/auth/",
    "owner": "platform_team",
    "description": "Handles JWT issuance and validation",
    "tags": ["core", "security"]
  }
}
```

**Rules:**
- `id`: unique, `snake_case`, no spaces
- `label`: human-readable display name
- `properties`: flexible, add what the text provides — don't leave fields empty
- Add `"source_line"` or `"source_section"` if the document has sections/headings

---

## Universal Relationship Schema

```json
{
  "source": "order_service",
  "target": "payment_processor",
  "type": "CALLS",
  "properties": {
    "method": "charge_card()",
    "protocol": "gRPC",
    "async": true,
    "context": "Called during checkout flow"
  }
}
```

**Rules:**
- `source` and `target` must be valid entity `id` values
- `type` should be a clear verb phrase (`CALLS`, `OWNS`, `EXTENDS`)
- Add `"context"`: one sentence from the source text justifying this relationship
- Directed relationships: source → target; for bidirectional add both directions

---

## Extraction Quality Principles

### For Codebases
- Trace dependencies: what imports what, what calls what
- Map ownership: which team/person owns which module
- Surface configuration: key env vars and their consuming modules
- Capture architectural patterns mentioned (MVC, event-driven, etc.)
- Note TODOs/FIXMEs as `KNOWN_ISSUE` entities if they're significant

### For Documentation
- Every named concept becomes an entity
- Every "see also", "refer to", "documented in" becomes a `REFERENCES` relationship
- Every "owned by", "maintained by" becomes an `OWNS` relationship
- Procedural steps → sequence of `PROCESS` entities linked by `PRECEDES`

### For Notes/Tickets
- Every named person is an entity
- Every task or action item is an entity
- Capture blockers as explicit `BLOCKER` entities with `BLOCKS` relationships

---

## Extraction Density vs. Precision Trade-off

| Dimension | Financial Extraction | General Extraction |
|-----------|---------------------|--------------------|
| Precision | Exact (numbers must match) | Semantic (meaning over literal match) |
| Coverage | Deep in financial semantics | Broad across any domain |
| Ambiguity | Resolve strictly (no inference) | Light inference OK if clearly implied |
| Missing values | Leave blank, don't guess | Infer from context if confident |

In general extraction, if a README says "the auth module handles login and token refresh", it's reasonable to extract a `CONCEPT` entity `token_refresh` and link it to the auth module via `IMPLEMENTS` even if not explicitly stated that way.

---

## Step-by-Step Agent Workflow

```
1. READ the full document (or repo files in scope)
2. IDENTIFY domain subtype (codebase, wiki, notes, etc.)
3. SCAN for all named entities — people, modules, tools, concepts, processes
4. EXTRACT entities with proper types and properties
5. EXTRACT relationships by asking: "how does X relate to Y in this text?"
6. VALIDATE:
   - No entity ID duplicates
   - All relationship source/target IDs exist in entities list
   - Each entity has at least one relationship
7. WRITE to extractions/{filename}_extracted.json
8. CALL ingest_from_file MCP tool
```

---

## Example: Codebase README Extraction

**Input text:**
> "The `OrderService` module is owned by the Payments team. It calls `InventoryService` to check stock before calling `PaymentProcessor` to charge the customer. It stores order records in the `orders` table of the PostgreSQL database."

**Output:**
```json
{
  "entities": [
    { "id": "order_service", "type": "MODULE", "label": "OrderService",
      "properties": { "owner": "payments_team" } },
    { "id": "inventory_service", "type": "MODULE", "label": "InventoryService", "properties": {} },
    { "id": "payment_processor", "type": "MODULE", "label": "PaymentProcessor", "properties": {} },
    { "id": "payments_team", "type": "TEAM", "label": "Payments Team", "properties": {} },
    { "id": "orders_table", "type": "DATABASE_TABLE", "label": "orders",
      "properties": { "db": "PostgreSQL" } }
  ],
  "relationships": [
    { "source": "payments_team", "target": "order_service", "type": "OWNS", "properties": {} },
    { "source": "order_service", "target": "inventory_service", "type": "CALLS",
      "properties": { "context": "Check stock before charging customer" } },
    { "source": "order_service", "target": "payment_processor", "type": "CALLS",
      "properties": { "context": "Charge customer after stock confirmed" } },
    { "source": "order_service", "target": "orders_table", "type": "STORES_IN", "properties": {} }
  ]
}
```

---

## After Extraction

- Run `ingest_from_file("extractions/{filename}_extracted.json")` via MCP
- If ingestion fails, use `reingest_from_file(...)` to replay without re-extracting
- Sample queries after ingestion:
  - `"What does OrderService depend on?"`
  - `"Which tables does the Payments team write to?"`
  - `"Who owns InventoryService?"`