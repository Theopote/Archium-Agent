"""Visual asset domain model."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel
from archium.domain.enums import AssetType


class Asset(IdentifiedModel):
    """A visual or media asset associated with a project."""

    project_id: UUID
    document_id: UUID | None = None
    filename: str = Field(min_length=1)
    path: str = Field(min_length=1)
    asset_type: AssetType = AssetType.OTHER
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, ge=1)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip().lower() for tag in value if tag.strip()]

    @property
    def aspect_ratio(self) -> float | None:
        if self.width and self.height:
            return self.width / self.height
        return None

    @property
    def is_low_resolution(self) -> bool:
        if self.width is None or self.height is None:
            return False
        return self.width < 800 or self.height < 600
