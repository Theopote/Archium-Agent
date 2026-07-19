"""Application-layer project deletion with related resource cleanup."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.exceptions import ProjectNotFoundError, WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from archium.logging import get_logger

logger = get_logger(__name__, operation="project_deletion")


@dataclass(frozen=True)
class ProjectDeletionResult:
    project_id: UUID
    deleted_presentations: int = 0
    removed_storage_dir: bool = False
    removed_vector_collection: bool = False
    removed_output_dirs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProjectDeletionService:
    """Delete a project and clean up database rows plus external stores."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._presentations = PresentationRepository(session)

    def delete_project(self, project_id: UUID) -> ProjectDeletionResult:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        presentations = self._presentations.list_by_project(project_id)
        warnings: list[str] = []
        removed_output_dirs: list[str] = []

        removed_vector_collection = self._delete_vector_index(project_id, warnings)
        removed_storage_dir = self._delete_project_storage(project_id, warnings)
        removed_output_dirs.extend(
            self._delete_presentation_outputs(presentations, warnings)
        )

        if not self._projects.delete(project_id):
            raise WorkflowError(f"项目 {project_id} 删除失败")

        self._session.commit()
        logger.info(
            "Deleted project %s (%d presentations, storage=%s, chroma=%s)",
            project_id,
            len(presentations),
            removed_storage_dir,
            removed_vector_collection,
        )
        return ProjectDeletionResult(
            project_id=project_id,
            deleted_presentations=len(presentations),
            removed_storage_dir=removed_storage_dir,
            removed_vector_collection=removed_vector_collection,
            removed_output_dirs=removed_output_dirs,
            warnings=warnings,
        )

    def _delete_vector_index(self, project_id: UUID, warnings: list[str]) -> bool:
        try:
            ChromaVectorStore(self._settings.chroma_path).delete_project(project_id)
            return True
        except Exception as exc:
            warnings.append(f"向量索引清理失败: {exc}")
            logger.warning("Failed to delete Chroma collection for project %s: %s", project_id, exc)
            return False

    def _delete_project_storage(self, project_id: UUID, warnings: list[str]) -> bool:
        project_dir = self._settings.project_storage_path / str(project_id)
        if not project_dir.exists():
            return False
        try:
            shutil.rmtree(project_dir)
            return True
        except OSError as exc:
            warnings.append(f"项目文件清理失败: {exc}")
            logger.warning("Failed to delete project storage %s: %s", project_dir, exc)
            return False

    def _delete_presentation_outputs(
        self,
        presentations: list[object],
        warnings: list[str],
    ) -> list[str]:
        removed: list[str] = []
        preview_root = self._settings.output_path / "studio-previews"
        for presentation in presentations:
            presentation_id = getattr(presentation, "id", None)
            if presentation_id is None:
                continue
            preview_dir = preview_root / str(presentation_id)
            if not preview_dir.exists():
                continue
            try:
                shutil.rmtree(preview_dir)
                removed.append(str(preview_dir))
            except OSError as exc:
                warnings.append(f"预览缓存清理失败 ({presentation_id}): {exc}")
                logger.warning("Failed to delete preview dir %s: %s", preview_dir, exc)
        return removed
