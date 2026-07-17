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


def _minimal_brief_storyline(presentation_id: object) -> tuple[PresentationBrief, Storyline]:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="客户",
        purpose="汇报",
        duration_minutes=15,
        target_slide_count=8,
        core_message="核心",
    )
    storyline = Storyline(
        presentation_id=presentation_id,  # type: ignore[arg-type]
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
    return brief, storyline


def test_build_presentation_spec_comparison_layout() -> None:
    presentation_id = uuid4()
    brief, storyline = _minimal_brief_storyline(presentation_id)
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="方案对比",
            message="改造后通行效率显著提升",
            slide_type=SlideType.COMPARISON,
            key_points=["改造前：人车混行", "改造后：人车分流", "改造前：入口拥堵", "改造后：环形组织"],
        )
    ]

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
    )

    comparison = spec.slides[-1]
    assert comparison.layout == "comparison"
    assert len(comparison.columns) == 2
    assert comparison.columns[0].label == "改造前"
    assert len(comparison.columns[0].bullets) == 2
    assert comparison.columns[1].label == "改造后"


def test_build_presentation_spec_timeline_layout() -> None:
    presentation_id = uuid4()
    brief, storyline = _minimal_brief_storyline(presentation_id)
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="实施计划",
            message="分三阶段推进",
            slide_type=SlideType.TIMELINE,
            key_points=["2026 Q1：方案确认", "2026 Q3：施工图完成", "2027 Q2：竣工验收"],
        )
    ]

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
    )

    timeline = spec.slides[-1]
    assert timeline.layout == "timeline"
    assert len(timeline.timeline_items) == 3
    assert timeline.timeline_items[0].label == "2026 Q1"
    assert timeline.timeline_items[0].text == "方案确认"


def test_build_presentation_spec_data_layout() -> None:
    presentation_id = uuid4()
    brief, storyline = _minimal_brief_storyline(presentation_id)
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="关键指标",
            message="核心规模数据",
            slide_type=SlideType.DATA,
            key_points=["总建筑面积：120000 ㎡", "床位数：800", "绿地率：35%"],
        )
    ]

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=slides,
    )

    data_slide = spec.slides[-1]
    assert data_slide.layout == "data"
    assert len(data_slide.metrics) == 3
    assert data_slide.metrics[0].label == "总建筑面积"
    assert data_slide.metrics[0].value == "120000 ㎡"


def test_build_presentation_spec_image_full_layout(tmp_path: Path) -> None:
    presentation_id = uuid4()
    asset_id = uuid4()
    asset_file = tmp_path / "rendering.png"
    asset_file.write_bytes(b"png")
    brief, storyline = _minimal_brief_storyline(presentation_id)
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="效果展示",
            message="主入口人视效果图",
            slide_type=SlideType.IMAGE,
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.RENDERING,
                    description="主入口效果图",
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

    image_slide = spec.slides[-1]
    assert image_slide.layout == "image_full"
    assert len(image_slide.images) == 1
    assert image_slide.images[0].w == 8.6
