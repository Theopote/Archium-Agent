"""/scenes — RenderScene facade for Studio."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.visual.studio_scene_service import (
    StudioSceneResult,
    StudioSceneService,
)
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.database.visual_repositories import RenderSceneRepository


class ScenesApi:
    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._scenes = RenderSceneRepository(session)
        self._studio = StudioSceneService(session)

    def list_for_slide(self, slide_id: UUID) -> list[RenderScene]:
        return self._scenes.list_by_slide(slide_id)

    def get_latest_for_slide(self, slide_id: UUID) -> RenderScene | None:
        scenes = self._scenes.list_by_slide(slide_id)
        return scenes[0] if scenes else None

    def ensure_for_slide(
        self,
        slide_id: UUID,
        *,
        force_recompile: bool = False,
    ) -> StudioSceneResult | None:
        return self._studio.ensure_scene_for_slide(
            slide_id,
            force_recompile=force_recompile,
        )
