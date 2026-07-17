"""Unit tests for PresentationSpec builder."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.domain.enums import PresentationType, SlideType, VisualType
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.renderers.presentation_spec_builder import build_presentation_spec


def test_build_presentation_spec_includes_title_and_thesis() -> None:
    presentation_id = uuid4()
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="院区更新汇报",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="医院管理层",
        purpose="确认方向",
        duration_minutes=20,
        target_slide_count=10,
        core_message="通过交通重组改善体验",
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="交通重组是更新核心",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="分析问题",
                key_message="交通混乱",
                order=0,
            )
        ],
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="现状问题",
            message="人车混行影响效率",
            key_points=["入口拥堵", "流线交叉"],
        )
    ]

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
    )

    assert spec.title == "院区更新汇报"
    assert spec.slides[0].layout == "title"
    assert spec.slides[1].layout == "thesis"
    assert spec.slides[2].layout == "content_bullets"
    assert spec.slides[2].bullets == ["入口拥堵", "流线交叉"]


def test_build_presentation_spec_uses_image_layout_when_assets_present(tmp_path: Path) -> None:
    presentation_id = uuid4()
    asset_id = uuid4()
    asset_file = tmp_path / "site_plan.png"
    asset_file.write_bytes(b"png")
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="客户",
        purpose="汇报",
        duration_minutes=15,
        target_slide_count=8,
        core_message="核心",
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="论点",
        chapters=[
            Chapter(
                id="ch1",
                title="章节",
                purpose="展开论述",
                key_message="核心观点",
                order=0,
            )
        ],
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="总图分析",
            message="交通组织需优化",
            slide_type=SlideType.CONTENT,
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    required=True,
                    preferred_asset_ids=[asset_id],
                )
            ],
        )
    ]

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
        asset_paths={asset_id: asset_file},
    )

    content_slide = spec.slides[-1]
    assert content_slide.layout == "image_content"
    assert len(content_slide.images) == 1
    assert content_slide.images[0].asset_path == str(asset_file)
