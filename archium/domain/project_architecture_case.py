"""Project-scoped architecture case — writable library row (seeds remain bootstrap)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.architecture_case import ArchitectureCase
from archium.domain.case_ref import normalize_case_id
from archium.domain.enums import ArchitectureCaseStatus


class ProjectArchitectureCase(IdentifiedModel, TimestampedModel):
    """Persisted ArchitectureCase under a project (slug = ArchitectureCase.id)."""

    project_id: UUID
    slug: str = Field(min_length=1, max_length=80)
    status: ArchitectureCaseStatus = ArchitectureCaseStatus.DRAFT
    source_knowledge_item_id: UUID | None = None
    name: str = Field(min_length=1)
    architect: str = ""
    location: str = ""
    year: str = ""
    building_type: str = ""
    context: str = ""
    design_problem: str = ""
    strategy: str = ""
    spatial_logic: str = ""
    material_language: str = ""
    atmosphere: str = ""
    transferable_principles: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: object) -> str:
        normalized = normalize_case_id(str(value) if value is not None else "")
        if normalized is None:
            raise ValueError("slug must be a valid case id (e.g. ningbo_museum)")
        return normalized

    def to_architecture_case(self) -> ArchitectureCase:
        return ArchitectureCase(
            id=self.slug,
            name=self.name,
            architect=self.architect,
            location=self.location,
            year=self.year,
            building_type=self.building_type,
            context=self.context,
            design_problem=self.design_problem,
            strategy=self.strategy,
            spatial_logic=self.spatial_logic,
            material_language=self.material_language,
            atmosphere=self.atmosphere,
            transferable_principles=list(self.transferable_principles),
            risks=list(self.risks),
            tags=list(self.tags),
        )

    def activate(self) -> None:
        self.status = ArchitectureCaseStatus.ACTIVE
        self.touch()

    def archive(self) -> None:
        self.status = ArchitectureCaseStatus.ARCHIVED
        self.touch()
