"""Fixture scenes for slide recovery spike — five page archetypes."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.slide_recovery import SlideRecoveryPageKind
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)

PAGE_W = 10.0
PAGE_H = 5.625


def _base_scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=PAGE_W,
        page_height=PAGE_H,
        background=BackgroundStyle(color="#F7F6F3"),
        nodes=[],
    )


def title_page_scene() -> RenderScene:
    scene = _base_scene()
    scene.nodes = [
        TextNode(
            id="title",
            x=0.7,
            y=1.8,
            width=8.6,
            height=0.8,
            z_index=1,
            text="城市更新医疗综合体方案",
            semantic_role="title",
            font_family="Microsoft YaHei",
            font_size=34,
            color="#1A1A1A",
            line_height=45,
        ),
        TextNode(
            id="subtitle",
            x=0.7,
            y=2.8,
            width=8.0,
            height=0.5,
            z_index=2,
            text="汇报单位 · 2026",
            semantic_role="subtitle",
            font_family="Microsoft YaHei",
            font_size=18,
            color="#555555",
            line_height=24,
        ),
    ]
    return scene


def image_text_scene() -> RenderScene:
    scene = _base_scene()
    scene.nodes = [
        TextNode(
            id="title",
            x=0.7,
            y=0.45,
            width=8.6,
            height=0.66,
            z_index=0,
            text="交通组织与流线分析",
            semantic_role="title",
            font_family="Microsoft YaHei",
            font_size=34,
            color="#1A1A1A",
            line_height=45,
        ),
        TextNode(
            id="body",
            x=0.7,
            y=1.4,
            width=4.0,
            height=3.5,
            z_index=1,
            text="东侧主入口设置落客区，车行流线与步行流线分层组织。",
            semantic_role="body",
            font_family="Microsoft YaHei",
            font_size=16,
            color="#333333",
            line_height=22,
        ),
        ImageNode(
            id="diagram",
            x=5.2,
            y=1.3,
            width=4.1,
            height=3.6,
            z_index=2,
            storage_uri="asset://traffic.png",
            semantic_role="diagram",
        ),
    ]
    return scene


def table_page_scene() -> RenderScene:
    scene = _base_scene()
    cells = [
        ("指标", "现状", "目标"),
        ("床位数", "800", "1200"),
        ("建筑面积", "12万㎡", "18万㎡"),
        ("绿化率", "28%", "35%"),
    ]
    nodes: list[object] = [
        TextNode(
            id="title",
            x=0.7,
            y=0.45,
            width=8.6,
            height=0.66,
            z_index=0,
            text="核心指标对比",
            semantic_role="title",
            font_family="Microsoft YaHei",
            font_size=34,
            color="#1A1A1A",
            line_height=45,
        ),
    ]
    start_x, start_y = 0.8, 1.5
    col_w, row_h = 2.8, 0.55
    for row_index, row in enumerate(cells):
        for col_index, value in enumerate(row):
            nodes.append(
                TextNode(
                    id=f"cell_{row_index}_{col_index}",
                    x=start_x + col_index * col_w,
                    y=start_y + row_index * row_h,
                    width=col_w - 0.1,
                    height=row_h - 0.05,
                    z_index=1 + row_index,
                    text=value,
                    semantic_role="table_cell",
                    font_family="Microsoft YaHei",
                    font_size=14,
                    color="#222222",
                    line_height=18,
                )
            )
    scene.nodes = nodes  # type: ignore[assignment]
    return scene


def photo_page_scene() -> RenderScene:
    scene = _base_scene()
    scene.nodes = [
        TextNode(
            id="title",
            x=0.7,
            y=0.45,
            width=8.6,
            height=0.66,
            z_index=0,
            text="现场环境记录",
            semantic_role="title",
            font_family="Microsoft YaHei",
            font_size=34,
            color="#1A1A1A",
            line_height=45,
        ),
        ImageNode(
            id="photo_a",
            x=0.7,
            y=1.3,
            width=4.2,
            height=3.6,
            z_index=1,
            storage_uri="asset://site_a.jpg",
            semantic_role="site_photo",
        ),
        ImageNode(
            id="photo_b",
            x=5.1,
            y=1.3,
            width=4.2,
            height=3.6,
            z_index=2,
            storage_uri="asset://site_b.jpg",
            semantic_role="site_photo",
        ),
    ]
    return scene


def drawing_dominant_scene() -> RenderScene:
    scene = _base_scene()
    scene.nodes = [
        TextNode(
            id="title",
            x=0.7,
            y=0.45,
            width=8.6,
            height=0.66,
            z_index=0,
            text="院区总平面与改造范围",
            semantic_role="title",
            font_family="Microsoft YaHei",
            font_size=34,
            color="#1A1A1A",
            line_height=45,
        ),
        DrawingNode(
            id="site_plan",
            x=0.9,
            y=1.2,
            width=8.2,
            height=4.0,
            z_index=1,
            storage_uri="asset://site_plan.png",
            drawing_type="site_plan",
            fit_mode="contain",
            semantic_role="site_plan",
        ),
        TextNode(
            id="caption",
            x=0.9,
            y=5.2,
            width=8.0,
            height=0.35,
            z_index=2,
            text="图1 院区总平面（改造范围以虚线标示）",
            semantic_role="caption",
            font_family="Microsoft YaHei",
            font_size=12,
            color="#666666",
            line_height=16,
        ),
        ShapeNode(
            id="divider",
            x=0.7,
            y=1.1,
            width=8.6,
            height=0.02,
            z_index=3,
            shape_kind="line",
            stroke_color="#CCCCCC",
            stroke_width=1,
            semantic_role="divider",
        ),
    ]
    return scene


SPIKE_SCENES: dict[SlideRecoveryPageKind, RenderScene] = {
    SlideRecoveryPageKind.TITLE: title_page_scene(),
    SlideRecoveryPageKind.IMAGE_TEXT: image_text_scene(),
    SlideRecoveryPageKind.TABLE: table_page_scene(),
    SlideRecoveryPageKind.PHOTO: photo_page_scene(),
    SlideRecoveryPageKind.DRAWING_DOMINANT: drawing_dominant_scene(),
}
