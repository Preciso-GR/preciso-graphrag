---
name: reconciliation-subagent
description: >
  Use this skill when you are a reconciliation subagent asked to clean
  a single extraction JSON (not raw document text). Your job is to
  identify entity name variants, duplicate relationships, conflicts, or
  orphaned references and produce a patch file. Do NOT call any ingest
  tools. Do NOT rewrite the base extraction. Output must be a patch JSON
  file with merge/remove/flag directives only.
---

# Reconciliation Subagent Skill

## Agent Runtime Contract

Use this skill only after an extraction JSON already exists in `extractions/`.

Execution contract:
- Read the extraction JSON, not the original raw document in `to_be_extracted/`.
- Write only patch directives.
- Do not replace the base extraction file.
- Return control to the main agent so it can ingest the base extraction plus patch flow afterward.

## Purpose

You are a reconciliation subagent. You do data cleanup on an existing
extraction JSON. You are not extracting from the original document.
Your output is a patch file that the main agent applies before ingestion.

## Inputs You May Receive

- Entities list only
- Relationships list only
- Entities + relationships together

You will NOT receive the full document text.

## Output Patch Schema (Required)

Write a patch file with one or more of these keys:

```json
{
  "merge_entities": [
    {
      "keep": "APPLE INC",
      "remove": ["APPLE", "APPLE INC."],
      "reason": "same company, variant names"
    }
  ],
  "remove_relationships": [
    {"src_id": "APPLE INC", "tgt_id": "NET_SALES_FY2024", "keyword": "REPORTED_METRIC"}
  ],
  "flag_conflicts": [
    {
      "type": "metric_conflict",
      "details": "Net sales reported as both +2% and -1% in FY2024",
      "entities": ["NET_SALES_FY2024"],
      "relationships": [
        {"src_id": "APPLE INC", "tgt_id": "NET_SALES_FY2024", "keyword": "REPORTED_METRIC"}
      ]
    }
  ],
  "broken_relationships": [
    {"src_id": "APPLE INC", "tgt_id": "MISSING_ENTITY", "keyword": "OWNS"}
  ],
  "suggested_fixes": [
    "Consider adding entity MISSING_ENTITY or removing the relationship."
  ]
}
```

## Rules

- You are cleaning data, not extracting from documents.
- Be conservative. Only merge entities if you are certain they refer to the same real-world entity.
- For temporal entities (FY2024, Q3 2024), NEVER merge even if similar. Different periods are different entities.
- Use the exact `entity_name` values you see in the extraction.
- Do not add new entities or relationships. Only rename, remove, or flag.
- Write the patch file to the filename you were given and stop.
- Do not call any ingest tool.

## If You Are Unsure

If something is ambiguous, add it to `flag_conflicts` instead of merging.
