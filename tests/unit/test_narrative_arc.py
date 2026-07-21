"""Unit tests for narrative arc modeling and deck coherence rules."""

from __future__ import annotations

from uuid import uuid4

from archium.application.deck_coherence_qa_service import DeckCoherenceQAService
from archium.application.outline_service import outline_from_draft
from archium.domain.deck_coherence import (
    DECK_NO_ADVANCEMENT,
    DECK_STAGE_REGRESSION,
    DECK_STRATEGY_UNANCHORED,
)
from archium.domain.enums import NarrativeStage
from archium.domain.narrative_arc import NarrativeArc, NarrativePosition
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Storyline
from archium.domain.slide import SlideSpec
from archium.infrastructure.llm.presentation_schemas import OutlinePlanDraft, StorylineDraft


def test_storyline_draft_accepts_narrative_arc() -> None:
    draft = StorylineDraft.model_validate(
        {
            "thesis": "总体论点",
            "narrative_pattern": "problem_solution",
            "narrative_arc": {
                "opening_context": "背景",
                "central_problem": "问题",
                "tension_building": ["矛盾一"],
                "turning_point": "转折",
                "proposed_resolution": "方案",
                "final_decision": "决策",
            },
            "chapters": [
                {
                    "id": "ch1",
                    "title": "现状",
                    "purpose": "问题",
                    "key_message": "痛点",
                    "order": 0,
                    "estimated_slide_count": 3,
                }
            ],
        }
    )
    assert draft.narrative_arc is not None
    storyline = Storyline(
        presentation_id=uuid4(),
        thesis=draft.thesis,
        narrative_pattern=draft.narrative_pattern,
        narrative_arc=NarrativeArc(
            opening_context=draft.narrative_arc.opening_context,
            central_problem=draft.narrative_arc.central_problem,
            tension_building=list(draft.narrative_arc.tension_building),
            turning_point=draft.narrative_arc.turning_point,
            proposed_resolution=draft.narrative_arc.proposed_resolution,
            final_decision=draft.narrative_arc.final_decision,
        ),
    )
    assert storyline.narrative_arc is not None
    assert storyline.narrative_arc.central_problem == "问题"
    assert storyline.narrative_arc.tension_building == ["矛盾一"]


def test_outline_from_draft_maps_narrative_position() -> None:
    draft = OutlinePlanDraft.model_validate(
        {
            "title": "汇报",
            "thesis": "论点",
            "audience": "甲方",
            "purpose": "决策",
            "sections": [
                {
                    "id": "s1",
                    "title": "现状",
                    "purpose": "诊断",
                    "key_message": "存在混行风险",
                    "order": 0,
                    "category": "problem",
                    "narrative_position": {
                        "stage": "problem",
                        "advances_from_previous": "从背景进入问题",
                        "prepares_for_next": "为策略铺垫",
                    },
                }
            ],
        }
    )
    outline = outline_from_draft(draft, presentation_id=uuid4())
    assert outline.sections[0].narrative_position is not None
    assert outline.sections[0].narrative_position.stage == NarrativeStage.PROBLEM


def test_deck_coherence_detects_no_advancement() -> None:
    presentation_id = uuid4()
    outline = OutlinePlan(
        presentation_id=presentation_id,
        title="汇报",
        thesis="论点",
        audience="甲方",
        purpose="决策",
        sections=[
            OutlineSection(
                id="s1",
                title="问题一",
                purpose="诊断",
                key_message="同一结论需要被推进",
                order=0,
                category="problem",
                narrative_position=NarrativePosition(
                    stage=NarrativeStage.PROBLEM,
                    advances_from_previous="开场进入问题",
                    prepares_for_next="继续展开",
                ),
            ),
            OutlineSection(
                id="s2",
                title="问题二",
                purpose="重复",
                key_message="同一结论需要被推进",
                order=1,
                category="problem",
                narrative_position=NarrativePosition(
                    stage=NarrativeStage.PROBLEM,
                    advances_from_previous="",
                    prepares_for_next="准备策略",
                ),
            ),
        ],
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="s1",
            order=0,
            title="页1",
            message="现状需要治理。",
        )
    ]
    report = DeckCoherenceQAService().evaluate(slides, outline=outline)
    codes = {finding.rule_code for finding in report.findings}
    assert DECK_NO_ADVANCEMENT in codes


def test_deck_coherence_detects_strategy_unanchored() -> None:
    presentation_id = uuid4()
    outline = OutlinePlan(
        presentation_id=presentation_id,
        title="汇报",
        thesis="论点",
        audience="甲方",
        purpose="决策",
        sections=[
            OutlineSection(
                id="s1",
                title="策略",
                purpose="给方案",
                key_message="先做交通重组",
                order=0,
                category="strategy",
                narrative_position=NarrativePosition(
                    stage=NarrativeStage.STRATEGY,
                    advances_from_previous="直接给方案",
                    prepares_for_next="收尾",
                ),
            )
        ],
    )
    report = DeckCoherenceQAService().evaluate([], outline=outline)
    assert any(f.rule_code == DECK_STRATEGY_UNANCHORED for f in report.findings)


def test_deck_coherence_detects_stage_regression() -> None:
    presentation_id = uuid4()
    outline = OutlinePlan(
        presentation_id=presentation_id,
        title="汇报",
        thesis="论点",
        audience="甲方",
        purpose="决策",
        sections=[
            OutlineSection(
                id="s1",
                title="策略",
                purpose="方案",
                key_message="提出策略",
                order=0,
                category="strategy",
                narrative_position=NarrativePosition(
                    stage=NarrativeStage.STRATEGY,
                    advances_from_previous="进入策略",
                    prepares_for_next="",
                ),
            ),
            OutlineSection(
                id="s2",
                title="背景",
                purpose="回退",
                key_message="又讲背景",
                order=1,
                category="context",
                narrative_position=NarrativePosition(
                    stage=NarrativeStage.CONTEXT,
                    advances_from_previous="突然回到背景",
                    prepares_for_next="",
                ),
            ),
        ],
    )
    report = DeckCoherenceQAService().evaluate([], outline=outline)
    assert any(f.rule_code == DECK_STAGE_REGRESSION for f in report.findings)
