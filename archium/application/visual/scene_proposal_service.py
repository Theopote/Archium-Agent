"""Create, review, and apply SceneChangeProposal workflows."""

from __future__ import annotations

import contextlib
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import save_render_scene
from archium.application.visual.asset_binding_validator import AssetBindingValidator
from archium.application.visual.drawing_readability_service import parse_geometry_token
from archium.application.visual.partial_edit_preservation import (
    assert_partial_edit_preservation,
)
from archium.application.visual.scene_deterministic_qa_service import (
    ProposalSceneQAResult,
    run_proposal_scene_qa,
)
from archium.application.visual.scene_geometry import apply_geometry_token
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_proposal_qa import (
    compare_proposal_qa,
    proposal_introduces_blocker,
)
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
    _upsert_asset_manifest,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain._base import utc_now
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue
from archium.domain.visual.partial_edit_preservation import PARTIAL_EDIT_INTERACTION_RULE
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
    compute_scene_hash,
    replace_text_node_content,
)
from archium.domain.visual.scene_change_proposal import (
    CommandProposalResult,
    ProposalAcceptResult,
    ProposalDecision,
    ProposalQAComparison,
    ProposalStatus,
    SceneChangeProposal,
)
from archium.domain.visual.studio_command import ScenePatchAction, StudioCommand
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    RenderSceneRepository,
    SceneProposalRepository,
)


class SceneProposalService:
    """Build candidate scene proposals and persist accepted revisions."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        executor: StudioCommandExecutor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._executor = executor or StudioCommandExecutor(
            asset_validator=AssetBindingValidator(session, settings=self._settings),
        )
        self._scenes = RenderSceneRepository(session)
        self._proposals = SceneProposalRepository(session)
        self._presentations = PresentationRepository(session)
        self._scene_history = SceneHistoryService(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)

    def create_proposal(
        self,
        *,
        base_scene: RenderScene,
        commands: list[StudioCommand],
        presentation_id: UUID,
        slide_id: UUID,
        slide_order: int = 0,
        base_revision_id: UUID | None = None,
        reasons: list[str] | None = None,
    ) -> SceneChangeProposal:
        if not commands:
            raise WorkflowError("至少需要一个 Studio 命令才能生成修改提案。")

        context = StudioExecutionContext(
            presentation_id=presentation_id,
            slide_order=slide_order,
            project_id=self._project_id_for_presentation(presentation_id),
        )
        candidate = base_scene.model_copy(deep=True)
        applied_actions: list[ScenePatchAction] = []
        command_results: list[CommandProposalResult] = []
        successful_commands: list[StudioCommand] = []
        failed_commands: list[StudioCommand] = []

        for command in commands:
            result = self._executor.execute(candidate, command, context)
            stamped_actions: list[ScenePatchAction] = []
            for action in result.applied_actions:
                stamped = action
                if action.command_id is None:
                    stamped = action.model_copy(update={"command_id": command.command_id})
                stamped_actions.append(stamped)

            if not result.success or result.candidate_scene is None:
                command_results.append(
                    CommandProposalResult(
                        command_id=command.command_id,
                        status="failed",
                        issues=list(result.issues),
                    )
                )
                failed_commands.append(command)
                continue

            candidate = result.candidate_scene
            applied_actions.extend(stamped_actions)

            if stamped_actions:
                command_results.append(
                    CommandProposalResult(
                        command_id=command.command_id,
                        status="applied",
                        action_ids=[action.action_id for action in stamped_actions],
                        issues=list(result.issues),
                    )
                )
                successful_commands.append(command)
            else:
                command_results.append(
                    CommandProposalResult(
                        command_id=command.command_id,
                        status="skipped",
                        issues=list(result.issues),
                    )
                )

        if failed_commands and not applied_actions:
            failure_messages = [
                issue.message
                for entry in command_results
                if entry.status == "failed"
                for issue in entry.issues
            ]
            raise WorkflowError(
                "；".join(failure_messages) or "所有 Studio 命令均未能应用到 Scene。"
            )

        preservation = assert_partial_edit_preservation(
            base_scene,
            candidate,
            commands=successful_commands or commands,
            patch_actions=applied_actions,
        )

        qa_before_result = self._qa_for_scene(
            base_scene,
            presentation_id,
            slide_order,
        )
        qa_after_result = self._qa_for_scene(
            candidate,
            presentation_id,
            slide_order,
        )
        proposal_reasons = list(reasons or [])
        if PARTIAL_EDIT_INTERACTION_RULE not in proposal_reasons:
            proposal_reasons.insert(0, PARTIAL_EDIT_INTERACTION_RULE)
        proposal_reasons.extend(preservation.captions())
        proposal_reasons.extend(action.reason for action in applied_actions if action.reason)
        status = (
            ProposalStatus.READY_WITH_WARNINGS
            if failed_commands
            else ProposalStatus.READY
        )

        return SceneChangeProposal(
            presentation_id=presentation_id,
            slide_id=slide_id,
            base_revision_id=base_revision_id,
            base_scene_hash=compute_scene_hash(base_scene),
            base_scene=base_scene,
            proposed_scene=candidate,
            commands=list(successful_commands),
            requested_commands=list(commands),
            successful_commands=list(successful_commands),
            failed_commands=list(failed_commands),
            command_results=command_results,
            patch_actions=applied_actions,
            reasons=_dedupe_strings(proposal_reasons),
            qa_before=list(qa_before_result.issues),
            qa_after=list(qa_after_result.issues),
            qa_before_by_layer={
                layer: list(items) for layer, items in qa_before_result.layers.items()
            },
            qa_after_by_layer={
                layer: list(items) for layer, items in qa_after_result.layers.items()
            },
            preservation=preservation,
            status=status,
        )

    def save_proposal(self, proposal: SceneChangeProposal) -> SceneChangeProposal:
        """Persist proposal metadata and scene snapshot references."""
        return self._proposals.save(proposal)

    def load_proposal(self, proposal_id: UUID) -> SceneChangeProposal | None:
        return self._proposals.get(proposal_id)

    def load_active_proposal(self, slide_id: UUID) -> SceneChangeProposal | None:
        return self._proposals.get_active_for_slide(slide_id)

    def qa_comparison(self, proposal: SceneChangeProposal) -> ProposalQAComparison:
        return compare_proposal_qa(proposal.qa_before, proposal.qa_after)

    def is_stale(self, proposal: SceneChangeProposal, current_scene: RenderScene) -> bool:
        return compute_scene_hash(current_scene) != proposal.base_scene_hash

    def reject_proposal(
        self,
        proposal: SceneChangeProposal,
        *,
        notes: str = "",
    ) -> SceneChangeProposal:
        rejected = proposal.model_copy(
            update={
                "status": ProposalStatus.REJECTED,
                "decided_at": utc_now(),
                "decision": ProposalDecision(
                    proposal_id=proposal.proposal_id,
                    rejected_action_ids=[
                        action.action_id for action in proposal.patch_actions
                    ],
                    notes=notes,
                ),
            }
        )
        saved = self._proposals.save(rejected, supersede_previous=False)
        self._sync_element_comments(saved)
        return saved

    def mark_proposal_superseded(self, proposal: SceneChangeProposal) -> SceneChangeProposal:
        superseded = proposal.model_copy(
            update={
                "status": ProposalStatus.SUPERSEDED,
                "decided_at": utc_now(),
            }
        )
        return self._proposals.save(superseded, supersede_previous=False)

    def accept_proposal(
        self,
        proposal: SceneChangeProposal,
        slide: SlideSpec,
        decision: ProposalDecision | None = None,
        *,
        current_scene: RenderScene | None = None,
    ) -> ProposalAcceptResult:
        if proposal.status in {ProposalStatus.ACCEPTED, ProposalStatus.PARTIALLY_ACCEPTED}:
            raise WorkflowError("该提案已被接受。")
        if proposal.status == ProposalStatus.REJECTED:
            raise WorkflowError("已拒绝的提案不能再次接受。")
        if proposal.status == ProposalStatus.SUPERSEDED:
            raise WorkflowError("该提案已过期，请重新生成提案。")

        live_scene = current_scene
        if live_scene is None and slide.layout_plan_id is not None:
            live_scene = self._scenes.get_by_layout_plan(slide.layout_plan_id)
        if live_scene is not None and self.is_stale(proposal, live_scene):
            self.mark_proposal_superseded(proposal)
            raise WorkflowError(
                "页面在提案生成后已被修改，请基于最新版本重新生成提案。"
            )

        accepted_scene = self._resolve_accepted_scene(
            proposal,
            decision,
            slide_order=slide.order,
        )
        accepted_commands = resolve_accepted_commands(proposal, decision)
        accepted_action_ids = (
            set(decision.accepted_action_ids)
            if decision is not None and decision.accepted_action_ids
            else {action.action_id for action in proposal.patch_actions}
        )
        accepted_actions = [
            action
            for action in proposal.patch_actions
            if action.action_id in accepted_action_ids
        ]
        # Re-assert preservation on the scene that will be committed.
        assert_partial_edit_preservation(
            proposal.base_scene,
            accepted_scene,
            commands=accepted_commands,
            patch_actions=accepted_actions,
            slide_before=slide,
            slide_after=slide,
        )
        accepted_qa = self._qa_for_scene(
            accepted_scene,
            proposal.presentation_id,
            slide.order,
        )
        comparison = compare_proposal_qa(proposal.qa_before, list(accepted_qa.issues))
        if proposal_introduces_blocker(comparison):
            raise WorkflowError("不能接受会引入新的 Blocker 级质量问题的修改。")
        if not accepted_qa.preview_render_success:
            raise WorkflowError("不能接受预览渲染失败的 Scene 修改。")

        saved = self._persist_scene(slide, accepted_scene)
        parent_revision_id = proposal.base_revision_id
        _, scene_revision = self._scene_history.record_scene(
            slide=slide,
            scene=saved,
            change_source=RevisionSource.AI_PROPOSAL,
            scene_revision_source="ai_proposal",
            commands=accepted_commands,
            parent_revision_id=parent_revision_id,
            note=decision.notes if decision is not None else None,
            summary=self._proposal_accept_summary(proposal, accepted_commands),
            qa_status=self._proposal_qa_status(accepted_qa),
        )
        self._studio_scene.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=saved.layout_plan_id,
        )
        updated_proposal = self._record_proposal_decision(proposal, decision)
        self._sync_element_comments(updated_proposal)
        return ProposalAcceptResult(revision=scene_revision, proposal=updated_proposal)

    def _record_proposal_decision(
        self,
        proposal: SceneChangeProposal,
        decision: ProposalDecision | None,
    ) -> SceneChangeProposal:
        if decision is None or len(decision.accepted_action_ids) == len(proposal.patch_actions):
            final_status = ProposalStatus.ACCEPTED
        else:
            final_status = ProposalStatus.PARTIALLY_ACCEPTED
        resolved_decision = decision
        if resolved_decision is None:
            resolved_decision = ProposalDecision(
                proposal_id=proposal.proposal_id,
                accepted_action_ids=[action.action_id for action in proposal.patch_actions],
            )
        else:
            accepted_ids = set(resolved_decision.accepted_action_ids)
            if not resolved_decision.rejected_action_ids:
                resolved_decision = resolved_decision.model_copy(
                    update={
                        "rejected_action_ids": [
                            action.action_id
                            for action in proposal.patch_actions
                            if action.action_id not in accepted_ids
                        ],
                    }
                )
        updated = proposal.model_copy(
            update={
                "status": final_status,
                "decision": resolved_decision,
                "decided_at": utc_now(),
            }
        )
        return self._proposals.save(updated, supersede_previous=False)

    def _sync_element_comments(self, proposal: SceneChangeProposal) -> None:
        session = getattr(self, "_session", None)
        if session is None:
            return
        from archium.application.visual.element_comment_service import ElementCommentService

        ElementCommentService(
            session,
            settings=getattr(self, "_settings", None) or get_settings(),
        ).sync_from_proposal_decision(proposal)

    def _resolve_accepted_scene(
        self,
        proposal: SceneChangeProposal,
        decision: ProposalDecision | None,
        *,
        slide_order: int = 0,
    ) -> RenderScene:
        if decision is None or not decision.accepted_action_ids:
            return proposal.proposed_scene.model_copy(deep=True)

        accepted_ids = set(decision.accepted_action_ids)
        selected = [
            action for action in proposal.patch_actions if action.action_id in accepted_ids
        ]
        if not selected:
            raise WorkflowError("请至少选择一项要接受的修改。")
        if len(selected) == len(proposal.patch_actions):
            return proposal.proposed_scene.model_copy(deep=True)

        actions_by_command: dict[UUID, list[ScenePatchAction]] = {}
        orphan_actions: list[ScenePatchAction] = []
        for action in proposal.patch_actions:
            if action.command_id is not None:
                actions_by_command.setdefault(action.command_id, []).append(action)
            else:
                orphan_actions.append(action)

        scene = proposal.base_scene.model_copy(deep=True)
        context = StudioExecutionContext(
            presentation_id=proposal.presentation_id,
            slide_order=slide_order,
            project_id=self._project_id_for_presentation(proposal.presentation_id),
        )
        fallback_actions: list[ScenePatchAction] = []

        for command in proposal.commands:
            command_actions = actions_by_command.get(command.command_id, [])
            if not command_actions:
                continue
            selected_command_actions = [
                action for action in command_actions if action.action_id in accepted_ids
            ]
            if not selected_command_actions:
                continue
            if len(selected_command_actions) == len(command_actions):
                result = self._executor.execute(scene, command, context)
                if not result.success or result.candidate_scene is None:
                    message = (
                        result.issues[0].message
                        if result.issues
                        else f"{command.command_type} failed during partial accept"
                    )
                    raise WorkflowError(message)
                scene = result.candidate_scene
            else:
                fallback_actions.extend(selected_command_actions)

        orphan_selected = [action for action in orphan_actions if action.action_id in accepted_ids]
        fallback_actions.extend(orphan_selected)

        if fallback_actions:
            scene = apply_patch_actions(scene, fallback_actions)

        return scene

    def _persist_scene(self, slide: SlideSpec, scene: RenderScene) -> RenderScene:
        existing = self._scenes.get_by_layout_plan(scene.layout_plan_id)
        payload = scene.model_copy(deep=True)
        if existing is not None:
            payload = payload.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
        return save_render_scene(self._scenes, payload)

    def _project_id_for_presentation(self, presentation_id: UUID) -> UUID | None:
        if self._presentations is None:
            return None
        presentation = self._presentations.get_presentation(presentation_id)
        return presentation.project_id if presentation is not None else None

    def _qa_for_scene(
        self,
        scene: RenderScene,
        presentation_id: UUID,
        slide_order: int,
    ) -> ProposalSceneQAResult:
        return run_proposal_scene_qa(
            presentation_id,
            scene,
            slide_order=slide_order,
            studio_scene=self._studio_scene,
        )

    @staticmethod
    def _proposal_accept_summary(
        proposal: SceneChangeProposal,
        accepted_commands: list,
    ) -> str:
        if proposal.reasons:
            return "AI 提案：" + "；".join(proposal.reasons[:2])
        if accepted_commands:
            first = accepted_commands[0]
            intent = getattr(first, "intent", None) or getattr(first, "command_type", None)
            if intent:
                return f"AI 提案：{intent}"
            return f"AI 提案：{len(accepted_commands)} 条命令"
        return "AI 提案：已接受"

    @staticmethod
    def _proposal_qa_status(accepted_qa: ProposalSceneQAResult) -> str:
        blockers = sum(
            1
            for issue in accepted_qa.issues
            if getattr(issue, "severity", None) is not None
            and str(getattr(issue.severity, "value", issue.severity))
            in {"blocker", "major", "BLOCKER", "MAJOR"}
        )
        if blockers:
            return "pass_with_warnings"
        if accepted_qa.issues:
            return "pass_with_warnings"
        return "passed"


def apply_patch_actions(
    base_scene: RenderScene,
    actions: list[ScenePatchAction],
) -> RenderScene:
    """Replay selected patch actions on the base scene for partial accept."""
    scene = base_scene.model_copy(deep=True)
    for action in actions:
        _apply_patch_action(scene, action)
    return scene


def resolve_accepted_commands(
    proposal: SceneChangeProposal,
    decision: ProposalDecision | None,
) -> list[StudioCommand]:
    """Return only the commands whose patch actions were fully accepted."""
    effective_commands = (
        proposal.successful_commands
        if proposal.successful_commands
        else proposal.commands
    )
    if decision is None or not decision.accepted_action_ids:
        return list(effective_commands)

    accepted_action_ids = set(decision.accepted_action_ids)
    selected_actions = [
        action for action in proposal.patch_actions if action.action_id in accepted_action_ids
    ]
    if len(selected_actions) == len(proposal.patch_actions):
        return list(effective_commands)

    actions_by_command: dict[UUID, list[ScenePatchAction]] = {}
    for action in proposal.patch_actions:
        if action.command_id is not None:
            actions_by_command.setdefault(action.command_id, []).append(action)

    accepted_command_ids: set[UUID] = set()
    for command in effective_commands:
        command_actions = actions_by_command.get(command.command_id, [])
        if not command_actions:
            continue
        selected_command_actions = [
            action for action in command_actions if action.action_id in accepted_action_ids
        ]
        if (
            selected_command_actions
            and len(selected_command_actions) == len(command_actions)
        ):
            accepted_command_ids.add(command.command_id)

    return [
        command
        for command in effective_commands
        if command.command_id in accepted_command_ids
    ]


def _apply_patch_action(scene: RenderScene, action: ScenePatchAction) -> None:
    node = scene.node_by_id(action.node_id)
    if node is None:
        return
    if action.action_type == "rewrite_text" and isinstance(node, TextNode):
        if action.after_value is not None:
            replace_text_node_content(node, action.after_value)
        return
    if action.action_type in {"replace_asset", "replace_drawing"} and isinstance(
        node, (ImageNode, DrawingNode)
    ):
        if action.after_payload:
            _apply_asset_patch(scene, node, action)
        else:
            if action.after_value is not None:
                node.storage_uri = action.after_value
                node.asset_path = action.after_value
            if action.after_asset_id is not None:
                node.asset_id = action.after_asset_id
            node.asset_unresolved = False
            if isinstance(node, DrawingNode):
                node.fit_mode = "contain"
        return
    if action.action_type == "enlarge_drawing" and isinstance(node, DrawingNode):
        if action.after_value:
            x, y, width, height = parse_geometry_token(action.after_value)
            node.x = x
            node.y = y
            node.width = width
            node.height = height
            node.fit_mode = "contain"
        return
    if action.action_type in {"move_node", "resize_node", "align_nodes"}:
        if action.after_value:
            apply_geometry_token(node, action.after_value)
        return
    if action.action_type == "delete_node":
        node.visible = action.after_value != "false"
        return
    if action.action_type == "set_node_visibility":
        if action.after_payload:
            node.visible = bool(action.after_payload.get("visible", node.visible))
        elif action.after_value is not None:
            node.visible = action.after_value != "false"
        return
    if action.action_type == "set_node_lock":
        if action.after_payload:
            node.locked = bool(action.after_payload.get("locked", node.locked))
            scopes = action.after_payload.get("lock_scopes", node.lock_scopes)
            if isinstance(scopes, list):
                node.lock_scopes = [str(item) for item in scopes]
        return
    if action.action_type == "reorder_node":
        with contextlib.suppress(TypeError, ValueError):
            node.z_index = int(action.after_value or node.z_index)
        return
    if action.action_type == "relocate_node":
        if action.after_value is not None:
            node.y = float(action.after_value)
        return
    if action.action_type == "shorten_text" and isinstance(node, TextNode):
        if action.after_value is not None:
            replace_text_node_content(node, action.after_value)
        return
    if action.action_type == "set_overflow_shrink" and isinstance(node, TextNode):
        node.overflow_policy = "shrink"
        return
    if action.action_type == "set_fit_mode_contain" and isinstance(
        node, (DrawingNode, ImageNode)
    ):
        node.fit_mode = "contain"
        return
    if action.action_type == "bump_font_size" and isinstance(node, TextNode):
        with contextlib.suppress(TypeError, ValueError):
            node.font_size = max(node.font_size, float(action.after_value or node.font_size))


def _apply_asset_patch(
    scene: RenderScene,
    node: ImageNode | DrawingNode,
    action: ScenePatchAction,
) -> None:
    payload = action.after_payload
    uri = str(payload.get("storage_uri") or action.after_value or "").strip()
    asset_id_raw = payload.get("asset_id") or action.after_asset_id
    asset_id = UUID(str(asset_id_raw)) if asset_id_raw else node.asset_id
    if uri:
        node.storage_uri = uri
        node.asset_path = uri
    if asset_id is not None:
        node.asset_id = asset_id
    node.asset_unresolved = False

    if isinstance(node, ImageNode):
        origin = payload.get("asset_origin")
        if isinstance(origin, str) and origin:
            node.asset_origin = origin  # type: ignore[assignment]
        if asset_id is not None and uri:
            _upsert_asset_manifest(
                scene,
                asset_id=asset_id,
                storage_uri=uri,
                origin=str(origin or node.asset_origin),
            )
        return

    drawing_type = payload.get("drawing_type")
    if isinstance(drawing_type, str) and drawing_type:
        node.drawing_type = drawing_type  # type: ignore[assignment]
    fit_mode = payload.get("fit_mode")
    if isinstance(fit_mode, str) and fit_mode:
        node.fit_mode = fit_mode  # type: ignore[assignment]
    if "preserve_aspect_ratio" in payload:
        node.preserve_aspect_ratio = bool(payload["preserve_aspect_ratio"])
    if "preserve_annotations" in payload:
        node.preserve_annotations = bool(payload["preserve_annotations"])
    origin = str(payload.get("asset_origin") or "project_upload")
    if asset_id is not None and uri:
        _upsert_asset_manifest(
            scene,
            asset_id=asset_id,
            storage_uri=uri,
            origin=origin,
        )


def summarize_patch_action(action: ScenePatchAction) -> str:
    """Human-readable summary for proposal compare UI."""
    if action.action_type == "rewrite_text":
        return f"改写文本 `{action.node_id}`"
    if action.action_type == "replace_asset":
        return f"替换图片 `{action.node_id}`"
    if action.action_type == "replace_drawing":
        return f"替换图纸 `{action.node_id}`"
    if action.action_type == "enlarge_drawing":
        return f"扩大图纸 `{action.node_id}`"
    if action.action_type == "relocate_node":
        return f"移动节点 `{action.node_id}`"
    if action.action_type == "shorten_text":
        return f"缩短文本 `{action.node_id}`"
    if action.action_type == "set_overflow_shrink":
        return f"文本 `{action.node_id}` 改为自动缩小"
    return action.reason or action.action_type


def summarize_command_type(command: StudioCommand) -> str:
    """Human-readable label for a Studio command."""
    labels = {
        "rewrite_text": "改写文本",
        "fix_overflow": "修复溢出",
        "replace_asset": "替换图片",
        "replace_drawing": "替换图纸",
        "increase_drawing_readability": "提高图纸可读性",
        "set_node_lock": "锁定设置",
        "set_node_visibility": "显示设置",
        "reorder_node": "图层顺序",
    }
    return labels.get(command.command_type, command.command_type)


def summarize_command_result(
    proposal: SceneChangeProposal,
    result: CommandProposalResult,
) -> str:
    """Human-readable summary for a per-command proposal outcome."""
    command = next(
        (
            item
            for item in proposal.requested_commands
            if item.command_id == result.command_id
        ),
        None,
    )
    label = summarize_command_type(command) if command is not None else result.command_id.hex[:8]
    if result.status == "applied":
        return f"{label}：已应用（{len(result.action_ids)} 项改动）"
    if result.status == "skipped":
        return f"{label}：已跳过（Scene 无需变更）"
    issue = result.issues[0].message if result.issues else "命令执行失败"
    return f"{label}：失败 — {issue}"


def count_issues_by_severity(issues: list[QualityIssue], severity: IssueSeverity) -> int:
    return sum(1 for issue in issues if issue.severity == severity)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
