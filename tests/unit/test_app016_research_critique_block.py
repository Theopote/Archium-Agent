"""APP-016 — Research Critic block rejects weak items and blocks hardening."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from archium.application.autonomous_research_service import (
    AutonomousResearchResult,
    AutonomousResearchService,
)
from archium.application.design_knowledge_context import list_design_knowledge_for_project
from archium.config.settings import Settings
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    ProjectType,
)
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.research_critique import ResearchCritiqueReport, ResearchCritiqueVerdict
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    ProjectKnowledgeRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _weak_item(project_id) -> ProjectKnowledgeItem:
    return ProjectKnowledgeItem(
        project_id=project_id,
        statement="随便说说建筑挺好",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[],
        design_knowledge=DesignKnowledge(
            topic="泛泛",
            insight="好看",
            principle="",
            spatial_translation="",
        ),
        category="research",
    )


def test_block_rejects_weak_items_and_raises(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="研究阻断", project_type=ProjectType.CULTURE)
    )
    item = ProjectKnowledgeRepository(db_session).create(
        _weak_item(project.id)
    )
    db_session.commit()

    settings = Settings(_env_file=None, research_critique_mode="block", research_critique_llm=False)
    service = AutonomousResearchService(db_session, MagicMock(), settings=settings)

    # Force a WEAK critique regardless of rules scoring
    fake_report = ResearchCritiqueReport(
        project_id=project.id,
        verdict=ResearchCritiqueVerdict.WEAK,
        validity=0.2,
        design_relevance=0.2,
        summary="弱研究",
    )

    class _FakeCritique:
        def critique_items(self, *args, **kwargs):
            return fake_report

    import archium.application.review.research_critique_service as rcs

    original = rcs.ResearchCritiqueService
    rcs.ResearchCritiqueService = lambda *a, **k: _FakeCritique()  # type: ignore[misc,assignment]
    try:
        result = AutonomousResearchResult(
            project_id=project.id,
            items=[item],
        )
        with pytest.raises(WorkflowError, match="研究批判阻断"):
            service._attach_research_critique(result, design_context="庭院")
    finally:
        rcs.ResearchCritiqueService = original

    refreshed = ProjectKnowledgeRepository(db_session).get_by_id(item.id)
    assert refreshed is not None
    assert refreshed.status == KnowledgeItemStatus.REJECTED
    assert list_design_knowledge_for_project(db_session, project.id) == []


def test_warn_keeps_weak_items(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="研究警告", project_type=ProjectType.CULTURE)
    )
    item = ProjectKnowledgeRepository(db_session).create(
        ProjectKnowledgeItem(
            project_id=project.id,
            statement="关中院落内向聚合可转译为文化中心庭院。",
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.UNVERIFIED,
            source_citations=[
                SourceCitation(url="https://example.org/c", source_title="院落研究")
            ],
            design_knowledge=DesignKnowledge(
                topic="关中院落",
                insight="内向聚合",
                principle="围合形成公共核",
                spatial_translation="四面围合中心庭院",
                problem="公共空间缺失",
                strategy="内院组织",
            ),
            category="research",
        )
    )
    settings = Settings(_env_file=None, research_critique_mode="warn", research_critique_llm=False)
    service = AutonomousResearchService(db_session, MagicMock(), settings=settings)
    result = AutonomousResearchResult(project_id=project.id, items=[item])
    # Real rules critique — may be ACCEPT or CAUTION; must not raise
    out = service._attach_research_critique(result, design_context="庭院文化中心")
    assert out.blocked is False
    refreshed = ProjectKnowledgeRepository(db_session).get_by_id(item.id)
    assert refreshed is not None
    assert refreshed.status != KnowledgeItemStatus.REJECTED
