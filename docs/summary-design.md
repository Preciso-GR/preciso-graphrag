# Agent-written summary maintenance

This guide uses ASD-STE100-inspired plain English. It does not claim formal
compliance.

## Purpose

Several documents can contribute descriptions to the same entity or relationship.
PRECISO preserves the newest extracted descriptions and asks the connected agent
to summarize older descriptions. The server does not call a language model to
write summaries.

An extracted description is not the original evidence passage. Source chunks and
the Contribution Ledger remain separate from the derived summary field.

## Ownership and flow

| Module | Responsibility |
|---|---|
| `core.summary` | Partition descriptions, check budgets, and maintain pending-work records |
| `core.summary_maintenance` | List current work, check freshness, and publish reviewed agent summaries |
| `core.documents` | Own the ledger and expose its rebuild generation |
| `preciso_mcp.server` | Register MCP tools and forward requests and results |

The old `preciso_mcp.tools.pending_summaries_tool` imports remain available.
They refer to the same core list and submit functions. They contain no summary
policy or persistence coordination.

```text
Extraction merge -> summary policy -> pending queue
Agent -> list_pending_summaries -> core prepares current work
Agent writes summary
Agent -> submit_summary -> core checks freshness
                       -> transaction publishes graph, vector, and queue changes
```

Both merging and summary submission use the same pending-work policy. The summary
workflow reads rebuild generation through the ledger's public metadata accessor.
It does not read private ledger state.

## Description storage

The graph description can contain two zones:

```text
<<SUM>> One rolling summary of older extracted descriptions
<SEP> Recent extracted description
<SEP> Another recent extracted description
```

The marker identifies a derived summary. It is not source evidence. Legacy fields
without a marker contain only extracted descriptions. Duplicate raw descriptions
are removed while preserving their original order.

A merge stores the descriptions verbatim. If their count exceeds `raw_tail_size`
or their token count exceeds `summary_context_size`, it marks the record pending.
It does not silently generate or truncate a summary.

## List pending work

Call `list_pending_summaries`. Each item includes:

- The entity name or relationship endpoints.
- The current `description_count`.
- A `content_token` and its requirement flag.
- The prior rolling summary.
- Older extracted descriptions to summarize.
- Recent extracted descriptions to keep verbatim.

The queue identifies work. The current graph supplies the actual descriptions.
The workflow recomputes the item when it is listed.

## Submit reviewed work

1. Write a summary of the older descriptions and prior rolling summary.
2. Preserve dates, units, uncertainty, and conflicting claims.
3. Call `submit_summary` with the item's identity, summary text, description count,
   and `content_token` as `expected_content_token`.
4. Inspect the returned status.
5. If the evidence changed, list the current work again before preparing another
   submission.

The content token depends on the description and rebuild generation. A document
replacement can change the evidence without changing the description count.
The generation prevents an old submission from passing that equal-count case.

A content token is mandatory after a lifecycle rebuild. Before the first rebuild,
legacy callers can omit it and use the description-count check. New callers should
always echo it. Retry acceptance still depends on the current freshness checks.

## Publish the result

The core workflow starts an artifact transaction. It checks freshness, stores one
rolling summary, retains the recent descriptions verbatim, updates the matching
entity or relationship vector, and updates the pending queue.

If the remaining description is still over its configured bounds, the record
stays pending. A failed publication restores the previous files and in-memory
stores. The MCP adapter does not apply these rules itself.

## Marker and size limits

The stored graph keeps the internal `<<SUM>>` marker. Derived vector content,
query descriptions, and export properties strip it with
`core.utils.strip_summary_marker`. Original evidence chunks remain separate.

If submitted summary text exceeds `summary_context_size`, the workflow trims
that text to `summary_max_tokens`. Shorter submissions remain unchanged. Recent
descriptions can themselves exceed the budget, so the whole field has no
unconditional hard size guarantee. Over-budget records remain pending.

Document replacement, deletion, and graph editing rebuild derived descriptions
from retained extraction contributions and invalidate old summaries. See
[document lifecycle](document-lifecycle.md).

## Verification

Run the offline checks from the repository root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python tests/manual/summary_merge_manual.py
.venv/bin/python tests/manual/marker_leak_manual.py
.venv/bin/python -m scripts.smoke_summaries
```

The tests cover recent-description retention, stale counts and tokens, marker
stripping, entity and relationship updates, and rollback after pending-queue
publication fails. The MCP smoke also checks restart persistence and fresh
submission after document replacement. It uses temporary data and deterministic
offline embeddings. It does not evaluate the factual quality of an agent's prose.
