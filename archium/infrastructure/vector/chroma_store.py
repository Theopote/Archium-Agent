"""Chroma-backed vector store for document chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, cast
from uuid import UUID

import chromadb

from archium.domain.document import DocumentChunk
from archium.logging import get_logger

logger = get_logger(__name__, operation="vector_store")


@dataclass(frozen=True)
class VectorSearchHit:
    """Single vector search result."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    page_number: int | None
    section_title: str | None
    chunk_index: int


class ChromaVectorStore:
    """Persist and query chunk embeddings per project."""

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

        collection = self._get_or_create_collection(project_id)
        ids = [str(chunk.id) for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "project_id": str(project_id),
                "page_number": chunk.page_number or 0,
                "section_title": chunk.section_title or "",
                "chunk_index": chunk.chunk_index,
                "document_name": document_name,
            }
            for chunk in chunks
        ]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "Indexed %d chunks for project %s in Chroma",
            len(chunks),
            project_id,
        )

    def delete_document(self, project_id: UUID, document_id: UUID) -> None:
        collection_name = self._collection_name(project_id)
        try:
            collection = self._client.get_collection(collection_name)
        except Exception:
            return
        collection.delete(where={"document_id": str(document_id)})
        logger.info("Removed vectors for document %s from project %s", document_id, project_id)

    def query(
        self,
        project_id: UUID,
        query_embedding: list[float],
        *,
        top_k: int,
    ) -> list[VectorSearchHit]:
        collection_name = self._collection_name(project_id)
        try:
            collection = self._client.get_collection(collection_name)
        except Exception:
            return []

        if collection.count() == 0:
            return []

        result = collection.query(
            query_embeddings=cast(Sequence[Sequence[float]], [query_embedding]),
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

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
            hits.append(
                VectorSearchHit(
                    chunk_id=UUID(str(metadata.get("chunk_id", chunk_id))),
                    document_id=UUID(str(metadata["document_id"])),
                    content=content or "",
                    score=max(0.0, 1.0 - float(distance)),
                    page_number=page_number if page_number else None,
                    section_title=section_title or None,
                    chunk_index=chunk_index,
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
