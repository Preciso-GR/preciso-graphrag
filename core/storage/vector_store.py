from __future__ import annotations

import asyncio
import base64
import os
import time
import zlib
from dataclasses import dataclass
from typing import Any, final

import numpy as np
from nano_vectordb import NanoVectorDB

from core.file_io import atomic_artifact_path

from core.storage.base import BaseVectorStorage
from core.storage.shared_storage import (
    get_namespace_lock,
    get_update_flag,
    set_all_update_flags,
)
from core.utils import compute_mdhash_id, logger


@final
@dataclass
class NanoVectorDBStorage(BaseVectorStorage):
    def __post_init__(self):
        self._validate_embedding_func()
        self._client = None
        self._storage_lock = None
        self.storage_updated = None
        self._last_seen_revision = 0
        kwargs = self.global_config.get("vector_db_storage_cls_kwargs", {})
        cosine_threshold = kwargs.get("cosine_better_than_threshold")
        if cosine_threshold is None:
            raise ValueError("cosine_better_than_threshold must be specified")
        self.cosine_better_than_threshold = cosine_threshold
        working_dir = self.global_config["working_dir"]
        self._working_dir = working_dir
        workspace_dir = os.path.join(working_dir, self.workspace) if self.workspace else working_dir
        self.workspace = self.workspace or ""
        os.makedirs(workspace_dir, exist_ok=True)
        self._client_file_name = os.path.join(workspace_dir, f"vdb_{self.namespace}.json")
        self._max_batch_size = self.global_config["embedding_batch_num"]
        try:
            self._client = NanoVectorDB(
                self.embedding_func.embedding_dim,
                storage_file=self._client_file_name,
            )
        except AssertionError as exc:
            raise ValueError(
                f"Vector index `{self.namespace}` is incompatible with the configured "
                f"embedding dimension {self.embedding_func.embedding_dim}. "
                "Existing artifacts were preserved; restore the original embedding "
                "configuration or rebuild the complete graph in a fresh working directory."
            ) from exc

    async def initialize(self):
        self.storage_updated = await get_update_flag(
            self.namespace, workspace=self.workspace, working_dir=self._working_dir
        )
        self._last_seen_revision = self.storage_updated.revision
        self._storage_lock = get_namespace_lock(
            self.namespace, workspace=self.workspace, working_dir=self._working_dir
        )

    async def _get_client(self):
        async with self._storage_lock:
            if self.storage_updated.revision != self._last_seen_revision:
                self._client = NanoVectorDB(
                    self.embedding_func.embedding_dim,
                    storage_file=self._client_file_name,
                )
                self._last_seen_revision = self.storage_updated.revision
            return self._client

    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return
        current_time = int(time.time())
        list_data = [
            {
                "__id__": key,
                "__created_at__": current_time,
                **{meta_key: meta_val for meta_key, meta_val in value.items() if meta_key in self.meta_fields},
            }
            for key, value in data.items()
        ]
        contents = [value["content"] for value in data.values()]
        batches = [
            contents[i : i + self._max_batch_size]
            for i in range(0, len(contents), self._max_batch_size)
        ]
        embeddings_list = await asyncio.gather(
            *(self.embedding_func(batch, context="document") for batch in batches)
        )
        embeddings = np.concatenate(embeddings_list) if embeddings_list else np.array([])
        if len(embeddings) != len(list_data):
            raise ValueError("embedding count mismatch during upsert")
        for i, record in enumerate(list_data):
            vector_f16 = embeddings[i].astype(np.float16)
            compressed = zlib.compress(vector_f16.tobytes())
            encoded = base64.b64encode(compressed).decode("utf-8")
            record["vector"] = encoded
            record["__vector__"] = embeddings[i]
        client = await self._get_client()
        client.upsert(datas=list_data)

    async def query(
        self, query: str, top_k: int, query_embedding: list[float] | None = None
    ) -> list[dict[str, Any]]:
        if query_embedding is None:
            query_embedding = (await self.embedding_func([query], context="query", _priority=5))[0]
        client = await self._get_client()
        results = client.query(
            query=query_embedding,
            top_k=top_k,
            better_than_threshold=self.cosine_better_than_threshold,
        )
        return [
            {
                **{k: v for k, v in item.items() if k != "vector"},
                "id": item["__id__"],
                "distance": item["__metrics__"],
                "created_at": item.get("__created_at__"),
            }
            for item in results
        ]

    async def delete(self, ids: list[str]):
        client = await self._get_client()
        client.delete(ids)

    async def delete_entity(self, entity_name: str) -> None:
        entity_id = compute_mdhash_id(entity_name, prefix="ent-")
        client = await self._get_client()
        if client.get([entity_id]):
            client.delete([entity_id])

    async def delete_entity_relation(self, entity_name: str) -> None:
        client = await self._get_client()
        storage = getattr(client, "_NanoVectorDB__storage")
        relations = [
            item
            for item in storage["data"]
            if item.get("src_id") == entity_name or item.get("tgt_id") == entity_name
        ]
        if relations:
            client.delete([relation["__id__"] for relation in relations])

    async def index_done_callback(self) -> bool:
        async with self._storage_lock:
            try:
                with atomic_artifact_path(self._client_file_name) as temporary:
                    # Keep the dependency's serialization format and save()
                    # contract, but redirect its destructive write to staging.
                    original_path = self._client.storage_file
                    self._client.storage_file = str(temporary)
                    try:
                        self._client.save()
                    finally:
                        self._client.storage_file = original_path
                await set_all_update_flags(
                    self.namespace, workspace=self.workspace, working_dir=self._working_dir
                )
                # Keep the update visible to every sibling instance.  This
                # instance has the current client, so only advance its cursor.
                self._last_seen_revision = self.storage_updated.revision
                return True
            except Exception as exc:
                logger.error("[%s] Error saving data for %s: %s", self.workspace, self.namespace, exc)
                raise RuntimeError(f"Failed to persist vector index `{self.namespace}`: {exc}") from exc

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        client = await self._get_client()
        result = client.get([id])
        if not result:
            return None
        item = result[0]
        return {
            **{k: v for k, v in item.items() if k != "vector"},
            "id": item.get("__id__"),
            "created_at": item.get("__created_at__"),
        }

    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any] | None]:
        if not ids:
            return []
        client = await self._get_client()
        # NanoVectorDB scans records and uses `id in ids`. A set avoids a
        # linear requested-ID search for every stored record. Restore caller
        # order (including duplicates/missing IDs) through result_map below.
        results = client.get(set(ids))
        result_map = {}
        for item in results:
            if not item:
                continue
            result_map[str(item.get("__id__"))] = {
                **{k: v for k, v in item.items() if k != "vector"},
                "id": item.get("__id__"),
                "created_at": item.get("__created_at__"),
            }
        return [result_map.get(str(requested_id)) for requested_id in ids]

    async def get_vectors_by_ids(self, ids: list[str]) -> dict[str, list[float]]:
        if not ids:
            return {}
        client = await self._get_client()
        results = client.get(set(ids))
        vectors: dict[str, list[float]] = {}
        for item in results:
            if not item:
                continue
            vector = item.get("__vector__")
            if vector is None and "vector" in item:
                compressed = base64.b64decode(item["vector"])
                vector = np.frombuffer(zlib.decompress(compressed), dtype=np.float16).astype(np.float32)
            if vector is not None:
                vectors[str(item["__id__"])] = vector.tolist()
        return vectors

    async def drop(self) -> dict[str, str]:
        try:
            client = await self._get_client()
            storage = getattr(client, "_NanoVectorDB__storage")
            storage["data"] = []
            await self.index_done_callback()
            return {"status": "success", "message": "data dropped"}
        except Exception as exc:
            logger.exception("NanoVectorDBStorage.drop failed (namespace=%s)", self.namespace)
            return {"status": "error", "message": str(exc)}
