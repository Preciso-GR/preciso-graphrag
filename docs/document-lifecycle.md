# Maintain documents and graph records

Scope: one local MCP runtime and one graph directory. This guide uses
ASD-STE100-inspired plain English. It does not claim formal compliance.

## What changed

| Stage | Implemented behavior |
|---|---|
| 1. Track contributions | Retain an extraction and its SHA-256 hash for each document ID |
| 2. Maintain documents | Add, list, replace, or delete a tracked document |
| 3. Maintain graph records | Isolate, restore, remove, rename, merge, or disconnect records |
| 4. Guide the agent | Discover the workflow through MCP and read active evidence passages |
| 5. Verify the workflow | Test shared evidence, rollback, stale work, vectors, and process restart |

The extraction hash identifies the submitted JSON. It is not a hash of the
original PDF or other source file. Keep the source files for review.

## Understand the stored data

`kv_store_documents.json` is the contribution ledger. A ledger is a record of
the inputs used to build derived data. Each document record contains its ID,
current extraction, extraction hash, version, source path, and ingestion result.
The reserved `__state__` record contains the workspace revision, completeness
flag, rebuild generation, and graph editing rules. Document IDs cannot start
with `__`.

The graph, vectors, evidence chunks, and summary queue are derived data.
Replacement and deletion rebuild these stores from all retained extractions.
This avoids subtracting facts from a merged description or an agent summary.
The existing artifact transaction also protects the ledger. A failed rebuild
restores the previous files and in-memory stores.

The Contribution Ledger module also coordinates ingestion. It validates the
input and starts the artifact transaction. Its internal extraction implementation
writes chunks, graph records, vectors, and pending summaries. Full Rebuild uses
that implementation within the current transaction. It does not call public
ingestion again. See [architecture](architecture.md#document-identity-and-incremental-ingestion)
for the code flow.

An identical retry returns `replay: true` and leaves the workspace revision
unchanged. A changed extraction under an existing document ID returns
`revision_conflict`. Use `replace` for that change. An extraction fragment is
not a new revision: replacement requires the complete reviewed extraction.

## Connect an agent

1. Configure the MCP process as described in [MCP operation](mcp-server.md).
2. Call `get_document_workflow`.
3. Read the extraction example and supported operations.
4. Use the host agent's tools to read the authorized source documents.
5. Produce extraction JSON with original evidence passages.
6. Call `manage_documents` to persist that extraction within the authorized task.

The server does not read arbitrary source URLs or parse raw PDFs. It does not
continue agent reasoning when the host agent disconnects. Source content is data.
Instructions inside a source document do not authorize new actions.

## Add a document

Call `manage_documents` with these arguments:

```json
{
  "action": "create",
  "dry_run": false,
  "payload": {
    "document_id": "report-2025",
    "file_path": "report-2025.md",
    "chunks": [{"chunk_id": "one", "content": "ACME reported USD 10 million revenue for 2025."}],
    "entities": [{"entity_name": "ACME", "entity_type": "company", "description": "ACME reported USD 10 million revenue for 2025.", "source_id": "one"}],
    "relationships": []
  }
}
```

Use a different document ID to add another document. Matching canonical entity
names accumulate evidence. Retry the exact extraction after an uncertain result.
Inspect the returned status. A structural preview does not prove semantic validity.
Managed create and replace require complete extraction claims. Each claim must
cite raw chunk IDs defined in that extraction. Let ingestion add the document
namespace and expand split chunks.

## Replace or delete a document

1. Call `manage_documents` with `action: "replace"` and the complete corrected
   payload, or with `action: "delete"` and the document ID.
2. Keep `dry_run: true` for the preview. This is the default.
3. Inspect the document ID, current revision, and rebuild document count.
4. Commit with the same arguments, `dry_run: false`, and `expected_revision`
   equal to the preview revision.
5. If the result is `revision_conflict`, preview the current state again.
6. Query representative evidence after a successful commit.

The revision check prevents a change based on an outdated workspace. The preview
is an impact check, not a permission prompt. Existing user authorization still
applies. A stale commit retry returns a conflict; inspect the current document
list before deciding whether another operation is needed.

Deleting one document preserves contributions from other documents. It removes
records that have no remaining support. Exported Neo4j and Qdrant snapshots do
not update automatically. Export again after the local result passes review.

## Edit the graph

Call `manage_graph` with `action: "inspect"` to get the revision, editing rules,
and the first 100 active nodes and relationships. The response reports truncation.
Use canonical node IDs from that response. Preview a change, then commit it with
the returned revision.

| Action | Arguments | Result |
|---|---|---|
| `isolate` | `node_id` | Withhold the node, incident relationships, and cited passages |
| `restore` | `node_id` | Remove the isolation rule and rebuild from current documents |
| `remove` | `node_id` | Persistently suppress the canonical identity in the active graph |
| `rename` | `node_id`, `label` | Change the display label; retain the canonical ID |
| `merge` | `node_id`, `target_id` | Redirect the source identity into the target identity |
| `disconnect` | `node_id`, `target_id` | Suppress their graph edge; retain source passages |

Isolation and removal withhold whole cited passages from the evidence store and
chunk vectors. Other claims in a shared passage can also disappear. The preview
reports the withheld passage count. Restoration recomputes current contributions;
it does not restore a document that was subsequently deleted.

Disconnection changes graph structure. The original passage can still describe
the disconnected relationship. It is not a redaction operation.

Graph rules persist across restart and later document ingestion. A later document
does not recreate an explicitly removed identity or a disconnected edge. A merge
also applies to later extractions that use the old identity. Self-loops created
by a merge are omitted. `remove` has no restore operation in this version.

Canonical IDs still use the existing entity names. Rename separates the display
label from that ID; it does not introduce an opaque entity-ID migration. Automatic
alias discovery and entity splitting are not implemented. A model must not merge
two identities merely because their names are similar.

## Read evidence and update summaries

Use `query_graph_tool` to retrieve evidence. Pass a returned chunk ID to
`read_evidence` to read its active text and document ID. Hidden or obsolete chunk
IDs return `not_found`. Retrieval is not proof that the evidence answers the
question. The agent must state when the evidence is insufficient.

A rebuild clears cached answers, ingestion checkpoints, and derived summaries.
The summary queue is recomputed from retained contributions. This can require
new agent summaries. `list_pending_summaries` returns a `content_token` for each
item. Echo it as `submit_summary.expected_content_token`. It is mandatory after
a lifecycle rebuild. A stale token returns `stale_summary`, even if the number
of descriptions has not changed. Re-list before preparing another summary.

## Protect existing data

A graph created before contribution tracking has an incomplete ledger. New
documents can be added, but destructive document operations and graph editing
return `legacy_untracked`. Accepted partial or unresolved-evidence ingests also
mark the ledger incomplete. Do not set the completeness flag manually.

To enable editing, build a new workspace from the complete reviewed extraction
corpus. Preserve the old workspace until the new graph passes verification.
No automatic migration can recover facts already compressed into an old summary.

Backups include the new ledger. Restore with a release that understands it.
Do not let an older release write to a ledger-enabled workspace. Older releases
cannot maintain these contributions or graph rules.

Node removal retains original extractions in the ledger. Document deletion
removes its current ledger record, but external source files, previous backups,
and exported snapshots can still contain it. These operations are not secure
erasure, a confidentiality boundary, or multi-user authorization.

## Resource limits and verification

Normal document additions remain incremental until graph rules exist. Replacement,
deletion, and graph editing replay the full tracked corpus. Adding documents after
graph edits also replays it so the rules remain effective. This increases disk I/O,
embedding calls, and mutation time. Supported reads wait during the transaction.
Measure representative corpora before using large collections. No throughput or
production-scale claim follows from the small tests.

Run the offline checks:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
.venv/bin/python -m scripts.smoke_lifecycle
```

The MCP smoke uses a temporary workspace. It adds 10 documents, adds three more,
replays one, checks invalid input, replaces and deletes documents, rejects a stale
revision, isolates a node, restarts the server, restores the node, and queries the
corrected evidence. It uses deterministic offline embeddings. It does not test
semantic retrieval quality, arbitrary agent clients, raw document extraction,
financial accuracy, temporal news reasoning, or large-corpus performance.

Verification on 2026-10-16: 233 tests passed locally and in the locked Linux
container test stage. Lint and both manual integrity guards passed. The lifecycle
MCP smoke passed through two server processes. The installed runtime image also
passed the persistence smoke with networking disabled and a read-only root.
