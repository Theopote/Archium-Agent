"""Retrieval filters for metadata-aware hybrid search."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.domain.architectural_chunk import ArchitecturalChunkType


@dataclass(frozen=True)
class RetrievalFilters:
    """Optional metadata constraints for Chroma / post-filters."""

    content_types: tuple[str, ...] = ()
    architectural_types: tuple[ArchitecturalChunkType, ...] = ()
    document_ids: tuple[UUID, ...] = ()

    def is_empty(self) -> bool:
        return not (self.content_types or self.architectural_types or self.document_ids)

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
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
