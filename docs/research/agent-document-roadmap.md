# Agent-connected document workflow: research and proposed design

Checked: 2026-10-16. Baseline application commit: `35fcf08`.
Purpose: define seamless agent connection, automation, control, and coordination.
Status: research and design only. No application feature in this proposal is implemented.

## Main recommendation

Keep PRECISO an agent-facing GraphRAG MCP server. The host agent plans document
work and uses its existing model for extraction and synthesis. PRECISO supplies
structured operations, persistent evidence, bounded execution, and recovery rules.

Do not promise autonomous processing merely because a client connects through MCP.
The host must expose tools to its agent, grant the requested access, and run the
reasoning loop. A disconnected host does not leave an agent reasoning inside PRECISO.

## What exists and what is missing

| Area | Repository evidence | Gap for seamless use |
|---|---|---|
| Connection | `src/preciso_mcp/server.py` exposes 11 tools over stdio | Selected client onboarding and compatibility still need end-to-end validation |
| Packaging | Installed wheel, local launcher, Docker runtime | No single published server installer or universal client registration flow was verified |
| Workflow instructions | `skills/` and `docs/document-preparation.md` | Agent needs repository files; instructions are not exposed through MCP |
| Inputs | Extraction JSON/Markdown/text, bounded file access | No raw-document registration, read interface, or built-in PDF conversion |
| Extraction | External agent produces structured records | No MCP-visible extraction contract or preparation state |
| Ingestion | Additive merge, record validation, transaction rollback | No complete document-revision lifecycle or safe replacement operation |
| Results | Query evidence in `raw_data`, tool dictionaries | Broad result types and varying empty/error shapes need a stable agent contract |
| Recovery | Transaction journal, ownership locks, verified offline backup | Transaction recovery is not a resumable end-to-end document job |

These observations describe the application. They do not establish that external
users have adopted it or that every client supports the same MCP features.

## Related systems

- **Graphiti MCP:** its published tool interface covers adding memory, searching
  nodes and facts, episode provenance, episode deletion, and status. GraphRAG or
  graph memory over MCP already exists. Novelty cannot rest on that label alone.
  [First-party MCP documentation](https://github.com/getzep/graphiti/blob/main/mcp_server/README.md)
- **LightRAG MCP:** a separate bridge exposes text insertion, document status,
  retry, document deletion, and structured queries. This is evidence that agents
  benefit from document lifecycle operations as well as search. The bridge is a
  separate project, not proof of an official upstream MCP implementation.
  [Bridge repository](https://github.com/d8corp/lightrag-mcp)
- **LightRAG processing design:** its document-processing specification separates
  parsing, optional analysis, chunking, extraction, status, and resume behavior.
  The page describes a v1.5.0 development pipeline. Treat it as design evidence,
  not a tested released baseline for PRECISO.
  [Upstream pipeline specification](https://github.com/HKUDS/LightRAG/blob/main/docs/FileProcessingPipeline.md)
- **Docling:** its project documents document conversion, a common document
  representation, local execution, OCR, and MCP integration. Evaluate a parser
  adapter or composition through the host agent before adding those dependencies
  to PRECISO's default image. Runtime cost and accuracy remain unmeasured here.
  [Project documentation](https://github.com/docling-project/docling)

These projects were inspected through documentation. No competitor was installed
or benchmarked. No superiority or uniqueness claim is established.

## Responsibility boundary

| Actor | Responsibility |
|---|---|
| Human | Select document scope, permissions, provider choices, and automation policy |
| Host agent | Plan the task, read instructions, extract records, compare sources, and synthesize an answer |
| PRECISO | Validate tool inputs, enforce scope and budgets, preserve revisions and evidence, execute graph operations, and report outcomes |
| Optional parser | Convert a supported raw format into text and source locations |

Host-provided extraction can avoid requiring an additional generation model inside
PRECISO. It still uses host-model tokens. Embeddings still need a configured provider.
A parser needs explicit support for the selected formats. MCP alone supplies neither.

## Proposed minimal workflow

```text
Connect once
    → Discover capabilities and workflow
    → Register selected document text or a scoped source reference
    → Read bounded document sections and extraction instructions
    → Host agent extracts records
    → Validate extraction without graph mutation
    → Commit the validated document revision
    → Query evidence and read cited source passages
```

Provide instructions and schema through MCP rather than filesystem-only skill paths.
Resources and prompts can help, but host behavior varies. Keep essential information
available through tool results for clients that do not automatically fetch resources
or invoke prompts. Prompts do not automatically execute a workflow.
[Official server concepts](https://modelcontextprotocol.io/docs/2026-07-28/learn/server-concepts)

Proposed logical operations, not committed API names:

| Operation | Agent-facing outcome |
|---|---|
| Describe capabilities/workflow | Supported formats, limits, extraction schema, available operations, and next steps |
| Prepare document | Stable document ID, content hash, revision, and readable sections |
| Read document sections | Bounded text with stable section or span identities |
| Validate extraction | Structured errors and warnings; no graph mutation |
| Commit extraction | Explicit revision, operation ID, counts, and committed state |
| Query evidence | Compact evidence, source revisions, references, and limits |
| Read evidence | Original passage and source locator for a returned reference |
| Inspect operation | Persisted state and actionable recovery information, when long jobs justify it |

Reuse existing ingestion/query internals and preserve existing tool names during a
compatibility period. Avoid adding one public tool for every internal helper.

## Coordination rules

Proposed document states:

```text
REGISTERED → TEXT_READY → EXTRACTED → VALIDATED → COMMITTED
                         failures → FAILED
                         cancellation → CANCELLED
```

The server owns the persisted state. The host agent requests transitions through
tools. The server rejects a transition when its required state or revision is missing.

- Record the source content hash and extraction revision.
- Require validation of the same revision before commit.
- Use an idempotency key to identify repeated requests. Return the completed result
  for an identical retry. Reject the same key with different content.
- Detect unchanged documents before repeated extraction and embedding.
- Detect changed sources. Initially stage the change and report that replacement
  requires rebuild. Do not silently treat additive ingestion as document replacement.
- Preserve per-document contributions before implementing safe replacement or deletion.
  Shared entities and summaries must retain contributions from remaining documents.
- Keep revision state and graph publication consistent. The existing transaction
  artifact list and backup list must include any new authoritative state.
- Track operation progress and retries without retaining unlimited output or work.
- Bound document bytes, section reads, extraction records, embedding work, and retries.
- Keep source content as data. Source instructions cannot change tool permissions.

For small documents, retain bounded request/response operations. Add persistent jobs
only when measured duration and disconnect behavior require them. No new database,
message broker, or additional agent is required by this proposed first slice.

An evaluator timeout must be reported as not evaluated. Retrieved passages must not
be labeled semantically supported solely because they pass a similarity threshold.

## Connection and compatibility

Connection success is not workflow success. A user should register the server once,
select a document scope, and issue an ordinary document task. The agent should not
need the user to name tools or copy extraction instructions on every request.

Test one named client/version first. Keep local stdio as the initial supported path.
Validate installed-package startup without relying on repository working-directory
assumptions. Test host and Docker document access separately. A host attachment or
local path is not automatically a readable path inside the server container.

The installed SDK reports `mcp 1.27.2`, supporting protocol revisions through
2025-11-25. Official current documentation identifies 2026-07-28 and substantial
protocol changes. Specify the client/SDK pair actually tested. Do not silently mix
message formats or require deprecated sampling/roots for the core workflow.
See [MCP capability research](mcp-document-capabilities.md) for exact sources.

## Delivery order and acceptance

1. **Connection and tool contracts.** Capture actual discovery and success/error
   results in the selected client. Define typed results and useful error codes.
   Success: invalid input is recognized as failure without user interpretation.
2. **MCP-visible preparation.** Expose preparation instructions, schema, and bounded
   text access. Success: the agent processes a tiny known source without repository
   filesystem access or manual tool-name coaching.
3. **Document identity and replay.** Add hashes, revision guards, and a document
   record. Success: identical retries do not duplicate records or embeddings;
   changed content is reported explicitly.
4. **Evidence navigation.** Add source readback and compact result limits. Success:
   the agent retrieves and cites the exact original evidence for an answer.
5. **Interruption and lifecycle.** Test cancellation, reconnection, and recovery.
   Add safe update/delete only with contribution tracking and shared-record tests.
6. **Additional formats and sources.** Add parser and connector adapters for actual
   requested formats. Keep large parsing/model dependencies outside the core image.

The first acceptance fixture should contain a supported fact, a negated fact, and
an unsupported question. Run it through discovery, preparation, validation, commit,
query, and citation. Repeat an identical call and interrupt one operation. Test
unavailable embeddings and an inaccessible source. These are proposed tests, not
completed results.

Measure task completion, manual interventions, tool-call count, output tokens,
source-reference correctness, unsupported answers, retry correctness, latency,
and memory. Compare the current workflow against the first improved slice on the
same client and documents. Broader quality still needs a reviewed held-out corpus.

## Scope decision

A useful product promise is: connect an agent to a lightweight, persistent document
knowledge tool with explicit evidence and recoverable operations. This is a proposed
positioning statement. User feedback and comparisons must validate its value.

“Fully automated for all external documents” is too broad to validate. Start with
supported text documents and explicit source permissions. Expand the format and
client matrix after the same end-to-end acceptance workflow passes.
