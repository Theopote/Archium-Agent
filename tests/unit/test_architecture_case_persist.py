"""Phase B — writable project ArchitectureCase library."""

from __future__ import annotations

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.application.architecture_case_service import ArchitectureCaseService
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import (
    ArchitectureCaseStatus,
    InformationOrigin,
    InformationReliability,
    ProjectOriginMode,
)
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    ArchitectureCaseRepository,
    ProjectRepository,
)


def test_create_draft_and_merge_into_library(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="案例库项目", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    service = ArchitectureCaseService(db_session)
    draft = service.create_draft(
        project.id,
        name="本地台地文化中心参照",
        design_problem="山地公共核缺失",
        strategy="台地层级组织公共性",
        spatial_logic="台地院落序列",
        material_language="夯土木构",
        slug="local_terrace_hub",
    )
    assert draft.status == ArchitectureCaseStatus.DRAFT
    assert draft.slug == "local_terrace_hub"
    db_session.commit()

    seeds_only = ArchitectureCaseLibraryService()
    assert seeds_only.get_by_id("local_terrace_hub") is None

    merged = ArchitectureCaseLibraryService(
        session=db_session,
        project_id=project.id,
        include_drafts=True,
    )
    assert merged.get_by_id("local_terrace_hub") is not None
    matches = merged.search("台地 公共", limit=3, min_score=0.2)
    assert any(m.case.id == "local_terrace_hub" for m in matches)


def test_project_case_overrides_seed_slug(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="覆盖种子", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    service = ArchitectureCaseService(db_session)
    service.create_draft(
        project.id,
        name="项目版宁波博物馆解读",
        design_problem="本项目的地方记忆问题",
        strategy="定制瓦爿策略",
        slug="ningbo_museum",
    )
    db_session.commit()
    library = ArchitectureCaseLibraryService(
        session=db_session,
        project_id=project.id,
        include_drafts=True,
    )
    case = library.get_by_id("ningbo_museum")
    assert case is not None
    assert case.name == "项目版宁波博物馆解读"
    assert "地方记忆" in case.design_problem


def test_confirm_knowledge_creates_draft_case(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="确认写回", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    knowledge_svc = ProjectKnowledgeService(db_session)
    item = knowledge_svc.create_item(
        project.id,
        statement="台地公共性洞察",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        category="research",
        requires_user_confirmation=True,
        design_knowledge=DesignKnowledge(
            topic="山地台地公共核",
            problem="乡镇缺少可停留公共空间",
            insight="公共性应沿台地展开",
            strategy="台地层级",
            principle="台地层级组织日常公共性",
            spatial_translation="台地院落",
            material_strategy="石材",
            applicability="坡地乡镇",
        ),
    )
    db_session.commit()
    confirmed = knowledge_svc.confirm_item(item.id)
    db_session.commit()
    assert confirmed.design_knowledge is not None
    assert confirmed.design_knowledge.precedent_ref
    assert confirmed.design_knowledge.precedent_ref.startswith("case:")

    cases = ArchitectureCaseRepository(db_session).list_by_project(project.id)
    assert len(cases) == 1
    assert cases[0].status == ArchitectureCaseStatus.DRAFT
    assert cases[0].source_knowledge_item_id == confirmed.id
    assert cases[0].design_problem.startswith("乡镇缺少")


def test_confirm_with_seed_precedent_does_not_create_row(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="种子链接", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    knowledge_svc = ProjectKnowledgeService(db_session)
    item = knowledge_svc.create_item(
        project.id,
        statement="宁波博物馆参照",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        category="research",
        requires_user_confirmation=True,
        design_knowledge=DesignKnowledge(
            topic="在地材料",
            problem="地方记忆容器",
            strategy="瓦爿墙",
            principle="材料回收承载叙事",
            precedent_ref="case:ningbo_museum",
        ),
    )
    db_session.commit()
    knowledge_svc.confirm_item(item.id)
    db_session.commit()
    assert ArchitectureCaseRepository(db_session).list_by_project(project.id) == []


def test_activate_case(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="激活", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    service = ArchitectureCaseService(db_session)
    draft = service.create_draft(
        project.id,
        name="可激活案例",
        strategy="线性廊道",
        slug="activatable_case",
    )
    active = service.activate(draft.id)
    assert active.status == ArchitectureCaseStatus.ACTIVE
    library = ArchitectureCaseLibraryService(session=db_session, project_id=project.id)
    assert library.get_by_id("activatable_case") is not None
