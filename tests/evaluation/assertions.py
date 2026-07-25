"""Shared assertions for role-level evaluation (product contracts, not Agent classes)."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import (
    DesignCritiqueChallenge,
    DesignCritiqueReport,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_knowledge import ProjectKnowledgeItem


def assert_non_empty(text: str, *, field: str) -> None:
    assert (text or "").strip(), f"evaluation: {field} must be non-empty"


def assert_concept_direction_contract(direction: ConceptDirection) -> None:
    """ConceptDirection must carry spatial strategy, formal language, and risks.

    Social background is **not** on ConceptDirection — see DesignIntent.
    """
    assert_non_empty(direction.spatial_strategy, field="spatial_strategy")
    assert_non_empty(direction.formal_language, field="formal_language")
    assert direction.risks, "evaluation: risks must include at least one item"
    assert all(str(item).strip() for item in direction.risks), (
        "evaluation: risks entries must be non-empty"
    )


def assert_design_intent_social_background(intent: DesignIntent | None) -> None:
    assert intent is not None, "evaluation: DesignIntent required"
    assert_non_empty(intent.social_background, field="DesignIntent.social_background")


def assert_research_item_has_sources(item: ProjectKnowledgeItem) -> None:
    assert item.source_citations, (
        "evaluation: research knowledge item must cite sources"
    )
    has_url_or_title = any(
        (c.url or "").strip() or (c.source_title or "").strip()
        for c in item.source_citations
    )
    assert has_url_or_title, (
        "evaluation: each research item needs a citation url or source_title"
    )


def assert_research_item_has_design_knowledge(item: ProjectKnowledgeItem) -> None:
    knowledge = item.design_knowledge
    assert knowledge is not None, "evaluation: research item must carry DesignKnowledge"
    assert knowledge.has_substance, "evaluation: DesignKnowledge must have substance"
    assert_non_empty(knowledge.principle or knowledge.insight, field="principle|insight")
    assert_non_empty(
        knowledge.spatial_translation or knowledge.project_link,
        field="spatial_translation|project_link",
    )


def assert_critique_offers_counterexamples(report: DesignCritiqueReport) -> None:
    assert report.alternative_directions, (
        "evaluation: Critic must propose alternative / counterexample directions"
    )
    assert any(
        item.challenge == DesignCritiqueChallenge.ALTERNATIVE
        or "替代" in item.text
        or "可" in item.text
        for item in report.alternative_directions
    ), "evaluation: alternative_directions should read as counterexamples"


def assert_presentation_intent_contract(intent) -> None:
    """PresentationIntent must carry audience persuasion cues."""
    assert intent is not None, "evaluation: PresentationIntent required"
    assert_non_empty(intent.audience, field="PresentationIntent.audience")
    assert_non_empty(intent.purpose, field="PresentationIntent.purpose")
    assert_non_empty(intent.key_message, field="PresentationIntent.key_message")
    assert_non_empty(
        intent.persuasion_strategy,
        field="PresentationIntent.persuasion_strategy",
    )


def assert_storyline_quality_contract(storyline) -> None:
    assert storyline is not None, "evaluation: Storyline required"
    assert_non_empty(storyline.thesis, field="Storyline.thesis")
    assert storyline.chapters, "evaluation: Storyline must have chapters"
    assert all(
        (chapter.title or "").strip() and (chapter.key_message or "").strip()
        for chapter in storyline.chapters
    ), "evaluation: each chapter needs title and key_message"


def assert_slides_have_roles(slides: list) -> None:
    assert slides, "evaluation: slides required"
    missing = [
        slide.title
        for slide in slides
        if getattr(slide, "slide_role", None) is None
    ]
    assert not missing, (
        "evaluation: every slide should have SlideRole; missing on: "
        + "、".join(str(item) for item in missing[:5])
    )


def assert_presentation_critique_contract(report) -> None:
    assert report is not None, "evaluation: PresentationCritiqueReport required"
    assert 0.0 <= float(report.story_strength) <= 1.0
    assert 0.0 <= float(report.visual_quality) <= 1.0
    assert 0.0 <= float(report.architectural_expression) <= 1.0
    assert report.suggestions or report.missing_points, (
        "evaluation: critique should offer suggestions or missing_points"
    )
