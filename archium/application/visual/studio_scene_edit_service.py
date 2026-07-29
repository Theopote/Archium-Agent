"""Apply Studio geometry commands directly to persisted RenderScene."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import save_render_scene
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
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    ApplySilhouetteMaskCommand,
    ConnectNodesCommand,
    CreateFreeformCommand,
    DeleteNodeCommand,
    DuplicateNodesCommand,
    GroupNodesCommand,
    MoveNodeCommand,
    MoveNodesCommand,
    NodeAlignment,
    NodeMoveTarget,
    NodeReorderDirection,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
    ScenePatchAction,
    SetGradientFillCommand,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    SetTextRunsCommand,
    StudioCommand,
    UngroupNodesCommand,
    UpdateNodeStyleCommand,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository, PresentationRepository
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
        self._assets = AssetRepository(session)
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

    def duplicate_layout_elements(
        self,
        slide_id: UUID,
        *,
        element_ids: list[str],
        offset_x: float = 0.25,
        offset_y: float = 0.25,
    ) -> SceneEditResult:
        """Copy selected layout/scene elements with a small offset (one Revision)."""
        if not element_ids:
            raise WorkflowError("没有可复制的元素。")
        slide, plan, _scene = self._require_scene_context(slide_id)
        node_ids: list[str] = []
        source_layout_by_node: dict[str, str] = {}
        for element_id in element_ids:
            node_id = self._resolve_node_id(slide_id, element_id)
            node_ids.append(node_id)
            source_layout_by_node[node_id] = element_id

        command = DuplicateNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=list(node_ids),
            node_ids=list(node_ids),
            offset_x=offset_x,
            offset_y=offset_y,
            reason="duplicate element",
        )
        result = self.apply_command(slide.id, command)

        # Clone LayoutElements for canvas hit-targets; sync also recreates orphans on redo.
        if plan is not None and result.scene is not None and result.applied_actions:
            slide = self._require_slide(slide_id)
            _, plan, scene = self._require_scene_context(slide_id)
            if plan is not None:
                plan = _append_cloned_layout_elements(
                    plan,
                    scene=scene,
                    source_layout_by_node=source_layout_by_node,
                    insert_actions=list(result.applied_actions),
                )
                plan = sync_layout_geometry_from_scene(scene, plan)
                plan = self._plans.save(plan)
                slide.layout_plan_id = plan.id
                self._presentations.save_slide(slide)
                result = SceneEditResult(
                    slide_id=result.slide_id,
                    scene=scene,
                    layout_plan=plan,
                    applied_actions=result.applied_actions,
                    message=result.message,
                )
        return result

    def group_layout_elements(
        self,
        slide_id: UUID,
        *,
        element_ids: list[str],
    ) -> SceneEditResult:
        """Create a GroupNode from two or more layout/scene elements."""
        if len(element_ids) < 2:
            raise WorkflowError("组合至少需要两个元素。")
        slide = self._require_slide(slide_id)
        node_ids = [self._resolve_node_id(slide_id, element_id) for element_id in element_ids]
        command = GroupNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=list(node_ids),
            node_ids=list(node_ids),
            reason="group elements",
        )
        return self.apply_command(slide.id, command)

    def connect_layout_elements(
        self,
        slide_id: UUID,
        *,
        start_element_id: str,
        end_element_id: str,
        routing: str = "straight",
    ) -> SceneEditResult:
        """Create a ConnectorNode between two layout/scene elements."""
        start_id = self._resolve_node_id(slide_id, start_element_id)
        end_id = self._resolve_node_id(slide_id, end_element_id)
        slide = self._require_slide(slide_id)
        command = ConnectNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[start_id, end_id],
            start_node_id=start_id,
            end_node_id=end_id,
            routing=routing,  # type: ignore[arg-type]
            reason="connect elements",
        )
        return self.apply_command(slide.id, command)

    def create_freeform_element(
        self,
        slide_id: UUID,
        *,
        preset: str = "triangle",
        x: float = 3.0,
        y: float = 1.5,
        width: float = 3.0,
        height: float = 2.5,
        fill_color: str | None = "#E8F0FE",
        stroke_color: str | None = "#1A73E8",
    ) -> SceneEditResult:
        """Create a FreeformNode analysis-zone polygon on the slide."""
        slide = self._require_slide(slide_id)
        command = CreateFreeformCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            preset=preset,  # type: ignore[arg-type]
            x=x,
            y=y,
            width=width,
            height=height,
            fill_color=fill_color,
            stroke_color=stroke_color,
            reason="create freeform",
        )
        return self.apply_command(slide.id, command)

    def apply_silhouette_mask(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        preset: str = "diamond",
    ) -> SceneEditResult:
        """Mark an image as silhouette and overlay a Freeform analysis frame."""
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = ApplySilhouetteMaskCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            preset=preset,  # type: ignore[arg-type]
            reason="apply silhouette mask",
        )
        return self.apply_command(slide.id, command)

    def ungroup_layout_element(
        self,
        slide_id: UUID,
        *,
        element_id: str,
    ) -> SceneEditResult:
        """Dissolve a GroupNode identified by layout/scene id."""
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = UngroupNodesCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            group_id=node_id,
            reason="ungroup elements",
        )
        return self.apply_command(slide.id, command)

    def rewrite_layout_element_text(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        new_text: str,
    ) -> SceneEditResult:
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = RewriteTextCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            new_text=new_text,
            reason="rewrite text",
        )
        return self.apply_command(slide.id, command)

    def replace_layout_element_asset(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        asset_id: UUID,
    ) -> SceneEditResult:
        """Replace image asset via ReplaceAssetCommand (Studio command chain)."""
        from archium.application.slide_evidence_edit_service import SlideEvidenceEditService

        result = self._replace_layout_element_asset_impl(
            slide_id,
            element_id=element_id,
            asset_id=asset_id,
        )
        SlideEvidenceEditService(self._session, settings=self._settings).sync_asset_from_photo_element(
            slide_id,
            element_id=element_id,
            asset_id=asset_id,
        )
        return result

    def _replace_layout_element_asset_impl(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        asset_id: UUID,
    ) -> SceneEditResult:
        from archium.application.visual.asset_path_resolver import storage_asset_uri

        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        asset = self._assets.get_by_id(asset_id)
        if asset is None:
            raise WorkflowError(f"素材不存在：{asset_id}")
        project_id = self._project_id_for_slide(slide) or asset.project_id
        storage_uri = storage_asset_uri(project_id, asset.path)
        command = ReplaceAssetCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            asset_id=asset.id,
            storage_uri=storage_uri,
            asset_origin="project_upload",
            reason="replace asset",
        )
        return self.apply_command(slide.id, command)

    def update_layout_element_style(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        color: str | None = None,
        font_size: float | None = None,
        fill_color: str | None = None,
    ) -> SceneEditResult:
        """Update text color / font size or shape fill via UpdateNodeStyleCommand."""
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = UpdateNodeStyleCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            color=color,
            font_size=font_size,
            fill_color=fill_color,
            reason="update node style",
        )
        return self.apply_command(slide.id, command)

    def set_layout_element_text_runs(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        runs: list[dict[str, object]],
    ) -> SceneEditResult:
        """Replace TextNode inline runs (mixed weight/color) via SetTextRunsCommand."""
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = SetTextRunsCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            runs=list(runs),
            reason="set text runs",
        )
        return self.apply_command(slide.id, command)

    def set_layout_element_gradient_fill(
        self,
        slide_id: UUID,
        *,
        element_id: str,
        fill: dict[str, object] | None = None,
        bottom_fade: bool = False,
    ) -> SceneEditResult:
        """Set or clear GradientFill on a shape/image element."""
        node_id = self._resolve_node_id(slide_id, element_id)
        slide = self._require_slide(slide_id)
        command = SetGradientFillCommand(
            presentation_id=slide.presentation_id,
            slide_id=slide.id,
            target_node_ids=[node_id],
            node_id=node_id,
            fill=fill,
            bottom_fade=bottom_fade,
            reason="set gradient fill",
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
        return save_render_scene(self._scenes, payload)

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
    """Mirror scene node geometry (and text) back to linked layout elements.

    After sync, ``geometry_authority`` is ``render_scene`` so
    ``ensure_scene_for_slide`` will not overwrite Studio edits by recompiling
    from a stale LayoutPlan (DOM-011).

    Also recreates LayoutElements for visible scene nodes that are missing from
    the plan (needed after Undo→Redo of Duplicate).
    """
    from archium.domain.visual.render_scene import ImageNode, TextNode

    patched = plan.model_copy(deep=True)
    visible_layout_ids: set[str] = set()
    elements_by_id = {element.id: element for element in patched.elements}
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
        if isinstance(node, ImageNode) and node.asset_id is not None:
            element.content_ref = str(node.asset_id)
        visible_layout_ids.add(element.id)

    next_elements = [element for element in patched.elements if element.id in visible_layout_ids]
    for node in scene.nodes:
        if not node.visible:
            continue
        layout_id = (node.source_layout_element_id or node.id).strip()
        if not layout_id or layout_id in visible_layout_ids:
            continue
        if layout_id in elements_by_id and elements_by_id[layout_id] in next_elements:
            continue
        next_elements.append(_layout_element_from_scene_node(node, layout_id))
        visible_layout_ids.add(layout_id)

    next_reading_order = [
        element_id
        for element_id in (patched.reading_order or [])
        if element_id in visible_layout_ids
    ]
    for element_id in visible_layout_ids:
        if element_id not in next_reading_order:
            next_reading_order.append(element_id)
    synced = patched.model_copy(
        update={
            "elements": next_elements,
            "reading_order": next_reading_order,
        }
    )
    return synced.with_scene_geometry_authority(scene.version)


def _append_cloned_layout_elements(
    plan: LayoutPlan,
    *,
    scene: RenderScene,
    source_layout_by_node: dict[str, str],
    insert_actions: list[ScenePatchAction],
) -> LayoutPlan:
    """Clone source LayoutElements for newly inserted duplicate nodes when possible."""
    existing = {element.id for element in plan.elements}
    extras = list(plan.elements)
    reading = list(plan.reading_order or [])
    # Match insert actions to source nodes by order within the duplicate command.
    source_ids = list(source_layout_by_node.keys())
    insert_index = 0
    for action in insert_actions:
        if action.action_type != "insert_node":
            continue
        new_id = action.node_id[:100]
        source_node_id = source_ids[insert_index] if insert_index < len(source_ids) else ""
        insert_index += 1
        source_layout_id = source_layout_by_node.get(source_node_id, "")
        source_element = next((item for item in plan.elements if item.id == source_layout_id), None)
        node = scene.node_by_id(action.node_id)
        if source_element is None and new_id in existing:
            continue
        if source_element is not None:
            cloned = source_element.model_copy(
                deep=True,
                update={
                    "id": new_id,
                    "x": node.x if node is not None else source_element.x,
                    "y": node.y if node is not None else source_element.y,
                    "z_index": node.z_index if node is not None else source_element.z_index + 1,
                    "locked": False,
                    "lock_scopes": [],
                },
            )
            extras = [item for item in extras if item.id != new_id]
        elif node is not None:
            cloned = _layout_element_from_scene_node(node, new_id)
        else:
            continue
        extras.append(cloned)
        existing.add(cloned.id)
        if cloned.id not in reading:
            reading.append(cloned.id)
    return plan.model_copy(update={"elements": extras, "reading_order": reading})


def _layout_element_from_scene_node(node: object, element_id: str) -> LayoutElement:
    from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
    from archium.domain.visual.render_scene import (
        ChartNode,
        ConnectorNode,
        DrawingNode,
        FreeformNode,
        GroupNode,
        ImageNode,
        ShapeNode,
        TableNode,
        TextNode,
    )

    role = LayoutElementRole.BODY_TEXT
    content_type = LayoutContentType.TEXT
    text_content: str | None = None
    content_ref: str | None = None
    semantic = str(getattr(node, "semantic_role", "") or "").strip()
    if semantic:
        with contextlib.suppress(ValueError):
            role = LayoutElementRole(semantic)

    if isinstance(node, TextNode):
        content_type = LayoutContentType.TEXT
        text_content = node.text
        if not semantic:
            role = LayoutElementRole.BODY_TEXT
    elif isinstance(node, ImageNode):
        content_type = LayoutContentType.IMAGE
        content_ref = str(node.asset_id) if node.asset_id is not None else None
        if not semantic:
            role = LayoutElementRole.SUPPORTING_VISUAL
    elif isinstance(node, DrawingNode):
        content_type = LayoutContentType.DRAWING
        content_ref = str(node.asset_id) if getattr(node, "asset_id", None) is not None else None
        if not semantic:
            role = LayoutElementRole.HERO_VISUAL
    elif isinstance(node, ShapeNode):
        content_type = LayoutContentType.SHAPE
        if not semantic:
            role = LayoutElementRole.DECORATION
    elif isinstance(node, ChartNode):
        content_type = LayoutContentType.CHART
        if not semantic:
            role = LayoutElementRole.SUPPORTING_VISUAL
    elif isinstance(node, TableNode):
        content_type = LayoutContentType.TABLE
        if not semantic:
            role = LayoutElementRole.BODY_TEXT
    elif isinstance(node, GroupNode):
        content_type = LayoutContentType.GROUP
        if not semantic:
            role = LayoutElementRole.DECORATION
    elif isinstance(node, ConnectorNode):
        content_type = LayoutContentType.CONNECTOR
        if not semantic:
            role = LayoutElementRole.ANNOTATION
    elif isinstance(node, FreeformNode):
        content_type = LayoutContentType.FREEFORM
        if not semantic:
            role = LayoutElementRole.ANNOTATION

    return LayoutElement(
        id=element_id[:100],
        role=role,
        content_type=content_type,
        content_ref=content_ref,
        text_content=text_content,
        x=float(getattr(node, "x", 0.0)),
        y=float(getattr(node, "y", 0.0)),
        width=max(float(getattr(node, "width", 1.0)), 0.05),
        height=max(float(getattr(node, "height", 0.5)), 0.05),
        z_index=int(getattr(node, "z_index", 0)),
        locked=bool(getattr(node, "locked", False)),
        lock_scopes=_layout_lock_scopes(list(getattr(node, "lock_scopes", []) or [])),
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
