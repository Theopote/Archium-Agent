"""Undo/redo for persisted RenderScene revisions (canvas geometry edits)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.revision_service import RevisionService
from archium.application.scene_revision_timeline_service import SceneRevisionTimelineService
from archium.application.visual.scene_history_service import (
    SCENE_STATE_SNAPSHOT_KIND,
    SceneHistoryService,
)
from archium.config.settings import Settings, get_settings
from archium.domain.scene_revision_summary import SceneRevisionRestoreResult
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.exceptions import WorkflowError
from archium.infrastructure.database.visual_repositories import RenderSceneRepository


class SceneUndoService:
    """Walk the scene revision parent chain for Studio geometry undo."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._revisions = RevisionService(session)
        self._scene_history = SceneHistoryService(session)
        self._timeline = SceneRevisionTimelineService(session, settings=self._settings)
        self._scenes = RenderSceneRepository(session)

    def count_undo_steps(self, slide: SlideSpec) -> int:
        revisions = self._scene_history.list_slide_scene_revisions(slide)
        if len(revisions) <= 1:
            return 0
        live_scene = (
            self._scenes.get_by_layout_plan(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )
        if live_scene is None:
            return 0
        live_hash = compute_scene_hash(live_scene)
        current_index = self._revision_index_for_hash(revisions, live_hash)
        if current_index is None:
            return 0
        return len(revisions) - current_index - 1

    def current_revision_id(self, slide: SlideSpec) -> UUID | None:
        summaries = self._timeline.list_summaries(slide, include_rejected_proposals=False)
        for item in summaries:
            if item.is_current:
                return item.revision_id
        for item in summaries:
            if item.accepted:
                return item.revision_id
        return None

    def revision_id_for_live_scene(self, slide: SlideSpec) -> UUID | None:
        revisions = self._scene_history.list_slide_scene_revisions(slide)
        live_scene = (
            self._scenes.get_by_layout_plan(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )
        if live_scene is None:
            return None
        live_hash = compute_scene_hash(live_scene)
        index = self._revision_index_for_hash(revisions, live_hash)
        if index is None:
            return None
        revision = revisions[index]
        return revision.id

    def undo(self, slide: SlideSpec) -> tuple[SceneRevisionRestoreResult, UUID | None]:
        revisions = self._scene_history.list_slide_scene_revisions(slide)
        live_scene = (
            self._scenes.get_by_layout_plan(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )
        if live_scene is None or len(revisions) < 2:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        live_hash = compute_scene_hash(live_scene)
        current_index = self._revision_index_for_hash(revisions, live_hash)
        if current_index is None or current_index >= len(revisions) - 1:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        parent_revision = revisions[current_index + 1]
        parent_scene = SceneHistoryService.scene_from_revision(parent_revision)
        if parent_scene is None:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        redo_revision_id = revisions[current_index].id
        result = self._timeline.reapply_scene_state(
            slide=slide,
            scene=parent_scene,
            source_revision_id=parent_revision.id,
            source_version=parent_revision.revision_number,
            note=f"撤销 Scene 编辑 · 回到版本 #{parent_revision.revision_number}",
        )
        return result, redo_revision_id

    def redo(self, slide: SlideSpec, revision_id: UUID) -> SceneRevisionRestoreResult:
        revision = self._revisions.get_revision(revision_id)
        if revision is None or revision.snapshot.get("kind") != SCENE_STATE_SNAPSHOT_KIND:
            raise WorkflowError("没有可重做的 Scene 编辑。")
        scene = SceneHistoryService.scene_from_revision(revision)
        if scene is None:
            raise WorkflowError("没有可重做的 Scene 编辑。")
        return self._timeline.reapply_scene_state(
            slide=slide,
            scene=scene,
            source_revision_id=revision.id,
            source_version=revision.revision_number,
            note=f"重做 Scene 编辑 · 版本 #{revision.revision_number}",
        )

    @staticmethod
    def is_scene_revision(revision_id: UUID, *, revisions: RevisionService) -> bool:
        revision = revisions.get_revision(revision_id)
        return revision is not None and revision.snapshot.get("kind") == SCENE_STATE_SNAPSHOT_KIND

    @staticmethod
    def _revision_index_for_hash(
        revisions: list[object],
        scene_hash: str,
    ) -> int | None:
        for index, revision in enumerate(revisions):
            scene = SceneHistoryService.scene_from_revision(revision)  # type: ignore[arg-type]
            if scene is not None and compute_scene_hash(scene) == scene_hash:
                return index
        return None
