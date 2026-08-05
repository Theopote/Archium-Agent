"""Text vs background contrast guard — readability hard requirement."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.color_contrast import (
    MIN_CONTRAST_BODY,
    contrast_ratio,
    ensure_contrast,
    ensure_readable_pair,
)
from archium.application.visual.text_contrast_guard import (
    apply_text_background_contrast_to_scene,
    scene_text_contrast_failures,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
    TextParagraph,
    ThemeTokens,
)


def _text(
    *,
    color: str,
    role: str = "body_text",
    size: float = 14.0,
    opacity: float = 1.0,
) -> TextNode:
    return TextNode(
        id=f"t_{role}",
        semantic_role=role,
        x=0.5,
        y=0.5,
        width=8,
        height=0.5,
        text="可读性测试",
        paragraphs=[TextParagraph(text="可读性测试")],
        font_family="Arial",
        font_size=size,
        font_weight=400,
        color=color,
        line_height=size * 1.2,
        opacity=opacity,
    )


def _scene(bg: str, *nodes: TextNode) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color=bg),
        nodes=list(nodes),
        theme_tokens=ThemeTokens(),
    )


def test_light_gray_on_white_is_corrected() -> None:
    scene = _scene("#FFFFFF", _text(color="#C8C8C8", role="body_text"))
    assert scene_text_contrast_failures(scene)
    fixed = apply_text_background_contrast_to_scene(scene)
    body = next(n for n in fixed.nodes if n.id == "t_body_text")
    assert contrast_ratio(body.color, "#FFFFFF") >= MIN_CONTRAST_BODY
    assert not scene_text_contrast_failures(fixed)
    assert "text_contrast:enforced" in fixed.warnings


def test_dark_gray_on_near_black_becomes_light_ink() -> None:
    scene = _scene("#1A1A1A", _text(color="#2A2A2A", role="title", size=28))
    fixed = apply_text_background_contrast_to_scene(scene)
    title = next(n for n in fixed.nodes if n.id == "t_title")
    assert contrast_ratio(title.color, "#1A1A1A") >= 3.0
    # Prefer light ink on dark boards.
    assert contrast_ratio(title.color, "#1A1A1A") > contrast_ratio("#121212", "#1A1A1A")


def test_ensure_readable_pair_upgrades_bad_design_tokens() -> None:
    bg, text = ensure_readable_pair("#EEEEEE", "#DDDDDD")
    assert contrast_ratio(text, bg) >= MIN_CONTRAST_BODY


def test_ensure_contrast_keeps_good_colors() -> None:
    assert ensure_contrast("#111111", "#FFFFFF") == "#111111"
    assert ensure_contrast("#F5F5F5", "#111111").upper() in {"#F5F5F5", "#F7F7F5"}
