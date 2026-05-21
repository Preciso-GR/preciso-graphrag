## How the Flow Works

1. Point agent at a markdown file with `skills/extraction.md` as instructions
2. Agent reads the file, extracts entities and relationships
3. Agent writes extraction to `extractions/{filename}_extracted.json`
4. Agent calls `ingest_from_file` MCP tool with that file path
5. Server reads file, validates, builds knowledge graph
6. Query with `query_graph` tool

## Re-running Ingestion Without Re-extracting

If ingestion fails but extraction file exists:
Use `reingest_from_file("extractions/{filename}_extracted.json")`
This replays ingestion without calling the agent again.
Saves time and API cost during development.

## Extraction Output Location

`extractions/`   <- all agent extraction JSON files land here
