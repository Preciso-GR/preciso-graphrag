# Financial Extraction Skill

Process one document at a time.

## Reading Rules

Read the input file sequentially in bounded sections.
Prefer section boundaries from headings, tables, notes, or page breaks.
If a section is still too large, split it again into smaller bounded blocks.

## Extraction Rules

Return strict JSON with:

- `chunks`
- `entities`
- `relationships`

Each entity must include:

- `entity_name`
- `entity_type`
- `description`
- `source_id`
- `file_path`

Each relationship must include:

- `src_id`
- `tgt_id`
- `description`
- `keywords`
- `weight`
- `source_id`
- `file_path`

## Consistency Rules

Maintain one canonical entity registry for the current document.
Do not create duplicate aliases when the entity clearly refers to the same financial concept.
Use the same entity name across all extracted sections of the document.

## MCP Call Rules

Do not ingest per sentence or per paragraph.
Finish the document extraction first.
Call `ingest_graph` once with the unified extraction payload for that document.
