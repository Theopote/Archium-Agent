"""Unit tests for outline planning."""

from __future__ import annotations

from uuid import uuid4

from archium.application.outline_service import (
    apply_audience_mode,
    infer_audience_mode,
    merge_template_with_storyline,
)
from archium.application.outline_templates import (
    cultural_village_outline_sections,
    detect_scenario_template,
    renovation_outline_sections,
)
from archium.domain.enums import ApprovalStatus, OutlineAudienceMode
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Chapter, PresentationBrief, Storyline


def _sample_brief(*, audience: str = "政府主管部门", purpose: str = "文化名村保护提升") -> PresentationBrief:
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="测试汇报",
        audience=audience,
        purpose=purpose,
        core_message="保护传承",
        target_slide_count=25,
        required_sections=["历史沿革", "传播品牌"],
    )


def _sample_storyline(presentation_id) -> Storyline:
    return Storyline(
        presentation_id=presentation_id,
        thesis="保护与发展并重",
        chapters=[
            Chapter(
                id="history",
                title="历史沿革",
                purpose="历史认知",
                key_message="明代建村",
                order=0,
            )
        ],
    )


def test_cultural_village_template_has_core_sections() -> None:
    sections = cultural_village_outline_sections()
    titles = {section.title for section in sections}
    assert "历史沿革" in titles
    assert "总结与决策事项" in titles
    assert len(sections) >= 25


def test_renovation_template_has_problem_strategy_sections() -> None:
    sections = renovation_outline_sections()
    titles = {section.title for section in sections}
    assert "交通问题" in titles
    assert "改造前后对比" in titles


def test_detect_scenario_template_for_cultural_village() -> None:
    key = detect_scenario_template(purpose="文化名村保护提升汇报", audience="文旅局")
    assert key == "cultural_village"


def test_apply_audience_mode_reorders_expert_technical_first() -> None:
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="测试",
        thesis="论点",
        audience="专家",
        purpose="评审",
        sections=[
            OutlineSection(
                id="a",
                title="封面",
                purpose="p",
                key_message="m",
                order=0,
                category="intro",
            ),
            OutlineSection(
                id="b",
                title="结构",
                purpose="p",
                key_message="m",
                order=1,
                category="technical",
            ),
        ],
    )
    updated = apply_audience_mode(outline, OutlineAudienceMode.EXPERT_REVIEW)
    assert updated.sections[0].category == "technical"


def test_merge_template_with_storyline_overlays_chapter_message() -> None:
    brief = _sample_brief()
    storyline = _sample_storyline(brief.presentation_id)
    outline = merge_template_with_storyline(brief, storyline)
    history = next(section for section in outline.sections if section.id == "history")
    assert history.key_message == "明代建村"
    assert outline.estimated_slide_total >= 20


def test_infer_audience_mode_from_text() -> None:
    assert infer_audience_mode("政府主管部门") == OutlineAudienceMode.GOVERNMENT
    assert infer_audience_mode("设计团队内部评审") == OutlineAudienceMode.INTERNAL_DESIGN


def test_outline_not_approved_blocks_slide_generation_semantics() -> None:
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title="测试",
        thesis="论点",
        audience="政府",
        purpose="汇报",
        approval_status=ApprovalStatus.PENDING,
        sections=[
            OutlineSection(
                id="cover",
                title="封面",
                purpose="p",
                key_message="m",
                order=0,
            )
        ],
    )
    assert not outline.is_approved
