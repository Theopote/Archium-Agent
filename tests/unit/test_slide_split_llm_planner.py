"""Unit tests for LLM-assisted narrative slide split planning."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.slide_split_llm_planner import (
    plan_from_llm_draft,
    try_build_llm_split_plan,
    validate_llm_split_draft,
)
from archium.application.slide_split_planner import build_split_plan
from archium.config.settings import Settings
from archium.domain.citation import Citation
from archium.domain.enums import SlideStatus, SlideType, VisualType
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.infrastructure.llm.presentation_schemas import SlideSplitDraft, SlideSplitPageDraft

from tests.fixtures.mock_llm import pipeline_mock_selector


def _traffic_slide(**overrides: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "ch-traffic",
        "order": 1,
        "title": "交通组织",
        "message": "人车混行导致通行效率低。",
        "slide_type": SlideType.CONTENT,
        "status": SlideStatus.PLANNED,
        "key_points": [
            "现状：人车混行 35%",
            "原因：落客区不足",
            "原因：货运与就医流线冲突",
            "策略一：分离人车动线",
            "策略二：增设落客缓冲",
            "策略三：优化货运时段",
        ],
        "source_citations": [
            Citation(
                document_id=uuid4(),
                document_name="交通专项规划.pdf",
                page_number=12,
                chunk_id=uuid4(),
                quote="人车混行比例 35%",
            )
        ],
        "visual_requirements": [
            VisualRequirement(type=VisualType.DIAGRAM, description="交通流线示意"),
        ],
    }
    defaults.update(overrides)
    return SlideSpec.model_construct(**defaults)  # type: ignore[arg-type]


def _storyline() -> Storyline:
    return Storyline(
        presentation_id=uuid4(),
        thesis="交通重组是改造核心",
        chapters=[
            Chapter(
                id="ch-traffic",
                title="交通组织",
                purpose="说明现状问题",
                key_message="人车冲突严重",
                order=0,
                estimated_slide_count=4,
            )
        ],
    )


def _brief() -> PresentationBrief:
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="老院区更新汇报",
        audience="院领导",
        purpose="确认改造方向",
        core_message="通过交通重组改善院区体验",
    )


class TestValidateLlmSplitDraft:
    def test_rejects_when_key_points_do_not_match_original(self) -> None:
        slide = _traffic_slide()
        draft = SlideSplitDraft(
            narrative_reason="测试",
            source=SlideSplitPageDraft(
                title="A",
                message="结论 A",
                key_points=slide.key_points[:5],
            ),
            continuation=SlideSplitPageDraft(
                title="B",
                message="结论 B",
                key_points=["编造的要点"],
            ),
        )

        valid, reason = validate_llm_split_draft(slide, draft)

        assert not valid
        assert "不一致" in reason

    def test_rejects_when_protected_content_is_dropped(self) -> None:
        slide = _traffic_slide()
        draft = SlideSplitDraft(
            narrative_reason="测试",
            source=SlideSplitPageDraft(
                title="A",
                message="结论 A",
                key_points=slide.key_points[:5],
            ),
            continuation=SlideSplitPageDraft(
                title="B",
                message="结论 B",
                key_points=["策略三：其他描述"],
            ),
        )

        valid, reason = validate_llm_split_draft(slide, draft)

        assert not valid
        assert "不一致" in reason


class TestLlmSplitPlanner:
    def test_plan_from_llm_draft_builds_narrative_pages(self) -> None:
        slide = _traffic_slide()
        draft = SlideSplitDraft(
            narrative_reason="按问题与策略拆分",
            source=SlideSplitPageDraft(
                title="交通组织 — 问题与原因",
                message="人车混行与落客不足是主要矛盾。",
                key_points=slide.key_points[:3],
                citation_indices=[0],
                visual_indices=[],
            ),
            continuation=SlideSplitPageDraft(
                title="交通组织 — 三项策略",
                message="通过三项策略改善交通组织。",
                key_points=slide.key_points[3:],
                citation_indices=[],
                visual_indices=[0],
            ),
        )

        plan = plan_from_llm_draft(
            slide,
            draft,
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert plan.planning_source == "llm"
        assert not plan.requires_human_approval
        assert plan.narrative_reason == "按问题与策略拆分"
        assert plan.primary_continuation.title.endswith("三项策略")
        assert len(plan.updated_source.key_points) == 3
        assert len(plan.primary_continuation.key_points) == 3
        assert plan.updated_source.source_citations
        assert plan.primary_continuation.visual_requirements

    def test_try_build_llm_split_plan_uses_mock_response(self) -> None:
        slide = _traffic_slide()
        llm = MockLLMProvider(selector=pipeline_mock_selector)

        plan = try_build_llm_split_plan(
            slide,
            "要点超过 5 条",
            llm=llm,
            settings=Settings(_env_file=None, slide_repair_enabled=True),
            brief=_brief(),
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert plan is not None
        assert plan.planning_source == "llm"
        assert llm.calls
        assert "叙事合理的两页拆分方案" in llm.calls[0].user_prompt

    def test_build_split_plan_prefers_llm_when_available(self) -> None:
        slide = _traffic_slide()
        llm = MockLLMProvider(selector=pipeline_mock_selector)

        plan = build_split_plan(
            slide,
            slide.model_copy(update={"key_points": slide.key_points[:5]}),
            slide.key_points[5:],
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
            llm=llm,
            settings=Settings(_env_file=None, slide_repair_enabled=True),
            brief=_brief(),
        )

        assert plan.planning_source == "llm"
        assert "问题与原因" in plan.updated_source.title
        assert plan.primary_continuation.message != "本页延续上一页内容，详见下列要点。"

    def test_build_split_plan_falls_back_to_rule_without_llm(self) -> None:
        slide = _traffic_slide()

        plan = build_split_plan(
            slide,
            slide.model_copy(update={"key_points": slide.key_points[:5]}),
            slide.key_points[5:],
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
        )

        assert plan.planning_source == "rule"
        assert len(plan.primary_continuation.key_points) == 1

    def test_build_split_plan_falls_back_when_repair_disabled(self) -> None:
        slide = _traffic_slide()
        llm = MockLLMProvider(selector=pipeline_mock_selector)

        plan = build_split_plan(
            slide,
            slide.model_copy(update={"key_points": slide.key_points[:5]}),
            slide.key_points[5:],
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
            llm=llm,
            settings=Settings(_env_file=None, slide_repair_enabled=False),
            brief=_brief(),
        )

        assert plan.planning_source == "rule"
        assert not llm.calls

    def test_choose_split_plan_prefers_rule_when_llm_needs_approval(self) -> None:
        from archium.application.slide_split_llm_planner import choose_split_plan
        from archium.domain.slide_split import SlideSplitPlan

        slide = _traffic_slide()
        rule_plan = build_split_plan(
            slide,
            slide.model_copy(update={"key_points": slide.key_points[:5]}),
            slide.key_points[5:],
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
        )
        llm_plan = plan_from_llm_draft(
            slide,
            SlideSplitDraft(
                narrative_reason="测试",
                source=SlideSplitPageDraft(
                    title="交通组织",
                    message="结论",
                    key_points=slide.key_points[:4],
                ),
                continuation=SlideSplitPageDraft(
                    title="交通组织（续）",
                    message="本页延续上一页内容，详见下列要点。",
                    key_points=slide.key_points[4:],
                ),
            ),
            "要点超过 5 条",
            storyline=_storyline(),
            chapter_slide_count=3,
        )
        assert llm_plan.requires_human_approval

        chosen = choose_split_plan(rule_plan, llm_plan)

        assert chosen.planning_source == "rule"

    def test_apply_tiered_layout_repair_uses_llm_narrative_split(self) -> None:
        from archium.application.slide_repair_policy import apply_tiered_layout_repair

        slide = _traffic_slide()
        llm = MockLLMProvider(selector=pipeline_mock_selector)

        outcome = apply_tiered_layout_repair(
            slide,
            storyline=_storyline(),
            chapter_slide_count=3,
            llm=llm,
            settings=Settings(_env_file=None, slide_repair_enabled=True),
            brief=_brief(),
        )

        assert outcome.split_plan is not None
        assert outcome.split_plan.planning_source == "llm"
        assert "问题与原因" in outcome.split_plan.updated_source.title
        assert outcome.split_slide is not None
        assert llm.calls
