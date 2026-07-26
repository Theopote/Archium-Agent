"""Unit tests for autonomous research service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from archium.application.autonomous_research_service import AutonomousResearchService
from archium.config.settings import Settings
from archium.domain.enums import InformationOrigin, InformationReliability, ProjectOriginMode
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.intent.research_run import ResearchRunStopReason
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ProjectKnowledgeRepository,
    ProjectRepository,
)
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
        self.calls: list[list[str]] = []

    @property
    def enabled(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return True

    def search_topics(self, topics: list[str]) -> tuple[list[WebSearchResult], str | None]:
        self.calls.append(list(topics))
        return list(self._hits), "stub"


@pytest.fixture
def concept_mission(db_session):
    project = ProjectRepository(db_session).create(
        Project(
            name="文化中心概念",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
            knowledge_state=KnowledgeState(
                completeness_score=0.3,
                dimensions=KnowledgeDimensions(
                    information_completeness=0.3,
                    design_intent_clarity=0.6,
                    evidence_confidence=0.25,
                    constraint_understanding=0.3,
                    user_alignment=0.5,
                    research_need=0.8,
                ),
            ),
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


def _finding(topic: str, url: str = "https://example.org/loess-public-space") -> ResearchFindingDraft:
    return ResearchFindingDraft(
        topic=topic,
        summary="关中乡村公共文化空间常结合集市、祠堂与小型展览功能。",
        insight="减少机构化，强化日常公共性。",
        principle="多功能复合与日常生产结合",
        spatial_translation="集市—祠堂—展览的串联院落",
        material_strategy="生土与木构",
        project_link="可为本项目提供尺度与功能复合参考",
        applicability="关中乡镇、中小公共建筑",
        key_points=["原则：多功能复合", "空间：与日常生产活动结合"],
        suggested_sources=[
            ResearchSourceDraft(
                title="关中传统聚落公共空间研究",
                url=url,
                note="背景综述",
            )
        ],
        relevance="可为本项目提供尺度与功能复合参考",
    )


def test_research_for_mission_creates_public_knowledge_items(db_session, concept_mission) -> None:
    project, mission = concept_mission
    llm = MagicMock()
    search_hit = WebSearchResult(
        title="关中传统聚落公共空间研究",
        url="https://example.org/loess-public-space",
        snippet="背景综述片段",
    )
    llm.generate_structured.return_value = AutonomousResearchDraft(
        findings=[_finding("关中乡村公共文化空间案例")]
    )

    settings = Settings(
        _env_file=None,
        autonomous_research_loop_enabled=True,
        autonomous_research_topics_per_step=2,
        autonomous_research_max_steps=3,
    )
    service = AutonomousResearchService(
        db_session,
        llm,
        settings=settings,
        web_research=_StubWebResearch([search_hit]),
    )
    result = service.research_for_mission(mission.id)

    assert len(result.items) == 1
    assert result.search_hit_count == 1
    assert result.search_provider == "stub"
    assert result.run is not None
    assert result.run.step_count == 1
    item = result.items[0]
    assert item.origin == InformationOrigin.PUBLIC_RESEARCH
    assert item.reliability == InformationReliability.UNVERIFIED
    assert item.requires_user_confirmation is True
    assert "关中" in item.statement
    assert item.source_citations
    assert item.source_citations[0].url == "https://example.org/loess-public-space"
    assert item.design_knowledge is not None
    assert item.design_knowledge.principle
    assert "复合" in item.design_knowledge.principle or "复合" in item.statement

    prompt = llm.generate_structured.call_args[0][0].user_prompt
    assert "联网检索结果" in prompt
    assert "https://example.org/loess-public-space" in prompt

    stored = ProjectKnowledgeRepository(db_session).list_by_project(project.id)
    assert len(stored) == 1


def test_research_loop_stops_at_max_steps(db_session, concept_mission) -> None:
    project, _mission = concept_mission
    llm = MagicMock()
    search_hit = WebSearchResult(
        title="关中传统聚落公共空间研究",
        url="https://example.org/loess-public-space",
        snippet="背景综述片段",
    )

    def _draft(_request, _schema):
        return AutonomousResearchDraft(
            findings=[_finding(f"topic-{llm.generate_structured.call_count}")]
        )

    llm.generate_structured.side_effect = _draft
    web = _StubWebResearch([search_hit])
    settings = Settings(
        _env_file=None,
        autonomous_research_loop_enabled=True,
        autonomous_research_topics_per_step=1,
        autonomous_research_max_steps=2,
        autonomous_research_stop_research_need=0.0,
    )
    result = AutonomousResearchService(
        db_session,
        llm,
        settings=settings,
        web_research=web,
    ).research_topics(
        project.id,
        ["主题甲", "主题乙", "主题丙"],
        design_context="概念探索",
    )
    assert result.run is not None
    assert result.run.step_count == 2
    assert result.run.stop_reason == ResearchRunStopReason.MAX_STEPS
    assert len(result.items) == 2
    assert len(web.calls) == 2
    assert web.calls[0] == ["主题甲"]
    assert web.calls[1] == ["主题乙"]
    assert "主题丙" not in result.run.completed_topics


def test_research_loop_stops_on_empty_findings(db_session, concept_mission) -> None:
    project, _mission = concept_mission
    llm = MagicMock()
    llm.generate_structured.return_value = AutonomousResearchDraft(findings=[])
    settings = Settings(
        _env_file=None,
        autonomous_research_loop_enabled=True,
        autonomous_research_topics_per_step=1,
        autonomous_research_max_steps=3,
    )
    result = AutonomousResearchService(
        db_session,
        llm,
        settings=settings,
        web_research=_StubWebResearch([]),
    ).research_topics(project.id, ["空主题", "下一主题"])
    assert result.run is not None
    assert result.run.stop_reason == ResearchRunStopReason.EMPTY_FINDINGS
    assert result.run.step_count == 1
    assert result.items == []


def test_research_batch_mode_legacy(db_session, concept_mission) -> None:
    _project, mission = concept_mission
    llm = MagicMock()
    llm.generate_structured.return_value = AutonomousResearchDraft(
        findings=[_finding("关中乡村公共文化空间案例")]
    )
    settings = Settings(_env_file=None, autonomous_research_loop_enabled=False)
    result = AutonomousResearchService(
        db_session,
        llm,
        settings=settings,
        web_research=_StubWebResearch(
            [
                WebSearchResult(
                    title="t",
                    url="https://example.org/loess-public-space",
                    snippet="s",
                )
            ]
        ),
    ).research_for_mission(mission.id)
    assert result.run is not None
    assert result.run.stop_reason == ResearchRunStopReason.BATCH
    assert len(result.items) == 1


def test_research_for_mission_requires_topics(db_session, concept_mission) -> None:
    _, mission = concept_mission
    mission.design_intent = DesignIntent(theme="only theme")
    mission.research_questions = []
    MissionRepository(db_session).save_mission(mission)

    service = AutonomousResearchService(db_session, MagicMock())
    with pytest.raises(WorkflowError, match="没有待研究项"):
        service.research_for_mission(mission.id)
