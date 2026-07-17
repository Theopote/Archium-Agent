"""Citation model linking claims to source documents."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import DomainModel


class Citation(DomainModel):
    """Reference to a source document supporting a fact or slide claim."""

    document_id: UUID
    document_name: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    chunk_id: UUID | None = None
    quote: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("document_name")
    @classmethod
    def _strip_document_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("document_name must not be empty")
        return stripped
