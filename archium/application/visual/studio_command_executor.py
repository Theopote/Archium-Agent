"""Execute StudioCommand mutations against RenderScene (candidate scene output)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from archium.application.visual.asset_binding_validator import AssetBindingValidator
from archium.application.visual.asset_path_resolver import AssetPathResolveContext
from archium.application.visual.drawing_readability_service import increase_drawing_readability
from archium.application.visual.scene_geometry import (
    _Box,
    align_nodes,
    geometry_token,
    page_box,
    reorder_node_z_index,
)
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.studio_errors import StudioAssetReferenceError
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.reference_slide import REFERENCE_TEMPLATE_ASSET_ORIGIN
from archium.domain.visual.render_scene import (
    BaseRenderNode,
    ConnectorEndpoint,
    ConnectorNode,
    DrawingNode,
    FreeformNode,
    GradientFill,
    GroupNode,
    ImageNode,
    RenderNode,
    RenderScene,
    SceneAssetReference,
    ShapeNode,
    TextNode,
    TextRun,
    bottom_fade_gradient,
    compute_group_bounds,
    compute_scene_hash,
    freeform_preset_points,
    group_children,
    move_freeform_to,
    refresh_connector_geometry,
    refresh_connectors_for_nodes,
    refresh_freeform_geometry,
    remap_freeform_points_to_bbox,
    replace_text_node_content,
    resize_freeform_to,
    set_text_node_runs,
    silhouette_overlay_frame,
    translate_freeform_points,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairAction, SceneRepairApplyMode
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    ApplySilhouetteMaskCommand,
    ConnectNodesCommand,
    CreateFreeformCommand,
    DeleteNodeCommand,
    DuplicateNodesCommand,
    FixOverflowCommand,
    GroupNodesCommand,
    IncreaseDrawingReadabilityCommand,
    MoveNodeCommand,
    MoveNodesCommand,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
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
    build_patch_action,
)


@dataclass(frozen=True)
class StudioExecutionContext:
    """Runtime context for command execution."""

    presentation_id: UUID
    slide_order: int = 0
    project_id: UUID | None = None
    asset_resolve_context: AssetPathResolveContext | None = None
    validate_asset_bindings: bool = True
    forbidden_asset_origins: frozenset[str] = field(
        default_factory=lambda: frozenset({REFERENCE_TEMPLATE_ASSET_ORIGIN})
    )


@dataclass(frozen=True)
class CommandExecutionResult:
    """Output of applying a StudioCommand to a base RenderScene."""

    success: bool
    base_scene_hash: str
    candidate_scene: RenderScene | None = None
    applied_actions: tuple[ScenePatchAction, ...] = ()
    skipped_actions: tuple[str, ...] = ()
    issues: tuple[QualityIssue, ...] = ()


_CONTENT_LOCK_SCOPES = frozenset({"content", "all"})
_ASSET_LOCK_SCOPES = frozenset({"asset", "all"})
_GEOMETRY_LOCK_SCOPES = frozenset({"position", "size", "all"})


def node_content_locked(node: BaseRenderNode) -> bool:
    """Return True when text content on a render node must not be mutated."""
    return _node_has_lock_scope(node, _CONTENT_LOCK_SCOPES)


def node_asset_locked(node: BaseRenderNode) -> bool:
    """Return True when asset binding on a render node must not be mutated."""
    return _node_has_lock_scope(node, _ASSET_LOCK_SCOPES)


def node_geometry_locked(node: BaseRenderNode) -> bool:
    """Return True when node position/size must not be mutated."""
    return _node_has_lock_scope(node, _GEOMETRY_LOCK_SCOPES)


def _node_has_lock_scope(node: BaseRenderNode, scopes: frozenset[str]) -> bool:
    if node.locked:
        return True
    return bool(scopes & set(node.lock_scopes))


class StudioCommandExecutor:
    """Apply structured Studio commands and return candidate scenes."""

    def __init__(
        self,
        *,
        scene_repair: SceneRepairService | None = None,
        asset_validator: AssetBindingValidator | None = None,
    ) -> None:
        self._scene_repair = scene_repair or SceneRepairService()
        self._asset_validator = asset_validator or AssetBindingValidator()

    def execute(
        self,
        scene: RenderScene,
        command: StudioCommand,
        context: StudioExecutionContext,
    ) -> CommandExecutionResult:
        base_hash = compute_scene_hash(scene)
        if isinstance(command, RewriteTextCommand):
            return self._execute_rewrite_text(scene, command, base_hash)
        if isinstance(command, FixOverflowCommand):
            return self._execute_fix_overflow(scene, command, context, base_hash)
        if isinstance(command, ReplaceAssetCommand):
            return self._execute_replace_asset(scene, command, context, base_hash)
        if isinstance(command, ReplaceDrawingCommand):
            return self._execute_replace_drawing(scene, command, context, base_hash)
        if isinstance(command, IncreaseDrawingReadabilityCommand):
            return self._execute_increase_drawing_readability(scene, command, base_hash)
        if isinstance(command, MoveNodeCommand):
            return self._execute_move_node(scene, command, base_hash)
        if isinstance(command, MoveNodesCommand):
            return self._execute_move_nodes(scene, command, base_hash)
        if isinstance(command, ResizeNodeCommand):
            return self._execute_resize_node(scene, command, base_hash)
        if isinstance(command, DeleteNodeCommand):
            return self._execute_delete_node(scene, command, base_hash)
        if isinstance(command, DuplicateNodesCommand):
            return self._execute_duplicate_nodes(scene, command, base_hash)
        if isinstance(command, SetNodeLockCommand):
            return self._execute_set_node_lock(scene, command, base_hash)
        if isinstance(command, SetNodeVisibilityCommand):
            return self._execute_set_node_visibility(scene, command, base_hash)
        if isinstance(command, AlignNodesCommand):
            return self._execute_align_nodes(scene, command, base_hash)
        if isinstance(command, ReorderNodeCommand):
            return self._execute_reorder_node(scene, command, base_hash)
        if isinstance(command, UpdateNodeStyleCommand):
            return self._execute_update_node_style(scene, command, base_hash)
        if isinstance(command, SetTextRunsCommand):
            return self._execute_set_text_runs(scene, command, base_hash)
        if isinstance(command, SetGradientFillCommand):
            return self._execute_set_gradient_fill(scene, command, base_hash)
        if isinstance(command, ConnectNodesCommand):
            return self._execute_connect_nodes(scene, command, base_hash)
        if isinstance(command, CreateFreeformCommand):
            return self._execute_create_freeform(scene, command, base_hash)
        if isinstance(command, ApplySilhouetteMaskCommand):
            return self._execute_apply_silhouette_mask(scene, command, base_hash)
        if isinstance(command, GroupNodesCommand):
            return self._execute_group_nodes(scene, command, base_hash)
        if isinstance(command, UngroupNodesCommand):
            return self._execute_ungroup_nodes(scene, command, base_hash)
        return CommandExecutionResult(
            success=False,
            base_scene_hash=base_hash,
            issues=(
                _issue(
                    code="STUDIO.COMMAND_UNSUPPORTED",
                    message=f"unsupported command type: {command.command_type}",
                    severity=IssueSeverity.BLOCKER,
                ),
            ),
        )

    def _execute_rewrite_text(
        self,
        scene: RenderScene,
        command: RewriteTextCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_FOUND",
                        message=f"node `{command.node_id}` not found",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if not isinstance(node, TextNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_TEXT",
                        message=f"node `{command.node_id}` is not a text node",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if node_content_locked(node):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                skipped_actions=(f"rewrite_text:{command.node_id}:locked",),
                issues=(
                    _issue(
                        code="STUDIO.NODE_LOCKED",
                        message=f"node `{command.node_id}` is locked for content edits",
                        evidence=[command.node_id],
                    ),
                ),
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, TextNode)
        before_text = target.text
        replace_text_node_content(target, command.new_text)

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="rewrite_text",
            property_name="text",
            before_value=before_text,
            after_value=command.new_text,
            reason=command.reason or "rewrite text content",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_fix_overflow(
        self,
        scene: RenderScene,
        command: FixOverflowCommand,
        context: StudioExecutionContext,
        base_hash: str,
    ) -> CommandExecutionResult:
        qa_report = run_scene_semantic_qa(
            context.presentation_id,
            [scene],
            slide_orders={scene.slide_id: context.slide_order},
        )
        overflow_findings = [
            finding
            for finding in qa_report.findings
            if finding.check_code == SceneSemanticCheckCode.TEXT_OVERFLOW
        ]

        target_ids = _resolve_target_node_ids(command)
        if target_ids:
            overflow_findings = [
                finding
                for finding in overflow_findings
                if any(node_id in target_ids for node_id in (finding.evidence_refs or []))
            ]

        if not overflow_findings:
            return CommandExecutionResult(
                success=True,
                base_scene_hash=base_hash,
                candidate_scene=scene.model_copy(deep=True),
            )

        repairable, skipped = _partition_locked_overflow(scene, overflow_findings)
        if not repairable:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                skipped_actions=tuple(skipped),
                issues=(
                    _issue(
                        code="STUDIO.NODE_LOCKED",
                        message="all overflow nodes are locked for content edits",
                        evidence=list(target_ids) if target_ids else [],
                    ),
                ),
            )

        repair_result = self._scene_repair.repair_scene(
            scene,
            repairable,
            apply_mode=SceneRepairApplyMode.ALL_REPAIRABLE,
        )
        applied = [
            _patch_from_repair_action(
                action,
                base_scene=scene,
                repaired_scene=repair_result.scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
            )
            for action in repair_result.actions
        ]
        return CommandExecutionResult(
            success=bool(applied) or not repairable,
            base_scene_hash=base_hash,
            candidate_scene=repair_result.scene,
            applied_actions=tuple(applied),
            skipped_actions=tuple(skipped),
        )

    def _execute_replace_asset(
        self,
        scene: RenderScene,
        command: ReplaceAssetCommand,
        context: StudioExecutionContext,
        base_hash: str,
    ) -> CommandExecutionResult:
        origin_issue = _validate_asset_origin(
            command.asset_origin,
            forbidden=context.forbidden_asset_origins,
        )
        if origin_issue is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(origin_issue,),
            )

        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, ImageNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_IMAGE",
                        message=f"node `{command.node_id}` is not an image node",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if node_asset_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="replace_asset",
                node_id=command.node_id,
                lock_kind="asset",
            )

        binding_issue = self._validate_asset_binding(
            context=context,
            asset_id=command.asset_id,
            storage_uri=command.storage_uri,
            asset_origin=command.asset_origin,
            expected_kind="image",
        )
        if binding_issue is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(binding_issue,),
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, ImageNode)
        before_payload = _image_asset_payload(node)
        before_uri = target.storage_uri or target.asset_path
        uri = command.storage_uri.strip()
        target.asset_id = command.asset_id
        target.storage_uri = uri
        target.asset_path = uri
        target.asset_origin = command.asset_origin
        target.asset_unresolved = False
        _upsert_asset_manifest(
            patched,
            asset_id=command.asset_id,
            storage_uri=uri,
            origin=command.asset_origin,
        )

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="replace_asset",
            property_name="storage_uri",
            before_value=before_uri or None,
            after_value=uri,
            after_asset_id=command.asset_id,
            before_payload=before_payload,
            after_payload=_image_asset_payload(
                target,
                asset_id=command.asset_id,
                storage_uri=uri,
                asset_origin=command.asset_origin,
            ),
            reason=command.reason or "replace image asset",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_replace_drawing(
        self,
        scene: RenderScene,
        command: ReplaceDrawingCommand,
        context: StudioExecutionContext,
        base_hash: str,
    ) -> CommandExecutionResult:
        origin_issue = _validate_asset_origin(
            "project_upload",
            forbidden=context.forbidden_asset_origins,
        )
        if origin_issue is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(origin_issue,),
            )

        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, DrawingNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_DRAWING",
                        message=f"node `{command.node_id}` is not a drawing node",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if node_asset_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="replace_drawing",
                node_id=command.node_id,
                lock_kind="asset",
            )

        binding_issue = self._validate_asset_binding(
            context=context,
            asset_id=command.asset_id,
            storage_uri=command.storage_uri,
            asset_origin="project_upload",
            expected_kind="drawing",
        )
        if binding_issue is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(binding_issue,),
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, DrawingNode)
        before_payload = _drawing_asset_payload(node)
        before_uri = target.storage_uri or target.asset_path
        uri = command.storage_uri.strip()
        target.asset_id = command.asset_id
        target.storage_uri = uri
        target.asset_path = uri
        target.fit_mode = "contain"
        target.preserve_aspect_ratio = command.preserve_aspect_ratio
        target.preserve_annotations = command.preserve_annotations
        target.asset_unresolved = False
        if command.drawing_type is not None:
            target.drawing_type = command.drawing_type
        _upsert_asset_manifest(
            patched,
            asset_id=command.asset_id,
            storage_uri=uri,
            origin="project_upload",
        )

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="replace_drawing",
            property_name="storage_uri",
            before_value=before_uri or None,
            after_value=uri,
            after_asset_id=command.asset_id,
            before_payload=before_payload,
            after_payload=_drawing_asset_payload(
                target,
                asset_id=command.asset_id,
                storage_uri=uri,
                drawing_type=command.drawing_type or node.drawing_type,
                fit_mode="contain",
                preserve_aspect_ratio=command.preserve_aspect_ratio,
                preserve_annotations=command.preserve_annotations,
            ),
            reason=command.reason or "replace drawing asset",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_increase_drawing_readability(
        self,
        scene: RenderScene,
        command: IncreaseDrawingReadabilityCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, DrawingNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_DRAWING",
                        message=f"node `{command.node_id}` is not a drawing node",
                        evidence=[command.node_id],
                        category=IssueCategory.ARCHITECTURAL,
                    ),
                ),
            )
        if node_geometry_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="increase_drawing_readability",
                node_id=command.node_id,
                lock_kind="geometry",
            )
        if command.forbid_cover_crop and node.fit_mode == "cover":
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.DRAWING_COVER_FORBIDDEN",
                        message="drawing must not use cover fit mode",
                        severity=IssueSeverity.BLOCKER,
                        category=IssueCategory.ARCHITECTURAL,
                        evidence=[command.node_id],
                    ),
                ),
            )

        try:
            result = increase_drawing_readability(scene, command, base_scene_hash=base_hash)
        except ValueError as exc:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.COMMAND_INVALID",
                        message=str(exc),
                        evidence=[command.node_id],
                    ),
                ),
            )

        if not result.actions:
            return CommandExecutionResult(
                success=True,
                base_scene_hash=base_hash,
                candidate_scene=result.scene,
            )

        return CommandExecutionResult(
            success=result.area_ratio_after + 1e-6 >= command.target_min_area_ratio
            or result.area_ratio_after > result.area_ratio_before,
            base_scene_hash=base_hash,
            candidate_scene=result.scene,
            applied_actions=result.actions,
        )

    def _execute_move_node(
        self,
        scene: RenderScene,
        command: MoveNodeCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if node_geometry_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="move_node",
                node_id=command.node_id,
                lock_kind="geometry",
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None
        before_token = geometry_token(target)
        dx = command.x - target.x
        dy = command.y - target.y
        if isinstance(target, FreeformNode):
            move_freeform_to(target, x=command.x, y=command.y)
        else:
            target.x = command.x
            target.y = command.y
        actions: list[ScenePatchAction] = [
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=command.node_id,
                action_type="move_node",
                property_name="geometry",
                before_value=before_token,
                after_value=geometry_token(target),
                reason=command.reason or "move node",
            )
        ]
        if isinstance(target, GroupNode) and (dx != 0 or dy != 0):
            for child in group_children(patched, target):
                if node_geometry_locked(child):
                    return _locked_result(
                        base_hash=base_hash,
                        command_type="move_node",
                        node_id=child.id,
                        lock_kind="geometry",
                    )
                child_before = geometry_token(child)
                if isinstance(child, FreeformNode):
                    translate_freeform_points(child, dx=dx, dy=dy)
                else:
                    child.x += dx
                    child.y += dy
                actions.append(
                    build_patch_action(
                        scene,
                        base_scene_hash=base_hash,
                        command_id=command.command_id,
                        node_id=child.id,
                        action_type="move_node",
                        property_name="geometry",
                        before_value=child_before,
                        after_value=geometry_token(child),
                        reason=command.reason or "move group child",
                    )
                )
        moved_ids = {command.node_id}
        if isinstance(target, GroupNode):
            moved_ids.update(child.id for child in group_children(patched, target))
        for connector_id in refresh_connectors_for_nodes(patched, moved_ids):
            connector = patched.node_by_id(connector_id)
            if connector is None:
                continue
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=connector_id,
                    action_type="refresh_connector",
                    property_name="geometry",
                    before_value=None,
                    after_value=geometry_token(connector),
                    reason=command.reason or "refresh connector after move",
                )
            )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_move_nodes(
        self,
        scene: RenderScene,
        command: MoveNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        patched = scene.model_copy(deep=True)
        actions: list[ScenePatchAction] = []
        moved_ids: set[str] = set()
        for move in command.moves:
            node = patched.node_by_id(move.node_id)
            if node is None:
                return _node_not_found(base_hash, move.node_id)
            if node_geometry_locked(node):
                return _locked_result(
                    base_hash=base_hash,
                    command_type="move_nodes",
                    node_id=move.node_id,
                    lock_kind="geometry",
                )
            before_token = geometry_token(node)
            if isinstance(node, FreeformNode):
                move_freeform_to(node, x=move.x, y=move.y)
            else:
                node.x = move.x
                node.y = move.y
            moved_ids.add(move.node_id)
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=move.node_id,
                    action_type="move_nodes",
                    property_name="geometry",
                    before_value=before_token,
                    after_value=geometry_token(node),
                    reason=command.reason or "move nodes",
                )
            )
        for connector_id in refresh_connectors_for_nodes(patched, moved_ids):
            connector = patched.node_by_id(connector_id)
            if connector is None:
                continue
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=connector_id,
                    action_type="refresh_connector",
                    property_name="geometry",
                    before_value=None,
                    after_value=geometry_token(connector),
                    reason=command.reason or "refresh connector after move",
                )
            )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_resize_node(
        self,
        scene: RenderScene,
        command: ResizeNodeCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if node_geometry_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="resize_node",
                node_id=command.node_id,
                lock_kind="geometry",
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None
        before_token = geometry_token(target)
        width = command.width
        height = command.height
        if command.preserve_aspect_ratio and target.width > 0 and target.height > 0:
            aspect = target.width / target.height
            if width / max(height, 1e-6) > aspect:
                width = height * aspect
            else:
                height = width / aspect

        actions: list[ScenePatchAction] = []
        if isinstance(target, GroupNode):
            # V1: uniform scale only — use the dominant axis scale factor.
            old_w = max(target.width, 1e-6)
            old_h = max(target.height, 1e-6)
            scale = min(width / old_w, height / old_h)
            origin_x = target.x
            origin_y = target.y
            for child in group_children(patched, target):
                if node_geometry_locked(child):
                    return _locked_result(
                        base_hash=base_hash,
                        command_type="resize_node",
                        node_id=child.id,
                        lock_kind="geometry",
                    )
                child_before = geometry_token(child)
                if isinstance(child, FreeformNode):
                    rel_x = child.x - origin_x
                    rel_y = child.y - origin_y
                    resize_freeform_to(
                        child,
                        x=command.x + rel_x * scale,
                        y=command.y + rel_y * scale,
                        width=max(child.width * scale, 0.05),
                        height=max(child.height * scale, 0.05),
                    )
                else:
                    rel_x = child.x - origin_x
                    rel_y = child.y - origin_y
                    child.x = command.x + rel_x * scale
                    child.y = command.y + rel_y * scale
                    child.width = max(child.width * scale, 0.05)
                    child.height = max(child.height * scale, 0.05)
                actions.append(
                    build_patch_action(
                        scene,
                        base_scene_hash=base_hash,
                        command_id=command.command_id,
                        node_id=child.id,
                        action_type="resize_node",
                        property_name="geometry",
                        before_value=child_before,
                        after_value=geometry_token(child),
                        reason=command.reason or "resize group child",
                    )
                )
            target.x = command.x
            target.y = command.y
            target.width = max(old_w * scale, 0.05)
            target.height = max(old_h * scale, 0.05)
        elif isinstance(target, FreeformNode):
            resize_freeform_to(
                target,
                x=command.x,
                y=command.y,
                width=width,
                height=height,
            )
        else:
            target.x = command.x
            target.y = command.y
            target.width = width
            target.height = height

        actions.insert(
            0,
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=command.node_id,
                action_type="resize_node",
                property_name="geometry",
                before_value=before_token,
                after_value=geometry_token(target),
                reason=command.reason or "resize node",
            ),
        )
        resized_ids = {command.node_id}
        if isinstance(target, GroupNode):
            resized_ids.update(child.id for child in group_children(patched, target))
        for connector_id in refresh_connectors_for_nodes(patched, resized_ids):
            connector = patched.node_by_id(connector_id)
            if connector is None:
                continue
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=connector_id,
                    action_type="refresh_connector",
                    property_name="geometry",
                    before_value=None,
                    after_value=geometry_token(connector),
                    reason=command.reason or "refresh connector after resize",
                )
            )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_delete_node(
        self,
        scene: RenderScene,
        command: DeleteNodeCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if node_geometry_locked(node):
            return _locked_result(
                base_hash=base_hash,
                command_type="delete_node",
                node_id=command.node_id,
                lock_kind="geometry",
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None
        before_visible = str(target.visible)
        target.visible = False
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="delete_node",
            property_name="visible",
            before_value=before_visible,
            after_value="false",
            reason=command.reason or "delete node",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_duplicate_nodes(
        self,
        scene: RenderScene,
        command: DuplicateNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        from uuid import uuid4

        patched = scene.model_copy(deep=True)
        actions: list[ScenePatchAction] = []
        max_z = max((node.z_index for node in patched.nodes), default=0)
        explicit_ids = list(command.new_node_ids)
        for index, node_id in enumerate(command.node_ids):
            source = patched.node_by_id(node_id)
            if source is None:
                return _node_not_found(base_hash, node_id)
            if node_geometry_locked(source):
                return _locked_result(
                    base_hash=base_hash,
                    command_type="duplicate_nodes",
                    node_id=node_id,
                    lock_kind="geometry",
                )
            if index < len(explicit_ids) and explicit_ids[index].strip():
                new_id = explicit_ids[index].strip()
            else:
                new_id = f"{source.id}__dup_{uuid4().hex[:8]}"
            if len(new_id) > 100:
                new_id = f"dup_{uuid4().hex[:12]}"
            if patched.node_by_id(new_id) is not None:
                return CommandExecutionResult(
                    success=False,
                    base_scene_hash=base_hash,
                    issues=(
                        _issue(
                            code="STUDIO.DUPLICATE_ID_COLLISION",
                            message=f"duplicate node id already exists: {new_id}",
                            severity=IssueSeverity.BLOCKER,
                        ),
                    ),
                )
            max_z += 1
            cloned = _clone_render_node(
                source,
                new_id=new_id,
                offset_x=command.offset_x,
                offset_y=command.offset_y,
                z_index=max_z,
                page_width=scene.page_width,
                page_height=scene.page_height,
            )
            patched.nodes = list(patched.nodes) + [cloned]
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=new_id,
                    action_type="insert_node",
                    property_name="nodes",
                    before_value=None,
                    after_value=new_id,
                    after_payload=cloned.model_dump(mode="json"),
                    reason=command.reason or f"duplicate {node_id}",
                )
            )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_align_nodes(
        self,
        scene: RenderScene,
        command: AlignNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        patched = scene.model_copy(deep=True)
        nodes = [patched.node_by_id(node_id) for node_id in command.node_ids]
        resolved = [node for node in nodes if node is not None]
        if not resolved:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.NODE_NOT_FOUND",
                        message="no alignable nodes found",
                        evidence=list(command.node_ids),
                    ),
                ),
            )

        locked = [node.id for node in resolved if node_geometry_locked(node)]
        if locked:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                skipped_actions=tuple(f"align_nodes:{node_id}:locked" for node_id in locked),
                issues=(
                    _issue(
                        code="STUDIO.NODE_LOCKED",
                        message="one or more nodes are locked for geometry edits",
                        evidence=locked,
                    ),
                ),
            )

        before_tokens = {node.id: geometry_token(node) for node in resolved}
        before_bboxes = {
            node.id: (node.x, node.y, node.width, node.height)
            for node in resolved
            if isinstance(node, FreeformNode)
        }
        align_reference: BaseRenderNode | _Box | None = None
        if command.reference_node_id:
            align_reference = patched.node_by_id(command.reference_node_id)
        elif len(resolved) == 1:
            align_reference = page_box(patched.page_width, patched.page_height)
        updates = align_nodes(
            cast(list[BaseRenderNode], resolved),
            command.alignment,
            reference=align_reference,
        )
        if not updates:
            return CommandExecutionResult(
                success=True,
                base_scene_hash=base_hash,
                candidate_scene=patched,
            )

        actions: list[ScenePatchAction] = []
        for node_id, after_token in updates.items():
            node = patched.node_by_id(node_id)
            if isinstance(node, FreeformNode) and node_id in before_bboxes:
                old_x, old_y, old_w, old_h = before_bboxes[node_id]
                remap_freeform_points_to_bbox(
                    node,
                    old_x=old_x,
                    old_y=old_y,
                    old_width=old_w,
                    old_height=old_h,
                )
                after_token = geometry_token(node)
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=node_id,
                    action_type="align_nodes",
                    property_name="geometry",
                    before_value=before_tokens[node_id],
                    after_value=after_token,
                    reason=command.reason or f"align {command.alignment}",
                )
            )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_set_node_lock(
        self,
        scene: RenderScene,
        command: SetNodeLockCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None

        before_locked = target.locked
        before_scopes = ",".join(target.lock_scopes)
        target.locked = command.locked
        target.lock_scopes = list(command.lock_scopes)

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="set_node_lock",
            property_name="lock",
            before_value=f"{before_locked}:{before_scopes}",
            after_value=f"{target.locked}:{','.join(target.lock_scopes)}",
            before_payload={"locked": before_locked, "lock_scopes": list(node.lock_scopes)},
            after_payload={"locked": target.locked, "lock_scopes": list(target.lock_scopes)},
            reason=command.reason or ("lock node" if command.locked else "unlock node"),
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_set_node_visibility(
        self,
        scene: RenderScene,
        command: SetNodeVisibilityCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None

        before_visible = target.visible
        target.visible = command.visible

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="set_node_visibility",
            property_name="visible",
            before_value=str(before_visible).lower(),
            after_value=str(target.visible).lower(),
            before_payload={"visible": before_visible},
            after_payload={"visible": target.visible},
            reason=command.reason or ("show node" if command.visible else "hide node"),
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_reorder_node(
        self,
        scene: RenderScene,
        command: ReorderNodeCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None
        before_z = str(target.z_index)
        target.z_index = reorder_node_z_index(patched, target, command.direction)
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="reorder_node",
            property_name="z_index",
            before_value=before_z,
            after_value=str(target.z_index),
            reason=command.reason or f"reorder {command.direction}",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_update_node_style(
        self,
        scene: RenderScene,
        command: UpdateNodeStyleCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if command.color is None and command.font_size is None and command.fill_color is None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.STYLE_EMPTY",
                        message="update_node_style requires color, font_size, or fill_color",
                        evidence=[command.node_id],
                    ),
                ),
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert target is not None
        before: dict[str, object] = {}
        after: dict[str, object] = {}

        if isinstance(target, TextNode):
            if command.color is not None:
                before["color"] = target.color
                target.color = command.color
                after["color"] = target.color
                for run in target.runs:
                    run.color = command.color
            if command.font_size is not None:
                before["font_size"] = target.font_size
                target.font_size = command.font_size
                after["font_size"] = target.font_size
                for run in target.runs:
                    run.font_size = command.font_size
        elif isinstance(target, ShapeNode):
            if command.fill_color is not None or command.color is not None:
                fill = command.fill_color or command.color
                before["fill_color"] = target.fill_color
                target.fill_color = fill
                after["fill_color"] = target.fill_color
        else:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.STYLE_UNSUPPORTED_NODE",
                        message=f"node `{command.node_id}` does not support style updates",
                        evidence=[command.node_id],
                    ),
                ),
            )

        if not after:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.STYLE_NO_CHANGE",
                        message=f"no applicable style fields for node `{command.node_id}`",
                        evidence=[command.node_id],
                    ),
                ),
            )

        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="update_node_style",
            property_name="style",
            before_value=str(before),
            after_value=str(after),
            before_payload=before,
            after_payload=after,
            reason=command.reason or "update node style",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_set_text_runs(
        self,
        scene: RenderScene,
        command: SetTextRunsCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, TextNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.TEXT_RUNS_NOT_TEXT",
                        message=f"node `{command.node_id}` is not a TextNode",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if node_content_locked(node):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.CONTENT_LOCKED",
                        message=f"node `{command.node_id}` content is locked",
                        evidence=[command.node_id],
                    ),
                ),
                skipped_actions=(f"set_text_runs:{command.node_id}:locked",),
            )

        try:
            parsed = [TextRun.model_validate(item) for item in command.runs]
        except Exception as exc:  # noqa: BLE001 — surface as studio issue
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.TEXT_RUNS_INVALID",
                        message=f"invalid text runs: {exc}",
                        evidence=[command.node_id],
                    ),
                ),
            )
        if not any(run.text for run in parsed):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.TEXT_RUNS_EMPTY",
                        message="set_text_runs requires at least one non-empty run text",
                        evidence=[command.node_id],
                    ),
                ),
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, TextNode)
        before_payload = {
            "text": target.text,
            "runs": [run.model_dump(mode="json") for run in target.runs],
        }
        set_text_node_runs(target, parsed)
        after_payload = {
            "text": target.text,
            "runs": [run.model_dump(mode="json") for run in target.runs],
        }
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="set_text_runs",
            property_name="runs",
            before_value=before_payload["text"],
            after_value=after_payload["text"],
            before_payload=before_payload,
            after_payload=after_payload,
            reason=command.reason or "set text runs",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_set_gradient_fill(
        self,
        scene: RenderScene,
        command: SetGradientFillCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, (ShapeNode, ImageNode)):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.GRADIENT_UNSUPPORTED_NODE",
                        message=f"node `{command.node_id}` does not support gradient fill",
                        evidence=[command.node_id],
                    ),
                ),
            )

        next_fill: GradientFill | None = None
        if command.bottom_fade and command.fill is None:
            next_fill = bottom_fade_gradient()
        elif command.fill is not None:
            try:
                next_fill = GradientFill.model_validate(command.fill)
            except Exception as exc:  # noqa: BLE001
                return CommandExecutionResult(
                    success=False,
                    base_scene_hash=base_hash,
                    issues=(
                        _issue(
                            code="STUDIO.GRADIENT_INVALID",
                            message=f"invalid gradient fill: {exc}",
                            evidence=[command.node_id],
                        ),
                    ),
                )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, (ShapeNode, ImageNode))
        before_payload = target.fill.model_dump(mode="json") if target.fill else None
        target.fill = next_fill
        if isinstance(target, ImageNode) and next_fill is not None and not target.image_mask:
            target.image_mask = "gradient_fade"
        after_payload = next_fill.model_dump(mode="json") if next_fill else None
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="set_gradient_fill",
            property_name="fill",
            before_value=str(before_payload),
            after_value=str(after_payload),
            before_payload=before_payload or {},
            after_payload=after_payload or {},
            reason=command.reason or "set gradient fill",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_connect_nodes(
        self,
        scene: RenderScene,
        command: ConnectNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        from uuid import uuid4

        if command.start_node_id == command.end_node_id:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.CONNECTOR_SAME_ENDPOINT",
                        message="connect_nodes requires two distinct nodes",
                        evidence=[command.start_node_id],
                    ),
                ),
            )
        start = scene.node_by_id(command.start_node_id)
        end = scene.node_by_id(command.end_node_id)
        if start is None:
            return _node_not_found(base_hash, command.start_node_id)
        if end is None:
            return _node_not_found(base_hash, command.end_node_id)
        if isinstance(start, ConnectorNode) or isinstance(end, ConnectorNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.CONNECTOR_TARGET_CONNECTOR",
                        message="cannot connect to another connector",
                        evidence=[command.start_node_id, command.end_node_id],
                    ),
                ),
            )

        explicit = (command.connector_id or "").strip()
        connector_id = explicit or f"cxn_{uuid4().hex[:10]}"
        if scene.node_by_id(connector_id) is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.CONNECTOR_ID_COLLISION",
                        message=f"connector id already exists: {connector_id}",
                        evidence=[connector_id],
                    ),
                ),
            )

        patched = scene.model_copy(deep=True)
        max_z = max((node.z_index for node in patched.nodes), default=0)
        connector = ConnectorNode(
            id=connector_id,
            x=0.05,
            y=0.05,
            width=0.05,
            height=0.05,
            z_index=max_z + 1,
            start=ConnectorEndpoint(
                node_id=command.start_node_id,
                anchor=command.start_anchor,
            ),
            end=ConnectorEndpoint(
                node_id=command.end_node_id,
                anchor=command.end_anchor,
            ),
            routing=command.routing,
            stroke_color=command.stroke_color,
            stroke_width=command.stroke_width,
            arrow_start=command.arrow_start,
            arrow_end=command.arrow_end,
            label=command.label,
            semantic_role="connector",
            source_layout_element_id=connector_id,
        )
        patched.nodes = list(patched.nodes) + [connector]
        if not refresh_connector_geometry(patched, connector):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.CONNECTOR_UNRESOLVED",
                        message="could not resolve connector endpoints",
                        evidence=[command.start_node_id, command.end_node_id],
                    ),
                ),
            )
        # Re-assign after geometry refresh so validation sees final bbox.
        patched.nodes = [n for n in patched.nodes if n.id != connector_id] + [connector]
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=connector_id,
            action_type="insert_node",
            property_name="nodes",
            before_value=None,
            after_value=connector_id,
            after_payload=connector.model_dump(mode="json"),
            reason=command.reason or "connect nodes",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_create_freeform(
        self,
        scene: RenderScene,
        command: CreateFreeformCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        from uuid import uuid4

        explicit = (command.freeform_id or "").strip()
        freeform_id = explicit or f"ff_{uuid4().hex[:10]}"
        if scene.node_by_id(freeform_id) is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.FREEFORM_ID_COLLISION",
                        message=f"freeform id already exists: {freeform_id}",
                        evidence=[freeform_id],
                    ),
                ),
            )

        points = freeform_preset_points(
            command.preset,
            x=command.x,
            y=command.y,
            width=command.width,
            height=command.height,
        )
        patched = scene.model_copy(deep=True)
        max_z = max((node.z_index for node in patched.nodes), default=0)
        freeform = FreeformNode(
            id=freeform_id,
            x=command.x,
            y=command.y,
            width=command.width,
            height=command.height,
            z_index=max_z + 1,
            points=points,
            closed=command.closed,
            fill_color=command.fill_color,
            stroke_color=command.stroke_color,
            stroke_width=command.stroke_width,
            semantic_role="annotation",
            source_layout_element_id=freeform_id,
        )
        refresh_freeform_geometry(freeform)
        patched.nodes = list(patched.nodes) + [freeform]
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=freeform_id,
            action_type="insert_node",
            property_name="nodes",
            before_value=None,
            after_value=freeform_id,
            after_payload=freeform.model_dump(mode="json"),
            reason=command.reason or f"create freeform ({command.preset})",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_apply_silhouette_mask(
        self,
        scene: RenderScene,
        command: ApplySilhouetteMaskCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        node = scene.node_by_id(command.node_id)
        if node is None:
            return _node_not_found(base_hash, command.node_id)
        if not isinstance(node, ImageNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.SILHOUETTE_NOT_IMAGE",
                        message=f"node `{command.node_id}` is not an ImageNode",
                        evidence=[command.node_id],
                    ),
                ),
            )

        explicit = (command.freeform_id or "").strip()
        freeform_id = explicit or f"{command.node_id}__silhouette"[:100]

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.node_id)
        assert isinstance(target, ImageNode)
        actions: list[ScenePatchAction] = []
        before_mask = target.image_mask
        target.image_mask = "silhouette"
        actions.append(
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=command.node_id,
                action_type="set_image_mask",
                property_name="image_mask",
                before_value=before_mask,
                after_value="silhouette",
                reason=command.reason or "apply silhouette mask",
            )
        )

        # Drop prior silhouette overlay for this image if present.
        patched.nodes = [n for n in patched.nodes if n.id != freeform_id]
        fx, fy, fw, fh, points = silhouette_overlay_frame(
            image_x=target.x,
            image_y=target.y,
            image_width=target.width,
            image_height=target.height,
            preset=command.preset,
        )
        max_z = max((n.z_index for n in patched.nodes), default=target.z_index)
        freeform = FreeformNode(
            id=freeform_id,
            x=fx,
            y=fy,
            width=fw,
            height=fh,
            z_index=max(max_z, target.z_index) + 1,
            points=points,
            closed=True,
            fill_color=None,
            stroke_color="#FFFFFF",
            stroke_width=1.5,
            semantic_role="annotation",
            source_layout_element_id=freeform_id,
        )
        refresh_freeform_geometry(freeform)
        patched.nodes = list(patched.nodes) + [freeform]
        actions.append(
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=freeform_id,
                action_type="insert_node",
                property_name="nodes",
                before_value=None,
                after_value=freeform_id,
                after_payload=freeform.model_dump(mode="json"),
                reason=command.reason or "silhouette freeform overlay",
            )
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_group_nodes(
        self,
        scene: RenderScene,
        command: GroupNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        from uuid import uuid4

        unique_ids = list(dict.fromkeys(command.node_ids))
        if len(unique_ids) < 2:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.GROUP_TOO_FEW",
                        message="group_nodes requires at least two distinct nodes",
                        evidence=list(command.node_ids),
                    ),
                ),
            )

        members: list[BaseRenderNode] = []
        for node_id in unique_ids:
            node = scene.node_by_id(node_id)
            if node is None:
                return _node_not_found(base_hash, node_id)
            if isinstance(node, GroupNode):
                return CommandExecutionResult(
                    success=False,
                    base_scene_hash=base_hash,
                    issues=(
                        _issue(
                            code="STUDIO.GROUP_NEST_GROUP",
                            message=(
                                "V1 group_nodes does not accept GroupNode targets; "
                                "select leaf nodes only"
                            ),
                            evidence=[node_id],
                        ),
                    ),
                )
            if node_geometry_locked(node):
                return _locked_result(
                    base_hash=base_hash,
                    command_type="group_nodes",
                    node_id=node_id,
                    lock_kind="geometry",
                )
            members.append(node)

        explicit = (command.group_id or "").strip()
        group_id = explicit or f"group_{uuid4().hex[:10]}"
        if scene.node_by_id(group_id) is not None:
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.GROUP_ID_COLLISION",
                        message=f"group id already exists: {group_id}",
                        evidence=[group_id],
                    ),
                ),
            )

        patched = scene.model_copy(deep=True)
        actions: list[ScenePatchAction] = []

        # Detach from any prior group membership.
        for node_id in unique_ids:
            child = patched.node_by_id(node_id)
            assert child is not None
            if not child.group_id:
                continue
            old_group = patched.node_by_id(child.group_id)
            if isinstance(old_group, GroupNode):
                old_group.children = [cid for cid in old_group.children if cid != node_id]
                if not old_group.children:
                    actions.append(
                        build_patch_action(
                            scene,
                            base_scene_hash=base_hash,
                            command_id=command.command_id,
                            node_id=old_group.id,
                            action_type="remove_node",
                            property_name="nodes",
                            before_value=old_group.id,
                            after_value=None,
                            before_payload=old_group.model_dump(mode="json"),
                            reason=command.reason or "remove empty prior group",
                        )
                    )
                    patched.nodes = [n for n in patched.nodes if n.id != old_group.id]
            before_gid = child.group_id
            child.group_id = None
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=node_id,
                    action_type="set_group_id",
                    property_name="group_id",
                    before_value=before_gid,
                    after_value=None,
                    reason=command.reason or "detach before regroup",
                )
            )

        live_members = [patched.node_by_id(nid) for nid in unique_ids]
        resolved = [m for m in live_members if m is not None]
        x, y, width, height = compute_group_bounds(resolved)
        max_z = max((node.z_index for node in patched.nodes), default=0)
        # Link children before inserting GroupNode so RenderScene validation passes.
        for node_id in unique_ids:
            child = patched.node_by_id(node_id)
            assert child is not None
            before_gid = child.group_id
            child.group_id = group_id
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=node_id,
                    action_type="set_group_id",
                    property_name="group_id",
                    before_value=before_gid,
                    after_value=group_id,
                    reason=command.reason or "join group",
                )
            )
        group = GroupNode(
            id=group_id,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=max_z + 1,
            children=list(unique_ids),
            semantic_role="group",
            source_layout_element_id=group_id,
        )
        patched.nodes = list(patched.nodes) + [group]
        actions.append(
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=group_id,
                action_type="insert_node",
                property_name="nodes",
                before_value=None,
                after_value=group_id,
                after_payload=group.model_dump(mode="json"),
                reason=command.reason or "create group",
            )
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _execute_ungroup_nodes(
        self,
        scene: RenderScene,
        command: UngroupNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        group = scene.node_by_id(command.group_id)
        if group is None:
            return _node_not_found(base_hash, command.group_id)
        if not isinstance(group, GroupNode):
            return CommandExecutionResult(
                success=False,
                base_scene_hash=base_hash,
                issues=(
                    _issue(
                        code="STUDIO.UNGROUP_NOT_GROUP",
                        message=f"node `{command.group_id}` is not a GroupNode",
                        evidence=[command.group_id],
                    ),
                ),
            )
        if node_geometry_locked(group):
            return _locked_result(
                base_hash=base_hash,
                command_type="ungroup_nodes",
                node_id=command.group_id,
                lock_kind="geometry",
            )

        patched = scene.model_copy(deep=True)
        target = patched.node_by_id(command.group_id)
        assert isinstance(target, GroupNode)
        actions: list[ScenePatchAction] = []
        for child_id in list(target.children):
            child = patched.node_by_id(child_id)
            if child is None:
                continue
            if node_geometry_locked(child):
                return _locked_result(
                    base_hash=base_hash,
                    command_type="ungroup_nodes",
                    node_id=child_id,
                    lock_kind="geometry",
                )
            before_gid = child.group_id
            child.group_id = None
            actions.append(
                build_patch_action(
                    scene,
                    base_scene_hash=base_hash,
                    command_id=command.command_id,
                    node_id=child_id,
                    action_type="set_group_id",
                    property_name="group_id",
                    before_value=before_gid,
                    after_value=None,
                    reason=command.reason or "leave group",
                )
            )
        actions.append(
            build_patch_action(
                scene,
                base_scene_hash=base_hash,
                command_id=command.command_id,
                node_id=command.group_id,
                action_type="remove_node",
                property_name="nodes",
                before_value=command.group_id,
                after_value=None,
                before_payload=target.model_dump(mode="json"),
                reason=command.reason or "remove group",
            )
        )
        patched.nodes = [node for node in patched.nodes if node.id != command.group_id]
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=tuple(actions),
        )

    def _validate_asset_binding(
        self,
        *,
        context: StudioExecutionContext,
        asset_id: UUID,
        storage_uri: str,
        asset_origin: str,
        expected_kind: str,
    ) -> QualityIssue | None:
        if not context.validate_asset_bindings:
            return None
        require_resolvable = (
            context.project_id is not None or context.asset_resolve_context is not None
        )
        try:
            self._asset_validator.validate(
                asset_id=asset_id,
                storage_uri=storage_uri,
                asset_origin=asset_origin,
                expected_kind=expected_kind,  # type: ignore[arg-type]
                project_id=context.project_id,
                require_resolvable=require_resolvable,
                resolve_context=context.asset_resolve_context,
            )
        except StudioAssetReferenceError as exc:
            return _issue(
                code=exc.code,
                message=str(exc),
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                evidence=[str(asset_id), storage_uri.strip()],
            )
        return None


def _clone_render_node(
    source: RenderNode,
    *,
    new_id: str,
    offset_x: float,
    offset_y: float,
    z_index: int,
    page_width: float,
    page_height: float,
) -> RenderNode:
    """Deep-clone a node with new identity, unlocked, offset within page bounds."""
    cloned = source.model_copy(deep=True)
    updates: dict[str, object] = {
        "id": new_id,
        "source_layout_element_id": new_id,
        "z_index": z_index,
        "locked": False,
        "lock_scopes": [],
        "visible": True,
    }
    width = max(float(source.width), 0.05)
    height = max(float(source.height), 0.05)
    max_x = max(page_width - width, 0.0)
    max_y = max(page_height - height, 0.0)
    updates["x"] = min(max(float(source.x) + offset_x, 0.0), max_x)
    updates["y"] = min(max(float(source.y) + offset_y, 0.0), max_y)
    cloned = cloned.model_copy(update=updates)
    if isinstance(cloned, FreeformNode):
        dx = float(cloned.x) - float(source.x)
        dy = float(cloned.y) - float(source.y)
        # model_copy kept source absolute points; shift to the new bbox origin.
        translate_freeform_points(cloned, dx=dx, dy=dy)
    return cloned


def _node_not_found(base_hash: str, node_id: str) -> CommandExecutionResult:
    return CommandExecutionResult(
        success=False,
        base_scene_hash=base_hash,
        issues=(
            _issue(
                code="STUDIO.NODE_NOT_FOUND",
                message=f"node `{node_id}` not found",
                evidence=[node_id],
            ),
        ),
    )


def _locked_result(
    *,
    base_hash: str,
    command_type: str,
    node_id: str,
    lock_kind: str,
) -> CommandExecutionResult:
    return CommandExecutionResult(
        success=False,
        base_scene_hash=base_hash,
        skipped_actions=(f"{command_type}:{node_id}:locked",),
        issues=(
            _issue(
                code="STUDIO.NODE_LOCKED",
                message=f"node `{node_id}` is locked for {lock_kind} edits",
                evidence=[node_id],
            ),
        ),
    )


def _validate_asset_origin(
    origin: str,
    *,
    forbidden: frozenset[str],
) -> QualityIssue | None:
    if origin in forbidden:
        return _issue(
            code="STUDIO.FORBIDDEN_ASSET_ORIGIN",
            message=f"asset origin `{origin}` is not allowed on project slides",
            severity=IssueSeverity.BLOCKER,
            category=IssueCategory.ARCHITECTURAL,
            evidence=[origin],
        )
    return None


def _upsert_asset_manifest(
    scene: RenderScene,
    *,
    asset_id: UUID,
    storage_uri: str,
    origin: str,
) -> None:
    uri = storage_uri.strip()
    for ref in scene.asset_manifest:
        if ref.asset_id == asset_id or ref.storage_uri == uri:
            ref.storage_uri = uri
            ref.asset_path = uri
            ref.origin = origin
            ref.asset_id = asset_id
            return
    scene.asset_manifest.append(
        SceneAssetReference(
            asset_id=asset_id,
            storage_uri=uri,
            asset_path=uri,
            origin=origin,
        )
    )


def _resolve_target_node_ids(command: FixOverflowCommand) -> set[str]:
    if command.node_ids:
        return set(command.node_ids)
    if command.target_node_ids:
        return set(command.target_node_ids)
    return set()


def _partition_locked_overflow(
    scene: RenderScene,
    findings: list[SlideSemanticFinding],
) -> tuple[list[SlideSemanticFinding], list[str]]:
    repairable: list[SlideSemanticFinding] = []
    skipped: list[str] = []
    for finding in findings:
        locked_nodes = [
            node_id
            for node_id in (finding.evidence_refs or [])
            if _is_locked_text_node(scene, node_id)
        ]
        if locked_nodes and len(locked_nodes) == len(finding.evidence_refs or []):
            for node_id in locked_nodes:
                skipped.append(f"fix_overflow:{node_id}:locked")
            continue
        repairable.append(finding)
    return repairable, skipped


def _is_locked_text_node(scene: RenderScene, node_id: str) -> bool:
    node = scene.node_by_id(node_id)
    if not isinstance(node, TextNode):
        return False
    return node_content_locked(node)


def _patch_from_repair_action(
    action: SceneRepairAction,
    *,
    base_scene: RenderScene,
    repaired_scene: RenderScene,
    base_scene_hash: str,
    command_id: UUID | None = None,
) -> ScenePatchAction:
    before_node = base_scene.node_by_id(action.node_id)
    after_node = repaired_scene.node_by_id(action.node_id)
    before_value: str | None = None
    after_value: str | None = None
    before_payload: dict[str, object] = {}
    after_payload: dict[str, object] = {}

    if action.action_type == "shorten_text":
        if isinstance(before_node, TextNode):
            before_value = before_node.text
        if isinstance(after_node, TextNode):
            after_value = after_node.text
    elif action.action_type == "set_overflow_shrink":
        if isinstance(before_node, TextNode):
            before_value = before_node.overflow_policy
        after_value = "shrink"
    elif action.action_type == "bump_font_size":
        if isinstance(before_node, TextNode):
            before_value = str(before_node.font_size)
        if isinstance(after_node, TextNode):
            after_value = str(after_node.font_size)
    elif action.action_type == "set_fit_mode_contain":
        if isinstance(before_node, (DrawingNode, ImageNode)):
            before_value = before_node.fit_mode
        after_value = "contain"
    else:
        after_value = action.reason

    return build_patch_action(
        repaired_scene,
        base_scene_hash=base_scene_hash,
        command_id=command_id,
        node_id=action.node_id,
        action_type=action.action_type,
        property_name=_property_for_repair_action(action.action_type),
        before_value=before_value,
        after_value=after_value,
        before_payload=before_payload,
        after_payload=after_payload,
        reason=action.reason,
    )


def _property_for_repair_action(action_type: str) -> str:
    if action_type == "shorten_text":
        return "text"
    if action_type == "set_overflow_shrink":
        return "overflow_policy"
    if action_type == "bump_font_size":
        return "font_size"
    if action_type == "set_fit_mode_contain":
        return "fit_mode"
    return ""


def _image_asset_payload(
    node: ImageNode,
    *,
    asset_id: UUID | None = None,
    storage_uri: str | None = None,
    asset_origin: str | None = None,
) -> dict[str, str]:
    resolved_id = asset_id if asset_id is not None else node.asset_id
    uri = (storage_uri if storage_uri is not None else node.storage_uri or node.asset_path).strip()
    origin = asset_origin if asset_origin is not None else node.asset_origin
    payload: dict[str, str] = {
        "storage_uri": uri,
        "asset_origin": origin,
    }
    if resolved_id is not None:
        payload["asset_id"] = str(resolved_id)
    return payload


def _drawing_asset_payload(
    node: DrawingNode,
    *,
    asset_id: UUID | None = None,
    storage_uri: str | None = None,
    drawing_type: str | None = None,
    fit_mode: str | None = None,
    preserve_aspect_ratio: bool | None = None,
    preserve_annotations: bool | None = None,
) -> dict[str, str | bool]:
    resolved_id = asset_id if asset_id is not None else node.asset_id
    uri = (storage_uri if storage_uri is not None else node.storage_uri or node.asset_path).strip()
    payload: dict[str, str | bool] = {
        "storage_uri": uri,
        "drawing_type": drawing_type if drawing_type is not None else node.drawing_type,
        "fit_mode": fit_mode if fit_mode is not None else node.fit_mode,
        "preserve_aspect_ratio": (
            preserve_aspect_ratio
            if preserve_aspect_ratio is not None
            else node.preserve_aspect_ratio
        ),
        "preserve_annotations": (
            preserve_annotations
            if preserve_annotations is not None
            else node.preserve_annotations
        ),
        "asset_origin": "project_upload",
    }
    if resolved_id is not None:
        payload["asset_id"] = str(resolved_id)
    return payload


def _issue(
    *,
    code: str,
    message: str,
    severity: IssueSeverity = IssueSeverity.MAJOR,
    category: IssueCategory = IssueCategory.DELIVERY_EDITABILITY,
    evidence: list[str] | None = None,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        category=category,
        message=message,
        evidence=evidence or [],
        source=QualityIssueSource.AUTO,
    )
