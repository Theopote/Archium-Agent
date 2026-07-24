"""Integration tests for research/programming planning without uploaded documents."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.project_mission_service import ProjectMissionService
from archium.domain.enums import ProjectOriginMode
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.mission_schemas import (
    AssumptionDraft,
    DesignIntentDraft,
    MissionGenerationDraft,
)


@pytest.fixture
def programming_project(db_session):
    return ProjectRepository(db_session).create(
        Project(
            name="文旅综合体前期策划",
            description="策划与可研",
            origin_mode=ProjectOriginMode.RESEARCH_PROGRAMMING,
        )
    )


def test_generate_mission_programming_mode_uses_lightweight_questions(
    db_session,
    programming_project,
) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = MissionGenerationDraft(
        title="某文旅综合体前期策划",
        task_statement="梳理功能定位、投资逻辑与关键未知项，形成投资人沟通提纲",
        design_intent=DesignIntentDraft(
            theme="城市更新中的文化商业",
            problem_statement="如何在指标未定情况下建立可讨论的策划框架？",
            target_users=["投资人", "政府平台"],
            core_questions=["功能配比与分期逻辑如何自洽？"],
            research_needed=["同类片区策划案例与政策约束"],
            working_assumptions=["地块处于城市更新试点片区，待确认"],
        ),
        assumptions=[
            AssumptionDraft(
                statement="假定项目以文化商业为主导业态",
                reason="用户描述侧重投资人沟通与功能策划",
                requires_confirmation=True,
            )
        ],
        clarifying_questions=[],
        knowledge_gaps=[],
    )

    service = ProjectMissionService(db_session, llm)
    result = service.generate_mission(
        programming_project.id,
        "某地块拟引入文化商业，需向投资人说明定位与风险",
        origin_mode=ProjectOriginMode.RESEARCH_PROGRAMMING,
    )

    assert result.mission.design_intent is not None
    assert "文化商业" in result.mission.design_intent.theme
    assert all(not question.blocking for question in result.clarifying_questions)
    llm.generate_structured.assert_called_once()
    request = llm.generate_structured.call_args[0][0]
    assert "策划与可研模式" in request.user_prompt
