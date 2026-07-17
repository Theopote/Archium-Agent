"""Source document and chunk models."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import DocumentType, ProcessingStatus


class SourceDocument(IdentifiedModel, TimestampedModel):
    """An imported project source file."""

    project_id: UUID
    filename: str = Field(min_length=1)
    original_path: str = Field(min_length=1)
    stored_path: str = Field(min_length=1)
    file_type: DocumentType
    file_hash: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    page_count: int | None = Field(default=None, ge=1)
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("file_hash")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.lower().strip()
        if len(normalized) != 64 or not all(c in "0123456789abcdef" for c in normalized):
            raise ValueError("file_hash must be a 64-character SHA-256 hex digest")
        return normalized

    def mark_processing(self) -> None:
        self.processing_status = ProcessingStatus.PROCESSING
        self.touch()

    def mark_completed(self, *, page_count: int | None = None) -> None:
        self.processing_status = ProcessingStatus.COMPLETED
        if page_count is not None:
            self.page_count = page_count
        self.touch()

    def mark_failed(self) -> None:
        self.processing_status = ProcessingStatus.FAILED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class DocumentChunk(IdentifiedModel):
    """A searchable text segment extracted from a source document."""

    project_id: UUID
    document_id: UUID
    content: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    content_type: str = "text"
    chunk_index: int = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)
