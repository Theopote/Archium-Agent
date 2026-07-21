"""Execute StudioCommand mutations against RenderScene (candidate scene output)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.application.visual.asset_binding_validator import AssetBindingValidator
from archium.application.visual.drawing_readability_service import increase_drawing_readability
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.application.visual.asset_path_resolver import AssetPathResolveContext
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
    DrawingNode,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    TextNode,
    compute_scene_hash,
    replace_text_node_content,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairAction
from archium.domain.visual.studio_command import (
    FixOverflowCommand,
    IncreaseDrawingReadabilityCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    RewriteTextCommand,
    ScenePatchAction,
    StudioCommand,
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

        repair_result = self._scene_repair.repair_scene(scene, repairable)
        applied = [
            _patch_from_repair_action(action, scene, base_hash)
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
    scene: RenderScene,
    base_scene_hash: str,
) -> ScenePatchAction:
    return build_patch_action(
        scene,
        base_scene_hash=base_scene_hash,
        node_id=action.node_id,
        action_type=action.action_type,
        property_name=_property_for_repair_action(action.action_type),
        after_value=action.reason,
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
