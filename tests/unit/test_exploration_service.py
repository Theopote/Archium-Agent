"""Unit tests for pre-mission ExplorationService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.exploration_service import ExplorationService
from archium.application.mission_context_bridge import resolve_selected_concept_direction
from archium.domain.enums import (
    ConceptDirectionStatus,
    ExplorationSessionStatus,
    ProjectOriginMode,
)
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
    ConceptVisualPromptDraft,
)
from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
from archium.infrastructure.llm.mission_schemas import (
    AssumptionDraft,
    DesignIntentDraft,
    MissionGenerationDraft,
)
from archium.prompts.concept_direction import build_exploration_direction_user_prompt


@pytest.fixture
def concept_project(db_session):
    return ProjectRepository(db_session).create(
        Project(
            name="黄土高原文化中心",
            description="概念探索",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )


def _idea_seed_draft() -> IdeaSeedDraft:
    return IdeaSeedDraft(
        theme="地域文化再生",
        inspiration="人与黄土高原地貌的关系探索",
        keywords=["自然", "窑洞", "台地", "社区"],
        imagination_level="open",
    )


def _direction_batch() -> ConceptDirectionBatchDraft:
    return ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(
                title="台地聚落",
                summary="沿台地展开的开放群落",
                theme="台地生活",
                spatial_idea="分散院落 + 共享庭院",
                spatial_strategy="台地层级 + 院落聚落",
                formal_language="低平体量，连续屋面",
                material_strategy="夯土与木构",
                reference_dna=["窑洞类型学", "村落公共性"],
                visual_prompt=ConceptVisualPromptDraft(
                    image_prompt="terraced village cultural center",
                    camera="axonometric",
                    style="concept sketch",
                ),
                experience_focus="村民日常与游客穿行并存",
                differentiator="以台地地貌组织公共空间",
                open_questions=["规模上限？"],
                risks=["运营负担"],
            ),
            ConceptDirectionDraft(
                title="窑洞再生",
                summary="以窑洞原型转译当代公共空间",
                theme="窑洞当代化",
                spatial_idea="半地下连续拱廊",
                experience_focus="庇护与仪式感",
                differentiator="窑洞构造作为主叙事",
                open_questions=["防水与采光？"],
                risks=["施工复杂度"],
            ),
            ConceptDirectionDraft(
                title="景观驿站",
                summary="轻量驿站串联周边景观",
                theme="轻介入",
                spatial_idea="线性廊道与眺望点",
                experience_focus="路过停留",
                differentiator="最小建筑量",
                open_questions=["是否需要常驻功能？"],
                risks=["辨识度不足"],
            ),
        ]
    )


def _mission_draft() -> MissionGenerationDraft:
    return MissionGenerationDraft(
        title="黄土高原文化中心概念探索",
        task_statement="探索嵌入地域文化的小型文化中心",
        design_intent=DesignIntentDraft(
            theme="地域文化再生",
            problem_statement="如何在缺少任务书时建立可讨论方向？",
            social_background="",
            cultural_context="",
            target_users=["村民"],
            desired_experience="在地认同",
            core_questions=["如何延伸社区生活？"],
            research_needed=["关中乡村案例"],
            working_assumptions=["规模待确认"],
        ),
        assumptions=[
            AssumptionDraft(
                statement="假定位于陕西关中",
                reason="用户未提供地点",
                requires_confirmation=True,
            )
        ],
        clarifying_questions=[],
        knowledge_gaps=[],
    )


def test_start_session_enriches_idea_seed(db_session, concept_project) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = _idea_seed_draft()
    service = ExplorationService(db_session, llm)

    result = service.start_session(
        concept_project.id,
        "我想在黄土高原做一个文化中心",
    )
    seed = result.exploration.idea_seed
    assert seed is not None
    assert seed.raw_input == "我想在黄土高原做一个文化中心"
    assert seed.theme == "地域文化再生"
    assert "窑洞" in seed.keywords
    assert seed.is_enriched
    assert result.warnings == []


def test_start_session_degrades_when_llm_fails(db_session, concept_project) -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("llm down")
    service = ExplorationService(db_session, llm)

    result = service.start_session(concept_project.id, "秦岭山中的禅意文化中心")
    assert result.exploration.idea_seed is not None
    assert result.exploration.idea_seed.raw_input == "秦岭山中的禅意文化中心"
    assert not result.exploration.idea_seed.is_enriched
    assert result.warnings
    assert "想法解读未完成" in result.warnings[0]


def test_exploration_direction_prompt_includes_seed_keywords() -> None:
    from archium.domain.intent.idea_seed import IdeaSeed

    seed = IdeaSeed(
        raw_input="秦岭山中的禅意文化中心",
        theme="东方静谧",
        inspiration="人与自然关系探索",
        keywords=["自然", "静谧", "东方"],
    )
    prompt = build_exploration_direction_user_prompt(
        project_name="禅意中心",
        idea_text=seed.raw_input,
        idea_seed_block=seed.to_prompt_block(),
        count=3,
    )
    assert "自然" in prompt
    assert "静谧" in prompt
    assert "人与自然关系探索" in prompt


def test_generate_select_commit_creates_mission_without_prior_mission(
    db_session,
    concept_project,
) -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = [
        _idea_seed_draft(),
        _direction_batch(),
        _mission_draft(),
    ]
    service = ExplorationService(db_session, llm)

    started = service.start_session(
        concept_project.id,
        "我想在黄土高原做一个文化中心",
    )
    exploration = started.exploration
    assert exploration.status == ExplorationSessionStatus.EXPLORING
    assert exploration.idea_seed is not None
    assert exploration.idea_seed.is_enriched

    generated = service.generate_directions(exploration.id, count=3)
    assert len(generated.directions) == 3
    assert all(item.mission_id is None for item in generated.directions)
    assert all(
        item.exploration_session_id == exploration.id for item in generated.directions
    )
    assert all(item.status == ConceptDirectionStatus.DRAFT for item in generated.directions)

    selected = service.select_direction(generated.directions[1].id)
    assert selected.direction.status == ConceptDirectionStatus.SELECTED
    assert selected.exploration.status == ExplorationSessionStatus.DIRECTION_SELECTED
    assert selected.exploration.selected_direction_id == selected.direction.id

    committed = service.commit_to_mission(exploration.id)
    assert committed.exploration.status == ExplorationSessionStatus.COMMITTED
    assert committed.exploration.mission_id == committed.mission.id
    assert committed.direction.mission_id == committed.mission.id
    assert committed.mission.design_intent is not None
    assert committed.mission.design_intent.theme == "窑洞当代化"
    assert "窑洞原型" in committed.mission.design_intent.problem_statement

    listed = service.list_directions(exploration.id)
    assert all(item.mission_id == committed.mission.id for item in listed)
    resolved = resolve_selected_concept_direction(db_session, committed.mission.id)
    assert resolved is not None
    assert resolved.title == "窑洞再生"


def test_resolve_selected_falls_back_to_exploration_session(
    db_session,
    concept_project,
) -> None:
    """Before mission SELECTED rows exist, use exploration.selected_direction_id."""
    llm = MagicMock()
    llm.generate_structured.side_effect = [
        _idea_seed_draft(),
        _direction_batch(),
        _mission_draft(),
    ]
    service = ExplorationService(db_session, llm)
    exploration = service.start_session(concept_project.id, "一句话想法").exploration
    generated = service.generate_directions(exploration.id)
    selected = service.select_direction(generated.directions[0].id)
    committed = service.commit_to_mission(exploration.id)

    for item in service.list_directions(exploration.id):
        if item.status == ConceptDirectionStatus.SELECTED:
            item.mark_draft()
            from archium.infrastructure.database.repositories import (
                ConceptDirectionRepository,
            )

            ConceptDirectionRepository(db_session).update(item)
    db_session.commit()

    resolved = resolve_selected_concept_direction(db_session, committed.mission.id)
    assert resolved is not None
    assert resolved.id == selected.direction.id


def test_enrich_idea_seed_retries(db_session, concept_project) -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = [
        RuntimeError("first fail"),
        _idea_seed_draft(),
    ]
    service = ExplorationService(db_session, llm)
    started = service.start_session(concept_project.id, "未来养老社区")
    assert not started.exploration.idea_seed.is_enriched

    enriched = service.enrich_idea_seed(started.exploration.id)
    assert enriched.exploration.idea_seed is not None
    assert enriched.exploration.idea_seed.theme == "地域文化再生"
    assert enriched.exploration.idea_seed.is_enriched
