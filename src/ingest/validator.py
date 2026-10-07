from __future__ import annotations

import json
import math
import os
from typing import Any

from config import GRAPH_FIELD_SEP


def _required_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_limit(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def validate_extraction_structure(payload: Any) -> list[str]:
    """Validate the required top-level shape shared by all ingestion APIs."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    for field in ("document_id", "entities", "relationships", "chunks"):
        if field not in payload:
            errors.append(f"missing required field `{field}`")

    if "document_id" in payload and not _required_text(payload["document_id"]):
        errors.append("`document_id` must be a non-empty string")
    if "entities" in payload and not isinstance(payload.get("entities"), list):
        errors.append("`entities` must be a list")
    if "relationships" in payload and not isinstance(payload.get("relationships"), list):
        errors.append("`relationships` must be a list")
    if "chunks" in payload and not isinstance(payload.get("chunks"), list):
        errors.append("`chunks` must be a list")
    if errors:
        return errors

    max_records = _positive_limit("GRAPHRAG_MAX_INGEST_RECORDS", 50000)
    if sum(len(payload[field]) for field in ("entities", "relationships", "chunks")) > max_records:
        return [f"extraction exceeds the {max_records} record limit"]
    text_fields = {
        "entities": ("entity_name", "entity_type", "description", "source_id", "file_path"),
        "relationships": ("src_id", "tgt_id", "source_entity", "target_entity", "description", "source_id", "keywords", "file_path"),
        "chunks": ("chunk_id", "content", "file_path"),
    }
    for field, fields in text_fields.items():
        for index, record in enumerate(payload[field]):
            if not isinstance(record, dict):
                errors.append(f"{field}[{index}] must be an object")
                continue
            for key in fields:
                if key in record and not isinstance(record[key], str):
                    errors.append(f"{field}[{index}].{key} must be a string")
            if field == "relationships" and "weight" in record:
                try:
                    if isinstance(record["weight"], bool) or not math.isfinite(float(record["weight"])):
                        raise ValueError
                except (TypeError, ValueError, OverflowError):
                    errors.append(f"{field}[{index}].weight must be finite and numeric")
            for key in ("timestamp", "tokens", "chunk_order_index"):
                if key in record:
                    try:
                        value = record[key]
                        if isinstance(value, bool) or int(value) < 0 or float(value) != int(value):
                            raise ValueError
                    except (TypeError, ValueError, OverflowError):
                        errors.append(f"{field}[{index}].{key} must be a non-negative integer")
    if errors:
        return errors
    try:
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ["payload must contain only valid, finite JSON values"]
    max_bytes = _positive_limit("GRAPHRAG_MAX_INGEST_BYTES", 25 * 1024 * 1024)
    if size > max_bytes:
        errors.append(f"extraction exceeds the {max_bytes} byte limit")
    return errors


def _unresolvable_source_ids(source_id: str, resolvable_source_ids: set[str]) -> list[str]:
    return [
        chunk_id
        for chunk_id in source_id.split(GRAPH_FIELD_SEP)
        if chunk_id and chunk_id not in resolvable_source_ids
    ]


def validate_entity(
    entity: dict,
    *,
    resolvable_source_ids: set[str] | None = None,
    strict_source_ids: bool = False,
) -> tuple[bool, str]:
    if not isinstance(entity, dict):
        return False, "entity must be an object"
    entity_name = entity.get("entity_name")
    if not _required_text(entity_name):
        return False, "entity_name is required"
    description = entity.get("description")
    if not _required_text(description):
        return False, f"entity `{entity_name}` requires description"
    source_id = entity.get("source_id")
    if not _required_text(source_id):
        return False, f"entity `{entity_name}` requires source_id"
    if strict_source_ids and resolvable_source_ids is not None:
        unresolved = _unresolvable_source_ids(source_id, resolvable_source_ids)
        if unresolved:
            return False, (
                f"entity `{entity_name}` has unresolvable source_id(s): "
                f"{', '.join(unresolved)}"
            )
    entity_type = entity.get("entity_type")
    if not _required_text(entity_type):
        return False, f"entity `{entity_name}` requires entity_type"
    return True, ""


def validate_relationship(
    rel: dict,
    known_entities: set,
    *,
    resolvable_source_ids: set[str] | None = None,
    strict_source_ids: bool = False,
) -> tuple[bool, str]:
    if not isinstance(rel, dict):
        return False, "relationship must be an object"
    src_id = rel.get("src_id") or rel.get("source_entity")
    tgt_id = rel.get("tgt_id") or rel.get("target_entity")
    if not _required_text(src_id) or not _required_text(tgt_id):
        return False, "relationship requires src_id/source_entity and tgt_id/target_entity"
    src_id, tgt_id = src_id.strip(), tgt_id.strip()
    if src_id == tgt_id:
        return False, f"self-loop relationship is not allowed for `{src_id}`"
    if src_id not in known_entities or tgt_id not in known_entities:
        return False, f"relationship `{src_id}->{tgt_id}` references unknown entities"
    description = rel.get("description")
    if not _required_text(description):
        return False, f"relationship `{src_id}->{tgt_id}` requires description"
    source_id = rel.get("source_id")
    if not _required_text(source_id):
        return False, f"relationship `{src_id}->{tgt_id}` requires source_id"
    if strict_source_ids and resolvable_source_ids is not None:
        unresolved = _unresolvable_source_ids(source_id, resolvable_source_ids)
        if unresolved:
            return False, (
                f"relationship `{src_id}->{tgt_id}` has unresolvable source_id(s): "
                f"{', '.join(unresolved)}"
            )
    weight = rel.get("weight", 1.0)
    try:
        numeric_weight = float(weight)
    except (TypeError, ValueError, OverflowError):
        return False, f"relationship `{src_id}->{tgt_id}` weight must be numeric"
    if isinstance(weight, bool) or not math.isfinite(numeric_weight):
        return False, f"relationship `{src_id}->{tgt_id}` weight must be finite and numeric"
    return True, ""
