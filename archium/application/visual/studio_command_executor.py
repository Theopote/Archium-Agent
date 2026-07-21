"""Execute StudioCommand mutations against RenderScene (candidate scene output)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.render_scene import RenderScene, TextNode, compute_scene_hash
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairAction
from archium.domain.visual.studio_command import (
    FixOverflowCommand,
    RewriteTextCommand,
    ScenePatchAction,
    StudioCommand,
)


@dataclass(frozen=True)
class StudioExecutionContext:
    """Runtime context for command execution."""

    presentation_id: UUID
    slide_order: int = 0


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


def node_content_locked(node: TextNode) -> bool:
    """Return True when text content on a render node must not be mutated."""
    if node.locked:
        return True
    return bool(_CONTENT_LOCK_SCOPES & set(node.lock_scopes))


class StudioCommandExecutor:
    """Apply structured Studio commands and return candidate scenes."""

    def __init__(self, *, scene_repair: SceneRepairService | None = None) -> None:
        self._scene_repair = scene_repair or SceneRepairService()

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
        target.text = command.new_text
        if target.paragraphs:
            target.paragraphs[0].text = command.new_text

        action = ScenePatchAction(
            scene_id=scene.slide_id,
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
            _patch_from_repair_action(action, scene.slide_id)
            for action in repair_result.actions
        ]
        return CommandExecutionResult(
            success=bool(applied) or not repairable,
            base_scene_hash=base_hash,
            candidate_scene=repair_result.scene,
            applied_actions=tuple(applied),
            skipped_actions=tuple(skipped),
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


def _patch_from_repair_action(action: SceneRepairAction, scene_id: UUID) -> ScenePatchAction:
    return ScenePatchAction(
        scene_id=scene_id,
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


def _issue(
    *,
    code: str,
    message: str,
    severity: IssueSeverity = IssueSeverity.MAJOR,
    evidence: list[str] | None = None,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        category=IssueCategory.DELIVERY_EDITABILITY,
        message=message,
        evidence=evidence or [],
        source=QualityIssueSource.AUTO,
    )
