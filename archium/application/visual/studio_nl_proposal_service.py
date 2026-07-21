"""Create SceneChangeProposal from natural-language Studio edit requests."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_proposal_service import SceneProposalService
from archium.application.visual.studio_nl_command_planner import (
    StudioCommandPlan,
    StudioNLCommandPlanner,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_change_proposal import SceneChangeProposal
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository


class StudioNLProposalService:
    """NL / preset intent → StudioCommand plan → SceneChangeProposal."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._planner = StudioNLCommandPlanner(settings=self._settings, use_llm=use_llm)
        self._proposals = SceneProposalService(session, settings=self._settings)
        self._scene_history = SceneHistoryService(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)

    def plan_from_text(
        self,
        text: str,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide: SlideSpec,
    ) -> StudioCommandPlan:
        return self._planner.plan_text(
            text,
            scene=scene,
            presentation_id=presentation_id,
            slide_id=slide.id,
        )

    def plan_from_intent(
        self,
        intent: VisualEditIntent,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide: SlideSpec,
        params: dict[str, object] | None = None,
    ) -> StudioCommandPlan:
        return self._planner.plan_intent(
            intent,
            scene=scene,
            presentation_id=presentation_id,
            slide_id=slide.id,
            params=params,
        )

    def create_proposal_from_text(
        self,
        slide_id: UUID,
        text: str,
    ) -> SceneChangeProposal:
        slide, scene, presentation_id = self._load_slide_scene(slide_id)
        plan = self.plan_from_text(
            text,
            scene=scene,
            presentation_id=presentation_id,
            slide=slide,
        )
        return self._create_from_plan(slide, scene, presentation_id, plan)

    def create_proposal_from_intent(
        self,
        slide_id: UUID,
        intent: VisualEditIntent,
        *,
        params: dict[str, object] | None = None,
    ) -> SceneChangeProposal:
        slide, scene, presentation_id = self._load_slide_scene(slide_id)
        plan = self.plan_from_intent(
            intent,
            scene=scene,
            presentation_id=presentation_id,
            slide=slide,
            params=params,
        )
        return self._create_from_plan(slide, scene, presentation_id, plan)

    def _create_from_plan(
        self,
        slide: SlideSpec,
        scene: RenderScene,
        presentation_id: UUID,
        plan: StudioCommandPlan,
    ) -> SceneChangeProposal:
        if not plan.commands:
            raise WorkflowError(plan.unsupported_reason or "无法生成 Scene 修改提案。")
        base_revision_id = self._scene_history.latest_scene_revision_id(slide)
        return self._proposals.create_proposal(
            base_scene=scene,
            commands=list(plan.commands),
            presentation_id=presentation_id,
            slide_id=slide.id,
            slide_order=slide.order,
            base_revision_id=base_revision_id,
            reasons=list(plan.reasons),
        )

    def _load_slide_scene(self, slide_id: UUID) -> tuple[SlideSpec, RenderScene, UUID]:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError("未找到当前页面。")
        if slide.layout_plan_id is None:
            raise WorkflowError("当前页面尚无 LayoutPlan，无法生成 Scene 提案。")

        scene_result = self._studio_scene.ensure_scene_for_slide(slide_id)
        if scene_result is None:
            raise WorkflowError("当前页面无法编译 RenderScene。")
        return slide, scene_result.scene, slide.presentation_id
