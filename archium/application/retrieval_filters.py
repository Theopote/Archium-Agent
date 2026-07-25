"""Retrieval filters for metadata-aware hybrid search."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.domain.architectural_chunk import ArchitecturalChunkType

RECORD_TYPE_CHUNK = "document_chunk"
RECORD_TYPE_KNOWLEDGE = "knowledge_item"


@dataclass(frozen=True)
class RetrievalFilters:
    """Optional metadata constraints for Chroma / post-filters."""

    content_types: tuple[str, ...] = ()
    architectural_types: tuple[ArchitecturalChunkType, ...] = ()
    document_ids: tuple[UUID, ...] = ()
    record_types: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (
            self.content_types
            or self.architectural_types
            or self.document_ids
            or self.record_types
        )

    def with_default_chunk_scope(self) -> RetrievalFilters:
        """Restrict to document chunks when record_types unset (exclude knowledge vectors)."""
        if self.record_types:
            return self
        return RetrievalFilters(
            content_types=self.content_types,
            architectural_types=self.architectural_types,
            document_ids=self.document_ids,
            record_types=(RECORD_TYPE_CHUNK,),
        )

    def to_chroma_where(self) -> dict[str, object] | None:
        """Build Chroma where clause; None means unrestricted."""
        clauses: list[dict[str, object]] = []
        if self.content_types:
            values = [str(v) for v in self.content_types if str(v).strip()]
            if len(values) == 1:
                clauses.append({"content_type": values[0]})
            elif values:
                clauses.append({"content_type": {"$in": values}})
        if self.architectural_types:
            values = [t.value for t in self.architectural_types]
            if len(values) == 1:
                clauses.append({"architectural_type": values[0]})
            elif values:
                clauses.append({"architectural_type": {"$in": values}})
        if self.document_ids:
            values = [str(doc_id) for doc_id in self.document_ids]
            if len(values) == 1:
                clauses.append({"document_id": values[0]})
            elif values:
                clauses.append({"document_id": {"$in": values}})
        if self.record_types:
            values = [str(v) for v in self.record_types if str(v).strip()]
            if len(values) == 1:
                clauses.append({"record_type": values[0]})
            elif values:
                clauses.append({"record_type": {"$in": values}})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
