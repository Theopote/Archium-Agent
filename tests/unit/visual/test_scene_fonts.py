"""Tests for shared RenderScene font policy."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_fonts import (
    DEFAULT_CJK_FONT,
    DEFAULT_LATIN_FONT,
    collect_font_assets,
    detect_font_fallbacks,
    repair_scene_fonts,
    resolve_text_fonts,
    text_has_cjk,
)
from archium.domain.visual import default_presentation_design_system
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
)


def test_resolve_text_fonts_prefers_cjk_for_chinese() -> None:
    resolved = resolve_text_fonts(
        "老院区交通与环境问题",
        cjk_family=DEFAULT_CJK_FONT,
        latin_family=DEFAULT_LATIN_FONT,
    )
    assert resolved.primary == DEFAULT_CJK_FONT
    assert resolved.cjk == DEFAULT_CJK_FONT
    assert resolved.latin == DEFAULT_LATIN_FONT
    assert resolved.script == "cjk"


def test_resolve_text_fonts_prefers_latin_for_english() -> None:
    resolved = resolve_text_fonts(
        "Hello Site Plan",
        cjk_family=DEFAULT_CJK_FONT,
        latin_family=DEFAULT_LATIN_FONT,
    )
    assert resolved.primary == DEFAULT_LATIN_FONT
    assert resolved.script == "latin"


def test_detect_font_fallbacks_flags_arial_on_cjk() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                x=0,
                y=0,
                width=8,
                height=1,
                text="老院区交通与环境问题",
                font_family="Arial",
                font_family_cjk=DEFAULT_CJK_FONT,
                font_family_latin="Arial",
                font_size=34,
                color="#111111",
                line_height=1.2,
            )
        ],
    )
    notes = detect_font_fallbacks(scene)
    assert any("Arial→Microsoft YaHei" in note for note in notes)
    assert text_has_cjk("老院区")


def test_repair_scene_fonts_rewrites_primary_to_cjk() -> None:
    design = default_presentation_design_system()
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                semantic_role="title",
                x=0,
                y=0,
                width=8,
                height=1,
                text="老院区交通与环境问题",
                font_family="Arial",
                font_size=34,
                color="#111111",
                line_height=1.2,
            )
        ],
        theme_tokens={
            "colors": {},
            "typography": {
                "title": {
                    "font_family": DEFAULT_CJK_FONT,
                    "font_family_latin": "Arial",
                    "font_size": 34,
                    "font_weight": 700,
                }
            },
            "spacing": {},
        },
    )
    # theme_tokens needs ThemeTokens model — use model_validate via compile path
    from archium.domain.visual.render_scene import ThemeTokens

    scene = scene.model_copy(
        update={
            "theme_tokens": ThemeTokens(
                typography={
                    "title": {
                        "font_family": DEFAULT_CJK_FONT,
                        "font_family_latin": "Arial",
                        "font_size": 34,
                        "font_weight": 700,
                    }
                }
            )
        }
    )
    repaired = repair_scene_fonts(scene)
    title = repaired.node_by_id("title")
    assert isinstance(title, TextNode)
    assert title.font_family == DEFAULT_CJK_FONT
    assert title.font_family_cjk == DEFAULT_CJK_FONT
    assert title.font_family_latin == "Arial"
    assert any(a.role == "title" and a.script == "cjk" for a in repaired.font_assets)
    assert any(a.family == DEFAULT_CJK_FONT for a in repaired.font_assets)


def test_collect_font_assets_covers_all_typography_roles() -> None:
    design = default_presentation_design_system()
    assets = collect_font_assets(design, [])
    roles = {a.role for a in assets}
    for role in (
        "display",
        "title",
        "subtitle",
        "heading",
        "body",
        "caption",
        "metric",
        "footnote",
        "source",
    ):
        assert role in roles
