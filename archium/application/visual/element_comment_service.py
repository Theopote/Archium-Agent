"""Create element-bound comments and drive them through SceneChangeProposal."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.comment_to_command_planner import CommentToCommandPlanner
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_proposal_service import SceneProposalService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.element_comment import ElementComment, ElementCommentStatus
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import ElementCommentRepository


class ElementCommentService:
    """Element comment CRUD + Comment → Command → Proposal workflow."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._comments = ElementCommentRepository(session)
        self._presentations = PresentationRepository(session)
        self._proposals = SceneProposalService(session, settings=self._settings)
        self._scene_history = SceneHistoryService(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)
        self._planner = CommentToCommandPlanner(
            settings=self._settings,
            use_llm=use_llm,
        )

    def create_comment(
        self,
        *,
        slide_id: UUID,
        node_id: str,
        note: str,
        layout_element_id: str | None = None,
        created_by: str = "user",
        presentation_id: UUID | None = None,
    ) -> ElementComment:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError("未找到当前页面。")

        scene = self._require_scene(slide_id)
        node = scene.node_by_id(node_id)
        if node is None:
            raise WorkflowError(f"绑定节点不存在：`{node_id}`")

        cleaned = note.strip()
        if not cleaned:
            raise WorkflowError("请输入修改描述。")

        scene_revision_id = self._scene_history.latest_scene_revision_id(slide)
        scene_hash = compute_scene_hash(scene)
        node_snapshot = node.model_dump(mode="json")

        comment = ElementComment(
            presentation_id=presentation_id or slide.presentation_id,
            slide_id=slide.id,
            node_id=node_id,
            layout_element_id=layout_element_id,
            note=cleaned,
            status=ElementCommentStatus.PENDING,
            scene_revision_id=scene_revision_id,
            scene_hash=scene_hash,
            node_snapshot_json=node_snapshot,
            created_by=created_by or "user",
        )
        return self._comments.save(comment)

    def get(self, comment_id: UUID) -> ElementComment | None:
        return self._comments.get(comment_id)

    def list_for_slide(self, slide_id: UUID) -> list[ElementComment]:
        return self._comments.list_by_slide(slide_id)

    def requires_rebase(
        self,
        comment: ElementComment,
        *,
        slide: SlideSpec,
        scene: RenderScene,
    ) -> bool:
        """True when the formal scene moved past the comment's bound revision/hash."""
        current_revision_id = self._scene_history.latest_scene_revision_id(slide)
        current_hash = compute_scene_hash(scene)
        if comment.scene_revision_id != current_revision_id:
            return True
        if comment.scene_hash and comment.scene_hash != current_hash:
            return True
        return False

    def mark_needs_rebase(self, comment: ElementComment) -> ElementComment:
        updated = comment.model_copy(
            update={
                "status": ElementCommentStatus.NEEDS_REBASE,
                "proposal_id": None,
            }
        )
        return self._comments.save(updated)

    def rebind_to_current_scene(self, comment_id: UUID) -> ElementComment:
        """Re-pin a needs_rebase comment to the current formal scene (same node_id)."""
        comment = self._comments.get(comment_id)
        if comment is None:
            raise WorkflowError("未找到元素评论。")
        if comment.status not in {
            ElementCommentStatus.NEEDS_REBASE,
            ElementCommentStatus.PENDING,
        }:
            raise WorkflowError(
                f"评论状态 `{comment.status.value}` 不能重新绑定到当前 Scene。"
            )

        slide = self._presentations.get_slide(comment.slide_id)
        if slide is None:
            raise WorkflowError("未找到当前页面。")
        scene = self._require_scene(comment.slide_id)
        node = scene.node_by_id(comment.node_id)
        if node is None:
            raise WorkflowError(
                f"当前 Scene 已无节点 `{comment.node_id}`，无法自动 rebase；请重新选择元素。"
            )

        rebound = comment.model_copy(
            update={
                "status": ElementCommentStatus.PENDING,
                "scene_revision_id": self._scene_history.latest_scene_revision_id(slide),
                "scene_hash": compute_scene_hash(scene),
                "node_snapshot_json": node.model_dump(mode="json"),
                "proposal_id": None,
            }
        )
        return self._comments.save(rebound)

    def propose_from_comment(self, comment_id: UUID) -> tuple[ElementComment, SceneChangeProposal]:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise WorkflowError("未找到元素评论。")
        if comment.status == ElementCommentStatus.NEEDS_REBASE:
            raise WorkflowError(
                "评论绑定的 Scene 版本已过期（needs_rebase）。"
                "请先重新绑定到当前正式 Scene，再生成提案。"
            )
        if comment.status not in {
            ElementCommentStatus.PENDING,
            ElementCommentStatus.PROPOSED,
        }:
            raise WorkflowError(f"评论状态 `{comment.status.value}` 不能再生成提案。")

        slide = self._presentations.get_slide(comment.slide_id)
        if slide is None:
            raise WorkflowError("未找到当前页面。")
        scene = self._require_scene(comment.slide_id)

        if self.requires_rebase(comment, slide=slide, scene=scene):
            self.mark_needs_rebase(comment)
            raise WorkflowError(
                "评论创建时的 SceneRevision 与当前正式版本不一致（needs_rebase）。"
                "请勿直接应用到新版本；请先确认节点语境后重新绑定。"
            )

        if scene.node_by_id(comment.node_id) is None:
            self.mark_needs_rebase(comment)
            raise WorkflowError(
                f"绑定节点 `{comment.node_id}` 在当前 Scene 中不存在（needs_rebase）。"
            )

        plan = self._planner.plan(
            comment,
            scene=scene,
            presentation_id=comment.presentation_id,
            slide_id=comment.slide_id,
        )
        if not plan.commands:
            raise WorkflowError(plan.unsupported_reason or "无法从评论生成 Scene 修改提案。")

        base_revision_id = self._scene_history.latest_scene_revision_id(slide)
        proposal = self._proposals.create_proposal(
            base_scene=scene,
            commands=list(plan.commands),
            presentation_id=comment.presentation_id,
            slide_id=comment.slide_id,
            slide_order=slide.order,
            base_revision_id=base_revision_id,
            reasons=list(plan.reasons),
        )
        updated = comment.model_copy(
            update={
                "status": ElementCommentStatus.PROPOSED,
                "proposal_id": proposal.proposal_id,
            }
        )
        saved = self._comments.save(updated)
        return saved, proposal

    def create_and_propose(
        self,
        *,
        slide_id: UUID,
        node_id: str,
        note: str,
        layout_element_id: str | None = None,
        created_by: str = "user",
    ) -> tuple[ElementComment, SceneChangeProposal]:
        comment = self.create_comment(
            slide_id=slide_id,
            node_id=node_id,
            note=note,
            layout_element_id=layout_element_id,
            created_by=created_by,
        )
        return self.propose_from_comment(comment.id)

    def resolve_comment(self, comment_id: UUID) -> ElementComment:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise WorkflowError("未找到元素评论。")
        if comment.status not in {
            ElementCommentStatus.ACCEPTED,
            ElementCommentStatus.REJECTED,
            ElementCommentStatus.RESOLVED,
            ElementCommentStatus.NEEDS_REBASE,
        }:
            # Allow manual close after review outcomes; pending/proposed go to resolved too.
            pass
        updated = comment.model_copy(update={"status": ElementCommentStatus.RESOLVED})
        return self._comments.save(updated)

    def sync_from_proposal_decision(self, proposal: SceneChangeProposal) -> list[ElementComment]:
        """Mirror proposal accept/reject onto linked element comments."""
        comments = self._comments.list_by_proposal(proposal.proposal_id)
        if not comments:
            return []

        if proposal.status in {
            ProposalStatus.ACCEPTED,
            ProposalStatus.PARTIALLY_ACCEPTED,
        }:
            next_status = ElementCommentStatus.ACCEPTED
        elif proposal.status == ProposalStatus.REJECTED:
            next_status = ElementCommentStatus.REJECTED
        else:
            return comments

        synced: list[ElementComment] = []
        for comment in comments:
            if comment.status in {
                ElementCommentStatus.ACCEPTED,
                ElementCommentStatus.REJECTED,
                ElementCommentStatus.RESOLVED,
                ElementCommentStatus.NEEDS_REBASE,
            }:
                synced.append(comment)
                continue
            updated = comment.model_copy(update={"status": next_status})
            synced.append(self._comments.save(updated))
        return synced

    def _require_scene(self, slide_id: UUID) -> RenderScene:
        scene_result = self._studio_scene.ensure_scene_for_slide(slide_id)
        if scene_result is None:
            raise WorkflowError("当前页面无法编译 RenderScene。")
        return scene_result.scene
