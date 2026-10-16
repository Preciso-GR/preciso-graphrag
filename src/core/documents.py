"""Document contributions are authoritative; graph and vector records are derived.

All writes run under the existing artifact transaction. No model framework or
second database is required. Legacy graphs remain readable but cannot be rebuilt.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

from config import GRAPH_FIELD_SEP
from core.session_lock import graph_read_session
from core.transactions import run_artifact_mutation
from ingest._materialize import apply_extraction
from ingest.validator import validate_entity, validate_extraction_structure, validate_relationship

STATE = "__state__"
DERIVED = (
    "graph", "text_chunks", "entity_chunks", "relation_chunks",
    "pending_summaries", "entities_vdb", "relationships_vdb", "chunks_vdb", "llm_cache", "checkpoints",
)


def failure(code: str, message: str, **extra) -> dict:
    return {"status": "error", "error_code": code, "message": message, **extra}


def payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _claim_errors(payload: dict) -> list[str]:
    """Validate original claims before an editing projection can omit them."""
    from core.utils import compute_mdhash_id

    errors = []
    names = set()
    sources = set()
    for index, chunk in enumerate(payload["chunks"]):
        if not chunk.get("content", "").strip():
            errors.append(f"chunk at index {index} requires non-empty content")
        chunk_id = chunk.get("chunk_id") or compute_mdhash_id(
            f"{payload['document_id']}:{index}:{chunk.get('content', '')}", prefix="chunk-",
        )
        sources.add(chunk_id)
    for entity in payload["entities"]:
        valid, message = validate_entity(entity, resolvable_source_ids=sources, strict_source_ids=True)
        if not valid:
            errors.append(message)
        else:
            names.add(entity["entity_name"].strip())
    for relation in payload["relationships"]:
        valid, message = validate_relationship(relation, names, resolvable_source_ids=sources, strict_source_ids=True)
        if not valid:
            errors.append(message)
    return errors


async def _state(stores: dict) -> dict:
    state = await stores["documents"].get_by_id(STATE)
    if state is not None:
        return copy.deepcopy(state)
    populated = bool(await stores["graph"].get_all_nodes()) or not await stores["text_chunks"].is_empty()
    if not populated:
        for name in ("entities_vdb", "relationships_vdb", "chunks_vdb"):
            empty = getattr(stores[name], "is_empty", None)
            if empty is None or not await empty():
                populated = True  # Unknown adapters cannot prove complete contributions.
                break
    return {"schema_version": 1, "revision": 0, "complete": not populated, "edits": {}}


async def _save_state(stores: dict, state: dict) -> None:
    await stores["documents"].upsert({STATE: state})
    await stores["documents"].index_done_callback()


async def get_rebuild_generation(stores: dict) -> int:
    """Read the summary freshness generation while the caller holds a session.

    Consumers do not need the ledger's private state layout or completeness
    checks. Legacy adapter sets without a ledger have generation zero.
    """
    documents = stores.get("documents")
    state = await documents.get_by_id(STATE) if documents is not None else None
    return (state or {}).get("generation", 0)


async def _records(stores: dict) -> dict:
    return {key: copy.deepcopy(value) for key, value in
            (await stores["documents"].get_all_items()).items() if key != STATE}


async def ingest_extracted_json(payload, storage_instances: dict, global_config: dict) -> dict:
    """Validate and commit an extraction with its document contributions.

    This is the public ingestion interface. Creates and Full Rebuilds share the
    same extraction implementation without re-entering this transaction.
    """
    if not isinstance(payload, dict):
        return {"status": "error", "message": "payload must be an object"}
    errors = validate_extraction_structure(payload)
    if errors:
        return {"status": "validation_failed", "errors": errors}
    return await run_artifact_mutation(
        lambda: _ingest_document(payload, storage_instances, global_config),
        storage_instances, global_config,
    )


async def _ingest_document(payload: dict, stores: dict, config: dict) -> dict:
    """Called inside the ingestion transaction; preserve custom adapter support."""
    if "documents" not in stores:
        return await apply_extraction(payload, stores, config)
    document_id = payload["document_id"]
    if document_id.startswith("__"):
        return failure("invalid_document_id", "Document IDs starting with __ are reserved")
    state = await _state(stores)
    old = await stores["documents"].get_by_id(document_id)
    digest = payload_hash(payload)
    if old and old["payload_hash"] != digest:
        return failure("revision_conflict", "Use document replacement to change an existing document", revision=state["revision"])
    if old:
        # Replays must not reintroduce records hidden by graph edits.
        result = copy.deepcopy(old["result"])
        for counts in result.get("ingestion_counts", {}).values():
            counts.update(added=0, merged=0, skipped_duplicate=sum(counts.values()))
        return {**result, "replay": True, "revision": state["revision"]}
    if state.get("edits"):
        errors = _claim_errors(payload)
        if errors:
            return failure("validation_failed", "Invalid extraction claims", errors=errors)
        # Reapply persistent graph edits to the enlarged source collection.
        records = await _records(stores)
        record = _record(payload, digest)
        records[document_id] = record
        result = await _rebuild(records, state, stores, config)
        if result["status"] != "success":
            return result
        result = {"status": "success", "document_id": document_id, "message": "Document added; graph edits retained"}
    else:
        record = _record(payload, digest)
        result = await apply_extraction(copy.deepcopy(record["payload"]), stores, config)
    if result["status"] not in {"success", "partial_success"}:
        return result
    # Incomplete/uncited legacy extraction remains readable, but is not safe to rebuild.
    if result["status"] != "success" or result.get("warnings"):
        state["complete"] = False
    state["revision"] += 1
    result = {**result, "revision": state["revision"], "replay": False}
    record["result"] = copy.deepcopy(result)
    await stores["documents"].upsert({document_id: record})
    await _save_state(stores, state)
    return result


def _record(payload: dict, digest: str) -> dict:
    saved = copy.deepcopy(payload)
    saved.setdefault("timestamp", int(time.time()))
    return {"schema_version": 1, "document_id": payload["document_id"],
            "payload_hash": digest, "payload": saved, "version": 1,
            "file_path": payload.get("file_path", "unknown_source")}


async def _rebuild(records: dict, state: dict, stores: dict, config: dict) -> dict:
    """Simple correctness baseline: replay complete contributions, not merged text."""
    for name in DERIVED:
        result = await stores[name].drop()
        if result.get("status") != "success":
            return failure("rebuild_failed", f"Could not clear derived store {name}")
    edits = state.get("edits", {})
    blocked = _blocked_chunks(records, edits)
    for record in records.values():
        payload = _project(record["payload"], edits, blocked)
        result = await apply_extraction(payload, stores, config)
        if result["status"] != "success" or result.get("warnings"):
            return failure("rebuild_failed", "A document could not be rebuilt with complete evidence", details=result)
    for node_id, label in edits.get("labels", {}).items():
        node = await stores["graph"].get_node(node_id)
        if node:
            await stores["graph"].upsert_node(node_id, {**node, "display_name": label})
            from core.utils import compute_mdhash_id, strip_summary_marker
            await stores["entities_vdb"].upsert({compute_mdhash_id(node_id, prefix="ent-"): {
                "entity_name": node_id, "entity_type": node.get("entity_type", "UNKNOWN"),
                "content": f"{node_id}\n{label}\n{strip_summary_marker(node.get('description', ''))}",
                "source_id": node.get("source_id", ""), "file_path": node.get("file_path", "unknown_source"),
            }})
    await stores["graph"].index_done_callback()
    await stores["entities_vdb"].index_done_callback()
    # Empty corpora must also publish counts and invalidate prior summaries/cache.
    from core.runtime_status import update_artifact_manifest
    await update_artifact_manifest(stores, config)
    state["generation"] = state.get("generation", 0) + 1
    return {"status": "success"}


def _canonical(node_id: str, edits: dict) -> str:
    aliases = edits.get("aliases", {})
    seen = set()
    while node_id in aliases:
        if node_id in seen:
            raise ValueError("Invalid cyclic entity aliases")
        seen.add(node_id)
        node_id = aliases[node_id]
    return node_id


def _sources(record: dict, document_id: str) -> set[str]:
    return {f"{document_id}::{value}"
            for value in record.get("source_id", "").strip().split(GRAPH_FIELD_SEP) if value}


def _blocked_chunks(records: dict, edits: dict) -> set[str]:
    hidden = set(edits.get("isolated", [])) | set(edits.get("removed", []))
    blocked = set()
    for row in records.values():
        payload = row["payload"]
        for entity in payload["entities"]:
            if _canonical(entity["entity_name"].strip(), edits) in hidden:
                blocked.update(_sources(entity, payload["document_id"]))
        for relation in payload["relationships"]:
            src, tgt = _endpoints(relation, edits)
            if src in hidden or tgt in hidden:
                blocked.update(_sources(relation, payload["document_id"]))
    return blocked


def _endpoints(relation: dict, edits: dict) -> tuple[str, str]:
    return (_canonical((relation.get("src_id") or relation["source_entity"]).strip(), edits),
            _canonical((relation.get("tgt_id") or relation["target_entity"]).strip(), edits))


def _project(payload: dict, edits: dict, blocked: set[str]) -> dict:
    projected = copy.deepcopy(payload)
    document_id = payload["document_id"]
    hidden = set(edits.get("isolated", [])) | set(edits.get("removed", []))
    # Whole cited passages are withheld. This is deliberately conservative:
    # retaining their vectors would expose isolated facts through chunk search.
    # Generated IDs must match the ingestion rule even when chunk_id is omitted.
    from core.utils import compute_mdhash_id
    chunks = []
    for index, chunk in enumerate(projected["chunks"]):
        raw_id = chunk.get("chunk_id") or compute_mdhash_id(
            f"{document_id}:{index}:{chunk.get('content', '')}", prefix="chunk-",
        )
        chunk_id = f"{document_id}::{raw_id}"
        if not any(value == chunk_id or value.startswith(chunk_id + "-p") for value in blocked):
            # Preserve generated IDs when removing a preceding chunk shifts its index.
            chunk["chunk_id"] = raw_id
            chunks.append(chunk)
    projected["chunks"] = chunks

    def allowed(record):
        # Drop the whole derived claim if any of its cited passages is hidden.
        return not (_sources(record, document_id) & blocked)

    entities = []
    for entity in projected["entities"]:
        entity["entity_name"] = _canonical(entity["entity_name"].strip(), edits)
        if entity["entity_name"] not in hidden and allowed(entity):
            entities.append(entity)
    projected["entities"] = entities
    names = {entity["entity_name"] for entity in entities}
    relationships = []
    disconnected = {tuple(pair) for pair in edits.get("disconnected", [])}
    for relation in projected["relationships"]:
        src, tgt = _endpoints(relation, edits)
        if src == tgt or src not in names or tgt not in names or not allowed(relation):
            continue
        if tuple(sorted((src, tgt))) in disconnected:
            continue
        relation["src_id"], relation["tgt_id"] = src, tgt
        relationships.append(relation)
    projected["relationships"] = relationships
    return projected


async def document_operation(stores: dict, config: dict, action: str,
                             document_id: str = "", payload: dict | None = None,
                             expected_revision: int | None = None, dry_run: bool = True) -> dict:
    """Preview or commit an operation; destructive commits require a revision."""
    if action not in {"list", "create", "replace", "delete"}:
        return failure("invalid_action", "Use list, create, replace, or delete")
    if action in {"create", "replace"}:
        errors = validate_extraction_structure(payload)
        if not errors:
            errors = _claim_errors(payload)
        if errors:
            return failure("validation_failed", "Invalid extraction", errors=errors)
        if document_id and document_id != payload["document_id"]:
            return failure("invalid_document_id", "Payload and operation document IDs differ")
        document_id = payload["document_id"]
    if document_id.startswith("__"):
        return failure("invalid_document_id", "Document IDs starting with __ are reserved")

    async def operation():
        state = await _state(stores)
        records = await _records(stores)
        revision = state["revision"]
        if action == "list":
            return {"status": "success", "revision": revision, "complete": state["complete"],
                    "documents": [{key: row[key] for key in
                        ("document_id", "payload_hash", "version", "file_path")} for row in records.values()]}
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != revision):
            return failure("revision_conflict", "Graph changed; preview the operation again", revision=revision)
        if action != "create" and not state["complete"]:
            return failure("legacy_untracked", "Rebuild a fresh workspace from complete extractions before destructive edits")
        old = records.get(document_id)
        if action != "create" and old is None:
            return failure("not_found", "Document does not exist", revision=revision)
        if action == "create" and old and old["payload_hash"] != payload_hash(payload):
            return failure("revision_conflict", "Use replace for an existing document", revision=revision)
        if dry_run:
            return {"status": "success", "dry_run": True, "action": action, "revision": revision,
                    "document_id": document_id,
                    "rebuild_documents": len(records) - (action == "delete") + (action == "create" and old is None)}
        if action == "create":
            return await _ingest_document(payload, stores, config)
        if expected_revision is None:
            return failure("revision_required", "Provide the revision returned by a preview")
        if action == "replace":
            if old["payload_hash"] == payload_hash(payload):
                return {"status": "success", "replay": True, "revision": revision}
            records[document_id] = _record(payload, payload_hash(payload))
            records[document_id]["version"] = old["version"] + 1
            records[document_id]["result"] = {"status": "success", "document_id": document_id}
        else:
            records.pop(document_id)
        result = await _rebuild(records, state, stores, config)
        if result["status"] != "success":
            return result
        state["revision"] += 1
        if action == "delete":
            await stores["documents"].delete([document_id])
        else:
            await stores["documents"].upsert({document_id: records[document_id]})
        await _save_state(stores, state)
        return {"status": "success", "action": action, "document_id": document_id, "revision": state["revision"]}

    if dry_run or action == "list":
        async with graph_read_session(config, getattr(stores["graph"], "workspace", "")):
            return await operation()
    return await run_artifact_mutation(operation, stores, config)


async def graph_operation(stores: dict, config: dict, action: str, node_id: str = "",
                          target_id: str = "", label: str = "",
                          expected_revision: int | None = None, dry_run: bool = True) -> dict:
    """Persist editing rules independently from the unmodified source evidence."""
    if action not in {"inspect", "isolate", "restore", "remove", "rename", "merge", "disconnect"}:
        return failure("invalid_action", "Unknown graph operation")
    node_id, target_id, label = node_id.strip(), target_id.strip(), label.strip()

    async def operation():
        state = await _state(stores)
        revision = state["revision"]
        edits = state.setdefault("edits", {})
        if action == "inspect":
            nodes = await stores["graph"].get_all_nodes()
            edges = await stores["graph"].get_all_edges()
            return {"status": "success", "revision": revision, "edits": edits,
                    "nodes": nodes[:100], "relationships": edges[:100],
                    "node_count": len(nodes), "relationship_count": len(edges),
                    "truncated": len(nodes) > 100 or len(edges) > 100}
        if not state["complete"]:
            return failure("legacy_untracked", "Graph edits require a complete document ledger")
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision != revision):
            return failure("revision_conflict", "Graph changed; preview the operation again", revision=revision)
        if not node_id:
            return failure("invalid_node_id", "A canonical node ID is required")
        if _canonical(node_id, edits) != node_id:
            return failure("invalid_node_id", "Use the canonical node ID", canonical_id=_canonical(node_id, edits))
        isolated = set(edits.get("isolated", []))
        removed = set(edits.get("removed", []))
        if action == "restore":
            if node_id not in isolated:
                return failure("not_found", "Node is not isolated")
        elif node_id not in isolated and not await stores["graph"].has_node(node_id):
            return failure("not_found", "Node does not exist in the active graph")
        if action in {"merge", "disconnect"}:
            if target_id == node_id or not await stores["graph"].has_node(target_id):
                return failure("invalid_target", "Provide a different active canonical target node")
            if action == "disconnect" and not await stores["graph"].has_edge(node_id, target_id):
                return failure("not_found", "Relationship does not exist")
        if action == "rename" and (not label or len(label) > 256):
            return failure("invalid_label", "Use a display label of 1 to 256 characters")
        if action == "isolate":
            isolated.add(node_id)
        elif action == "restore":
            isolated.remove(node_id)
        elif action == "remove":
            isolated.discard(node_id)
            removed.add(node_id)
        elif action == "merge":
            if node_id in isolated:
                return failure("invalid_node_id", "Restore an isolated node before merging")
            # Retarget previous rules when the canonical identity changes.
            aliases = edits.setdefault("aliases", {})
            aliases[node_id] = target_id
            edits["disconnected"] = [sorted({target_id if value == node_id else value for value in pair})
                                      for pair in edits.get("disconnected", [])]
            edits.setdefault("labels", {}).pop(node_id, None)
        elif action == "disconnect":
            pair = sorted((node_id, target_id))
            disconnected = edits.setdefault("disconnected", [])
            if pair not in disconnected:
                disconnected.append(pair)
        elif action == "rename":
            edits.setdefault("labels", {})[node_id] = label
        edits["isolated"], edits["removed"] = sorted(isolated), sorted(removed)
        records = await _records(stores)
        blocked = _blocked_chunks(records, edits)
        preview = {"status": "success", "action": action, "node_id": node_id,
                   "revision": revision, "withheld_source_passages": len(blocked),
                   "rebuild_documents": len(records)}
        if dry_run:
            return {**preview, "dry_run": True}
        if expected_revision is None:
            return failure("revision_required", "Provide the revision returned by a preview")
        result = await _rebuild(records, state, stores, config)
        if result["status"] != "success":
            return result
        state["revision"] += 1
        await _save_state(stores, state)
        return {**preview, "revision": state["revision"]}

    if dry_run or action == "inspect":
        async with graph_read_session(config, getattr(stores["graph"], "workspace", "")):
            return await operation()
    return await run_artifact_mutation(operation, stores, config)


async def read_evidence(stores: dict, config: dict, chunk_id: str) -> dict:
    """Read only active indexed evidence; hidden ledger payloads are not exposed."""
    async with graph_read_session(config, getattr(stores["graph"], "workspace", "")):
        chunk = await stores["text_chunks"].get_by_id(chunk_id)
        if chunk is None:
            return failure("not_found", "Active evidence passage does not exist")
        return {"status": "success", "chunk_id": chunk_id,
                "document_id": chunk["full_doc_id"], "content": chunk["content"],
                "file_path": chunk.get("file_path"), "revision": (await _state(stores))["revision"]}
