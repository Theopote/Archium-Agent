"""Build and act on per-page pipeline status boards."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_matching_service import AssetMatchingService
from archium.application.regeneration_service import RegenerationService
from archium.domain.deck_delivery import apply_deck_delivery_to_presentation, mark_slide_delivery
from archium.domain.enums import (
    PresentationWorkflowStep,
    SlideDeliveryStatus,
    VisualType,
    VisualWorkflowStep,
)
from archium.domain.page_pipeline_status import (
    PAGE_ACTION_LABELS,
    PAGE_PHASE_LABELS,
    PagePipelinePhase,
    PagePipelineStatus,
    PageStatusAction,
    PageStatusBoard,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutFamily, LayoutValidationStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    LayoutPlanRepository,
    RenderSceneRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.llm.factory import create_llm_provider

_DRAWING_VISUAL_TYPES = frozenset(
    {
        VisualType.SITE_PLAN,
        VisualType.FLOOR_PLAN,
        VisualType.SECTION,
        VisualType.ELEVATION,
        VisualType.DIAGRAM,
        VisualType.MAP,
    }
)
_PHOTO_VISUAL_TYPES = frozenset({VisualType.SITE_PHOTO, VisualType.RENDERING, VisualType.COMPARISON})
_METRIC_VISUAL_TYPES = frozenset({VisualType.CHART, VisualType.TABLE, VisualType.TIMELINE})


class PageStatusBoardService:
    """Derive actionable per-page statuses from slides + visual artifacts."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._layouts = LayoutPlanRepository(session)
        self._scenes = RenderSceneRepository(session)
        self._llm = llm

    def build_board(
        self,
        presentation_id: UUID,
        *,
        workflow_step: str | None = None,
        free_composition_slide_ids: set[str] | None = None,
    ) -> PageStatusBoard:
        slides = sorted(
            self._presentations.list_slides(presentation_id),
            key=lambda item: item.order,
        )
        free_ids = free_composition_slide_ids or set()
        rows = [
            self._status_for_slide(
                slide,
                workflow_step=workflow_step,
                free_composition=str(slide.id) in free_ids or slide.logical_key in free_ids,
            )
            for slide in slides
        ]
        summary = _board_summary(rows, workflow_step=workflow_step)
        return PageStatusBoard(
            presentation_id=presentation_id,
            current_workflow_step=workflow_step,
            rows=rows,
            summary=summary,
        )

    def run_action(
        self,
        presentation_id: UUID,
        slide_id: UUID,
        action: PageStatusAction,
        *,
        workflow_run_id: UUID | None = None,
    ) -> SlideSpec:
        if action == PageStatusAction.RETRY:
            return self._retry(presentation_id, slide_id, workflow_run_id=workflow_run_id)
        if action == PageStatusAction.REBIND_ASSETS:
            return self._rebind(presentation_id, slide_id)
        if action == PageStatusAction.SKIP:
            return self._set_skipped(presentation_id, slide_id, skipped=True)
        if action == PageStatusAction.UNSKIP:
            return self._set_skipped(presentation_id, slide_id, skipped=False)
        if action in {PageStatusAction.OPEN_STUDIO, PageStatusAction.CHANGE_TEMPLATE}:
            # Navigation-only — UI handles routing; keep slide untouched.
            slide = self._presentations.get_slide(slide_id)
            if slide is None or slide.presentation_id != presentation_id:
                raise WorkflowError(f"Slide not found: {slide_id}")
            return slide
        raise WorkflowError(f"Unsupported page action: {action.value}")

    def _retry(
        self,
        presentation_id: UUID,
        slide_id: UUID,
        *,
        workflow_run_id: UUID | None,
    ) -> SlideSpec:
        llm = self._llm or create_llm_provider()
        regenerated = RegenerationService(self._session, llm).retry_slide(
            presentation_id,
            slide_id,
            workflow_run_id=workflow_run_id,
        )
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None:
            AssetMatchingService(self._session).match_slides(
                presentation.project_id,
                [regenerated],
                slide_ids={regenerated.id},
                rematch=True,
            )
            refreshed = self._presentations.get_slide(slide_id)
            return refreshed or regenerated
        return regenerated

    def _rebind(self, presentation_id: UUID, slide_id: UUID) -> SlideSpec:
        presentation = self._presentations.get_presentation(presentation_id)
        slide = self._presentations.get_slide(slide_id)
        if presentation is None or slide is None or slide.presentation_id != presentation_id:
            raise WorkflowError(f"Slide not found: {slide_id}")
        slides, _count = AssetMatchingService(self._session).match_slides(
            presentation.project_id,
            [slide],
            slide_ids={slide.id},
            rematch=True,
        )
        updated = slides[0] if slides else slide
        all_slides = self._presentations.list_slides(presentation_id)
        apply_deck_delivery_to_presentation(presentation, all_slides)
        self._presentations.update_presentation(presentation)
        return updated

    def _set_skipped(
        self,
        presentation_id: UUID,
        slide_id: UUID,
        *,
        skipped: bool,
    ) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None or slide.presentation_id != presentation_id:
            raise WorkflowError(f"Slide not found: {slide_id}")
        if skipped:
            mark_slide_delivery(slide, SlideDeliveryStatus.SKIPPED, detail="user skipped page")
        else:
            mark_slide_delivery(slide, SlideDeliveryStatus.READY, detail=None)
            from archium.domain.deck_delivery import refresh_slide_asset_delivery

            refresh_slide_asset_delivery(slide)
        saved = self._presentations.save_slide(slide)
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is not None:
            apply_deck_delivery_to_presentation(
                presentation,
                self._presentations.list_slides(presentation_id),
            )
            self._presentations.update_presentation(presentation)
        return saved

    def _status_for_slide(
        self,
        slide: SlideSpec,
        *,
        workflow_step: str | None,
        free_composition: bool,
    ) -> PagePipelineStatus:
        layout = (
            self._layouts.get(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )
        scene = (
            self._scenes.get_by_layout_plan(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )

        layout_family = layout.layout_family if layout is not None else None
        is_free = free_composition
        if layout is not None:
            metadata = getattr(layout, "metadata", None)
            if isinstance(metadata, dict) and metadata.get("fallback_mode") == "free_composition":
                is_free = True

        phase, label, detail, severity = _derive_phase(
            slide,
            workflow_step=workflow_step,
            layout_family=layout_family,
            layout_validation=layout.validation_status if layout is not None else None,
            has_scene=scene is not None,
            free_composition=is_free,
        )
        actions = _actions_for_phase(phase)
        return PagePipelineStatus(
            slide_id=slide.id,
            order=slide.order,
            title=slide.title,
            phase=phase,
            status_label=label,
            detail=detail or (slide.delivery_detail or ""),
            severity=severity,
            actions=actions,
        )


def _derive_phase(
    slide: SlideSpec,
    *,
    workflow_step: str | None,
    layout_family: LayoutFamily | None,
    layout_validation: LayoutValidationStatus | None,
    has_scene: bool,
    free_composition: bool,
) -> tuple[PagePipelinePhase, str, str, str]:
    delivery = slide.delivery_status

    if delivery == SlideDeliveryStatus.SKIPPED:
        return PagePipelinePhase.SKIPPED, PAGE_PHASE_LABELS[PagePipelinePhase.SKIPPED], "", "info"
    if delivery == SlideDeliveryStatus.RENDER_FAILED:
        return (
            PagePipelinePhase.RENDER_FAILED,
            PAGE_PHASE_LABELS[PagePipelinePhase.RENDER_FAILED],
            slide.delivery_detail or "",
            "error",
        )
    if delivery == SlideDeliveryStatus.SCHEMA_BLOCKED:
        return (
            PagePipelinePhase.SCHEMA_BLOCKED,
            PAGE_PHASE_LABELS[PagePipelinePhase.SCHEMA_BLOCKED],
            slide.delivery_detail or "",
            "error",
        )
    if delivery == SlideDeliveryStatus.FALLBACK_USED:
        return (
            PagePipelinePhase.FALLBACK,
            PAGE_PHASE_LABELS[PagePipelinePhase.FALLBACK],
            slide.delivery_detail or "",
            "warn",
        )

    if layout_validation == LayoutValidationStatus.INVALID and _has_drawing_requirement(slide):
        return (
            PagePipelinePhase.DRAWING_QA_FAILED,
            PAGE_PHASE_LABELS[PagePipelinePhase.DRAWING_QA_FAILED],
            "版式/图纸校验未通过",
            "error",
        )

    if workflow_step == PresentationWorkflowStep.MATCH_ASSETS.value and _needs_asset_binding(slide):
        label = _binding_label(slide)
        return PagePipelinePhase.BINDING_ASSETS, label, "", "info"

    if delivery == SlideDeliveryStatus.ASSET_MISSING or _missing_required_assets(slide):
        label = _asset_missing_label(slide)
        return PagePipelinePhase.ASSET_MISSING, label, slide.delivery_detail or "", "warn"

    if slide.layout_plan_id is not None and not has_scene:
        if workflow_step in {
            VisualWorkflowStep.VISUAL_RENDER.value,
            VisualWorkflowStep.VISUAL_CRITIQUE.value,
            PresentationWorkflowStep.MARP.value,
        }:
            return (
                PagePipelinePhase.COMPILING_SCENE,
                PAGE_PHASE_LABELS[PagePipelinePhase.COMPILING_SCENE],
                "",
                "info",
            )
        return (
            PagePipelinePhase.COMPILING_SCENE,
            PAGE_PHASE_LABELS[PagePipelinePhase.COMPILING_SCENE],
            "版式已选，等待编译 Scene",
            "info",
        )

    if free_composition:
        if has_scene and delivery == SlideDeliveryStatus.READY:
            return (
                PagePipelinePhase.FREE_COMPOSITION,
                PAGE_PHASE_LABELS[PagePipelinePhase.FREE_COMPOSITION],
                "",
                "success",
            )
        return (
            PagePipelinePhase.FREE_COMPOSITION,
            PAGE_PHASE_LABELS[PagePipelinePhase.FREE_COMPOSITION],
            "",
            "info",
        )

    if layout_family is not None:
        if has_scene and delivery == SlideDeliveryStatus.READY:
            return (
                PagePipelinePhase.COMPLETE,
                "完成",
                "模板匹配成功",
                "success",
            )
        return (
            PagePipelinePhase.TEMPLATE_MATCHED,
            PAGE_PHASE_LABELS[PagePipelinePhase.TEMPLATE_MATCHED],
            layout_family.value,
            "success",
        )

    if has_scene and delivery == SlideDeliveryStatus.READY:
        return PagePipelinePhase.COMPLETE, PAGE_PHASE_LABELS[PagePipelinePhase.COMPLETE], "", "success"

    if workflow_step == PresentationWorkflowStep.SLIDES.value:
        return (
            PagePipelinePhase.GENERATING,
            PAGE_PHASE_LABELS[PagePipelinePhase.GENERATING],
            "",
            "info",
        )

    if delivery == SlideDeliveryStatus.READY:
        return (
            PagePipelinePhase.CONTENT_READY,
            PAGE_PHASE_LABELS[PagePipelinePhase.CONTENT_READY],
            "",
            "success",
        )

    return PagePipelinePhase.QUEUED, PAGE_PHASE_LABELS[PagePipelinePhase.QUEUED], "", "info"


def _actions_for_phase(phase: PagePipelinePhase) -> list[PageStatusAction]:
    if phase == PagePipelinePhase.SKIPPED:
        return [PageStatusAction.UNSKIP, PageStatusAction.OPEN_STUDIO]
    actions = [
        PageStatusAction.RETRY,
        PageStatusAction.REBIND_ASSETS,
        PageStatusAction.CHANGE_TEMPLATE,
        PageStatusAction.OPEN_STUDIO,
        PageStatusAction.SKIP,
    ]
    if phase == PagePipelinePhase.COMPLETE:
        return [
            PageStatusAction.OPEN_STUDIO,
            PageStatusAction.CHANGE_TEMPLATE,
            PageStatusAction.REBIND_ASSETS,
        ]
    if phase in {
        PagePipelinePhase.ASSET_MISSING,
        PagePipelinePhase.BINDING_ASSETS,
    }:
        return [
            PageStatusAction.REBIND_ASSETS,
            PageStatusAction.RETRY,
            PageStatusAction.OPEN_STUDIO,
            PageStatusAction.SKIP,
        ]
    if phase == PagePipelinePhase.DRAWING_QA_FAILED:
        return [
            PageStatusAction.OPEN_STUDIO,
            PageStatusAction.CHANGE_TEMPLATE,
            PageStatusAction.RETRY,
            PageStatusAction.SKIP,
        ]
    return actions


def _missing_required_assets(slide: SlideSpec) -> bool:
    for req in slide.visual_requirements:
        if not req.required or req.type == VisualType.TEXT_ONLY:
            continue
        if req.type == VisualType.ICON:
            if not req.icon_id:
                return True
            continue
        if not req.preferred_asset_ids:
            return True
    return False


def _needs_asset_binding(slide: SlideSpec) -> bool:
    return any(
        req.required
        and req.type != VisualType.TEXT_ONLY
        and (
            (req.type == VisualType.ICON and not req.icon_id)
            or (req.type != VisualType.ICON and not req.preferred_asset_ids)
        )
        for req in slide.visual_requirements
    )


def _has_drawing_requirement(slide: SlideSpec) -> bool:
    return any(req.type in _DRAWING_VISUAL_TYPES for req in slide.visual_requirements)


def _asset_missing_label(slide: SlideSpec) -> str:
    missing_types = {
        req.type
        for req in slide.visual_requirements
        if req.required
        and req.type != VisualType.TEXT_ONLY
        and (
            (req.type == VisualType.ICON and not req.icon_id)
            or (req.type != VisualType.ICON and not req.preferred_asset_ids)
        )
    }
    if missing_types & _METRIC_VISUAL_TYPES:
        return "缺少指标来源"
    if missing_types & _PHOTO_VISUAL_TYPES:
        return "缺少现场照片"
    if missing_types & _DRAWING_VISUAL_TYPES:
        return "缺少图纸素材"
    if missing_types & {VisualType.REFERENCE_CASE}:
        return "缺少参考案例"
    return PAGE_PHASE_LABELS[PagePipelinePhase.ASSET_MISSING]


def _binding_label(slide: SlideSpec) -> str:
    types = {req.type for req in slide.visual_requirements if req.required}
    if types & _PHOTO_VISUAL_TYPES:
        return "正在绑定现场照片"
    if types & _DRAWING_VISUAL_TYPES:
        return "正在绑定图纸"
    if types & _METRIC_VISUAL_TYPES:
        return "正在绑定指标素材"
    return PAGE_PHASE_LABELS[PagePipelinePhase.BINDING_ASSETS]


def _board_summary(
    rows: list[PagePipelineStatus],
    *,
    workflow_step: str | None,
) -> str:
    if not rows:
        return "尚无页面状态。"
    attention = sum(1 for row in rows if row.severity in {"warn", "error"})
    complete = sum(
        1
        for row in rows
        if row.phase in {PagePipelinePhase.COMPLETE, PagePipelinePhase.TEMPLATE_MATCHED}
    )
    skipped = sum(1 for row in rows if row.phase == PagePipelinePhase.SKIPPED)
    parts = [f"共 {len(rows)} 页", f"{complete} 页完成/匹配"]
    if attention:
        parts.append(f"{attention} 页需处理")
    if skipped:
        parts.append(f"{skipped} 页已跳过")
    if workflow_step:
        parts.append(f"当前步骤：{workflow_step}")
    return " · ".join(parts)


def action_label(action: PageStatusAction) -> str:
    return PAGE_ACTION_LABELS.get(action, action.value)
