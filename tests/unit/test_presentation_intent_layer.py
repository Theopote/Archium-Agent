"""Tests for PresentationIntent / SlideRole / VisualStrategy / PresentationCritic."""

from __future__ import annotations

from uuid import uuid4

from archium.application.presentation_critic import critique_presentation
from archium.application.presentation_intent_layer import (
    ensure_brief_presentation_intent,
    ensure_slide_role_layer,
    presentation_intent_from_mission,
)
from archium.domain.enums import PresentationType, ServiceDepth, SlideType
from archium.domain.presentation import PresentationBrief
from archium.domain.presentation_intent import (
    default_persuasion_for_type,
    infer_audience_mode,
)
from archium.domain.project_mission import ProjectMission
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import (
    SlideRole,
    resolve_slide_role,
    visual_strategy_from_role,
)
from archium.domain.enums import OutlineAudienceMode
from archium.domain.visual.visual_grammar import PageArchetype


def test_presentation_intent_from_mission_competition() -> None:
    mission = ProjectMission(
        project_id=uuid4(),
        title="山地艺术中心",
        task_statement="概念竞赛方案",
        requested_service_depths=[ServiceDepth.CONCEPT_DESIGN],
    )
    intent = presentation_intent_from_mission(
        mission,
        presentation_type=PresentationType.COMPETITION,
        audience="竞赛评委",
        purpose="展示概念力度",
        key_message="嵌入山体而非对峙",
    )
    assert "概念" in intent.persuasion_strategy or "创新" in intent.persuasion_strategy
    assert intent.audience_mode == OutlineAudienceMode.EXPERT_REVIEW
    assert intent.depth_level
    assert not intent.is_empty()
    assert "说服策略" in intent.to_prompt_block()


def test_ensure_brief_fills_persuasion() -> None:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="院领导汇报",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="院领导与投资方",
        purpose="争取改造立项",
        core_message="连廊重塑就医体验",
    )
    enriched = ensure_brief_presentation_intent(brief)
    assert enriched.presentation_intent is not None
    assert enriched.presentation_intent.persuasion_strategy.strip()
    assert enriched.presentation_intent.visual_style.strip()
    assert enriched.presentation_intent.audience_mode in {
        OutlineAudienceMode.CLIENT,
        OutlineAudienceMode.INVESTOR,
    }


def test_slide_role_from_archetype_and_strategy() -> None:
    role = resolve_slide_role(
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        slide_type=SlideType.CONTENT,
    )
    assert role == SlideRole.PROBLEM_ANALYSIS
    strategy = visual_strategy_from_role(role, page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS)
    assert not strategy.is_empty()
    assert "流线" in strategy.recommended_diagram or strategy.recommended_diagram


def test_ensure_slide_role_layer() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="交通冲突",
        message="现有流线导致医患交叉。",
        slide_type=SlideType.CONTENT,
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    )
    enriched = ensure_slide_role_layer(slide)
    assert enriched.slide_role == SlideRole.PROBLEM_ANALYSIS
    assert enriched.visual_strategy is not None
    assert not enriched.visual_strategy.is_empty()


def test_critique_to_review_issues_are_soft() -> None:
    from archium.application.presentation_critic import (
        critique_presentation,
        critique_to_review_issues,
    )
    from archium.domain.enums import ReviewLayer, ReviewSeverity

    brief = ensure_brief_presentation_intent(
        PresentationBrief(
            project_id=uuid4(),
            presentation_id=uuid4(),
            title="t",
            presentation_type=PresentationType.CLIENT_REVIEW,
            audience="甲方",
            purpose="决策",
            core_message="改善体验",
        )
    )
    slides = [
        SlideSpec(
            presentation_id=brief.presentation_id,
            chapter_id="ch1",
            order=0,
            title="问题",
            message="交通冲突严重。",
            slide_type=SlideType.CONTENT,
            slide_role=SlideRole.PROBLEM_ANALYSIS,
        )
    ]
    report = critique_presentation(brief=brief, slides=slides)
    issues = critique_to_review_issues(brief.presentation_id, report)
    assert issues
    assert all(i.reviewer_layer == ReviewLayer.PRESENTATION for i in issues)
    assert all(i.severity != ReviewSeverity.CRITICAL for i in issues)
    assert all(not i.auto_fixable for i in issues)


def test_presentation_critic_flags_missing_strategy_pages() -> None:
    brief = ensure_brief_presentation_intent(
        PresentationBrief(
            project_id=uuid4(),
            presentation_id=uuid4(),
            title="t",
            presentation_type=PresentationType.CLIENT_REVIEW,
            audience="甲方",
            purpose="决策",
            core_message="改善体验",
        )
    )
    slides = [
        SlideSpec(
            presentation_id=uuid4(),
            chapter_id="ch1",
            order=0,
            title="问题",
            message="交通冲突严重。",
            slide_type=SlideType.CONTENT,
            slide_role=SlideRole.PROBLEM_ANALYSIS,
        ),
        SlideSpec(
            presentation_id=uuid4(),
            chapter_id="ch1",
            order=1,
            title="策略",
            message=(
                "用风雨连廊重组动线并改善候诊体验同时兼顾后勤与急救通道的多重目标"
                "还要回应投资与工期约束下的分期实施问题。"
            ),
            slide_type=SlideType.CONTENT,
            slide_role=SlideRole.STRATEGY,
        ),
    ]
    report = critique_presentation(brief=brief, slides=slides)
    assert 0.0 <= report.story_strength <= 1.0
    assert report.missing_points or report.suggestions or report.overloaded_slides
    assert default_persuasion_for_type(PresentationType.COMPETITION)
    assert infer_audience_mode("规委审查", PresentationType.OTHER) == OutlineAudienceMode.GOVERNMENT
