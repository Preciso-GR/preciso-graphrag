# Reviewed extraction files

This directory contains agent-produced extractions. It does not contain the raw
source documents. Keep raw source documents in `to_be_extracted/`.

Follow [document preparation](../docs/document-preparation.md) before ingestion.
Each extraction requires `document_id`, `entities`, `relationships`, and `chunks`.
Keep one extraction per source unless combined processing is explicitly requested.

Writing a file here does not create a graph. Ingestion requires an explicit tool
call. For extraction-only requests, return the file and review summary without
starting the MCP server.

Use `ingest_from_file` only within the authorized scope. It adds evidence to the
graph. It does not replace previous document contributions. Preserve the reviewed
source files separately for a later rebuild.

Generated extractions are ignored by Git. Do not commit private source content.
