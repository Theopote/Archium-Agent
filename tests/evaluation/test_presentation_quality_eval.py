"""Evaluation: Presentation Delivery contracts (Narrative → Visual critique).

Scenario: mountain cultural center deck must carry PresentationIntent,
storyline chapters, slide roles, and a usable PresentationCritic report.
"""

from __future__ import annotations

from uuid import uuid4

from archium.application.presentation_critic import critique_presentation
from archium.domain.enums import PresentationType
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.presentation_intent import PresentationIntent
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole, VisualStrategy
from tests.evaluation.assertions import (
    assert_presentation_critique_contract,
    assert_presentation_intent_contract,
    assert_slides_have_roles,
    assert_storyline_quality_contract,
)


def _intent() -> PresentationIntent:
    return PresentationIntent(
        audience="竞赛评委",
        purpose="说服评委接受山地文化中心概念",
        key_message="建筑以台地聚落融入山体，成为地域文化公共核",
        persuasion_strategy="概念力度 + 空间转译 + 地域证据",
        visual_style="稀疏图板 · 剖面与体量并重",
        depth_level="concept",
        presentation_type=PresentationType.COMPETITION,
    )


def _storyline(presentation_id) -> Storyline:
    return Storyline(
        presentation_id=presentation_id,
        thesis="山地文化中心通过台地组织成为聚落式公共文化核",
        narrative_pattern="problem_solution",
        chapters=[
            Chapter(
                id="ch-site",
                title="山地语境",
                purpose="建立基地与地域文化条件",
                key_message="坡地与聚落肌理是设计起点",
                order=0,
            ),
            Chapter(
                id="ch-concept",
                title="概念判断",
                purpose="提出空间策略",
                key_message="台地层级组织公共空间",
                order=1,
            ),
            Chapter(
                id="ch-experience",
                title="体验与形式",
                purpose="证明空间体验",
                key_message="低平体量嵌入坡地",
                order=2,
            ),
        ],
    )


def _slides(presentation_id) -> list[SlideSpec]:
    return [
        SlideSpec(
            id=uuid4(),
            presentation_id=presentation_id,
            chapter_id="ch-site",
            order=0,
            title="基地与坡地",
            message="坡地与聚落肌理约束公共建筑落位",
            key_points=["等高线", "聚落肌理"],
            slide_role=SlideRole.SITE_ANALYSIS,
            visual_strategy=VisualStrategy(recommended_diagram="坡地剖面"),
        ),
        SlideSpec(
            id=uuid4(),
            presentation_id=presentation_id,
            chapter_id="ch-concept",
            order=1,
            title="台地策略",
            message="台地层级组织公共空间与观景轴线",
            key_points=["台地", "轴线"],
            slide_role=SlideRole.STRATEGY,
            visual_strategy=VisualStrategy(recommended_diagram="空间结构图"),
        ),
        SlideSpec(
            id=uuid4(),
            presentation_id=presentation_id,
            chapter_id="ch-experience",
            order=2,
            title="空间体验",
            message="低平体量嵌入坡地，形成漫游文化体验",
            key_points=["漫游", "嵌入"],
            slide_role=SlideRole.EXPERIENCE,
        ),
    ]


def test_presentation_quality_contract_for_mountain_center() -> None:
    presentation_id = uuid4()
    intent = _intent()
    assert_presentation_intent_contract(intent)

    storyline = _storyline(presentation_id)
    assert_storyline_quality_contract(storyline)

    slides = _slides(presentation_id)
    assert_slides_have_roles(slides)

    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="山地文化中心概念汇报",
        purpose=intent.purpose,
        audience=intent.audience,
        core_message=intent.key_message,
        presentation_intent=intent,
    )
    report = critique_presentation(brief=brief, storyline=storyline, slides=slides)
    assert_presentation_critique_contract(report)
    assert report.story_strength >= 0.55
