"""Built-in PPTX master/layout catalogs and Node export payload (DOM-014).

Relocated from ``archium.domain.visual.pptx_structure`` factories.
"""

from __future__ import annotations

from archium.domain.visual.pptx_structure import (
    PlaceholderKind,
    PlaceholderSpec,
    PptxStructureMode,
    PresentationStructureSpec,
    SlideLayoutSpec,
    SlideMasterSpec,
)


def structure_spec_to_pptxgen_payload(spec: PresentationStructureSpec) -> dict[str, object]:
    """Serialize for the Node structured-export path."""
    return {
        "mode": spec.mode.value,
        "default_layout_id": spec.default_layout_id,
        "masters": [master.model_dump(mode="json") for master in spec.masters],
        "layouts": [layout.model_dump(mode="json") for layout in spec.layouts],
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


def p0_structured_spike_spec(
    *,
    page_width: float = 10.0,
    page_height: float = 5.625,
    background_color: str = "FFFFFF",
) -> PresentationStructureSpec:
    """P0-5 spike: one Master, three Layouts, required placeholder kinds.

    Required placeholders across the package:
    Title, Body, Picture (image), Slide Number.
    """
    margin_x = 0.5
    margin_y = 0.35
    content_w = max(1.0, page_width - margin_x * 2)
    title_h = 0.7
    body_y = margin_y + title_h + 0.15
    body_h = max(1.0, page_height - body_y - 0.55)
    bg = background_color.lstrip("#").upper() or "FFFFFF"
    master = SlideMasterSpec(
        id="master.spike",
        name="ARCHIUM_SPIKE_MASTER",
        fixed_scene_node_ids=["chrome.page_number"],
        background_color=bg,
        description="P0 structured spike - single shared master",
    )
    layouts = [
        SlideLayoutSpec(
            id="layout.spike_title",
            master_id=master.id,
            name="ARCHIUM_SPIKE_TITLE",
            layout_families=["hero"],
            description="Title layout with title + body + slide number",
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
                ),
                PlaceholderSpec(
                    id="ph.sldNum",
                    name="slide_number",
                    placeholder_type=PlaceholderKind.SLIDE_NUMBER,
                    semantic_role="slide_number",
                    x=page_width - 1.2,
                    y=page_height - 0.4,
                    width=0.7,
                    height=0.3,
                    idx=12,
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.spike_content",
            master_id=master.id,
            name="ARCHIUM_SPIKE_CONTENT",
            layout_families=["textual_argument"],
            description="Title + body + slide number",
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
                PlaceholderSpec(
                    id="ph.sldNum",
                    name="slide_number",
                    placeholder_type=PlaceholderKind.SLIDE_NUMBER,
                    semantic_role="slide_number",
                    x=page_width - 1.2,
                    y=page_height - 0.4,
                    width=0.7,
                    height=0.3,
                    idx=12,
                ),
            ],
        ),
        SlideLayoutSpec(
            id="layout.spike_picture",
            master_id=master.id,
            name="ARCHIUM_SPIKE_PICTURE",
            layout_families=["drawing_focus", "evidence_board"],
            description="Title + picture + body + slide number",
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
                    id="ph.picture",
                    name="picture",
                    placeholder_type=PlaceholderKind.IMAGE,
                    semantic_role="hero_image",
                    x=margin_x,
                    y=body_y,
                    width=content_w * 0.62,
                    height=body_h,
                    idx=1,
                ),
                PlaceholderSpec(
                    id="ph.caption",
                    name="caption",
                    placeholder_type=PlaceholderKind.BODY,
                    semantic_role="caption",
                    x=margin_x + content_w * 0.62 + 0.2,
                    y=body_y,
                    width=content_w * 0.38 - 0.2,
                    height=body_h,
                    idx=2,
                ),
                PlaceholderSpec(
                    id="ph.sldNum",
                    name="slide_number",
                    placeholder_type=PlaceholderKind.SLIDE_NUMBER,
                    semantic_role="slide_number",
                    x=page_width - 1.2,
                    y=page_height - 0.4,
                    width=0.7,
                    height=0.3,
                    idx=12,
                ),
            ],
        ),
    ]
    return PresentationStructureSpec(
        mode=PptxStructureMode.STRUCTURED,
        masters=[master],
        layouts=layouts,
        default_layout_id="layout.spike_content",
    )
