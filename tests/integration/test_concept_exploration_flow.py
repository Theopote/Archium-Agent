"""Integration tests for concept exploration planning without uploaded documents."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from archium.application.exploration_service import ExplorationService
from archium.application.mission_parser import parse_mission_draft
from archium.application.project_mission_service import ProjectMissionService
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
)
from archium.infrastructure.llm.mission_schemas import (
    AssumptionDraft,
    ClarifyingQuestionDraft,
    DesignIntentDraft,
    MissionGenerationDraft,
)


@pytest.fixture
def concept_project(db_session):
    return ProjectRepository(db_session).create(
        Project(
            name="黄土高原文化中心",
            description="概念探索",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )


def test_generate_mission_concept_mode_persists_design_intent(
    db_session,
    concept_project,
) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = MissionGenerationDraft(
        title="黄土高原文化中心概念探索",
        task_statement="探索一种嵌入黄土高原地域文化的当代文化中心模式",
        design_intent=DesignIntentDraft(
            theme="地域文化再生",
            problem_statement="如何在缺乏完整任务书时建立可讨论的设计方向？",
            social_background="乡村人口外流与本土文化记忆断层",
            cultural_context="黄土高原窑洞与台地景观",
            target_users=["村民", "游客"],
            desired_experience="在地认同与开放交流并存",
            core_questions=["如何让建筑成为社区生活的延伸？"],
            research_needed=["关中乡村公共文化空间案例"],
            working_assumptions=["初期规模约 500–800㎡，待确认"],
        ),
        assumptions=[
            AssumptionDraft(
                statement="假定项目位于陕西关中乡村",
                reason="用户未提供精确地点，需后续确认",
                requires_confirmation=True,
            )
        ],
        clarifying_questions=[],
        knowledge_gaps=[],
    )

    service = ProjectMissionService(db_session, llm)
    result = service.generate_mission(
        concept_project.id,
        "我想在黄土高原做一个文化中心",
        origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
    )

    assert result.mission.design_intent is not None
    assert "地域文化" in result.mission.design_intent.theme
    assert result.assumptions
    assert all(not question.blocking for question in result.clarifying_questions)


def test_exploration_before_mission_commit_flow(db_session, concept_project) -> None:
    from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft

    llm = MagicMock()
    llm.generate_structured.side_effect = [
        IdeaSeedDraft(
            theme="地域文化",
            inspiration="黄土高原生活",
            keywords=["台地", "窑洞"],
            imagination_level="open",
        ),
        ConceptDirectionBatchDraft(
            directions=[
                ConceptDirectionDraft(
                    title="台地聚落",
                    summary="沿台地展开",
                    theme="台地生活",
                    spatial_idea="分散院落",
                    experience_focus="日常与穿行",
                    differentiator="台地组织",
                    open_questions=["规模？"],
                    risks=["运营"],
                ),
                ConceptDirectionDraft(
                    title="窑洞再生",
                    summary="窑洞原型转译",
                    theme="窑洞当代化",
                    spatial_idea="连续拱廊",
                    experience_focus="庇护",
                    differentiator="窑洞叙事",
                    open_questions=["采光？"],
                    risks=["施工"],
                ),
            ]
        ),
        MissionGenerationDraft(
            title="黄土高原文化中心概念探索",
            task_statement="探索嵌入地域文化的小型文化中心",
            design_intent=DesignIntentDraft(
                theme="地域文化再生",
                problem_statement="如何建立可讨论方向？",
                social_background="",
                cultural_context="",
                target_users=["村民"],
                desired_experience="在地认同",
                core_questions=[],
                research_needed=[],
                working_assumptions=[],
            ),
            assumptions=[],
            clarifying_questions=[],
            knowledge_gaps=[],
        ),
    ]

    service = ExplorationService(db_session, llm)
    exploration = service.start_session(
        concept_project.id, "我想在黄土高原做一个文化中心"
    ).exploration
    assert exploration.idea_seed is not None
    assert exploration.idea_seed.is_enriched

    generated = service.generate_directions(exploration.id)
    assert all(d.mission_id is None for d in generated.directions)

    selected = service.select_direction(generated.directions[0].id)
    assert selected.direction.status == ConceptDirectionStatus.SELECTED

    committed = service.commit_to_mission(exploration.id)
    assert committed.exploration.status == ExplorationSessionStatus.COMMITTED
    assert committed.mission.design_intent is not None
    assert committed.mission.design_intent.theme == "台地生活"
    assert committed.direction.mission_id == committed.mission.id


def test_mission_parser_concept_mode_coerces_blocking_questions() -> None:
    draft = MissionGenerationDraft(
        title="测试",
        task_statement="探索新型养老社区",
        clarifying_questions=[
            ClarifyingQuestionDraft(
                question="具体面积？",
                why_asked="影响规模",
                blocking=True,
                can_assume=False,
            )
        ],
    )
    parsed = parse_mission_draft(
        draft,
        project_id=uuid4(),
        facts=[],
        concept_mode=True,
    )
    assert parsed.clarifying_questions
    assert parsed.clarifying_questions[0].blocking is False
