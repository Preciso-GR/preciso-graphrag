"""
reconciler.py

Reconciles multiple subagent extraction outputs into a single
unified extraction dict ready for ingestion.

Called by ingest_with_reconciliation MCP tool.
"""

import re
import time
from collections import defaultdict


def _normalize(name: str) -> str:
    """
    Normalize entity name for comparison.
    Uppercase, remove punctuation, collapse spaces.
    """
    name = name.upper().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def collect_all_entities(extraction_list: list[dict]) -> list[dict]:
    """
    Flatten all entities from all subagent extractions into one list.
    Tag each with _source_file for traceability.
    """
    all_entities = []
    for extraction in extraction_list:
        source_file = extraction.get("file_path", "unknown")
        for entity in extraction.get("entities", []):
            entity = dict(entity)
            entity["_source_file"] = source_file
            all_entities.append(entity)
    return all_entities


def _find_canonical_groups(names: list[str]) -> dict[str, str]:
    """
    Three-pass canonical name resolution:
    Pass 1: Exact match after normalization
    Pass 2: Substring containment
    Pass 3: Known abbreviation patterns (INC/INCORPORATED etc)

    Returns dict mapping variant_name -> canonical_name
    Always keeps the longer/more specific name as canonical.
    """
    result = {}

    normalized = {name: _normalize(name) for name in names}

    # Pass 1: exact match after normalization
    norm_to_canonical = {}
    for name, norm in normalized.items():
        if norm not in norm_to_canonical:
            norm_to_canonical[norm] = name
        else:
            existing = norm_to_canonical[norm]
            if len(name) > len(existing):
                norm_to_canonical[norm] = name
                result[existing] = name
            else:
                result[name] = existing

    # Pass 2: substring containment
    canonical_names = list(norm_to_canonical.values())
    for i, name_a in enumerate(canonical_names):
        for name_b in canonical_names[i + 1 :]:
            norm_a = _normalize(name_a)
            norm_b = _normalize(name_b)
            if (
                norm_a in norm_b
                and name_a not in result
                and len(norm_a) >= 10
                and len(norm_a.split()) >= 2
            ):
                result[name_a] = name_b
            elif (
                norm_b in norm_a
                and name_b not in result
                and len(norm_b) >= 10
                and len(norm_b.split()) >= 2
            ):
                result[name_b] = name_a

    # Pass 3: known abbreviation patterns
    abbreviation_patterns = [
        ("INCORPORATED", "INC"),
        ("CORPORATION", "CORP"),
        ("LIMITED", "LTD"),
        ("INTERNATIONAL", "INTL"),
    ]
    for name in canonical_names:
        norm = _normalize(name)
        for long_form, short_form in abbreviation_patterns:
            if long_form in norm:
                variant_norm = norm.replace(long_form, short_form)
                if len(variant_norm) <= 4:
                    continue
                for other_name in canonical_names:
                    if _normalize(other_name) == variant_norm and other_name not in result:
                        result[other_name] = name

    return result


def _resolve_canonical_chains(canonical_map: dict[str, str]) -> dict[str, str]:
    """
    Resolve chained canonical mappings (A->B->C) into direct mappings (A->C).
    Detect cycles via a seen set and keep the original mapping if found.
    """
    resolved = {}
    for name in canonical_map:
        seen = set()
        current = name
        final_name = None

        while current in canonical_map:
            next_name = canonical_map[current]
            if next_name in seen:
                final_name = canonical_map[name]
                break
            seen.add(next_name)
            current = next_name

        if final_name is None:
            final_name = current
        resolved[name] = final_name

    return resolved


def build_canonical_map(all_entities: list[dict]) -> dict[str, str]:
    """
    Build canonical name map across all entities.
    Groups entities by type before comparing
    so COMPANY entities never merge with PERSON entities.

    Returns dict: any_variant_name -> canonical_name
    """
    by_type = defaultdict(list)
    for entity in all_entities:
        entity_type = entity.get("entity_type", "UNKNOWN")
        by_type[entity_type].append(entity["entity_name"])

    canonical_map = {}
    for entity_type, names in by_type.items():
        unique_names = list(dict.fromkeys(names))  # preserve order, dedupe
        group_map = _find_canonical_groups(unique_names)
        canonical_map.update(group_map)

    return _resolve_canonical_chains(canonical_map)


def apply_canonical_map(
    extraction_list: list[dict],
    canonical_map: dict[str, str],
) -> list[dict]:
    """
    Walk every entity and relationship in every extraction.
    Replace variant names with canonical names using canonical_map.
    """
    updated = []

    for extraction in extraction_list:
        extraction = dict(extraction)

        updated_entities = []
        for entity in extraction.get("entities", []):
            entity = dict(entity)
            old_name = entity["entity_name"]
            entity["entity_name"] = canonical_map.get(old_name, old_name)
            updated_entities.append(entity)
        extraction["entities"] = updated_entities

        updated_relationships = []
        for rel in extraction.get("relationships", []):
            rel = dict(rel)
            rel["src_id"] = canonical_map.get(rel["src_id"], rel["src_id"])
            rel["tgt_id"] = canonical_map.get(rel["tgt_id"], rel["tgt_id"])
            updated_relationships.append(rel)
        extraction["relationships"] = updated_relationships

        updated.append(extraction)

    return updated


def merge_into_unified(
    updated_extractions: list[dict],
    document_id: str,
) -> dict:
    """
    Merge all extractions into one unified dict after canonical names applied.

    Deduplication rules:
      Entities:      same entity_name -> keep longest description
      Relationships: same (src_id, tgt_id, first_keyword) -> merge descriptions, keep max weight
      Chunks:        all kept, no deduplication (chunks are evidence)
    """
    # Entities: keep longest description per canonical name
    entity_map = {}
    for extraction in updated_extractions:
        for entity in extraction.get("entities", []):
            name = entity["entity_name"]
            if name not in entity_map:
                entity_map[name] = dict(entity)
            else:
                existing_len = len(entity_map[name].get("description", ""))
                new_len = len(entity.get("description", ""))
                if new_len > existing_len:
                    entity_map[name] = dict(entity)

    # Relationships: deduplicate by (src, tgt, first keyword)
    rel_map = {}
    total_rels_before = 0
    for extraction in updated_extractions:
        for rel in extraction.get("relationships", []):
            total_rels_before += 1
            first_keyword = rel.get("keywords", "").split(",")[0].strip()
            key = (rel["src_id"], rel["tgt_id"], first_keyword)

            if key not in rel_map:
                rel_map[key] = dict(rel)
            else:
                existing_desc = rel_map[key].get("description", "")
                new_desc = rel.get("description", "")
                if new_desc and new_desc not in existing_desc:
                    rel_map[key]["description"] = f"{existing_desc} {new_desc}".strip()
                rel_map[key]["weight"] = max(
                    rel_map[key].get("weight", 1.0),
                    rel.get("weight", 1.0),
                )

    # Chunks: collect all, deduplicate by chunk_id only
    all_chunks = []
    seen_chunk_ids = set()
    for extraction in updated_extractions:
        for chunk in extraction.get("chunks", []):
            cid = chunk.get("chunk_id")
            if cid and cid not in seen_chunk_ids:
                all_chunks.append(chunk)
                seen_chunk_ids.add(cid)

    total_entities_before = sum(len(e.get("entities", [])) for e in updated_extractions)

    final_entities = [
        {key: value for key, value in entity.items() if not key.startswith("_")}
        for entity in entity_map.values()
    ]

    return {
        "document_id": document_id,
        "file_path": updated_extractions[0].get("file_path", "unknown")
        if updated_extractions
        else "unknown",
        "timestamp": int(time.time()),
        "entities": final_entities,
        "relationships": list(rel_map.values()),
        "chunks": all_chunks,
        "_reconciliation_stats": {
            "input_files": len(updated_extractions),
            "total_entities_before": total_entities_before,
            "total_entities_after": len(entity_map),
            "total_relationships_before": total_rels_before,
            "total_relationships_after": len(rel_map),
            "total_chunks": len(all_chunks),
        },
    }


def reconcile_extractions(
    extraction_list: list[dict],
    document_id: str,
) -> dict:
    """
    Main entry point. Called by ingest_with_reconciliation MCP tool.

    Steps:
      1. Collect all entities from all subagent outputs
      2. Build canonical name map (normalize + deduplicate names)
      3. Apply canonical names to all entities and relationships
      4. Merge into single unified extraction
    """
    all_entities = collect_all_entities(extraction_list)
    canonical_map = build_canonical_map(all_entities)
    updated_extractions = apply_canonical_map(extraction_list, canonical_map)
    unified = merge_into_unified(updated_extractions, document_id)
    return unified
