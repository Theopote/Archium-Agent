"""Topic 08 C1 — session actor + visible projects + bootstrap mitigation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.project_access_service import ProjectAccessService
from archium.application.project_permission_gate import require_project_permission
from archium.domain.access import LOCAL_ACTOR_ID, ProjectPermission, ProjectRole
from archium.domain.project import Project
from archium.exceptions import AccessDeniedError
from archium.infrastructure.database.repositories import (
    ProjectMemberRepository,
    ProjectRepository,
)


def test_list_visible_projects_filters_by_membership(db_session) -> None:
    projects = ProjectRepository(db_session)
    access = ProjectAccessService(db_session)
    mine = projects.create(Project(name="我的项目"))
    other = projects.create(Project(name="他人项目"))
    # create() already ensures local-user owner — reassign other to guest only
    members = ProjectMemberRepository(db_session)
    for mid in members.list_for_project(other.id):
        if mid.actor_id == LOCAL_ACTOR_ID:
            members.delete(mid.id)
    access.add_member(other.id, "guest-a", ProjectRole.CLIENT, display_name="甲方")

    visible_local = access.list_visible_projects(LOCAL_ACTOR_ID)
    ids_local = {p.id for p in visible_local}
    assert mine.id in ids_local
    assert other.id not in ids_local

    visible_guest = access.list_visible_projects("guest-a")
    assert [p.id for p in visible_guest] == [other.id]


def test_empty_project_promotes_local_user_to_owner(db_session) -> None:
    projects = ProjectRepository(db_session)
    project = projects.create(Project(name="遗留空项目"))
    members = ProjectMemberRepository(db_session)
    for mid in list(members.list_for_project(project.id)):
        members.delete(mid.id)
    assert members.list_for_project(project.id) == []

    access = ProjectAccessService(db_session)
    assert access.can(project.id, LOCAL_ACTOR_ID, ProjectPermission.EDIT) is True
    owned = members.get_by_project_actor(project.id, LOCAL_ACTOR_ID)
    assert owned is not None
    assert owned.role == ProjectRole.OWNER


def test_guest_without_membership_denied(db_session) -> None:
    projects = ProjectRepository(db_session)
    project = projects.create(Project(name="受控项目"))
    access = ProjectAccessService(db_session)
    assert access.can(project.id, "stranger", ProjectPermission.VIEW) is False
    with pytest.raises(AccessDeniedError):
        require_project_permission(
            db_session,
            project.id,
            ProjectPermission.EDIT,
            actor_id="stranger",
        )


def test_require_gate_allows_local_owner(db_session) -> None:
    projects = ProjectRepository(db_session)
    project = projects.create(Project(name="门面项目"))
    member = require_project_permission(
        db_session,
        project.id,
        ProjectPermission.MANAGE_MEMBERS,
        actor_id=LOCAL_ACTOR_ID,
    )
    assert member is not None
    assert member.actor_id == LOCAL_ACTOR_ID
