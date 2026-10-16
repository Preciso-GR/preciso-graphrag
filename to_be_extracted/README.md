# to_be_extracted

Drop raw source material here before asking an agent to run the workflow.

Good inputs:

- `.md` and `.txt` files
- READMEs, technical docs, wikis, notes, and codebase-adjacent text
- financial filings and earnings transcripts that have already been converted to text or markdown
- research material that is already in a text-first format

For better graph quality, prefer `.md` and `.txt` inputs.

Warning:
Preciso does not include built-in PDF parsing or OCR. PDFs are discouraged in the default workflow unless you convert them first or rely on an external agent with strong native PDF support.

Preparation procedure: [mechanism 0](../docs/document-preparation.md).

For extraction-only work, use this prompt:

```text
Read the selected files in to_be_extracted/.
Follow docs/document-preparation.md and the appropriate extraction skill.
Write one extraction JSON per source in extractions/.
Check evidence wording, entity identities, relationship endpoints, and chunk references.
Show record counts, validation results, and unresolved concerns.
Do not call ingestion tools or start the MCP server.
```

Graph creation is a separate action. If ingestion is authorized, check server
status and call ingest_from_file with the reviewed extraction path. Existing
files are not processed automatically.
