"""Unit tests for ArchitectureCase semantic library."""

from __future__ import annotations

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.application.design_knowledge_context import format_architecture_case_block
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.research_question import (
    ResearchQuestion,
    ResearchQuestionCategory,
)
from archium.prompts.concept_direction import build_exploration_direction_user_prompt


def test_meditation_query_retrieves_cross_type_cases() -> None:
    library = ArchitectureCaseLibraryService()
    matches = library.search("想创造一个安静冥想空间", limit=3)
    assert matches
    names = " ".join(m.case.name for m in matches)
    # Should migrate beyond literal "冥想室" naming — Vals / Bruder Klaus tags
    assert "Vals" in names or "Klaus" in names or "冥想" in " ".join(
        " ".join(m.case.tags) for m in matches
    )


def test_mountain_cultural_center_hits_terrace_type() -> None:
    library = ArchitectureCaseLibraryService()
    intent = DesignIntent(
        theme="山地公共文化",
        problem_statement="山地乡镇公共空间缺失",
        cultural_context="台地农耕聚落",
        research_needed=["山地文化建筑"],
    )
    matches = library.search_for_intent(intent, limit=3)
    assert matches
    assert any(
        "台地" in m.case.name or "台地" in " ".join(m.case.tags) for m in matches
    )


def test_case_block_injected_into_concept_prompt() -> None:
    questions = [
        ResearchQuestion(
            question="如何让山地文化中心成为社区公共核？",
            category=ResearchQuestionCategory.SOCIAL,
        )
    ]
    block = format_architecture_case_block(
        research_questions=questions,
        query_hint="山地文化中心 台地",
        limit=2,
    )
    assert "ArchitectureCase" in block
    prompt = build_exploration_direction_user_prompt(
        project_name="山地文化中心",
        idea_text="山地文化中心",
        count=2,
        design_knowledge_block=block,
    )
    assert "可迁移原则" in prompt or "核心策略" in prompt


def test_case_maps_to_design_knowledge() -> None:
    library = ArchitectureCaseLibraryService()
    matches = library.search("院落 社区", limit=1)
    assert matches
    knowledge = matches[0].case.to_design_knowledge()
    assert knowledge.has_substance
    assert knowledge.problem  # KN-013: design_problem kept as problem
    assert knowledge.strategy or knowledge.spatial_translation
    assert knowledge.precedent_ref == f"case:{matches[0].case.id}"
    round_trip = library.get_by_id(knowledge.precedent_ref)
    assert round_trip is not None
    assert round_trip.id == matches[0].case.id


def test_resolve_case_ids() -> None:
    library = ArchitectureCaseLibraryService()
    cases = library.resolve_ids(["case:ningbo_museum", "therme_vals", "missing_case"])
    assert [c.id for c in cases] == ["ningbo_museum", "therme_vals"]
