"""Apply Studio geometry commands directly to persisted RenderScene."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.studio_command_executor import (
    CommandExecutionResult,
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    DeleteNodeCommand,
    MoveNodeCommand,
    NodeAlignment,
    NodeReorderDirection,
    ReorderNodeCommand,
    ResizeNodeCommand,
    SetNodeLockCommand,
    ScenePatchAction,
    StudioCommand,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    LayoutPlanRepository,
    RenderSceneRepository,
)


@dataclass(frozen=True)
class SceneEditResult:
    slide_id: UUID
    scene: RenderScene
    layout_plan: LayoutPlan | None
    applied_actions: tuple[ScenePatchAction, ...]
    message: str = ""


class StudioSceneEditService:
    """Execute Studio commands on the live RenderScene and sync layout geometry."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        executor: StudioCommandExecutor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._executor = executor or StudioCommandExecutor()
        self._presentations = PresentationRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._scenes = RenderSceneRepository(session)
        self._scene_history = SceneHistoryService(session)
        self._visual_history = VisualHistoryService(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)

    def apply_command(self, slide_id: UUID, command: StudioCommand) -> SceneEditResult:
        slide, plan, scene = self._require_scene_context(slide_id)
        parent_revision_id = SceneHistoryService(self._session).latest_scene_revision_id(slide)

        if plan is not None:
            self._visual_history.record_state(
                slide=slide,
                visual_intent=None,
                layout_plan=plan,
                change_source=RevisionSource.MANUAL_EDIT,
                note=command.command_type,
            )

        context = StudioExecutionContext(
            presentation_id=slide.presentation_id,
            slide_order=slide.order,
            project_id=self._project_id_for_slide(slide),
            validate_asset_bindings=False,
        )
        result = self._executor.execute(scene, command, context)
        if not result.success or result.candidate_scene is None:
            raise WorkflowError(_failure_message(result))

        saved_scene = self._persist_scene(scene, result.candidate_scene)
        updated_plan = None
        if plan is not None:
            updated_plan = sync_layout_geometry_from_scene(saved_scene, plan)
            updated_plan = self._plans.save(updated_plan)
            slide.layout_plan_id = updated_plan.id
            self._presentations.save_slide(slide)

        summary = command.reason or command.command_type.replace("_", " ")
        self._scene_history.record_scene(
            slide=slide,
            scene=saved_scene,
            change_source=RevisionSource.MANUAL_EDIT,
            scene_revision_source="manual",
            commands=[command],
            parent_revision_id=parent_revision_id,
            note=summary,
            summary=summary,
            qa_status="edited",
        )
        self._studio_scene.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=saved_scene.layout_plan_id,
        )
        self._studio_scene.render_scene_preview(slide.presentation_id, saved_scene)
        self._session.commit()

        return SceneEditResult(
            slide_id=slide.id,
            scene=saved_scene,
            layout_plan=updated_plan,
            applied_actions=result.applied_actions,
            message=summary,
        )

    def move_layout_element(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        x: float,
        y: float,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = MoveNodeCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            x=x,
            y=y,
            reason="move element",
        )
        return self.apply_command(slide.id, command)

    def resize_layout_element(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        preserve_aspect_ratio: bool = False,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = ResizeNodeCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            x=x,
            y=y,
            width=width,
            height=height,
            preserve_aspect_ratio=preserve_aspect_ratio,
            reason="resize element",
        )
        return self.apply_command(slide.id, command)

    def delete_layout_element(self, slide_id: UUID, *, element_id: str) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = DeleteNodeCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            reason="delete element",
        )
        return self.apply_command(slide.id, command)

    def align_layout_elements(
        self,
        slide_id: UUID,
        *,
        element_ids: list[str],
        alignment: NodeAlignment,
        reference_element_id: str | None = None,
    ) -> SceneEditResult:
        slide = self._require_slide(slide_id)
        node_ids = [self._resolve_node_id(slide.id, element_id) for element_id in element_ids]
        reference_node_id = None
        if reference_element_id:
            reference_node_id = self._resolve_node_id(slide.id, reference_element_id)
        command = AlignNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=node_ids,
            node_ids=node_ids,
            alignment=alignment,
            reference_node_id=reference_node_id,
            reason=f"align {alignment}",
        )
        return self.apply_command(slide.id, command)

    def reorder_layout_element(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        direction: NodeReorderDirection,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = ReorderNodeCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            direction=direction,
            reason=f"reorder {direction}",
        )
        return self.apply_command(slide.id, command)

    def set_layout_element_lock(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        locked: bool,
        lock_scopes: list[str] | None = None,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = SetNodeLockCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            locked=locked,
            lock_scopes=list(lock_scopes or []),
            reason="lock element" if locked else "unlock element",
        )
        return self.apply_command(slide.id, command)

    def _require_scene_context(
        self,
        slide_id: UUID,
    ) -> tuple[SlideSpec, LayoutPlan | None, RenderScene]:
        slide = self._require_slide(slide_id)
        plan = self._plans.get(slide.layout_plan_id) if slide.layout_plan_id else None
        scene = self._scenes.get_by_layout_plan(plan.id) if plan is not None else None
        if scene is None:
            ensured = self._studio_scene.ensure_scene_for_slide(slide.id, force_recompile=True)
            if ensured is None:
                raise WorkflowError("当前页面尚无 RenderScene，无法执行几何编辑。")
            scene = ensured.scene
            plan = self._plans.get(slide.layout_plan_id) if slide.layout_plan_id else plan
        return slide, plan, scene

    def _resolve_node_id(self, slide_id: UUID, element_id: str) -> str:
        _, _, scene = self._require_scene_context(slide_id)
        node = scene.node_by_layout_element_id(element_id) or scene.node_by_id(element_id)
        if node is None:
            raise WorkflowError(f"元素 `{element_id}` 在 RenderScene 中不存在。")
        return node.id

    def _persist_scene(self, existing: RenderScene, candidate: RenderScene) -> RenderScene:
        payload = candidate.model_copy(
            update={
                "id": existing.id,
                "version": existing.version + 1,
                "created_at": existing.created_at,
            }
        )
        if compute_scene_hash(payload) == compute_scene_hash(existing):
            return existing
        return self._scenes.save(payload)

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError("页面不存在。")
        return slide

    def _project_id_for_slide(self, slide: SlideSpec) -> UUID | None:
        presentation = self._presentations.get_presentation(slide.presentation_id)
        return presentation.project_id if presentation is not None else None


def sync_layout_geometry_from_scene(scene: RenderScene, plan: LayoutPlan) -> LayoutPlan:
    """Mirror scene node geometry back to linked layout elements."""
    patched = plan.model_copy(deep=True)
    visible_layout_ids: set[str] = set()
    for element in patched.elements:
        node = scene.node_by_layout_element_id(element.id) or scene.node_by_id(element.id)
        if node is None:
            continue
        if not node.visible:
            continue
        element.x = node.x
        element.y = node.y
        element.width = node.width
        element.height = node.height
        element.z_index = node.z_index
        visible_layout_ids.add(element.id)
    patched.elements = [element for element in patched.elements if element.id in visible_layout_ids]
    if patched.reading_order:
        patched.reading_order = [
            element_id for element_id in patched.reading_order if element_id in visible_layout_ids
        ]
    return patched


def _failure_message(result: CommandExecutionResult) -> str:
    if result.issues:
        return "；".join(issue.message for issue in result.issues)
    if result.skipped_actions:
        return "；".join(result.skipped_actions)
    return "Scene 几何编辑失败。"
