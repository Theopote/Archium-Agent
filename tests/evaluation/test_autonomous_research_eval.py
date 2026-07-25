"""Evaluation: Research role must ground findings in citable sources."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.autonomous_research_service import AutonomousResearchService
from archium.config.settings import Settings
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.research_schemas import (
    AutonomousResearchDraft,
    ResearchFindingDraft,
    ResearchSourceDraft,
)
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService
from tests.evaluation.assertions import (
    assert_research_item_has_design_knowledge,
    assert_research_item_has_sources,
)


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
def research_project(db_session):
    return ProjectRepository(db_session).create(
        Project(
            name="山地文化中心",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
            knowledge_state=KnowledgeState(
                completeness_score=0.3,
                dimensions=KnowledgeDimensions(
                    information_completeness=0.3,
                    design_intent_clarity=0.55,
                    evidence_confidence=0.2,
                    constraint_understanding=0.3,
                    user_alignment=0.5,
                    research_need=0.75,
                ),
            ),
        )
    )


def test_research_eval_requires_source_citations(db_session, research_project) -> None:
    """Eval: autonomous research findings must cite sources (url/title)."""
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=research_project.id,
            title="山地文化中心",
            task_statement="补山地文化中心类型先例",
            design_intent=DesignIntent(
                theme="山地公共文化",
                research_needed=["山地文化建筑与聚落公共空间案例"],
            ),
        )
    )
    llm = MagicMock()
    hit = WebSearchResult(
        title="山地公共建筑研究",
        url="https://example.org/mountain-cultural-center",
        snippet="案例综述",
    )
    llm.generate_structured.return_value = AutonomousResearchDraft(
        findings=[
            ResearchFindingDraft(
                topic="山地文化建筑与聚落公共空间案例",
                summary="山地文化设施常结合台地与聚落入口广场。",
                insight="公共性应沿地貌台地展开，而非单一大厅。",
                principle="以台地层级组织公共空间",
                spatial_translation="台地院落 + 入口广场",
                material_strategy="本地石材与木构",
                project_link="可支撑山地文化中心空间策略讨论",
                applicability="适用于坡地乡镇、中小体量",
                key_points=["原则：台地层级", "空间：入口公共性"],
                suggested_sources=[
                    ResearchSourceDraft(
                        title="山地公共建筑研究",
                        url="https://example.org/mountain-cultural-center",
                        note="类型综述",
                    )
                ],
                relevance="可支撑山地文化中心空间策略讨论",
            )
        ]
    )
    settings = Settings(
        _env_file=None,
        autonomous_research_loop_enabled=True,
        autonomous_research_topics_per_step=2,
        autonomous_research_max_steps=2,
    )
    result = AutonomousResearchService(
        db_session,
        llm,
        settings=settings,
        web_research=_StubWebResearch([hit]),
    ).research_for_mission(mission.id)

    assert result.items, "evaluation: research must produce knowledge items"
    for item in result.items:
        assert_research_item_has_sources(item)
        assert_research_item_has_design_knowledge(item)
        assert item.design_knowledge is not None
        assert "台地" in item.design_knowledge.principle
