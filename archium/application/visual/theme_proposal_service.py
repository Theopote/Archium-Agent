"""Create, review, and accept deck-wide ThemeChangeProposal workflows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.deck_theme_apply import apply_tokens_to_design_system
from archium.application.visual.scene_deterministic_qa_service import run_proposal_scene_qa
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain._base import utc_now
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue
from archium.domain.visual.render_scene import compute_scene_hash
from archium.domain.visual.theme_change_proposal import (
    ThemeChangeProposal,
    ThemeProposalDecision,
    ThemeProposalStatus,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    ThemeProposalRepository,
)


class ThemeProposalService:
    """Deck theme tokens → ThemeChangeProposal → DesignSystem switch on accept."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._art_directions = ArtDirectionRepository(session)
        self._design_systems = DesignSystemRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._proposals = ThemeProposalRepository(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)
        self._scene_history = SceneHistoryService(session)

    def create_proposal(
        self,
        presentation_id: UUID,
        tokens: DeckThemeTokens,
        *,
        preferred_slide_id: UUID | None = None,
    ) -> ThemeChangeProposal:
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError("未找到汇报。")

        art = self._resolve_art_direction(presentation.project_id, presentation_id)
        if art is None or art.design_system_id is None:
            raise WorkflowError("当前汇报尚无 ArtDirection / DesignSystem，无法生成风格提案。")

        base = self._design_systems.get(art.design_system_id)
        if base is None:
            raise WorkflowError("DesignSystem 不存在。")

        proposed = apply_tokens_to_design_system(base, tokens)
        slides = self._presentations.list_slides(presentation_id)
        sample_slides = self._select_sample_slides(slides, preferred_slide_id=preferred_slide_id)

        preview_hashes: dict[str, str] = {}
        qa_by_slide: dict[str, list[QualityIssue]] = {}
        qa_summary: list[QualityIssue] = []

        for slide in sample_slides:
            if slide.layout_plan_id is None:
                continue
            plan = self._plans.get(slide.layout_plan_id)
            if plan is None:
                continue
            intent = None
            if slide.visual_intent_id is not None:
                from archium.infrastructure.database.visual_repositories import (
                    VisualIntentRepository,
                )

                intent = VisualIntentRepository(self._session).get(slide.visual_intent_id)
            scene = self._studio_scene.compile_scene(
                slide=slide,
                plan=plan,
                design_system=proposed,
                visual_intent=intent,
                art_direction=art,
                presentation_id=presentation_id,
                project_id=presentation.project_id,
            )
            preview_hashes[str(slide.id)] = compute_scene_hash(scene)
            qa = run_proposal_scene_qa(
                presentation_id,
                scene,
                slide_order=slide.order,
                studio_scene=self._studio_scene,
                include_post_render=False,
            )
            issues = list(qa.issues)
            qa_by_slide[str(slide.id)] = issues
            qa_summary.extend(issues)

        status = ThemeProposalStatus.READY
        if any(issue.severity == IssueSeverity.BLOCKER for issue in qa_summary):
            status = ThemeProposalStatus.READY_WITH_WARNINGS
        elif qa_summary:
            status = ThemeProposalStatus.READY_WITH_WARNINGS

        proposal = ThemeChangeProposal(
            presentation_id=presentation_id,
            art_direction_id=art.id,
            base_design_system=base,
            proposed_design_system=proposed,
            base_design_system_id=base.id,
            proposed_design_system_id=proposed.id,
            token_patch=tokens,
            sample_slide_ids=[slide.id for slide in sample_slides],
            preview_scene_hashes=preview_hashes,
            qa_by_slide=qa_by_slide,
            qa_summary=_dedupe_issues(qa_summary),
            status=status,
        )
        return self._proposals.save(proposal, supersede_previous=True)

    def get(self, proposal_id: UUID) -> ThemeChangeProposal | None:
        return self._proposals.get(proposal_id)

    def get_active(self, presentation_id: UUID) -> ThemeChangeProposal | None:
        return self._proposals.get_active_for_presentation(presentation_id)

    def reject_proposal(
        self,
        proposal: ThemeChangeProposal,
        *,
        notes: str = "",
    ) -> ThemeChangeProposal:
        rejected = proposal.model_copy(
            update={
                "status": ThemeProposalStatus.REJECTED,
                "decided_at": utc_now(),
                "decision": ThemeProposalDecision(
                    proposal_id=proposal.proposal_id,
                    notes=notes,
                ),
            }
        )
        return self._proposals.save(rejected, supersede_previous=False)

    def accept_proposal(
        self,
        proposal: ThemeChangeProposal,
        *,
        notes: str = "",
        allow_blockers: bool = False,
    ) -> ThemeChangeProposal:
        if proposal.status in {
            ThemeProposalStatus.ACCEPTED,
            ThemeProposalStatus.REJECTED,
            ThemeProposalStatus.SUPERSEDED,
        }:
            raise WorkflowError(f"提案状态 `{proposal.status.value}` 不能接受。")

        if not allow_blockers and any(
            issue.severity == IssueSeverity.BLOCKER for issue in proposal.qa_summary
        ):
            raise WorkflowError(
                "风格提案含 Blocker 级质量问题，请调整 Token 后重新生成，或确认后强制接受。"
            )

        art_id = proposal.art_direction_id
        if art_id is None:
            raise WorkflowError("提案缺少 ArtDirection 绑定。")
        art = self._art_directions.get(art_id)
        if art is None:
            raise WorkflowError("ArtDirection 不存在。")

        proposed = proposal.proposed_design_system.model_copy(
            update={
                "name": proposal.proposed_design_system.name.replace(
                    " (theme proposal)", ""
                ).strip()
                or proposal.proposed_design_system.name,
            }
        )
        saved_ds = self._design_systems.save(proposed)
        updated_art = art.model_copy(
            update={
                "design_system_id": saved_ds.id,
                "version": art.version + 1,
            }
        )
        updated_art.touch()
        self._art_directions.save(updated_art)

        slides = self._presentations.list_slides(proposal.presentation_id)
        for slide in slides:
            if slide.layout_plan_id is None:
                continue
            result = self._studio_scene.ensure_scene_for_slide(
                slide.id,
                force_recompile=True,
            )
            if result is None:
                continue
            self._scene_history.record_scene(
                slide=slide,
                scene=result.scene,
                change_source=RevisionSource.AI_PROPOSAL,
                scene_revision_source="ai_proposal",
                note=notes or "theme_change",
                summary="全稿风格 Token 已应用",
            )

        accepted = proposal.model_copy(
            update={
                "status": ThemeProposalStatus.ACCEPTED,
                "decided_at": utc_now(),
                "decision": ThemeProposalDecision(
                    proposal_id=proposal.proposal_id,
                    notes=notes,
                ),
                "proposed_design_system": saved_ds,
                "proposed_design_system_id": saved_ds.id,
            }
        )
        return self._proposals.save(accepted, supersede_previous=False)

    def _resolve_art_direction(self, project_id: UUID, presentation_id: UUID):
        arts = self._art_directions.list_by_project(project_id)
        for art in arts:
            if art.presentation_id == presentation_id:
                return art
        return arts[0] if arts else None

    def _select_sample_slides(
        self,
        slides: list[SlideSpec],
        *,
        preferred_slide_id: UUID | None,
    ) -> list[SlideSpec]:
        with_plans = [slide for slide in slides if slide.layout_plan_id is not None]
        if not with_plans:
            return []

        selected: list[SlideSpec] = []
        seen: set[UUID] = set()

        def _add(slide: SlideSpec | None) -> None:
            if slide is None or slide.id in seen:
                return
            selected.append(slide)
            seen.add(slide.id)

        if preferred_slide_id is not None:
            _add(next((s for s in with_plans if s.id == preferred_slide_id), None))

        ordered = sorted(with_plans, key=lambda item: item.order)
        _add(ordered[0] if ordered else None)

        for slide in ordered:
            if len(selected) >= 3:
                break
            plan = self._plans.get(slide.layout_plan_id) if slide.layout_plan_id else None
            if plan is not None and plan.layout_family == LayoutFamily.DRAWING_FOCUS:
                _add(slide)

        for slide in ordered:
            if len(selected) >= 3:
                break
            _add(slide)

        return selected[:3]


def _dedupe_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    seen: set[tuple[str, str]] = set()
    result: list[QualityIssue] = []
    for issue in issues:
        key = (issue.code, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result
