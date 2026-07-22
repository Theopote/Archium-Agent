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
from archium.domain.revision import EntityRevision
from archium.domain.scene_revision_summary import SceneRevisionRestoreResult
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import compute_scene_hash
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
        current = self._revision_for_hash(revisions, live_hash)
        if current is None:
            return 0
        return self._parent_chain_depth(current, revisions)

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
        current = self._revision_for_hash(revisions, live_hash)
        return current.id if current is not None else None

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
        current = self._revision_for_hash(revisions, live_hash)
        if current is None:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        parent_revision = self._parent_revision(current, revisions)
        if parent_revision is None:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        parent_scene = SceneHistoryService.scene_from_revision(parent_revision)
        if parent_scene is None:
            raise WorkflowError("没有可撤销的 Scene 编辑。")
        redo_revision_id = current.id
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
    def _revision_for_hash(
        revisions: list[EntityRevision],
        scene_hash: str,
    ) -> EntityRevision | None:
        for revision in revisions:
            scene = SceneHistoryService.scene_from_revision(revision)
            if scene is not None and compute_scene_hash(scene) == scene_hash:
                return revision
        return None

    @staticmethod
    def _revision_index_for_hash(
        revisions: list[object],
        scene_hash: str,
    ) -> int | None:
        """Backward-compatible index lookup (newest-first lists)."""
        for index, revision in enumerate(revisions):
            scene = SceneHistoryService.scene_from_revision(revision)  # type: ignore[arg-type]
            if scene is not None and compute_scene_hash(scene) == scene_hash:
                return index
        return None

    @staticmethod
    def _parent_revision(
        current: EntityRevision,
        revisions: list[EntityRevision],
    ) -> EntityRevision | None:
        """Resolve undo parent via snapshot parent_revision_id, else chronological older."""
        by_id = {revision.id: revision for revision in revisions}
        raw_parent = current.snapshot.get("parent_revision_id")
        if raw_parent:
            parent = by_id.get(UUID(str(raw_parent)))
            if parent is not None:
                return parent
        # Legacy snapshots without parent: walk newest-first list toward older entries.
        try:
            index = next(i for i, item in enumerate(revisions) if item.id == current.id)
        except StopIteration:
            return None
        if index + 1 >= len(revisions):
            return None
        return revisions[index + 1]

    @classmethod
    def _parent_chain_depth(
        cls,
        current: EntityRevision,
        revisions: list[EntityRevision],
    ) -> int:
        steps = 0
        cursor = current
        seen: set[UUID] = set()
        while True:
            parent = cls._parent_revision(cursor, revisions)
            if parent is None or parent.id in seen:
                break
            seen.add(parent.id)
            steps += 1
            cursor = parent
        return steps
