"""Topic 08 C2 — write-path RBAC (COLLAB-001) + invite deep link (COLLAB-004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archium.application.formal_pptx_export_service import FormalPptxExportService
from archium.application.ingestion_service import IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_service import PresentationService
from archium.application.project_access_service import ProjectAccessService
from archium.domain.access import LOCAL_ACTOR_ID, ProjectRole
from archium.domain.enums import PresentationType
from archium.domain.project import Project
from archium.exceptions import AccessDeniedError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.mock import MockLLMProvider
from archium.ui.invite_deep_link import invite_share_path


def test_invite_share_path_format() -> None:
    assert invite_share_path("ab12cd") == "?invite=AB12CD"


def test_client_cannot_create_presentation(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="禁写汇报"))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "client-x",
        ProjectRole.CLIENT,
        display_name="甲方",
        actor=LOCAL_ACTOR_ID,
    )
    service = PresentationService(db_session, MockLLMProvider())
    request = PresentationRequest(
        title="t",
        audience="a",
        purpose="p",
        presentation_type=PresentationType.CONCEPT,
    )
    with pytest.raises(AccessDeniedError):
        service.create_presentation(project.id, request, actor_id="client-x")


def test_client_cannot_import_file(db_session, tmp_path: Path) -> None:
    project = ProjectRepository(db_session).create(Project(name="禁写资料"))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "client-y",
        ProjectRole.CLIENT,
        display_name="甲方",
        actor=LOCAL_ACTOR_ID,
    )
    sample = tmp_path / "note.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises(AccessDeniedError):
        IngestionService(db_session).import_file(
            project.id, sample, actor_id="client-y"
        )


def test_owner_can_create_presentation(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="可写汇报"))
    service = PresentationService(db_session, MockLLMProvider())
    request = PresentationRequest(
        title="方案汇报",
        audience="甲方",
        purpose="推进决策",
        presentation_type=PresentationType.CONCEPT,
    )
    created = service.create_presentation(
        project.id, request, actor_id=LOCAL_ACTOR_ID
    )
    assert created.project_id == project.id
    assert created.title == "方案汇报"


def test_client_cannot_formal_export(db_session) -> None:
    from archium.domain.presentation import Presentation
    from archium.infrastructure.database.repositories import PresentationRepository

    project = ProjectRepository(db_session).create(Project(name="禁导出"))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "reviewer-no-export-wait",
        ProjectRole.ARCHITECT,
        actor=LOCAL_ACTOR_ID,
    )
    # Client has EXPORT — use a stranger instead
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="册")
    )
    with pytest.raises(AccessDeniedError):
        FormalPptxExportService(db_session).export_editable_pptx(
            presentation.id, actor_id="stranger"
        )
