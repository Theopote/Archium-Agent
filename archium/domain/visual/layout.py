"""LayoutPlan — concrete spatial arrangement for a single slide."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.visual.element_lock import ElementLockScope
from archium.domain.visual.enums import (
    ConstraintPriority,
    CropPolicy,
    ImageFit,
    LayoutConstraintType,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    LayoutValidationStatus,
    OverflowPolicy,
)
from archium.domain.visual.render_scene import ChartSeriesData

# Post-compile spatial SSOT (DOM-011):
# - layout_plan: geometry owned by layout engine / LayoutPlan (compile source)
# - render_scene: geometry owned by RenderScene after Studio/scene mutation;
#   LayoutPlan is a synced mirror until the next layout-engine rewrite.
GeometryAuthority = Literal["layout_plan", "render_scene"]


class LayoutChartData(DomainModel):
    """Optional structured chart payload on a LayoutElement."""

    chart_type: str = Field(default="bar", min_length=1)
    title: str | None = None
    series: list[ChartSeriesData] = Field(default_factory=list)
    show_legend: bool = True
    show_value: bool = False


class LayoutTableData(DomainModel):
    """Optional structured table payload on a LayoutElement."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class LayoutElement(DomainModel):
    """A positioned element on the page (coordinates in page units)."""

    id: str = Field(min_length=1, max_length=100)
    role: LayoutElementRole
    content_type: LayoutContentType
    content_ref: str | None = None
    text_content: str | None = None
    chart_data: LayoutChartData | None = None
    table_data: LayoutTableData | None = None
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    z_index: int = 0
    alignment: str = "left"
    style_token: str | None = None
    font_size_override: float | None = Field(default=None, gt=0)
    fit_mode: ImageFit | None = None
    crop_policy: CropPolicy | None = None
    min_width: float | None = Field(default=None, gt=0)
    min_height: float | None = Field(default=None, gt=0)
    max_width: float | None = Field(default=None, gt=0)
    max_height: float | None = Field(default=None, gt=0)
    locked: bool = False
    lock_scopes: list[ElementLockScope] = Field(default_factory=list)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return self.width * self.height


class LayoutConstraint(DomainModel):
    """Declarative layout constraint attached to a plan."""

    constraint_type: LayoutConstraintType
    element_ids: list[str] = Field(default_factory=list)
    value: float | str | None = None
    priority: ConstraintPriority = ConstraintPriority.REQUIRED


class LayoutPlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """Concrete layout for one slide — independent of any renderer."""

    schema_version: int = Field(default=1, ge=1)
    slide_id: UUID
    layout_family: LayoutFamily
    layout_variant: str = Field(min_length=1)
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    grid_columns: int = Field(default=12, ge=1)
    grid_rows: int | None = Field(default=None, ge=1)
    hero_element_id: str | None = None
    reading_order: list[str] = Field(default_factory=list)
    whitespace_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    balance_strategy: str = "left_weighted"
    overflow_policy: OverflowPolicy = OverflowPolicy.WARN
    elements: list[LayoutElement] = Field(default_factory=list)
    constraints: list[LayoutConstraint] = Field(default_factory=list)
    design_system_id: UUID
    visual_intent_id: UUID
    validation_status: LayoutValidationStatus = LayoutValidationStatus.PENDING
    source_template_id: UUID | None = None
    source_template_layout_id: str | None = None
    geometry_authority: GeometryAuthority = "layout_plan"
    synced_scene_version: int | None = Field(
        default=None,
        description="RenderScene.version last mirrored into this plan when authority is render_scene.",
    )

    def with_layout_geometry_authority(self) -> Self:
        """Mark LayoutPlan as compile-time geometry source (layout engine rewrite)."""
        return self.model_copy(
            update={
                "geometry_authority": "layout_plan",
                "synced_scene_version": None,
            }
        )

    def with_scene_geometry_authority(self, scene_version: int) -> Self:
        """Mark RenderScene as spatial SSOT; plan elements are a synced mirror."""
        return self.model_copy(
            update={
                "geometry_authority": "render_scene",
                "synced_scene_version": scene_version,
            }
        )

    @model_validator(mode="after")
    def _validate_elements(self) -> LayoutPlan:
        ids = [element.id for element in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate layout element IDs are not allowed")
        for element in self.elements:
            if element.width <= 0 or element.height <= 0:
                raise ValueError(f"element {element.id} has non-positive size")
        if self.hero_element_id is not None and self.hero_element_id not in ids:
            raise ValueError(f"hero_element_id {self.hero_element_id} not found in elements")
        unknown = [ref for ref in self.reading_order if ref not in ids]
        if unknown:
            raise ValueError(f"reading_order references unknown elements: {unknown}")
        return self

    def element_by_id(self, element_id: str) -> LayoutElement | None:
        for element in self.elements:
            if element.id == element_id:
                return element
        return None

    def elements_by_role(self, role: LayoutElementRole) -> list[LayoutElement]:
        return [element for element in self.elements if element.role == role]
