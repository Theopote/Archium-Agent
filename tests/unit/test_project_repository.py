"""Tests for ProjectRepository."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.enums import ProjectStage, ProjectStatus, ProjectType
from archium.domain.project import Project
from archium.exceptions import RepositoryError
from archium.infrastructure.database.repositories import ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def repo(db_session: Session) -> ProjectRepository:
    return ProjectRepository(db_session)


def test_create_and_get_project(repo: ProjectRepository) -> None:
    project = Project(
        name="某医院老院区更新",
        project_type=ProjectType.HEALTHCARE,
        stage=ProjectStage.CONCEPT,
        location="上海",
    )
    created = repo.create(project)
    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "某医院老院区更新"
    assert fetched.project_type == ProjectType.HEALTHCARE


def test_list_projects(repo: ProjectRepository) -> None:
    repo.create(Project(name="项目 A"))
    repo.create(Project(name="项目 B"))
    all_projects = repo.list_all()
    assert len(all_projects) == 2


def test_list_projects_by_status(repo: ProjectRepository) -> None:
    active = Project(name="活跃项目")
    archived = Project(name="归档项目")
    repo.create(active)
    repo.create(archived)
    archived.archive()
    repo.update(archived)

    active_list = repo.list_all(status=ProjectStatus.ACTIVE)
    assert len(active_list) == 1
    assert active_list[0].name == "活跃项目"


def test_update_project(repo: ProjectRepository) -> None:
    project = repo.create(Project(name="原始名称"))
    project.name = "更新名称"
    project.stage = ProjectStage.SCHEMATIC
    updated = repo.update(project)
    assert updated.name == "更新名称"
    assert updated.stage == ProjectStage.SCHEMATIC


def test_delete_project(repo: ProjectRepository) -> None:
    project = repo.create(Project(name="待删除"))
    assert repo.delete(project.id) is True
    assert repo.get_by_id(project.id) is None
    assert repo.delete(uuid4()) is False


def test_update_missing_project_raises(repo: ProjectRepository) -> None:
    project = Project(name="不存在")
    with pytest.raises(RepositoryError, match="not found"):
        repo.update(project)


def test_get_current_project_artifact_pointers(repo: ProjectRepository) -> None:
    from archium.domain.reference_style import ReferenceStyleProfile
    from archium.domain.renovation_issue import RenovationIssueMap

    project = repo.create(Project(name="指针测试"))
    assert repo.get_current_renovation_issue_map(project.id) is None
    assert repo.get_current_reference_style_profile(project.id) is None
    assert repo.get_current_reference_style_profile_id(project.id) is None

    renovation_map = RenovationIssueMap(
        project_id=project.id,
        building_summary="老旧院区",
    )
    saved_map = repo.save_renovation_issue_map(renovation_map)
    repo.set_current_renovation_issue_map(project.id, saved_map.id)
    current_map = repo.get_current_renovation_issue_map(project.id)
    assert current_map is not None
    assert current_map.id == saved_map.id

    profile = ReferenceStyleProfile(
        project_id=project.id,
        style_name="参考风格",
    )
    saved_profile = repo.save_reference_style_profile(profile)
    repo.set_current_reference_style_profile(project.id, saved_profile.id)
    current_profile = repo.get_current_reference_style_profile(project.id)
    assert current_profile is not None
    assert current_profile.id == saved_profile.id
    assert repo.get_current_reference_style_profile_id(project.id) == saved_profile.id

