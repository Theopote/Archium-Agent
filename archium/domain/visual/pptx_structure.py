"""Native PPTX master / layout / placeholder structure declarations.

``FLAT`` mode places freeform shapes at absolute coordinates (historical V1).
``STRUCTURED`` mode declares real Slide Master / Slide Layout / Placeholder
graphs so PptxGenJS can emit OOXML ``p:sldMaster`` / ``p:sldLayout`` parts with
Slide → Layout → Master relationships.

Informed by the MIT-licensed ``hugohe3/ppt-master`` structured-template route;
this module is Archium's own domain model and contains no copied converter code.

Catalog factories and Node payload helpers live in
``archium.infrastructure.renderers.pptx_structure_catalog`` (DOM-014).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel


class PptxStructureMode(StrEnum):
    """How PPTX delivery encodes slide structure."""

    FLAT = "flat"
    STRUCTURED = "structured"


class PlaceholderKind(StrEnum):
    """PptxGenJS / OOXML placeholder types Archium emits."""

    TITLE = "title"
    BODY = "body"
    IMAGE = "image"
    CHART = "chart"
    TABLE = "table"
    MEDIA = "media"
    SLIDE_NUMBER = "slideNumber"


class PlaceholderSpec(DomainModel):
    """One placeholder slot on a slide layout (geometry in inches)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    placeholder_type: PlaceholderKind = PlaceholderKind.BODY
    semantic_role: str = ""
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    idx: int | None = Field(default=None, ge=0)
    prompt_text: str = ""

    @field_validator("name", "id", "semantic_role", "prompt_text", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _default_semantic_role(self) -> PlaceholderSpec:
        if not self.semantic_role:
            object.__setattr__(self, "semantic_role", self.placeholder_type.value)
        return self


class SlideMasterSpec(DomainModel):
    """A real PowerPoint slide master declaration.

    ``fixed_scene_node_ids`` lists RenderScene node ids that belong on the master
    chrome (logo, footer band, page number) rather than on each slide instance.
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    fixed_scene_node_ids: list[str] = Field(default_factory=list)
    background_color: str = "FFFFFF"
    description: str = ""

    @field_validator("fixed_scene_node_ids", mode="before")
    @classmethod
    def _normalize_node_ids(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value


class SlideLayoutSpec(DomainModel):
    """A real PowerPoint slide layout bound to a master, with placeholders."""

    id: str = Field(min_length=1)
    master_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    placeholder_specs: list[PlaceholderSpec] = Field(default_factory=list)
    layout_families: list[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("layout_families", mode="before")
    @classmethod
    def _normalize_families(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @model_validator(mode="after")
    def _unique_placeholder_names(self) -> SlideLayoutSpec:
        names = [spec.name for spec in self.placeholder_specs]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate placeholder names on layout {self.id!r}")
        return self


class PresentationStructureSpec(DomainModel):
    """Deck-level master/layout/placeholder graph for structured PPTX export."""

    mode: PptxStructureMode = PptxStructureMode.FLAT
    masters: list[SlideMasterSpec] = Field(default_factory=list)
    layouts: list[SlideLayoutSpec] = Field(default_factory=list)
    default_layout_id: str = ""

    @model_validator(mode="after")
    def _validate_graph(self) -> PresentationStructureSpec:
        if self.mode == PptxStructureMode.FLAT:
            return self
        if not self.masters:
            raise ValueError("STRUCTURED mode requires at least one SlideMasterSpec")
        if not self.layouts:
            raise ValueError("STRUCTURED mode requires at least one SlideLayoutSpec")
        master_ids = {master.id for master in self.masters}
        if len(master_ids) != len(self.masters):
            raise ValueError("duplicate SlideMasterSpec.id values")
        layout_ids = {layout.id for layout in self.layouts}
        if len(layout_ids) != len(self.layouts):
            raise ValueError("duplicate SlideLayoutSpec.id values")
        for layout in self.layouts:
            if layout.master_id not in master_ids:
                raise ValueError(
                    f"layout {layout.id!r} references unknown master_id {layout.master_id!r}"
                )
        if self.default_layout_id and self.default_layout_id not in layout_ids:
            raise ValueError(f"default_layout_id {self.default_layout_id!r} not in layouts")
        if not self.default_layout_id:
            object.__setattr__(self, "default_layout_id", self.layouts[0].id)
        return self

    def master_by_id(self, master_id: str) -> SlideMasterSpec:
        for master in self.masters:
            if master.id == master_id:
                return master
        raise KeyError(master_id)

    def layout_by_id(self, layout_id: str) -> SlideLayoutSpec:
        for layout in self.layouts:
            if layout.id == layout_id:
                return layout
        raise KeyError(layout_id)

    def layout_for_family(self, layout_family: str | None) -> SlideLayoutSpec:
        """Resolve the best layout for an Archium layout family name."""
        family = (layout_family or "").strip()
        if family:
            for layout in self.layouts:
                if family in layout.layout_families:
                    return layout
        return self.layout_by_id(self.default_layout_id)

