"""Tests for research knowledge listing."""

from __future__ import annotations

from uuid import uuid4

from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository


def test_list_research_knowledge_items_returns_pending_research(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="研究预览"))
    service = ProjectKnowledgeService(db_session)
    service.create_item(
        project.id,
        statement="关中乡村公共文化空间常结合集市与祠堂。",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        requires_user_confirmation=True,
        category="research",
    )
    service.create_item(
        project.id,
        statement="已确认条目",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        requires_user_confirmation=True,
        category="research",
    )
    confirmed = service.create_item(
        project.id,
        statement="另一条",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        requires_user_confirmation=True,
        category="research",
    )
    service.confirm_item(confirmed.id)

    pending = service.list_research_knowledge_items(project.id, pending_only=True, limit=10)

    assert len(pending) == 2
    assert all(not item.is_confirmed for item in pending)
    assert all(item.category == "research" for item in pending)
