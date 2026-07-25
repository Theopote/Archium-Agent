"""Chroma-backed vector store for document chunks and knowledge items."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import chromadb

from archium.domain.document import DocumentChunk
from archium.application.retrieval_credibility import score_chunk_credibility
from archium.logging import get_logger

logger = get_logger(__name__, operation="vector_store")

_NIL_UUID = UUID(int=0)


@dataclass(frozen=True)
class VectorSearchHit:
    """Single vector search result (chunk or knowledge record)."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    page_number: int | None
    section_title: str | None
    chunk_index: int
    content_type: str = "text"
    architectural_type: str = "general"
    record_type: str = "document_chunk"
    authority: float = 0.5
    transferability: float = 0.5
    reliability: str = ""


class ChromaVectorStore:
    """Persist and query embeddings per project (chunks + knowledge)."""

    def __init__(self, persist_path: Path) -> None:
        persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_path))

    def upsert_chunks(
        self,
        project_id: UUID,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        *,
        document_name: str = "",
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")

        records = []
        for chunk in chunks:
            cred = score_chunk_credibility(chunk)
            records.append(
                {
                    "id": str(chunk.id),
                    "content": chunk.content,
                    "metadata": {
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "project_id": str(project_id),
                        "page_number": chunk.page_number or 0,
                        "section_title": chunk.section_title or "",
                        "chunk_index": chunk.chunk_index,
                        "document_name": document_name,
                        "content_type": chunk.content_type,
                        "architectural_type": str(
                            chunk.metadata.get("architectural_type")
                            or chunk.architectural_type.value
                        ),
                        "asset_id": str(chunk.metadata.get("asset_id") or ""),
                        "record_type": "document_chunk",
                        "authority": round(cred.authority, 4),
                        "transferability": round(cred.transferability, 4),
                        "reliability": "",
                    },
                }
            )
        self.upsert_records(project_id, records, embeddings)
        logger.info(
            "Indexed %d chunks for project %s in Chroma",
            len(chunks),
            project_id,
        )

    def upsert_records(
        self,
        project_id: UUID,
        records: list[dict[str, object]],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert generic text records (document chunks or knowledge items)."""
        if not records:
            return
        if len(records) != len(embeddings):
            raise ValueError("records and embeddings length mismatch")
        collection = self._get_or_create_collection(project_id)
        ids = [str(record["id"]) for record in records]
        documents = [str(record["content"]) for record in records]
        metadatas = [dict(cast(dict[str, object], record["metadata"])) for record in records]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_ids(self, project_id: UUID, ids: list[str]) -> None:
        if not ids:
            return
        collection_name = self._collection_name(project_id)
        try:
            collection = self._client.get_collection(collection_name)
        except Exception:
            return
        collection.delete(ids=ids)

    def delete_document(self, project_id: UUID, document_id: UUID) -> None:
        collection_name = self._collection_name(project_id)
        try:
            collection = self._client.get_collection(collection_name)
        except Exception:
            return
        try:
            collection.delete(
                where={
                    "$and": [
                        {"document_id": str(document_id)},
                        {"record_type": "document_chunk"},
                    ]
                }
            )
        except Exception:
            collection.delete(where={"document_id": str(document_id)})
        logger.info("Removed vectors for document %s from project %s", document_id, project_id)

    def delete_project(self, project_id: UUID) -> bool:
        """Remove the entire vector collection for a project."""
        collection_name = self._collection_name(project_id)
        try:
            self._client.delete_collection(collection_name)
            logger.info("Removed Chroma collection for project %s", project_id)
            return True
        except Exception:
            return False

    def query(
        self,
        project_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int,
        where: dict[str, object] | None = None,
    ) -> list[VectorSearchHit]:
        collection_name = self._collection_name(project_id)
        try:
            collection = self._client.get_collection(collection_name)
        except Exception:
            return []

        if collection.count() == 0:
            return []

        query_kwargs: dict[str, Any] = {
            "query_embeddings": cast(Any, [query_embedding]),
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        try:
            result = collection.query(**query_kwargs)
        except Exception as exc:
            if where:
                logger.warning("Chroma where query failed (%s); retrying without filter", exc)
                query_kwargs.pop("where", None)
                result = collection.query(**query_kwargs)
            else:
                raise

        hits: list[VectorSearchHit] = []
        ids = result.get("ids") or [[]]
        documents = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        for chunk_id, content, metadata, distance in zip(
            ids[0],
            documents[0],
            metadatas[0],
            distances[0],
            strict=False,
        ):
            if metadata is None:
                continue
            page_value = metadata.get("page_number")
            page_number = int(page_value) if isinstance(page_value, (int, float)) else None
            section_value = metadata.get("section_title")
            section_title = str(section_value) if section_value else None
            chunk_index_value = metadata.get("chunk_index", 0)
            chunk_index = int(chunk_index_value) if isinstance(chunk_index_value, (int, float)) else 0
            doc_raw = metadata.get("document_id")
            try:
                document_id = UUID(str(doc_raw)) if doc_raw else _NIL_UUID
            except ValueError:
                document_id = _NIL_UUID
            auth_raw = metadata.get("authority", 0.5)
            xfer_raw = metadata.get("transferability", 0.5)
            try:
                authority = float(auth_raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                authority = 0.5
            try:
                transferability = float(xfer_raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                transferability = 0.5
            hits.append(
                VectorSearchHit(
                    chunk_id=UUID(str(metadata.get("chunk_id", chunk_id))),
                    document_id=document_id,
                    content=content or "",
                    score=max(0.0, 1.0 - float(distance)),
                    page_number=page_number if page_number else None,
                    section_title=section_title or None,
                    chunk_index=chunk_index,
                    content_type=str(metadata.get("content_type") or "text"),
                    architectural_type=str(metadata.get("architectural_type") or "general"),
                    record_type=str(metadata.get("record_type") or "document_chunk"),
                    authority=max(0.0, min(1.0, authority)),
                    transferability=max(0.0, min(1.0, transferability)),
                    reliability=str(metadata.get("reliability") or ""),
                )
            )
        return hits

    def _get_or_create_collection(self, project_id: UUID) -> Any:
        return self._client.get_or_create_collection(
            name=self._collection_name(project_id),
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _collection_name(project_id: UUID) -> str:
        return f"project_{project_id.hex}"
