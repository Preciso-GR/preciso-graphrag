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

Recommended agent prompt:

```text
Call get_server_status() first.
If overall is degraded, explain what is degraded, what still works, and ask whether to proceed or fix first.
Read the files in to_be_extracted/.
Choose the most appropriate extraction skill from the skills folder for each file.
Extract entities, relationships, and chunks into extractions/{source_name}_extracted.json.
Validate the extraction, reconcile if needed, then call ingest_from_file.
Finally confirm the graph artifacts written to GRAPH_IS_HERE/.
```

Expected workflow:

1. agent calls `get_server_status()`
2. if degraded, the agent explains the state and asks whether to proceed
3. raw file is read from this folder
4. the agent chooses the correct skill
5. extraction JSON is written to `extractions/`
6. MCP ingestion is called
7. graph artifacts appear in `GRAPH_IS_HERE/`
