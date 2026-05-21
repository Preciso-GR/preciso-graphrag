# Financial Extraction Skill

Process one document at a time.

## Reading Rules

Read the input file sequentially in bounded sections.
Prefer section boundaries from headings, tables, notes, or page breaks.
If a section is still too large, split it again into smaller bounded blocks.

## Output Instructions

Step 1: After reading and extracting the complete file,
write your extraction output to:
  extractions/{original_filename}_extracted.json

Use exactly this JSON format:
{
  "source_file": "original_filename.md",
  "extracted_at": "2025-05-21T10:30:00",
  "document_id": "original_filename_001",
  "entities": [
    {
      "entity_name": "ENTITY NAME IN UPPERCASE",
      "entity_type": "company|person|metric|instrument|date_period|risk_factor|regulation|market|transaction",
      "description": "factual description, 1-2 sentences",
      "source_id": "chunk_001"
    }
  ],
  "relationships": [
    {
      "src_id": "SOURCE ENTITY NAME",
      "tgt_id": "TARGET ENTITY NAME",
      "keywords": "comma, separated, relationship, keywords",
      "description": "description of this relationship",
      "weight": 0.0,
      "source_id": "chunk_001"
    }
  ],
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "content": "the original text this was extracted from",
      "file_path": "original_filename.md"
    }
  ]
}

Step 2: After writing the file successfully, call:
  ingest_from_file("extractions/{original_filename}_extracted.json")

Rules:
  - Write the file BEFORE calling ingest_from_file
  - Call ingest_from_file ONCE per document
  - Do NOT call ingest_from_file if file write failed
  - All src_id and tgt_id values must exactly match
    an entity_name in your entities list
  - entity_name must be UPPERCASE
  - weight must be between 0.1 and 1.0
