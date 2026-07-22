"""Generate, update, and approve per-page SlideDesignBrief records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.review_models import (
    OutlineSectionUpdate,
    OutlineUpdate,
    SlideAssetBindingUpdate,
    SlideDesignBriefUpdate,
    SlideIntentUpdate,
)
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import SlideAssetBindingRole
from archium.domain.outline import OutlinePlan
from archium.domain.slide_asset_binding import SlideAssetBinding, index_page_asset_bindings
from archium.domain.slide_design_brief import (
    BriefStatus,
    DrawingDisplayPolicy,
    ImageDisplayPolicy,
    SlideDesignBrief,
    default_drawing_policy,
    default_image_policy,
    default_protection_rules_for_page,
    index_design_briefs,
    infer_primary_visual_type,
)
from archium.domain.visual.template_usage_brief import TemplateUsageBrief
from archium.domain.slide_intent import SlideIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository

_LAYOUT_FAMILY_BY_VISUAL: dict[str, str] = {
    "drawing": "drawing_focus",
    "photo": "photo_evidence_grid",
    "metric": "metric_dashboard",
    "title": "hero",
    "comparison": "comparative_matrix",
    "content": "process_narrative",
}


_DENSITY_BY_TYPE: dict[str, str] = {
    "title": "low",
    "drawing": "medium",
    "photo": "medium",
    "metric": "high",
    "comparison": "high",
    "content": "medium",
}


@dataclass(frozen=True)
class DesignBriefSummary:
    total: int
    approved: int
    pending: int
    draft: int

    @property
    def all_approved(self) -> bool:
        return self.total > 0 and self.approved == self.total


def design_briefs_ready(outline: OutlinePlan) -> tuple[bool, list[str]]:
    """Gate for layout / visual batch generation."""
    missing: list[str] = []
    if not outline.page_intents:
        missing.append("至少一个页面意图")
        return False, missing
    briefs = _ensure_briefs_aligned(outline)
    if not briefs:
        missing.append("请生成页面设计摘要")
        return False, missing
    unapproved = [b for b in briefs if b.status != BriefStatus.APPROVED]
    if unapproved:
        orders = ", ".join(str(b.page_order + 1) for b in unapproved[:6])
        suffix = "…" if len(unapproved) > 6 else ""
        missing.append(f"未批准页面：{orders}{suffix}")
        return False, missing
    return True, []


def summarize_design_briefs(outline: OutlinePlan) -> DesignBriefSummary:
    briefs = _ensure_briefs_aligned(outline)
    approved = sum(1 for b in briefs if b.status == BriefStatus.APPROVED)
    pending = sum(
        1
        for b in briefs
        if b.status in {BriefStatus.READY_FOR_REVIEW, BriefStatus.CHANGES_PENDING}
    )
    draft = sum(1 for b in briefs if b.status == BriefStatus.DRAFT)
    return DesignBriefSummary(
        total=len(briefs),
        approved=approved,
        pending=pending,
        draft=draft,
    )


class SlideDesignBriefService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._reviews = PresentationReviewService(session)

    def generate_all(self, outline_id: UUID) -> list[SlideDesignBrief]:
        outline = self._require_outline(outline_id)
        usage = self._resolve_usage_brief(outline)
        briefs = [
            self._generate_from_intent(
                intent,
                bindings=index_page_asset_bindings(outline.page_asset_bindings).get(
                    intent.order, []
                ),
                usage_brief=usage,
            )
            for intent in sorted(outline.page_intents, key=lambda item: item.order)
        ]
        return self._persist_briefs(outline, briefs)

    def regenerate_page(self, outline_id: UUID, page_order: int) -> SlideDesignBrief:
        outline = self._require_outline(outline_id)
        intent = next(
            (item for item in outline.page_intents if item.order == page_order),
            None,
        )
        if intent is None:
            raise WorkflowError(f"页面 {page_order + 1} 无对应 SlideIntent。")
        existing = index_design_briefs(outline.page_design_briefs).get(page_order)
        usage = self._resolve_usage_brief(outline)
        brief = self._generate_from_intent(
            intent,
            bindings=index_page_asset_bindings(outline.page_asset_bindings).get(page_order, []),
            preserve_status=False,
            usage_brief=usage,
        )
        if existing is not None and existing.status == BriefStatus.APPROVED:
            brief.status = BriefStatus.CHANGES_PENDING
        briefs = list(outline.page_design_briefs)
        briefs = [b for b in briefs if b.page_order != page_order]
        briefs.append(brief)
        saved = self._persist_briefs(outline, briefs)
        return next(item for item in saved if item.page_order == page_order)

    def update_brief(
        self,
        outline_id: UUID,
        update: SlideDesignBriefUpdate,
        *,
        expected_version: int | None = None,
    ) -> SlideDesignBrief:
        outline = self._require_outline(outline_id)
        if expected_version is not None and outline.version != expected_version:
            raise WorkflowError(
                f"大纲版本冲突（期望 v{expected_version}，当前 v{outline.version}）。"
            )
        briefs = list(_ensure_briefs_aligned(outline))
        index = next(
            (i for i, b in enumerate(briefs) if b.page_order == update.page_order),
            None,
        )
        if index is None:
            raise WorkflowError(f"页面 {update.page_order + 1} 尚无设计摘要。")

        previous = briefs[index]
        next_status = BriefStatus(update.status) if update.status else previous.status
        if previous.status == BriefStatus.APPROVED and self._brief_content_changed(
            previous, update
        ):
            next_status = BriefStatus.CHANGES_PENDING

        drawing_policy = (
            DrawingDisplayPolicy.model_validate(update.drawing_policy)
            if update.drawing_policy
            else previous.drawing_policy
        )
        image_policy = (
            ImageDisplayPolicy.model_validate(update.image_policy)
            if update.image_policy
            else previous.image_policy
        )

        briefs[index] = SlideDesignBrief(
            slide_id=previous.slide_id,
            page_order=update.page_order,
            page_task=update.page_task.strip() or previous.page_task,
            central_claim=update.central_claim.strip(),
            primary_visual_type=update.primary_visual_type.strip() or previous.primary_visual_type,
            primary_asset_ids=list(update.primary_asset_ids),
            supporting_asset_ids=list(update.supporting_asset_ids),
            evidence_ids=list(update.evidence_ids),
            layout_family=update.layout_family.strip(),
            expected_density=update.expected_density,  # type: ignore[arg-type]
            drawing_policy=drawing_policy,
            image_policy=image_policy,
            required_content=list(update.required_content),
            forbidden_content=list(update.forbidden_content),
            protection_rules=list(update.protection_rules) or list(previous.protection_rules),
            template_usage_brief_id=(
                update.template_usage_brief_id
                if update.template_usage_brief_id is not None
                else previous.template_usage_brief_id
            ),
            template_usage_brief_version=(
                update.template_usage_brief_version
                if update.template_usage_brief_version is not None
                else previous.template_usage_brief_version
            ),
            status=next_status,
        )
        saved = self._persist_briefs(outline, briefs)
        return next(item for item in saved if item.page_order == update.page_order)

    def approve_page(
        self,
        outline_id: UUID,
        page_order: int,
        *,
        expected_version: int | None = None,
    ) -> SlideDesignBrief:
        outline = self._require_outline(outline_id)
        if expected_version is not None and outline.version != expected_version:
            raise WorkflowError(
                f"大纲版本冲突（期望 v{expected_version}，当前 v{outline.version}）。"
            )
        briefs = list(_ensure_briefs_aligned(outline))
        updated: list[SlideDesignBrief] = []
        found = False
        for brief in briefs:
            if brief.page_order == page_order:
                brief.approve()
                found = True
            updated.append(brief)
        if not found:
            raise WorkflowError(f"页面 {page_order + 1} 尚无设计摘要。")
        saved = self._persist_briefs(outline, updated)
        return next(item for item in saved if item.page_order == page_order)

    def approve_all(
        self,
        outline_id: UUID,
        *,
        expected_version: int | None = None,
    ) -> list[SlideDesignBrief]:
        outline = self._require_outline(outline_id)
        if expected_version is not None and outline.version != expected_version:
            raise WorkflowError(
                f"大纲版本冲突（期望 v{expected_version}，当前 v{outline.version}）。"
            )
        briefs = list(_ensure_briefs_aligned(outline))
        for brief in briefs:
            brief.approve()
        return self._persist_briefs(outline, briefs)

    def _generate_from_intent(
        self,
        intent: SlideIntent,
        *,
        bindings: list[SlideAssetBinding],
        preserve_status: bool = False,
        usage_brief: TemplateUsageBrief | None = None,
    ) -> SlideDesignBrief:
        from archium.application.visual.image_treatment_planning_service import (
            ImageTreatmentPlanningService,
        )
        from archium.application.visual.template_usage_brief_context import (
            constraints_from_brief,
        )
        from archium.domain.visual.enums import ImageFit

        primary_visual = infer_primary_visual_type(intent.expected_layout)
        primary_assets: list[UUID] = []
        supporting_assets: list[UUID] = []
        for binding in bindings:
            if binding.binding_role == SlideAssetBindingRole.PRIMARY_DRAWING:
                primary_assets.append(binding.asset_id)
            else:
                supporting_assets.append(binding.asset_id)

        drawing_policy = default_drawing_policy() if primary_visual == "drawing" else None
        image_policy = (
            default_image_policy(
                allow_reference=primary_visual in {"photo", "comparison"},
            )
            if primary_visual in {"photo", "comparison", "content"}
            else None
        )

        brief_id = None
        brief_version = None
        if isinstance(usage_brief, TemplateUsageBrief):
            brief_id = usage_brief.id
            brief_version = usage_brief.version
            constraints = constraints_from_brief(usage_brief)
            treatment = ImageTreatmentPlanningService().plan(
                content_type=primary_visual,
                brief=usage_brief,
                constraints=constraints,
            )
            if primary_visual == "drawing" or treatment.forbid_cover_crop:
                drawing_policy = default_drawing_policy()
                if treatment.fit_mode == ImageFit.CONTAIN:
                    drawing_policy = drawing_policy.model_copy(
                        update={
                            "fit_mode": "contain",
                            "forbid_cover_crop": True,
                            "show_legend": treatment.show_legend,
                            "show_north_arrow": treatment.show_north_arrow,
                            "show_scale_bar": treatment.show_scale_bar,
                        }
                    )
            if image_policy is not None and not treatment.forbid_cover_crop:
                image_policy = image_policy.model_copy(
                    update={"fit_mode": treatment.fit_mode.value}
                )

        forbidden = list(intent.forbidden_content)
        if primary_visual == "drawing":
            forbidden.extend(
                item
                for item in (
                    "参考案例替代项目图纸",
                    "AI 生成现场效果图冒充事实",
                )
                if item not in forbidden
            )
        if isinstance(usage_brief, TemplateUsageBrief):
            for pattern in usage_brief.forbidden_patterns:
                if pattern and pattern not in forbidden:
                    forbidden.append(pattern)

        protection_rules = default_protection_rules_for_page(
            primary_visual_type=primary_visual,
            drawing_policy=drawing_policy,
        )
        if isinstance(usage_brief, TemplateUsageBrief):
            protection_rules.append(
                f"TemplateUsageBrief v{usage_brief.version} ({usage_brief.id})"
            )

        required_content: list[str] = []
        if intent.required_evidence:
            required_content.extend(intent.required_evidence[:6])
        if intent.central_conclusion.strip():
            required_content.insert(0, intent.central_conclusion.strip())

        return SlideDesignBrief(
            page_order=intent.order,
            page_task=intent.page_task.strip() or "待填写页面任务",
            central_claim=intent.central_conclusion.strip(),
            primary_visual_type=primary_visual,
            primary_asset_ids=primary_assets,
            supporting_asset_ids=supporting_assets,
            layout_family=intent.expected_layout.strip()
            or _LAYOUT_FAMILY_BY_VISUAL.get(primary_visual, "process_narrative"),
            expected_density=_DENSITY_BY_TYPE.get(primary_visual, "medium"),  # type: ignore[arg-type]
            drawing_policy=drawing_policy,
            image_policy=image_policy,
            required_content=required_content,
            forbidden_content=forbidden,
            protection_rules=protection_rules,
            template_usage_brief_id=brief_id,
            template_usage_brief_version=brief_version,
            status=BriefStatus.READY_FOR_REVIEW if not preserve_status else BriefStatus.DRAFT,
        )

    def _resolve_usage_brief(self, outline: OutlinePlan) -> TemplateUsageBrief | None:
        presentation = self._presentations.get_presentation(outline.presentation_id)
        if presentation is None:
            return None
        from archium.application.visual.template_usage_brief_context import (
            resolve_brief_for_presentation,
        )

        return resolve_brief_for_presentation(
            self._session,
            project_id=presentation.project_id,
            presentation_id=presentation.id,
        )

    def _persist_briefs(
        self,
        outline: OutlinePlan,
        briefs: list[SlideDesignBrief],
    ) -> list[SlideDesignBrief]:
        ordered = sorted(briefs, key=lambda item: item.page_order)
        update = _outline_update_from_plan(
            outline,
            page_design_briefs=[_brief_to_update(brief) for brief in ordered],
        )
        saved = self._reviews.update_outline(outline.id, update)
        return list(saved.page_design_briefs)

    def _require_outline(self, outline_id: UUID) -> OutlinePlan:
        outline = self._presentations.get_outline(outline_id)
        if outline is None:
            raise WorkflowError(f"OutlinePlan {outline_id} not found")
        return outline

    @staticmethod
    def _brief_content_changed(
        previous: SlideDesignBrief,
        update: SlideDesignBriefUpdate,
    ) -> bool:
        return any(
            [
                previous.page_task != update.page_task.strip(),
                previous.central_claim != update.central_claim.strip(),
                previous.primary_visual_type != update.primary_visual_type.strip(),
                previous.layout_family != update.layout_family.strip(),
                list(previous.primary_asset_ids) != list(update.primary_asset_ids),
            ]
        )


def _ensure_briefs_aligned(outline: OutlinePlan) -> list[SlideDesignBrief]:
    if outline.page_design_briefs:
        return sorted(outline.page_design_briefs, key=lambda item: item.page_order)
    return []


def _outline_update_from_plan(
    outline: OutlinePlan,
    *,
    page_design_briefs: list[SlideDesignBriefUpdate] | None = None,
) -> OutlineUpdate:
    return OutlineUpdate(
        title=outline.title,
        thesis=outline.thesis,
        audience=outline.audience,
        purpose=outline.purpose,
        target_slide_count=outline.target_slide_count,
        audience_mode=outline.audience_mode.value,
        sections=[
            OutlineSectionUpdate(
                id=section.id,
                title=section.title,
                purpose=section.purpose,
                key_message=section.key_message,
                order=section.order,
                estimated_slide_count=section.estimated_slide_count,
                evidence_requirements=list(section.evidence_requirements),
                required_assets=list(section.required_assets),
                required=section.required,
                expanded=section.expanded,
                category=section.category,
            )
            for section in outline.sections
        ],
        page_intents=[
            SlideIntentUpdate(
                order=intent.order,
                chapter_id=intent.chapter_id,
                page_task=intent.page_task,
                central_conclusion=intent.central_conclusion,
                required_evidence=list(intent.required_evidence),
                required_assets=list(intent.required_assets),
                forbidden_content=list(intent.forbidden_content),
                expected_layout=intent.expected_layout,
                notes=intent.notes,
            )
            for intent in outline.page_intents
        ],
        page_asset_bindings=[
            SlideAssetBindingUpdate(
                page_order=binding.page_order,
                asset_id=str(binding.asset_id),
                binding_role=binding.binding_role.value,
                user_description=binding.user_description,
                required=binding.required,
                slide_id=str(binding.slide_id) if binding.slide_id else None,
            )
            for binding in outline.page_asset_bindings
        ],
        page_design_briefs=page_design_briefs
        if page_design_briefs is not None
        else [_brief_to_update(brief) for brief in outline.page_design_briefs],
        expected_version=outline.version,
    )


def _brief_to_update(brief: SlideDesignBrief) -> SlideDesignBriefUpdate:
    return SlideDesignBriefUpdate(
        page_order=brief.page_order,
        page_task=brief.page_task,
        central_claim=brief.central_claim,
        primary_visual_type=brief.primary_visual_type,
        primary_asset_ids=list(brief.primary_asset_ids),
        supporting_asset_ids=list(brief.supporting_asset_ids),
        evidence_ids=list(brief.evidence_ids),
        layout_family=brief.layout_family,
        expected_density=brief.expected_density,
        drawing_policy=brief.drawing_policy.model_dump(mode="json")
        if brief.drawing_policy
        else None,
        image_policy=brief.image_policy.model_dump(mode="json") if brief.image_policy else None,
        required_content=list(brief.required_content),
        forbidden_content=list(brief.forbidden_content),
        protection_rules=list(brief.protection_rules),
        template_usage_brief_id=brief.template_usage_brief_id,
        template_usage_brief_version=brief.template_usage_brief_version,
        status=brief.status.value,
    )
