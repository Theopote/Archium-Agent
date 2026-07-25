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
