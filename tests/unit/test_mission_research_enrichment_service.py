"""Tests for mission research enrichment service."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from archium.application.mission_research_enrichment_service import (
    MissionResearchEnrichmentService,
)
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.config.settings import Settings
from archium.domain.enums import InformationOrigin, InformationReliability, ProjectOriginMode
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.mission_enrichment_schemas import MissionResearchEnrichmentDraft


@pytest.fixture
def mission_with_confirmed_research(db_session):
    project = ProjectRepository(db_session).create(
        Project(name="研究写回", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="概念探索",
            task_statement="探索黄土高原文化中心",
            project_context="初始语境",
        )
    )
    knowledge = ProjectKnowledgeService(db_session)
    item = knowledge.create_item(
        project.id,
        statement="关中乡村公共文化空间常结合集市与祠堂功能。",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        requires_user_confirmation=True,
        category="research",
    )
    knowledge.confirm_item(item.id)
    return project, mission, item


def test_enrich_mission_appends_confirmed_research(db_session, mission_with_confirmed_research) -> None:
    _, mission, _ = mission_with_confirmed_research
    service = MissionResearchEnrichmentService(db_session, llm=None)

    result = service.enrich_mission(mission.id, prefer_llm=False)

    assert result.items_enriched == 1
    assert result.used_llm is False
    assert result.needs_reapproval is False
    assert "【已确认公开研究】" in result.mission.project_context
    assert "关中" in result.mission.project_context
    assert service.list_pending_items(mission.id) == []


def test_enrich_mission_marks_needs_reapproval_after_prior_approval(
    db_session,
    mission_with_confirmed_research,
) -> None:
    from archium.application.project_mission_service import ProjectMissionService
    from archium.infrastructure.llm.mock import MockLLMProvider

    _, mission, _ = mission_with_confirmed_research
    ProjectMissionService(db_session, MockLLMProvider()).approve_mission(mission.id)
    service = MissionResearchEnrichmentService(db_session, llm=None)

    result = service.enrich_mission(mission.id, prefer_llm=False)

    assert result.needs_reapproval is True


def test_enrich_mission_with_llm_updates_context(
    db_session,
    mission_with_confirmed_research,
) -> None:
    _, mission, _ = mission_with_confirmed_research
    llm = MagicMock()
    llm.generate_structured.return_value = MissionResearchEnrichmentDraft(
        project_context="整合后的项目语境，包含关中乡村公共文化空间公开背景。",
        current_situation="概念阶段，已有公开案例研究。",
        key_unknowns=["具体用地尚未确定"],
        note="test",
    )
    settings = Settings(_env_file=None, llm_api_key="test-key")
    service = MissionResearchEnrichmentService(db_session, llm, settings=settings)

    result = service.enrich_mission(mission.id, prefer_llm=True)

    assert result.used_llm is True
    assert "整合后的项目语境" in result.mission.project_context
    assert result.mission.current_situation.startswith("概念阶段")


def test_revise_mission_from_written_research_updates_task_fields(
    db_session,
    mission_with_confirmed_research,
) -> None:
    from unittest.mock import MagicMock

    from archium.infrastructure.llm.mission_enrichment_schemas import MissionResearchRevisionDraft

    _, mission, _ = mission_with_confirmed_research
    service = MissionResearchEnrichmentService(db_session, llm=None)
    service.enrich_mission(mission.id, prefer_llm=False)

    llm = MagicMock()
    llm.generate_structured.return_value = MissionResearchRevisionDraft(
        task_statement="探索黄土高原文化中心，并参考关中乡村公共文化空间公开案例。",
        key_unknowns=["具体用地与规模待确认"],
        research_questions=["哪些功能应优先复合？"],
    )
    revision_service = MissionResearchEnrichmentService(
        db_session,
        llm,
        settings=Settings(_env_file=None, llm_api_key="test-key"),
    )

    result = revision_service.revise_mission_from_written_research(mission.id)

    assert result.mission_revised is True
    assert "公开案例" in result.mission.task_statement
    assert result.mission.key_unknowns == ["具体用地与规模待确认"]


def test_list_written_back_items_tracks_enrichment(db_session, mission_with_confirmed_research) -> None:
    _, mission, item = mission_with_confirmed_research
    service = MissionResearchEnrichmentService(db_session, llm=None)
    service.enrich_mission(mission.id, prefer_llm=False)

    written = service.list_written_back_items(mission.id)

    assert len(written) == 1
    assert written[0].id == item.id
    assert str(item.id) in service.get_enriched_item_ids(mission.id)


def test_enrich_mission_requires_confirmed_items(db_session, mission_with_confirmed_research) -> None:
    _, mission, item = mission_with_confirmed_research
    service = MissionResearchEnrichmentService(db_session, llm=None)
    service.enrich_mission(mission.id, prefer_llm=False)

    with pytest.raises(WorkflowError, match="没有可写回"):
        service.enrich_mission(mission.id, prefer_llm=False)

    with pytest.raises(WorkflowError, match="不可写回"):
        service.enrich_mission(mission.id, item_ids=[item.id], prefer_llm=False)
