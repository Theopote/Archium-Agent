"""Tests for ProjectDeletionService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.project_deletion_service import ProjectDeletionService
from archium.config.settings import Settings
from archium.domain.enums import ProjectStatus
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.exceptions import ProjectNotFoundError, WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def deletion_settings(tmp_path, monkeypatch) -> Settings:
    base = tmp_path / "deletion-test"
    settings = Settings(
        _env_file=None,
        database_path=base / "archium.db",
        project_storage_path=base / "projects",
        output_path=base / "outputs",
        chroma_path=base / "chroma",
    )
    monkeypatch.setattr("archium.application.project_deletion_service.get_settings", lambda: settings)
    return settings


def test_delete_project_removes_record(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    repo = ProjectRepository(db_session)
    project = repo.create(Project(name="待删除"))
    db_session.commit()

    service = ProjectDeletionService(db_session, settings=deletion_settings)
    result = service.delete_project(project.id)

    assert result.deleted_presentations == 0
    assert repo.get_by_id(project.id) is None


def test_delete_missing_project_raises(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    service = ProjectDeletionService(db_session, settings=deletion_settings)
    with pytest.raises(ProjectNotFoundError):
        service.delete_project(uuid4())


def test_delete_project_cleans_storage_and_preview_outputs(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="含文件"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    db_session.commit()

    project_dir = deletion_settings.project_storage_path / str(project.id)
    project_dir.mkdir(parents=True)
    (project_dir / "sources").mkdir()
    (project_dir / "sources" / "brief.docx").write_bytes(b"docx")

    preview_dir = deletion_settings.output_path / "studio-previews" / str(presentation.id)
    preview_dir.mkdir(parents=True)
    (preview_dir / "slide-0.png").write_bytes(b"png")

    service = ProjectDeletionService(db_session, settings=deletion_settings)
    result = service.delete_project(project.id)

    assert result.deleted_presentations == 1
    assert result.removed_storage_dir is True
    assert str(preview_dir) in result.removed_output_dirs
    assert not project_dir.exists()
    assert not preview_dir.exists()
    assert not (deletion_settings.project_storage_path.parent / "trash" / str(project.id)).exists()
    assert projects.get_by_id(project.id) is None


def test_delete_project_cleans_all_presentation_output_artifacts(
    db_session: Session,
    deletion_settings: Settings,
) -> None:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="含输出"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    db_session.commit()

    pid = str(presentation.id)
    output_root = deletion_settings.output_path
    parent_paths = [
        output_root / "studio-previews" / pid,
        output_root / "visual-composition" / pid,
        output_root / "presentations" / pid,
        output_root / "studio-reviews" / f"{pid}.json",
    ]
    nested_paths = {
        output_root / "studio-previews" / pid,
        output_root / "visual-composition" / pid / "workflow-run",
        output_root / "presentations" / pid / "v1",
        output_root / "studio-reviews" / f"{pid}.json",
    }
    for path in nested_paths:
        if path.suffix == ".json":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        else:
            path.mkdir(parents=True)
            (path / "artifact.bin").write_bytes(b"data")

    service = ProjectDeletionService(db_session, settings=deletion_settings)
    result = service.delete_project(project.id)

    assert result.deleted_presentations == 1
    assert {str(path) for path in parent_paths}.issubset(set(result.removed_output_dirs))
    assert all(not path.exists() for path in nested_paths)


def test_delete_project_records_vector_cleanup_warning(
    db_session: Session,
    deletion_settings: Settings,
    monkeypatch,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="向量失败"))
    db_session.commit()

    class _BrokenChroma:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def delete_project(self, _project_id):  # noqa: ANN001
            raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(
        "archium.application.project_deletion_service.ChromaVectorStore",
        _BrokenChroma,
    )

    service = ProjectDeletionService(db_session, settings=deletion_settings)
    result = service.delete_project(project.id)

    assert result.removed_vector_collection is False
    assert any("向量索引清理失败" in warning for warning in result.warnings)
    assert ProjectRepository(db_session).get_by_id(project.id) is None


def test_delete_project_raises_when_repository_delete_fails(
    db_session: Session,
    deletion_settings: Settings,
    monkeypatch,
) -> None:
    projects = ProjectRepository(db_session)
    project = projects.create(Project(name="删除失败"))
    db_session.commit()

    project_dir = deletion_settings.project_storage_path / str(project.id)
    project_dir.mkdir(parents=True)
    (project_dir / "brief.docx").write_bytes(b"docx")

    service = ProjectDeletionService(db_session, settings=deletion_settings)

    def _fail_delete(self, _project_id):  # noqa: ANN001
        return False

    monkeypatch.setattr(ProjectRepository, "delete", _fail_delete)

    with pytest.raises(WorkflowError, match="删除失败"):
        service.delete_project(project.id)

    restored = projects.get_by_id(project.id)
    assert restored is not None
    assert restored.status == ProjectStatus.ACTIVE
    assert project_dir.exists()
    assert (project_dir / "brief.docx").exists()
    assert not (deletion_settings.project_storage_path.parent / "trash" / str(project.id)).exists()


def test_deleting_projects_are_hidden_from_default_list(
    db_session: Session,
) -> None:
    repo = ProjectRepository(db_session)
    repo.create(Project(name="可见"))
    deleting = repo.create(Project(name="删除中"))
    deleting.mark_deleting()
    repo.update(deleting)
    db_session.commit()

    listed = repo.list_all()
    assert [project.name for project in listed] == ["可见"]
    assert repo.list_all(include_hidden=True)
