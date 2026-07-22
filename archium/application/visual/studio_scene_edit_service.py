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
from archium.domain.visual.element_lock import ElementLockScope
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    DeleteNodeCommand,
    MoveNodeCommand,
    MoveNodesCommand,
    NodeAlignment,
    NodeMoveTarget,
    NodeReorderDirection,
    ReorderNodeCommand,
    ResizeNodeCommand,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
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
        parent_revision_id = self._parent_revision_for_live_scene(slide)

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

    def move_layout_elements(
        self,
        slide_id: UUID,
        *,
        moves: list[tuple[str, float, float]],
    ) -> SceneEditResult:
        """Batch-move layout elements (one revision). ``moves`` is (element_id, x, y)."""
        slide = self._require_slide(slide_id)
        targets: list[NodeMoveTarget] = []
        node_ids: list[str] = []
        for element_id, x, y in moves:
            node_id = self._resolve_node_id(slide_id, element_id)
            node_ids.append(node_id)
            targets.append(NodeMoveTarget(node_id=node_id, x=x, y=y))
        command = MoveNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=node_ids,
            moves=targets,
            reason="move elements",
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

    def rewrite_layout_element_text(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        new_text: str,
    ) -> SceneEditResult:
        from archium.domain.visual.studio_command import RewriteTextCommand

        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = RewriteTextCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            new_text=new_text,
            reason="canvas rewrite text",
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

    def set_layout_element_visibility(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        visible: bool,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = SetNodeVisibilityCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            visible=visible,
            reason="show element" if visible else "hide element",
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

    def _parent_revision_for_live_scene(self, slide: SlideSpec) -> UUID | None:
        """Parent new edits from the revision matching live scene (branch after undo)."""
        from archium.application.visual.scene_undo_service import SceneUndoService

        live_id = SceneUndoService(self._session, settings=self._settings).revision_id_for_live_scene(
            slide
        )
        if live_id is not None:
            return live_id
        return self._scene_history.latest_scene_revision_id(slide)


def sync_layout_geometry_from_scene(scene: RenderScene, plan: LayoutPlan) -> LayoutPlan:
    """Mirror scene node geometry (and text) back to linked layout elements."""
    from archium.domain.visual.render_scene import TextNode

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
        element.locked = node.locked
        element.lock_scopes = _layout_lock_scopes(node.lock_scopes)
        if isinstance(node, TextNode):
            element.text_content = node.text
        visible_layout_ids.add(element.id)
    next_elements = [element for element in patched.elements if element.id in visible_layout_ids]
    next_reading_order = [
        element_id
        for element_id in (patched.reading_order or [])
        if element_id in visible_layout_ids
    ]
    return patched.model_copy(
        update={
            "elements": next_elements,
            "reading_order": next_reading_order,
        }
    )


def _layout_lock_scopes(raw_scopes: list[str]) -> list[ElementLockScope]:
    scopes: list[ElementLockScope] = []
    for raw in raw_scopes:
        try:
            scopes.append(ElementLockScope(raw))
        except ValueError:
            continue
    return scopes


def _failure_message(result: CommandExecutionResult) -> str:
    if result.issues:
        return "；".join(issue.message for issue in result.issues)
    if result.skipped_actions:
        return "；".join(result.skipped_actions)
    return "Scene 几何编辑失败。"
