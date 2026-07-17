"""Models for chunk management."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.domain.document import DocumentChunk


@dataclass(frozen=True)
class ProjectContextBundle:
    """Retrieved project context for LLM prompts and citation linking."""

    text: str
    chunks: list[DocumentChunk] = field(default_factory=list)
    document_names: dict[UUID, str] = field(default_factory=dict)
