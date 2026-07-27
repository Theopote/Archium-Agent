"""Topic 08 — thin Organization tenant root (DOM-032)."""

from __future__ import annotations

import pytest
from archium.application.organization_service import OrganizationService
from archium.application.project_management_service import ProjectManagementService
from archium.domain.project import Project
from archium.exceptions import ValidationError
from archium.infrastructure.database.repositories import ProjectRepository


def test_create_organization_and_attach_project(db_session) -> None:
    orgs = OrganizationService(db_session)
    org = orgs.create_organization(
        "南山事务所",
        slug="nanshan-studio",
        display_name="南山",
    )
    assert org.label() == "南山"
    assert OrganizationService(db_session).get_by_slug("nanshan-studio") is not None

    projects = ProjectManagementService(db_session)
    project = projects.create_project(
        "文化中心",
        organization_id=org.id,
    )
    assert project.organization_id == org.id

    listed = OrganizationService(db_session).list_projects(org.id)
    assert [p.id for p in listed] == [project.id]


def test_attach_and_detach_project(db_session) -> None:
    orgs = OrganizationService(db_session)
    org = orgs.create_organization("西岸团队", slug="west-bank")
    project = ProjectRepository(db_session).create(Project(name="未归属"))
    db_session.commit()

    attached = orgs.attach_project(project.id, org.id)
    assert attached.organization_id == org.id
    cleared = orgs.attach_project(project.id, None)
    assert cleared.organization_id is None


def test_duplicate_slug_rejected(db_session) -> None:
    OrganizationService(db_session).create_organization("甲", slug="dup-org")
    with pytest.raises(ValidationError):
        OrganizationService(db_session).create_organization("乙", slug="dup-org")


def test_project_create_rejects_missing_org(db_session) -> None:
    from uuid import uuid4

    with pytest.raises(ValidationError):
        ProjectManagementService(db_session).create_project(
            "孤儿",
            organization_id=uuid4(),
        )
