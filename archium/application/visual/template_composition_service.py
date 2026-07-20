"""Compose LayoutPlan candidates from a published ArchitecturalTemplate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.layout_locked import preserve_locked_elements
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.template_layout_filler import fill_layout_plan_from_template
from archium.application.visual.template_layout_matcher import TemplateLayoutMatcher
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_template import ArchitecturalTemplate, TemplateStatus
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.template_match import TemplateLayoutCandidate
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository, PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArchitecturalTemplateRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)


@dataclass(frozen=True)
class TemplateCompositionResult:
    template: ArchitecturalTemplate
    candidates: list[TemplateLayoutCandidate]
    layout_plans: list[LayoutPlan]
    selected_plan: LayoutPlan | None
    design_system: DesignSystem


class TemplateCompositionService:
    """Match template pages, fill content, and persist layout candidates for Studio."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        matcher: TemplateLayoutMatcher | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._matcher = matcher or TemplateLayoutMatcher()
        self._templates = ArchitecturalTemplateRepository(session)
        self._presentations = PresentationRepository(session)
        self._intents = VisualIntentRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._designs = DesignSystemRepository(session)
        self._assets = AssetRepository(session)
        self._validator = LayoutValidationService()

    def generate_candidates_for_slide(
        self,
        *,
        slide_id: UUID,
        template_id: UUID,
        candidate_count: int = 3,
        select_best: bool = True,
    ) -> TemplateCompositionResult:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面不存在：{slide_id}")
        template = self._templates.get(template_id)
        if template is None:
            raise WorkflowError(f"模板不存在：{template_id}")
        if template.status not in {
            TemplateStatus.PUBLISHED,
            TemplateStatus.REVIEWED,
            TemplateStatus.DRAFT,
        }:
            raise WorkflowError("模板状态不可用于匹配。")
        if template.status == TemplateStatus.DEPRECATED:
            raise WorkflowError("已废弃的模板不可用于匹配。")

        intent = self._require_intent(slide)
        presentation = self._presentations.get_presentation(slide.presentation_id)
        project_id = presentation.project_id if presentation is not None else None
        assets = self._assets_for_slide(project_id=project_id, slide=slide, intent=intent)

        design = self._resolve_template_design_system(template)
        ranked = self._matcher.rank_layouts(
            slide_spec=slide,
            visual_intent=intent,
            assets=assets,
            template=template,
            limit=candidate_count,
        )
        if not ranked:
            raise WorkflowError("当前模板没有可匹配的版式页面（请先完成槽位标注）。")

        previous = None
        if slide.layout_plan_id is not None:
            previous = self._plans.get(slide.layout_plan_id)

        saved_plans: list[LayoutPlan] = []
        for candidate in ranked:
            layout = template.layout_by_id(candidate.layout_id)
            if layout is None:
                continue
            plan = fill_layout_plan_from_template(
                layout=layout,
                slide=slide,
                visual_intent=intent,
                design_system_id=design.id,
                template_id=template.id,
            )
            plan = preserve_locked_elements(plan, previous)
            report = self._validator.validate(
                plan,
                design,
                require_source=False,
                drawing_hero=any(
                    el.content_type.value == "drawing" for el in plan.elements
                ),
            )
            plan = plan.model_copy(
                update={
                    "validation_status": (
                        report.status if hasattr(report, "status") else plan.validation_status
                    )
                }
            )
            # Keep validation status enum if report exposes valid flag.
            from archium.domain.visual.enums import LayoutValidationStatus

            plan = plan.model_copy(
                update={
                    "validation_status": (
                        LayoutValidationStatus.VALID
                        if report.valid
                        else LayoutValidationStatus.INVALID
                    )
                }
            )
            saved_plans.append(self._plans.save(plan))

        selected = None
        if select_best and saved_plans:
            selected = saved_plans[0]
            slide.layout_plan_id = selected.id
            if template.design_system_id is not None:
                # Keep intent linked; DesignSystem comes from the selected plan.
                pass
            self._presentations.save_slide(slide)

        return TemplateCompositionResult(
            template=template,
            candidates=ranked,
            layout_plans=saved_plans,
            selected_plan=selected,
            design_system=design,
        )

    def list_published_templates(self, *, project_id: UUID | None = None) -> list[ArchitecturalTemplate]:
        templates = (
            self._templates.list_by_project(project_id)
            if project_id is not None
            else self._templates.list_all()
        )
        published = [item for item in templates if item.status == TemplateStatus.PUBLISHED]
        if published:
            return published
        # Allow reviewed/draft for local iteration when nothing is published yet.
        return [
            item
            for item in templates
            if item.status in {TemplateStatus.REVIEWED, TemplateStatus.DRAFT}
        ]

    def _require_intent(self, slide: SlideSpec) -> VisualIntent:
        intent = None
        if slide.visual_intent_id is not None:
            intent = self._intents.get(slide.visual_intent_id)
        if intent is None:
            intent = self._intents.get_by_slide(slide.id)
        if intent is None:
            raise WorkflowError("当前页面缺少 VisualIntent，请先运行视觉编排或重新排版。")
        return intent

    def _resolve_template_design_system(self, template: ArchitecturalTemplate) -> DesignSystem:
        if template.design_system_id is not None:
            design = self._designs.get(template.design_system_id)
            if design is not None:
                return design
        return default_presentation_design_system()

    def _assets_for_slide(
        self,
        *,
        project_id: UUID | None,
        slide: SlideSpec,
        intent: VisualIntent,
    ) -> list[Asset]:
        if project_id is None:
            return []
        wanted: set[UUID] = set()
        if intent.hero_asset_id is not None:
            wanted.add(intent.hero_asset_id)
        wanted.update(intent.supporting_asset_ids)
        for requirement in slide.visual_requirements:
            wanted.update(requirement.bound_asset_ids())
        assets: list[Asset] = []
        for asset_id in wanted:
            asset = self._assets.get_by_id(asset_id)
            if asset is not None and asset.project_id == project_id:
                assets.append(asset)
        if assets:
            return assets
        # Fallback: project catalog sample for scoring only.
        return self._assets.list_by_project(project_id)[:12]
