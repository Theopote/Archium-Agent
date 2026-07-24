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
    ChartNode,
    DrawingNode,
    ImageNode,
    RenderNode,
    RenderScene,
    SceneAssetReference,
    ShapeNode,
    TableNode,
    TextNode,
    compute_scene_hash,
    replace_text_node_content,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairAction, SceneRepairApplyMode
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    DeleteNodeCommand,
    DuplicateNodesCommand,
    FixOverflowCommand,
    IncreaseDrawingReadabilityCommand,
    MoveNodeCommand,
    MoveNodesCommand,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
    ScenePatchAction,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    StudioCommand,
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
        target.x = command.x
        target.y = command.y
        action = build_patch_action(
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
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
        )

    def _execute_move_nodes(
        self,
        scene: RenderScene,
        command: MoveNodesCommand,
        base_hash: str,
    ) -> CommandExecutionResult:
        patched = scene.model_copy(deep=True)
        actions: list[ScenePatchAction] = []
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
            node.x = move.x
            node.y = move.y
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
        target.x = command.x
        target.y = command.y
        target.width = width
        target.height = height
        action = build_patch_action(
            scene,
            base_scene_hash=base_hash,
            command_id=command.command_id,
            node_id=command.node_id,
            action_type="resize_node",
            property_name="geometry",
            before_value=before_token,
            after_value=geometry_token(target),
            reason=command.reason or "resize node",
        )
        return CommandExecutionResult(
            success=True,
            base_scene_hash=base_hash,
            candidate_scene=patched,
            applied_actions=(action,),
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
            if command.font_size is not None:
                before["font_size"] = target.font_size
                target.font_size = command.font_size
                after["font_size"] = target.font_size
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
    return cloned.model_copy(update=updates)


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
