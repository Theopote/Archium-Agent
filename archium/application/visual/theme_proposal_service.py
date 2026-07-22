"""Create, review, and accept deck-wide ThemeChangeProposal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.deck_theme_apply import apply_tokens_to_design_system
from archium.application.visual.scene_deterministic_qa_service import run_proposal_scene_qa
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.application.visual.theme_integrity_qa import run_theme_integrity_qa
from archium.application.visual.theme_scene_resolve import resolve_scene_with_design_system
from archium.config.settings import Settings, get_settings
from archium.domain._base import utc_now
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue
from archium.domain.visual.render_scene import compute_scene_hash
from archium.domain.visual.theme_change_proposal import (
    ThemeChangeProposal,
    ThemeDeckImpactStats,
    ThemeProposalDecision,
    ThemeProposalStatus,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    RenderSceneRepository,
    ThemeProposalRepository,
)

# Prefer these roles when sampling; skip silently if absent.
_SAMPLE_ROLE_ORDER: tuple[str, ...] = (
    "cover",
    "section",
    "drawing_focus",
    "photo_evidence",
    "data",
    "text_dense",
)


@dataclass(frozen=True)
class _SamplePick:
    slide: SlideSpec
    reason: str


class ThemeProposalService:
    """Deck theme tokens → ThemeChangeProposal → DesignSystem switch on accept.

    Accept updates ArtDirection.design_system_id and refreshes scene caches by
    recompile / token re-resolution. It does **not** write per-slide SceneRevision
    rows for a theme-only change (avoids meaningless diffs and revision bloat).
    """

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
        self._scenes = RenderSceneRepository(session)
        self._studio_scene = StudioSceneService(session, settings=self._settings)

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
        sample_picks = self._select_sample_slides(
            slides, preferred_slide_id=preferred_slide_id
        )
        sample_slides = [pick.slide for pick in sample_picks]
        sample_selection_reason = {
            str(pick.slide.id): pick.reason for pick in sample_picks
        }

        preview_hashes: dict[str, str] = {}
        qa_by_slide: dict[str, list[QualityIssue]] = {}
        qa_summary: list[QualityIssue] = []
        sample_scenes = []

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
            sample_scenes.append(scene)
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

        integrity = run_theme_integrity_qa(
            base=base,
            proposed=proposed,
            sample_scenes=sample_scenes,
        )
        qa_summary.extend(integrity)
        for issue in integrity:
            qa_by_slide.setdefault("_theme_integrity", []).append(issue)

        from archium.application.visual.template_usage_brief_context import (
            constraints_from_brief,
            load_brief_for_art_direction,
        )

        usage_brief = load_brief_for_art_direction(self._session, art)
        if usage_brief is not None:
            constraints = constraints_from_brief(usage_brief)
            brief_issues = _theme_brief_gate(proposed, constraints)
            qa_summary.extend(brief_issues)
            for issue in brief_issues:
                qa_by_slide.setdefault("_template_usage_brief", []).append(issue)

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
            sample_selection_reason=sample_selection_reason,
            preview_scene_hashes=preview_hashes,
            qa_by_slide=qa_by_slide,
            qa_summary=_dedupe_issues(qa_summary),
            deck_impact=_compute_deck_impact(
                slides=slides,
                base=base,
                proposed=proposed,
                sample_scenes=sample_scenes,
                qa_summary=_dedupe_issues(qa_summary),
            ),
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

        # Theme accept = DesignSystem pointer switch + token re-resolve.
        # Do NOT force-recompile or record per-slide SceneRevision (theme ≠ content).
        slides = self._presentations.list_slides(proposal.presentation_id)
        for slide in slides:
            if slide.layout_plan_id is None:
                continue
            existing = self._scenes.get_by_layout_plan(slide.layout_plan_id)
            if existing is None:
                continue
            resolved = resolve_scene_with_design_system(existing, saved_ds)
            if compute_scene_hash(resolved) == compute_scene_hash(existing):
                self._studio_scene.invalidate_preview_cache(
                    proposal.presentation_id,
                    layout_plan_id=slide.layout_plan_id,
                )
                continue
            saved_scene = resolved.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
            self._scenes.save(saved_scene)
            self._studio_scene.invalidate_preview_cache(
                proposal.presentation_id,
                layout_plan_id=slide.layout_plan_id,
            )

        accepted = proposal.model_copy(
            update={
                "status": ThemeProposalStatus.ACCEPTED,
                "decided_at": utc_now(),
                "decision": ThemeProposalDecision(
                    proposal_id=proposal.proposal_id,
                    notes=notes or "theme_change:design_system_switch",
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
    ) -> list[_SamplePick]:
        """Explainable sampling: cover / section / drawing / photo / data / text."""
        with_plans = [slide for slide in slides if slide.layout_plan_id is not None]
        if not with_plans:
            return []

        ordered = sorted(with_plans, key=lambda item: item.order)
        classified: dict[str, list[tuple[SlideSpec, str]]] = {role: [] for role in _SAMPLE_ROLE_ORDER}

        for slide in ordered:
            plan = self._plans.get(slide.layout_plan_id) if slide.layout_plan_id else None
            for role, reason in self._classify_sample_roles(slide, plan):
                classified.setdefault(role, []).append((slide, reason))

        selected: list[_SamplePick] = []
        seen: set[UUID] = set()

        def _add(slide: SlideSpec, reason: str) -> None:
            if slide.id in seen:
                return
            selected.append(_SamplePick(slide=slide, reason=reason))
            seen.add(slide.id)

        if preferred_slide_id is not None:
            preferred = next((s for s in ordered if s.id == preferred_slide_id), None)
            if preferred is not None:
                _add(preferred, "preferred:当前编辑页")

        for role in _SAMPLE_ROLE_ORDER:
            candidates = classified.get(role) or []
            if not candidates:
                continue
            slide, reason = candidates[0]
            _add(slide, reason)

        # Ensure at least one page when roles are sparse.
        if not selected and ordered:
            _add(ordered[0], "fallback:首张有 LayoutPlan 的页面")

        return selected

    def _classify_sample_roles(
        self,
        slide: SlideSpec,
        plan: LayoutPlan | None,
    ) -> list[tuple[str, str]]:
        roles: list[tuple[str, str]] = []
        family = plan.layout_family if plan is not None else None
        slide_type = slide.slide_type

        if (
            slide.order == 0
            or slide_type == SlideType.TITLE
            or family == LayoutFamily.HERO
        ):
            roles.append(("cover", "cover:封面/开篇页"))
        if slide_type == SlideType.SECTION or (
            "章节" in (slide.title or "") or "section" in (slide.title or "").lower()
        ):
            roles.append(("section", "section:章节页"))
        if family == LayoutFamily.DRAWING_FOCUS:
            roles.append(("drawing_focus", "drawing_focus:图纸主导页"))
        if family == LayoutFamily.EVIDENCE_BOARD or slide_type == SlideType.IMAGE:
            roles.append(("photo_evidence", "photo_evidence:照片证据页"))
        if family in {
            LayoutFamily.METRIC_DASHBOARD,
            LayoutFamily.ANALYTICAL_DIAGRAM,
            LayoutFamily.COMPARATIVE_MATRIX,
        } or slide_type == SlideType.DATA:
            roles.append(("data", "data:数据/指标页"))
        if family == LayoutFamily.TEXTUAL_ARGUMENT or (
            slide_type == SlideType.CONTENT and len((slide.message or "").strip()) >= 80
        ):
            roles.append(("text_dense", "text_dense:文字密集页"))
        return roles


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


def _compute_deck_impact(
    *,
    slides: list[SlideSpec],
    base,
    proposed,
    sample_scenes: list,
    qa_summary: list[QualityIssue],
) -> ThemeDeckImpactStats:
    """Estimate full-deck impact from DesignSystem delta + sample scenes."""
    from archium.domain.visual.render_scene import DrawingNode, ImageNode

    font_changed = (
        base.typography.title.font_family != proposed.typography.title.font_family
        or base.typography.body.font_family != proposed.typography.body.font_family
        or abs(base.typography.title.font_size - proposed.typography.title.font_size) > 1e-6
        or abs(base.typography.body.font_size - proposed.typography.body.font_size) > 1e-6
    )
    bg_changed = base.colors.background != proposed.colors.background
    photo_mode_changed = (
        base.image_style.photo_treatment != proposed.image_style.photo_treatment
    )

    drawing_nodes = 0
    evidence_photos = 0
    for scene in sample_scenes:
        for node in scene.nodes:
            if isinstance(node, DrawingNode):
                drawing_nodes += 1
            elif isinstance(node, ImageNode) and node.asset_origin == "project_upload":
                evidence_photos += 1

    page_count = len(slides)
    return ThemeDeckImpactStats(
        affected_pages=page_count,
        font_changes=page_count if font_changed else 0,
        background_changes=page_count if bg_changed else 0,
        # Theme resolve does not rewrite drawing pixels; report sample count as exposure.
        drawing_node_changes=0 if not font_changed else drawing_nodes,
        evidence_photo_changes=evidence_photos if photo_mode_changed else 0,
        warnings=sum(
            1 for issue in qa_summary if issue.severity in {IssueSeverity.MINOR, IssueSeverity.MAJOR}
        ),
        blockers=sum(1 for issue in qa_summary if issue.severity == IssueSeverity.BLOCKER),
    )


def _theme_brief_gate(proposed, constraints) -> list[QualityIssue]:
    """Ensure ThemeChangeProposal does not violate the bound TemplateUsageBrief."""
    from archium.domain.visual.enums import ImageFit, PhotoTreatment
    from archium.domain.visual.page_quality import (
        IssueCategory,
        IssueSeverity,
        QualityIssue,
        QualityIssueSource,
    )

    issues: list[QualityIssue] = []
    if constraints.forbid_drawing_cover_crop and (
        proposed.image_style.default_fit != ImageFit.CONTAIN
        or not proposed.image_style.drawing_preserve_aspect_ratio
    ):
        issues.append(
            QualityIssue(
                code="THEME.TEMPLATE_USAGE_BRIEF",
                severity=IssueSeverity.BLOCKER,
                category=IssueCategory.ARCHITECTURAL,
                message=(
                    f"主题提案违反已绑定 TemplateUsageBrief "
                    f"v{constraints.brief_version} 的图纸 contain 规则。"
                ),
                evidence=[
                    str(constraints.brief_id),
                    str(constraints.brief_version),
                    proposed.image_style.default_fit.value,
                ],
                source=QualityIssueSource.AUTO,
                suggested_fix="保持 default_fit=contain 与 drawing_preserve_aspect_ratio。",
            )
        )
    if constraints.photo_treatment_policy == PhotoTreatment.NONE.value:
        # Brief prefers none — historical is still flagged by integrity QA.
        pass
    for pattern in constraints.forbidden_patterns:
        if "cover" in pattern.lower() and proposed.image_style.default_fit == ImageFit.COVER:
            issues.append(
                QualityIssue(
                    code="THEME.TEMPLATE_USAGE_BRIEF",
                    severity=IssueSeverity.MAJOR,
                    category=IssueCategory.ARCHITECTURAL,
                    message=f"主题 default_fit=cover 触及 Brief 禁用模式：{pattern}",
                    evidence=[str(constraints.brief_id), pattern],
                    source=QualityIssueSource.AUTO,
                )
            )
    return issues
