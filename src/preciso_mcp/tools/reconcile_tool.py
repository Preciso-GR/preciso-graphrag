"""
reconcile_tool.py

MCP tool: ingest_with_reconciliation

Called by orchestrator agent after all subagents finish.
Reads multiple extraction files, reconciles them into
one unified extraction, writes unified file to disk,
then runs the ingestion pipeline.
"""

import json
import re
import time
from pathlib import Path

from core.utils import logger
from core.utils import write_json
from ingest.file_access import read_extraction_text, resolve_input_file
from ingest.validator import _positive_limit
from uuid import uuid4
from ingest.reconciler import reconcile_extractions
from ingest.pipeline import ingest_extracted_json


def _is_full_extraction(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    required = {"document_id", "entities", "relationships", "chunks"}
    return required.issubset(payload.keys())


def _is_patch_file(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    patch_keys = {
        "merge_entities",
        "remove_relationships",
        "flag_conflicts",
        "broken_relationships",
        "suggested_fixes",
    }
    return any(key in payload for key in patch_keys)


async def ingest_with_reconciliation(
    extraction_files: list[str],
    storage_instances: dict,
    global_config: dict,
) -> dict:
    """
    Args:
          extraction_files: list of paths including one base extraction JSON file
                      plus zero or more reconciliation patch files
                      e.g. ["extractions/doc_extracted.json",
                          "extractions/doc_patch_entities.json"]
        storage_instances: initialized storage dict from server startup
        global_config: LightRAG global config dict

    Returns:
        {
          "status": "success" | "error" | "validation_failed",
          "unified_file": "extractions/reconciled_{timestamp}.json",
          "files_reconciled": int,
          "duplicate_entities_merged": int,
          "entities_added": int,
          "relationships_added": int,
          "chunks_stored": int,
          "reconciliation_stats": {...},
          "errors": []
        }
    """

    if not extraction_files or len(extraction_files) > 100:
        return {"status": "validation_failed", "message": "provide between 1 and 100 extraction files"}

    # Step 2: Read all extraction files
    extraction_list = []
    patch_list = []
    read_errors = []
    total_bytes = 0
    for fp in extraction_files:
        try:
            path = resolve_input_file(fp, global_config)
            if path.suffix.lower() != ".json":
                raise ValueError("reconciliation requires JSON files")
            content = read_extraction_text(path)
            total_bytes += len(content.encode("utf-8"))
            if total_bytes > _positive_limit("GRAPHRAG_MAX_INGEST_BYTES", 25 * 1024 * 1024):
                raise ValueError("combined extraction files exceed the byte limit")
            data = json.loads(content)
            if _is_full_extraction(data):
                extraction_list.append(data)
            elif _is_patch_file(data):
                patch_list.append(data)
            else:
                read_errors.append(f"Unrecognized payload format in {fp}")
        except json.JSONDecodeError as e:
            read_errors.append(f"Invalid JSON in {fp}: {e}")
        except Exception as e:
            logger.exception("ingest_with_reconciliation: failed to read extraction file %s", fp)
            read_errors.append(f"Failed to read {fp}: {e}")

    if read_errors:
        return {
            "status": "error",
            "message": "Failed to read one or more extraction files",
            "errors": read_errors,
        }

    if not extraction_list:
        return {
            "status": "error",
            "message": "No valid extraction file could be read",
        }

    if len(extraction_list) > 1:
        return {
            "status": "error",
            "message": "Multiple base extractions provided; expected exactly one",
        }

    # Step 3: Build document_id from first file
    first = extraction_list[0]
    base_document_id = first.get("document_id", "reconciled")
    # Strip _part1, _part2 suffixes to get clean document_id
    document_id = re.sub(r"_part\d+$", "", base_document_id)

    # Step 4: Reconcile base extraction with patches
    try:
        unified = reconcile_extractions(first, patch_list, document_id=document_id)
    except Exception as e:
        logger.exception("ingest_with_reconciliation: reconcile_extractions failed (document_id=%s)", document_id)
        return {
            "status": "error",
            "message": f"Reconciliation failed: {e}",
        }

    entity_names = {entity.get("entity_name") for entity in unified.get("entities", [])}
    entity_names.discard(None)
    relationship_errors = []
    for rel in unified.get("relationships", []):
        src_id = rel.get("src_id")
        tgt_id = rel.get("tgt_id")
        if src_id not in entity_names:
            relationship_errors.append(f"Missing src_id entity: {src_id}")
        if tgt_id not in entity_names:
            relationship_errors.append(f"Missing tgt_id entity: {tgt_id}")

    if relationship_errors:
        return {
            "status": "validation_failed",
            "message": "Broken relationship references found",
            "errors": relationship_errors,
        }

    stats = unified.pop("_reconciliation_stats", {})
    duplicate_entities_merged = stats.get("total_entities_before", 0) - stats.get(
        "total_entities_after", 0
    )

    # Step 5: Write unified file to disk
    timestamp = int(time.time())
    output_root = Path(global_config.get("reconciliation_dir") or Path(global_config.get("working_dir", ".")) / "reconciled")
    # A document ID is data, never a filesystem name. Random IDs also prevent
    # concurrent requests from replacing each other's output in the same second.
    unified_path = str(output_root / f"reconciled_{timestamp}_{uuid4().hex}.json")

    try:
        write_json(unified, unified_path)
    except Exception as e:
        logger.exception("ingest_with_reconciliation: failed to write unified file %s", unified_path)
        return {
            "status": "error",
            "message": f"Failed to write unified file: {e}",
        }

    # Step 6: Run ingestion pipeline on unified output
    try:
        ingest_result = await ingest_extracted_json(
            payload=unified,
            storage_instances=storage_instances,
            global_config=global_config,
        )
    except Exception as e:
        logger.exception("ingest_with_reconciliation: ingestion failed after reconciliation (document_id=%s)", document_id)
        return {
            "status": "error",
            "message": f"Ingestion failed after reconciliation: {e}",
            "unified_file": unified_path,
            "note": "Unified file was written. Use reingest_from_file to retry.",
        }

    return {
        "status": ingest_result.get("status", "unknown"),
        "unified_file": unified_path,
        "files_reconciled": len(extraction_files),
        "duplicate_entities_merged": duplicate_entities_merged,
        "entities_added": ingest_result.get("entities_merged", 0),
        "relationships_added": ingest_result.get("relationships_merged", 0),
        "chunks_stored": ingest_result.get("chunks_ingested", 0),
        "reconciliation_stats": stats,
        "errors": ingest_result.get("errors", []),
        "warnings": ingest_result.get("warnings", []),
    }
