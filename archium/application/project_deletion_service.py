"""Application-layer project deletion with related resource cleanup."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.enums import ProjectStatus
from archium.domain.presentation import Presentation
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
    """Delete a project and clean up database rows plus external stores.

    Deletion is staged so database state and on-disk project storage stay
    recoverable until the database row is removed:

    1. Mark project ``deleting`` and commit (hide from listings).
    2. Move ``data/projects/<id>`` to ``data/trash/<id>``.
    3. Delete the project row (cascade) and commit.
    4. Best-effort cleanup of Chroma, presentation outputs, and trash.
    """

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
        previous_status = project.status
        quarantine_path: Path | None = None

        if project.status != ProjectStatus.DELETING:
            project.mark_deleting()
            self._projects.update(project)
            self._session.commit()

        try:
            quarantine_path = self._quarantine_project_storage(project_id, warnings)
            if not self._projects.delete(project_id):
                raise WorkflowError(f"项目 {project_id} 删除失败")
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            self._recover_failed_database_delete(
                project_id,
                quarantine_path,
                previous_status,
                warnings,
            )
            if isinstance(exc, WorkflowError):
                raise
            raise WorkflowError(f"项目 {project_id} 删除失败") from exc

        removed_vector_collection = self._delete_vector_index(project_id, warnings)
        removed_output_dirs = self._delete_presentation_outputs(presentations, warnings)
        removed_storage_dir = self._purge_quarantined_storage(quarantine_path, warnings)

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

    def _recover_failed_database_delete(
        self,
        project_id: UUID,
        quarantine_path: Path | None,
        previous_status: ProjectStatus,
        warnings: list[str],
    ) -> None:
        if quarantine_path is not None:
            self._restore_quarantined_storage(project_id, quarantine_path, warnings)

        project = self._projects.get_by_id(project_id)
        if project is None or project.status != ProjectStatus.DELETING:
            return

        project.status = previous_status
        self._projects.update(project)
        try:
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            warnings.append(f"删除失败后恢复项目状态异常: {exc}")
            logger.warning(
                "Failed to restore project %s after deletion rollback: %s",
                project_id,
                exc,
            )

    def _project_trash_root(self) -> Path:
        return self._settings.project_storage_path.parent / "trash"

    def _quarantine_project_storage(
        self,
        project_id: UUID,
        warnings: list[str],
    ) -> Path | None:
        project_dir = self._settings.project_storage_path / str(project_id)
        if not project_dir.exists():
            return None

        trash_root = self._project_trash_root()
        trash_root.mkdir(parents=True, exist_ok=True)
        destination = trash_root / str(project_id)
        if destination.exists():
            try:
                shutil.rmtree(destination)
            except OSError as exc:
                warnings.append(f"清理旧隔离目录失败: {exc}")
                logger.warning("Failed to clear stale trash dir %s: %s", destination, exc)
                return None

        try:
            shutil.move(str(project_dir), str(destination))
            return destination
        except OSError as exc:
            warnings.append(f"项目文件隔离失败: {exc}")
            logger.warning("Failed to quarantine project storage %s: %s", project_dir, exc)
            return None

    def _restore_quarantined_storage(
        self,
        project_id: UUID,
        quarantine_path: Path,
        warnings: list[str],
    ) -> bool:
        if not quarantine_path.exists():
            return False

        target = self._settings.project_storage_path / str(project_id)
        if target.exists():
            warnings.append("项目文件目录已存在，跳过从隔离区恢复。")
            return False

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(quarantine_path), str(target))
            return True
        except OSError as exc:
            warnings.append(f"从隔离区恢复项目文件失败: {exc}")
            logger.warning(
                "Failed to restore quarantined storage %s -> %s: %s",
                quarantine_path,
                target,
                exc,
            )
            return False

    def _purge_quarantined_storage(
        self,
        quarantine_path: Path | None,
        warnings: list[str],
    ) -> bool:
        if quarantine_path is None or not quarantine_path.exists():
            return False
        try:
            shutil.rmtree(quarantine_path)
            return True
        except OSError as exc:
            warnings.append(f"隔离项目文件清理失败: {exc}")
            logger.warning("Failed to purge quarantined storage %s: %s", quarantine_path, exc)
            return False

    def _delete_vector_index(self, project_id: UUID, warnings: list[str]) -> bool:
        try:
            ChromaVectorStore(self._settings.chroma_path).delete_project(project_id)
            return True
        except Exception as exc:
            warnings.append(f"向量索引清理失败: {exc}")
            logger.warning("Failed to delete Chroma collection for project %s: %s", project_id, exc)
            return False

    def _presentation_output_paths(self, presentation_id: UUID) -> list[Path]:
        output_root = self._settings.output_path
        pid = str(presentation_id)
        return [
            output_root / "studio-previews" / pid,
            output_root / "visual-composition" / pid,
            output_root / "presentations" / pid,
            output_root / "studio-reviews" / f"{pid}.json",
        ]

    def _delete_presentation_outputs(
        self,
        presentations: Sequence[Presentation],
        warnings: list[str],
    ) -> list[str]:
        removed: list[str] = []
        for presentation in presentations:
            for path in self._presentation_output_paths(presentation.id):
                if not path.exists():
                    continue
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    removed.append(str(path))
                except OSError as exc:
                    label = "目录" if path.is_dir() else "文件"
                    warnings.append(f"输出{label}清理失败 ({path.name}): {exc}")
                    logger.warning("Failed to delete presentation output %s: %s", path, exc)
        return removed
