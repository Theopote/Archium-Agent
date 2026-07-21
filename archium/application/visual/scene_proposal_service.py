"""Create, review, and apply SceneChangeProposal workflows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_proposal_qa import (
    compare_proposal_qa,
    findings_to_quality_issues,
    proposal_introduces_blocker,
)
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
    compute_scene_hash,
)
from archium.domain.visual.scene_change_proposal import (
    ProposalDecision,
    ProposalQAComparison,
    ProposalStatus,
    SceneChangeProposal,
    SceneRevision,
)
from archium.domain.visual.studio_command import ScenePatchAction, StudioCommand
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import RenderSceneRepository


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
        self._executor = executor or StudioCommandExecutor()
        self._scenes = RenderSceneRepository(session)
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
        )
        qa_before = self._qa_for_scene(base_scene, presentation_id, slide_order)
        candidate = base_scene.model_copy(deep=True)
        applied_actions: list[ScenePatchAction] = []
        issues: list[str] = []

        for command in commands:
            result = self._executor.execute(candidate, command, context)
            if not result.success or result.candidate_scene is None:
                issues.append(
                    result.issues[0].message if result.issues else f"{command.command_type} failed"
                )
                continue
            candidate = result.candidate_scene
            applied_actions.extend(result.applied_actions)

        if issues and not applied_actions:
            raise WorkflowError("；".join(issues))

        qa_after = self._qa_for_scene(candidate, presentation_id, slide_order)
        proposal_reasons = list(reasons or [])
        proposal_reasons.extend(action.reason for action in applied_actions if action.reason)

        return SceneChangeProposal(
            presentation_id=presentation_id,
            slide_id=slide_id,
            base_revision_id=base_revision_id,
            base_scene_hash=compute_scene_hash(base_scene),
            base_scene=base_scene,
            proposed_scene=candidate,
            commands=commands,
            patch_actions=applied_actions,
            reasons=_dedupe_strings(proposal_reasons),
            qa_before=qa_before,
            qa_after=qa_after,
            status=ProposalStatus.READY,
        )

    def qa_comparison(self, proposal: SceneChangeProposal) -> ProposalQAComparison:
        return compare_proposal_qa(proposal.qa_before, proposal.qa_after)

    def is_stale(self, proposal: SceneChangeProposal, current_scene: RenderScene) -> bool:
        return compute_scene_hash(current_scene) != proposal.base_scene_hash

    def reject_proposal(self, proposal: SceneChangeProposal) -> SceneChangeProposal:
        return proposal.model_copy(update={"status": ProposalStatus.REJECTED})

    def accept_proposal(
        self,
        proposal: SceneChangeProposal,
        slide: SlideSpec,
        decision: ProposalDecision | None = None,
        *,
        current_scene: RenderScene | None = None,
    ) -> SceneRevision:
        if proposal.status in {ProposalStatus.ACCEPTED, ProposalStatus.PARTIALLY_ACCEPTED}:
            raise WorkflowError("该提案已被接受。")
        if proposal.status == ProposalStatus.REJECTED:
            raise WorkflowError("已拒绝的提案不能再次接受。")

        live_scene = current_scene
        if live_scene is None and slide.layout_plan_id is not None:
            live_scene = self._scenes.get_by_layout_plan(slide.layout_plan_id)
        if live_scene is not None and self.is_stale(proposal, live_scene):
            raise WorkflowError(
                "页面在提案生成后已被修改，请基于最新版本重新生成提案。"
            )

        accepted_scene = self._resolve_accepted_scene(proposal, decision)
        comparison = compare_proposal_qa(proposal.qa_before, self._qa_issues_for_scene(
            accepted_scene,
            proposal.presentation_id,
            slide.order,
        ))
        if proposal_introduces_blocker(comparison):
            raise WorkflowError("不能接受会引入新的 Blocker 级质量问题的修改。")

        saved = self._persist_scene(slide, accepted_scene)
        parent_revision_id = proposal.base_revision_id
        _, scene_revision = self._scene_history.record_scene(
            slide=slide,
            scene=saved,
            change_source=RevisionSource.AI_PROPOSAL,
            scene_revision_source="ai_proposal",
            commands=proposal.commands,
            parent_revision_id=parent_revision_id,
            note=decision.notes if decision is not None else None,
        )
        self._studio_scene.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=saved.layout_plan_id,
        )
        return scene_revision

    def _resolve_accepted_scene(
        self,
        proposal: SceneChangeProposal,
        decision: ProposalDecision | None,
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
        return apply_patch_actions(proposal.base_scene, selected)

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
        return self._scenes.save(payload)

    def _qa_for_scene(
        self,
        scene: RenderScene,
        presentation_id: UUID,
        slide_order: int,
    ) -> list:
        return self._qa_issues_for_scene(scene, presentation_id, slide_order)

    def _qa_issues_for_scene(
        self,
        scene: RenderScene,
        presentation_id: UUID,
        slide_order: int,
    ):
        report = run_scene_semantic_qa(
            presentation_id,
            [scene],
            slide_orders={scene.slide_id: slide_order},
        )
        slide_findings = [
            finding for finding in report.findings if finding.slide_id == scene.slide_id
        ]
        return findings_to_quality_issues(slide_findings)


def apply_patch_actions(
    base_scene: RenderScene,
    actions: list[ScenePatchAction],
) -> RenderScene:
    """Replay selected patch actions on the base scene for partial accept."""
    scene = base_scene.model_copy(deep=True)
    for action in actions:
        _apply_patch_action(scene, action)
    return scene


def _apply_patch_action(scene: RenderScene, action: ScenePatchAction) -> None:
    node = scene.node_by_id(action.node_id)
    if node is None:
        return
    if action.action_type == "rewrite_text" and isinstance(node, TextNode):
        if action.after_value is not None:
            node.text = action.after_value
            if node.paragraphs:
                node.paragraphs[0].text = action.after_value
        return
    if action.action_type in {"replace_asset", "replace_drawing"} and isinstance(
        node, (ImageNode, DrawingNode)
    ):
        if action.after_value is not None:
            node.storage_uri = action.after_value
            node.asset_path = action.after_value
        if action.after_asset_id is not None:
            node.asset_id = action.after_asset_id
        node.asset_unresolved = False
        if isinstance(node, DrawingNode):
            node.fit_mode = "contain"
        return
    if action.action_type == "shorten_text" and isinstance(node, TextNode):
        if action.after_value is not None:
            node.text = action.after_value
            if node.paragraphs:
                node.paragraphs[0].text = action.after_value
        return
    if action.action_type == "set_overflow_shrink" and isinstance(node, TextNode):
        node.overflow_policy = "shrink"
        return
    if action.action_type == "bump_font_size" and isinstance(node, TextNode):
        try:
            node.font_size = max(node.font_size, float(action.after_value or node.font_size))
        except (TypeError, ValueError):
            pass


def summarize_patch_action(action: ScenePatchAction) -> str:
    """Human-readable summary for proposal compare UI."""
    if action.action_type == "rewrite_text":
        return f"改写文本 `{action.node_id}`"
    if action.action_type == "replace_asset":
        return f"替换图片 `{action.node_id}`"
    if action.action_type == "replace_drawing":
        return f"替换图纸 `{action.node_id}`"
    if action.action_type == "shorten_text":
        return f"缩短文本 `{action.node_id}`"
    if action.action_type == "set_overflow_shrink":
        return f"文本 `{action.node_id}` 改为自动缩小"
    return action.reason or action.action_type


def count_issues_by_severity(issues: list, severity) -> int:
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
