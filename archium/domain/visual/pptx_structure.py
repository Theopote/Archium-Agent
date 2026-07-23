"""Native PPTX master / layout / placeholder structure declarations.

``FLAT`` mode places freeform shapes at absolute coordinates (historical V1).
``STRUCTURED`` mode declares real Slide Master / Slide Layout / Placeholder
graphs so PptxGenJS can emit OOXML ``p:sldMaster`` / ``p:sldLayout`` parts with
Slide → Layout → Master relationships.

Informed by the MIT-licensed ``hugohe3/ppt-master`` structured-template route;
this module is Archium's own domain model and contains no copied converter code.
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

    def to_pptxgen_payload(self) -> dict[str, object]:
        """Serialize for the Node structured-export path."""
        return {
            "mode": self.mode.value,
            "default_layout_id": self.default_layout_id,
            "masters": [master.model_dump(mode="json") for master in self.masters],
            "layouts": [layout.model_dump(mode="json") for layout in self.layouts],
        }


def default_archium_structure_spec(
    *,
    page_width: float = 10.0,
    page_height: float = 5.625,
    background_color: str = "FFFFFF",
) -> PresentationStructureSpec:
    """Built-in master/layout/placeholder catalog for structured export.

    PptxGenJS maps each layout to one ``defineSlideMaster`` call (master + layout
    pair in OOXML). Multiple layouts therefore produce multiple real
    ``ppt/slideMasters`` and ``ppt/slideLayouts`` parts with inheritance links.
    """
    margin_x = 0.5
    margin_y = 0.35
    content_w = max(1.0, page_width - margin_x * 2)
    title_h = 0.7
    body_y = margin_y + title_h + 0.15
    body_h = max(1.0, page_height - body_y - 0.45)
    half_w = (content_w - 0.3) / 2
    bg = background_color.lstrip("#").upper() or "FFFFFF"

    masters = [
        SlideMasterSpec(
            id="master.chrome",
            name="ARCHIUM_CHROME_MASTER",
            fixed_scene_node_ids=["chrome.page_number", "chrome.footer"],
            background_color=bg,
            description="Shared chrome master for content layouts",
        ),
        SlideMasterSpec(
            id="master.title",
            name="ARCHIUM_TITLE_MASTER",
            fixed_scene_node_ids=["chrome.page_number"],
            background_color=bg,
            description="Title / section opening master",
        ),
        SlideMasterSpec(
            id="master.drawing",
            name="ARCHIUM_DRAWING_MASTER",
            fixed_scene_node_ids=["chrome.page_number", "chrome.footer"],
            background_color=bg,
            description="Drawing-dominant master",
        ),
    ]

    layouts = [
        SlideLayoutSpec(
            id="layout.title",
            master_id="master.title",
            name="ARCHIUM_LAYOUT_TITLE",
            layout_families=["hero"],
            description="Title + subtitle placeholders",
            placeholder_specs=[
                PlaceholderSpec(
                    id="ph.title",
                    name="title",
                    placeholder_type=PlaceholderKind.TITLE,
                    semantic_role="title",
                    x=margin_x,
                    y=page_height * 0.32,
                    width=content_w,
                    height=1.0,
                    idx=0,
                    prompt_text="Click to edit title",
                ),
                PlaceholderSpec(
                    id="ph.subtitle",
                    name="subtitle",
                    placeholder_type=PlaceholderKind.BODY,
                    semantic_role="subtitle",
                    x=margin_x,
                    y=page_height * 0.32 + 1.15,
                    width=content_w,
                    height=0.7,
                    idx=1,
                    prompt_text="Click to edit subtitle",
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.title_content",
            master_id="master.chrome",
            name="ARCHIUM_LAYOUT_TITLE_CONTENT",
            layout_families=[
                "textual_argument",
                "strategy_cards",
                "process_narrative",
                "metric_dashboard",
                "hybrid_canvas",
            ],
            description="Title + body placeholders",
            placeholder_specs=[
                PlaceholderSpec(
                    id="ph.title",
                    name="title",
                    placeholder_type=PlaceholderKind.TITLE,
                    semantic_role="title",
                    x=margin_x,
                    y=margin_y,
                    width=content_w,
                    height=title_h,
                    idx=0,
                ),
                PlaceholderSpec(
                    id="ph.body",
                    name="body",
                    placeholder_type=PlaceholderKind.BODY,
                    semantic_role="body",
                    x=margin_x,
                    y=body_y,
                    width=content_w,
                    height=body_h,
                    idx=1,
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.drawing_focus",
            master_id="master.drawing",
            name="ARCHIUM_LAYOUT_DRAWING",
            layout_families=["drawing_focus", "analytical_diagram"],
            description="Title + drawing image + caption",
            placeholder_specs=[
                PlaceholderSpec(
                    id="ph.title",
                    name="title",
                    placeholder_type=PlaceholderKind.TITLE,
                    semantic_role="title",
                    x=margin_x,
                    y=margin_y,
                    width=content_w,
                    height=title_h,
                    idx=0,
                ),
                PlaceholderSpec(
                    id="ph.drawing",
                    name="drawing",
                    placeholder_type=PlaceholderKind.IMAGE,
                    semantic_role="drawing",
                    x=margin_x,
                    y=body_y,
                    width=content_w * 0.72,
                    height=body_h,
                    idx=1,
                ),
                PlaceholderSpec(
                    id="ph.caption",
                    name="caption",
                    placeholder_type=PlaceholderKind.BODY,
                    semantic_role="caption",
                    x=margin_x + content_w * 0.72 + 0.2,
                    y=body_y,
                    width=content_w * 0.28 - 0.2,
                    height=body_h,
                    idx=2,
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.photo_grid",
            master_id="master.chrome",
            name="ARCHIUM_LAYOUT_PHOTO_GRID",
            layout_families=["evidence_board", "comparative_matrix"],
            description="Title + two image placeholders + body",
            placeholder_specs=[
                PlaceholderSpec(
                    id="ph.title",
                    name="title",
                    placeholder_type=PlaceholderKind.TITLE,
                    semantic_role="title",
                    x=margin_x,
                    y=margin_y,
                    width=content_w,
                    height=title_h,
                    idx=0,
                ),
                PlaceholderSpec(
                    id="ph.image_left",
                    name="image_left",
                    placeholder_type=PlaceholderKind.IMAGE,
                    semantic_role="hero_image",
                    x=margin_x,
                    y=body_y,
                    width=half_w,
                    height=body_h * 0.72,
                    idx=1,
                ),
                PlaceholderSpec(
                    id="ph.image_right",
                    name="image_right",
                    placeholder_type=PlaceholderKind.IMAGE,
                    semantic_role="supporting_image",
                    x=margin_x + half_w + 0.3,
                    y=body_y,
                    width=half_w,
                    height=body_h * 0.72,
                    idx=2,
                ),
                PlaceholderSpec(
                    id="ph.body",
                    name="body",
                    placeholder_type=PlaceholderKind.BODY,
                    semantic_role="body",
                    x=margin_x,
                    y=body_y + body_h * 0.72 + 0.12,
                    width=content_w,
                    height=max(0.4, body_h * 0.28 - 0.12),
                    idx=3,
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.blank",
            master_id="master.chrome",
            name="ARCHIUM_LAYOUT_BLANK",
            layout_families=[],
            description="Chrome-only fallback layout (absolute placement still allowed)",
            placeholder_specs=[],
        ),
    ]

    return PresentationStructureSpec(
        mode=PptxStructureMode.STRUCTURED,
        masters=masters,
        layouts=layouts,
        default_layout_id="layout.title_content",
    )
