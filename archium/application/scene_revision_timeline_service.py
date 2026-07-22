"""Build and restore RenderScene revision timelines for Studio."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import save_render_scene
from archium.application.revision_service import RevisionService
from archium.application.visual.scene_history_service import (
    SCENE_STATE_SNAPSHOT_KIND,
    SceneHistoryService,
)
from archium.application.visual.studio_scene_edit_service import sync_layout_geometry_from_scene
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.revision import EntityRevision
from archium.domain.scene_revision_summary import (
    SceneRevisionRestoreResult,
    SceneRevisionSummary,
    map_scene_revision_source,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    LayoutPlanRepository,
    RenderSceneRepository,
    SceneProposalRepository,
)

_TIMELINE_SOURCE_LABELS: dict[str, str] = {
    "manual_edit": "手动编辑",
    "ai_proposal": "AI 提案",
    "qa_repair": "QA 修复",
    "layout_replan": "版式重排",
    "asset_rebind": "素材重绑",
    "import_recovery": "导入恢复",
}


def timeline_source_label(source: str) -> str:
    return _TIMELINE_SOURCE_LABELS.get(source, source)


class SceneRevisionTimelineService:
    """Summarize, compare, and restore persisted RenderScene revisions."""

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
        self._studio_scene = StudioSceneService(session, settings=self._settings)
        self._scenes = RenderSceneRepository(session)
        self._proposals = SceneProposalRepository(session)

    def list_summaries(
        self,
        slide: SlideSpec,
        *,
        include_rejected_proposals: bool = True,
    ) -> list[SceneRevisionSummary]:
        summaries = [
            self._summary_from_revision(revision)
            for revision in self._scene_history.list_slide_scene_revisions(slide)
        ]
        if include_rejected_proposals:
            for proposal in self._proposals.list_by_slide(slide.id):
                if proposal.status == ProposalStatus.REJECTED:
                    summaries.append(self._summary_from_rejected_proposal(proposal))
        summaries.sort(key=lambda item: (item.accepted, item.created_at), reverse=True)
        current_revision_id = self._current_revision_id(slide, summaries)
        if current_revision_id is not None:
            summaries = [
                item.model_copy(update={"is_current": item.revision_id == current_revision_id})
                if item.accepted
                else item
                for item in summaries
            ]
        return summaries

    def _current_revision_id(
        self,
        slide: SlideSpec,
        summaries: list[SceneRevisionSummary],
    ) -> UUID | None:
        """Prefer the accepted revision whose scene_hash matches the live RenderScene."""
        live_scene = None
        if slide.layout_plan_id is not None:
            live_scene = self._scenes.get_by_layout_plan(slide.layout_plan_id)
        if live_scene is not None:
            from archium.domain.visual.render_scene import compute_scene_hash

            live_hash = compute_scene_hash(live_scene)
            for item in summaries:
                if not item.accepted:
                    continue
                scene = self.scene_for_revision(item.revision_id)
                if scene is not None and compute_scene_hash(scene) == live_hash:
                    return item.revision_id
        for item in summaries:
            if item.accepted:
                return item.revision_id
        return None

    def get_summary(self, revision_id: UUID) -> SceneRevisionSummary | None:
        revision = self._revisions.get_revision(revision_id)
        if (
            revision is not None
            and revision.snapshot.get("kind") == SCENE_STATE_SNAPSHOT_KIND
        ):
            return self._summary_from_revision(revision)
        proposal = self._proposals.get(revision_id)
        if proposal is not None and proposal.status == ProposalStatus.REJECTED:
            return self._summary_from_rejected_proposal(proposal)
        return None

    def scene_for_revision(self, revision_id: UUID) -> RenderScene | None:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            return None
        return SceneHistoryService.scene_from_revision(revision)

    def preview_cache_path(
        self,
        presentation_id: UUID,
        revision_id: UUID,
    ) -> Path | None:
        scene = self.scene_for_revision(revision_id)
        if scene is None:
            return None
        return self._studio_scene.preview_cache_path(presentation_id, scene)

    def render_preview(
        self,
        presentation_id: UUID,
        revision_id: UUID,
    ) -> Path | None:
        scene = self.scene_for_revision(revision_id)
        if scene is None:
            return None
        return self._studio_scene.render_scene_preview(presentation_id, scene)

    def compare_revisions(
        self,
        left_revision_id: UUID,
        right_revision_id: UUID,
    ) -> tuple[RenderScene, RenderScene]:
        left = self.scene_for_revision(left_revision_id)
        right = self.scene_for_revision(right_revision_id)
        if left is None or right is None:
            raise WorkflowError("无法加载对比版本中的 Scene 快照。")
        return left, right

    def restore_revision(
        self,
        *,
        slide: SlideSpec,
        source_revision_id: UUID,
    ) -> SceneRevisionRestoreResult:
        source_revision = self._revisions.get_revision(source_revision_id)
        if source_revision is None:
            raise WorkflowError("修订版本不存在。")
        source_scene = SceneHistoryService.scene_from_revision(source_revision)
        if source_scene is None:
            raise WorkflowError("该修订不包含可恢复的 RenderScene。")

        saved = self._persist_restored_scene(source_scene)
        self._sync_layout_plan_from_scene(slide, saved)
        source_version = source_revision.revision_number
        note = f"从 Scene 版本 #{source_version} 恢复"
        entity_revision, _ = self._scene_history.record_scene(
            slide=slide,
            scene=saved,
            change_source=RevisionSource.MANUAL_EDIT,
            scene_revision_source="manual",
            parent_revision_id=source_revision_id,
            note=note,
            summary=note,
            qa_status="restored",
        )
        self._studio_scene.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=saved.layout_plan_id,
        )
        with contextlib.suppress(MemoryError, OSError):
            self._studio_scene.render_scene_preview(slide.presentation_id, saved)
        self._session.commit()
        summary = self._summary_from_revision(entity_revision)
        return SceneRevisionRestoreResult(
            summary=summary,
            restored_scene_id=saved.id,
            source_revision_id=source_revision_id,
            source_version=source_version,
        )

    def reapply_scene_state(
        self,
        *,
        slide: SlideSpec,
        scene: RenderScene,
        source_revision_id: UUID,
        source_version: int,
        note: str,
    ) -> SceneRevisionRestoreResult:
        """Restore a scene snapshot in place without creating a new revision branch."""
        saved = self._persist_restored_scene(scene)
        self._sync_layout_plan_from_scene(slide, saved)
        self._studio_scene.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=saved.layout_plan_id,
        )
        with contextlib.suppress(MemoryError, OSError):
            self._studio_scene.render_scene_preview(slide.presentation_id, saved)
        self._session.commit()
        summary = SceneRevisionSummary(
            revision_id=source_revision_id,
            scene_id=saved.id,
            version=source_version,
            source="manual_edit",
            summary=note,
            command_ids=[],
            created_at=datetime.now(UTC),
            qa_status="restored",
            accepted=True,
            parent_revision_id=None,
            is_current=True,
        )
        return SceneRevisionRestoreResult(
            summary=summary,
            restored_scene_id=saved.id,
            source_revision_id=source_revision_id,
            source_version=source_version,
        )

    def _persist_restored_scene(self, scene: RenderScene) -> RenderScene:
        existing = self._scenes.get_by_layout_plan(scene.layout_plan_id)
        payload = scene.model_copy(deep=True)
        if existing is not None:
            payload = payload.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
        return save_render_scene(self._scenes, payload)

    def _sync_layout_plan_from_scene(self, slide: SlideSpec, scene: RenderScene) -> None:
        if slide.layout_plan_id is None:
            return
        plans = LayoutPlanRepository(self._session)
        presentations = PresentationRepository(self._session)
        plan = plans.get(slide.layout_plan_id)
        if plan is None:
            return
        synced = sync_layout_geometry_from_scene(scene, plan)
        plans.save(synced)
        slide_ref = presentations.get_slide(slide.id)
        if slide_ref is not None:
            slide_ref.layout_plan_id = synced.id
            presentations.save_slide(slide_ref)

    def _summary_from_revision(self, revision: EntityRevision) -> SceneRevisionSummary:
        snapshot = revision.snapshot
        raw_source = str(snapshot.get("scene_revision_source") or "manual")
        source = map_scene_revision_source(raw_source)
        command_ids = self._command_ids_from_snapshot(snapshot)
        scene_id = self._scene_id_from_snapshot(snapshot, revision)
        qa_status = str(snapshot.get("qa_status") or "unknown")
        summary_text = self._summary_text(revision, snapshot, source, len(command_ids))
        parent_raw = snapshot.get("parent_revision_id")
        parent_revision_id = UUID(str(parent_raw)) if parent_raw else None
        return SceneRevisionSummary(
            revision_id=revision.id,
            scene_id=scene_id,
            version=revision.revision_number,
            source=source,
            summary=summary_text,
            command_ids=command_ids,
            created_at=revision.created_at,
            qa_status=qa_status,
            accepted=True,
            parent_revision_id=parent_revision_id,
        )

    def _summary_from_rejected_proposal(
        self,
        proposal: SceneChangeProposal,
    ) -> SceneRevisionSummary:
        command_ids = [command.command_id for command in proposal.commands]
        reasons = " · ".join(proposal.reasons[:2]) if proposal.reasons else "已拒绝的 AI 提案"
        return SceneRevisionSummary(
            revision_id=proposal.proposal_id,
            scene_id=proposal.proposed_scene.id,
            version=0,
            source="ai_proposal",
            summary=reasons,
            command_ids=command_ids,
            created_at=proposal.decided_at or proposal.created_at,
            qa_status="rejected",
            accepted=False,
            parent_revision_id=proposal.base_revision_id,
            proposal_id=proposal.proposal_id,
        )

    @staticmethod
    def _command_ids_from_snapshot(snapshot: dict[str, object]) -> list[UUID]:
        raw_commands = snapshot.get("commands")
        if not isinstance(raw_commands, list):
            return []
        command_ids: list[UUID] = []
        for item in raw_commands:
            if not isinstance(item, dict):
                continue
            command_id = item.get("command_id")
            if command_id is None:
                continue
            command_ids.append(UUID(str(command_id)))
        return command_ids

    @staticmethod
    def _scene_id_from_snapshot(snapshot: dict[str, object], revision: EntityRevision) -> UUID:
        scene_id = snapshot.get("scene_id")
        if scene_id is not None:
            return UUID(str(scene_id))
        if revision.entity_id is not None:
            return revision.entity_id
        scene_data = snapshot.get("scene")
        if isinstance(scene_data, dict) and scene_data.get("id") is not None:
            return UUID(str(scene_data["id"]))
        raise WorkflowError("Scene 修订快照缺少 scene_id。")

    @staticmethod
    def _summary_text(
        revision: EntityRevision,
        snapshot: dict[str, object],
        source: str,
        command_count: int,
    ) -> str:
        stored = snapshot.get("summary")
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
        if revision.note and revision.note.strip():
            return revision.note.strip()
        label = timeline_source_label(source)
        if command_count:
            return f"{label} · {command_count} 条命令"
        return label
