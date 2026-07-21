"""Revision history for persisted RenderScene snapshots."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.revision_service import RevisionService
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.scene_change_proposal import SceneRevision, SceneRevisionSource
from archium.domain.visual.studio_command import StudioCommand

SCENE_STATE_SNAPSHOT_KIND = "slide_scene_state"


class SceneHistoryService:
    """Record and query RenderScene revisions per slide lineage."""

    def __init__(self, session: Session) -> None:
        self._revisions = RevisionService(session)

    def record_scene(
        self,
        *,
        slide: SlideSpec,
        scene: RenderScene,
        change_source: RevisionSource,
        scene_revision_source: SceneRevisionSource = "ai_proposal",
        commands: list[StudioCommand] | None = None,
        parent_revision_id: UUID | None = None,
        note: str | None = None,
    ) -> tuple[EntityRevision, SceneRevision]:
        scene_hash = compute_scene_hash(scene)
        snapshot = {
            "kind": SCENE_STATE_SNAPSHOT_KIND,
            "slide_id": str(slide.id),
            "scene_id": str(scene.id),
            "scene_hash": scene_hash,
            "scene_revision_source": scene_revision_source,
            "parent_revision_id": (
                str(parent_revision_id) if parent_revision_id is not None else None
            ),
            "scene": scene.model_dump(mode="json"),
            "commands": [
                command.model_dump(mode="json") for command in (commands or [])
            ],
        }
        entity_revision = self._revisions.record(
            entity_type=RevisionEntityType.RENDER_SCENE,
            entity_id=scene.id,
            lineage_id=slide.lineage_id,
            presentation_id=slide.presentation_id,
            change_source=change_source,
            snapshot=snapshot,
            note=note,
        )
        scene_revision = SceneRevision(
            revision_id=entity_revision.id,
            parent_revision_id=parent_revision_id,
            slide_id=slide.id,
            scene_id=scene.id,
            source=scene_revision_source,
            scene_hash=scene_hash,
            commands=list(commands or []),
            created_at=entity_revision.created_at,
        )
        return entity_revision, scene_revision

    def list_slide_scene_revisions(self, slide: SlideSpec) -> list[EntityRevision]:
        revisions = self._revisions.list_by_lineage(slide.lineage_id)
        return [
            revision
            for revision in revisions
            if revision.snapshot.get("kind") == SCENE_STATE_SNAPSHOT_KIND
        ]

    def latest_scene_revision_id(self, slide: SlideSpec) -> UUID | None:
        revisions = self.list_slide_scene_revisions(slide)
        return revisions[0].id if revisions else None

    @staticmethod
    def scene_from_revision(revision: EntityRevision) -> RenderScene | None:
        snapshot = revision.snapshot
        if snapshot.get("kind") != SCENE_STATE_SNAPSHOT_KIND:
            return None
        scene_data = snapshot.get("scene")
        if not isinstance(scene_data, dict):
            return None
        return RenderScene.model_validate(scene_data)
