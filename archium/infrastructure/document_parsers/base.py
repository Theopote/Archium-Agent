"""Parsed document intermediate models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from archium.domain.enums import AssetType


class ParsedPage(BaseModel):
    """Text content extracted from a single page or section."""

    page_number: int | None = Field(default=None, ge=1)
    text: str
    section_title: str | None = None
    content_type: str = "text"


class ExtractedAsset(BaseModel):
    """Binary asset extracted during document parsing."""

    filename: str
    data: bytes
    page_number: int | None = Field(default=None, ge=1)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    asset_type: AssetType = AssetType.OTHER
    description: str | None = None


class ParsedDocument(BaseModel):
    """Normalized output from any document parser."""

    text: str
    pages: list[ParsedPage] = Field(default_factory=list)
    assets: list[ExtractedAsset] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    needs_ocr: bool = False
