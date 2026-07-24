"""Unit tests for autonomous research service."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from archium.application.autonomous_research_service import AutonomousResearchService
from archium.exceptions import WorkflowError
from archium.domain.enums import InformationOrigin, InformationReliability, ProjectOriginMode
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectKnowledgeRepository, ProjectRepository
from archium.infrastructure.llm.research_schemas import (
    AutonomousResearchDraft,
    ResearchFindingDraft,
    ResearchSourceDraft,
)
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService


class _StubWebResearch(WebResearchSearchService):
    def __init__(self, hits: list[WebSearchResult]) -> None:
        self._hits = hits

    @property
    def enabled(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return True

    def search_topics(self, topics: list[str]) -> tuple[list[WebSearchResult], str | None]:
        return list(self._hits), "stub"


@pytest.fixture
def concept_mission(db_session):
    project = ProjectRepository(db_session).create(
        Project(
            name="文化中心概念",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )
    mission = ProjectMission(
        project_id=project.id,
        title="概念探索",
        task_statement="探索黄土高原文化中心方向",
        design_intent=DesignIntent(
            theme="地域文化",
            research_needed=["关中乡村公共文化空间案例"],
        ),
        research_questions=["中国乡村文化建筑有哪些典型模式？"],
    )
    saved = MissionRepository(db_session).save_mission(mission)
    return project, saved


def test_research_for_mission_creates_public_knowledge_items(db_session, concept_mission) -> None:
    project, mission = concept_mission
    llm = MagicMock()
    search_hit = WebSearchResult(
        title="关中传统聚落公共空间研究",
        url="https://example.org/loess-public-space",
        snippet="背景综述片段",
    )
    llm.generate_structured.return_value = AutonomousResearchDraft(
        findings=[
            ResearchFindingDraft(
                topic="关中乡村公共文化空间案例",
                summary="关中乡村公共文化空间常结合集市、祠堂与小型展览功能。",
                key_points=["多功能复合", "与日常生产活动结合"],
                suggested_sources=[
                    ResearchSourceDraft(
                        title="关中传统聚落公共空间研究",
                        url="https://example.org/loess-public-space",
                        note="背景综述",
                    )
                ],
                relevance="可为本项目提供尺度与功能复合参考",
            )
        ]
    )

    service = AutonomousResearchService(
        db_session,
        llm,
        web_research=_StubWebResearch([search_hit]),
    )
    result = service.research_for_mission(mission.id)

    assert len(result.items) == 1
    assert result.search_hit_count == 1
    assert result.search_provider == "stub"
    item = result.items[0]
    assert item.origin == InformationOrigin.PUBLIC_RESEARCH
    assert item.reliability == InformationReliability.UNVERIFIED
    assert item.requires_user_confirmation is True
    assert "关中" in item.statement
    assert item.source_citations
    assert item.source_citations[0].url == "https://example.org/loess-public-space"

    prompt = llm.generate_structured.call_args[0][0].user_prompt
    assert "联网检索结果" in prompt
    assert "https://example.org/loess-public-space" in prompt

    stored = ProjectKnowledgeRepository(db_session).list_by_project(project.id)
    assert len(stored) == 1


def test_research_for_mission_requires_topics(db_session, concept_mission) -> None:
    _, mission = concept_mission
    mission.design_intent = DesignIntent(theme="only theme")
    mission.research_questions = []
    MissionRepository(db_session).save_mission(mission)

    service = AutonomousResearchService(db_session, MagicMock())
    with pytest.raises(WorkflowError, match="没有待研究项"):
        service.research_for_mission(mission.id)
