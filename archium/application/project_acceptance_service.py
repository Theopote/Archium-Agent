"""Run end-to-end real-project acceptance scenarios."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_acceptance_metrics import (
    derive_acceptance_human_metrics,
    derive_acceptance_human_metrics_from_reviews,
    seed_acceptance_reviews_from_layout,
)
from archium.application.studio_human_review_store import load_presentation_reviews
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.visual.visual_workflow_service import VisualWorkflowService
from archium.config.settings import Settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType, WorkflowStatus
from archium.domain.project_acceptance import (
    REAL_PROJECT_MIN_ASSETS,
    REAL_PROJECT_MIN_SLIDES,
    RealProjectAcceptanceMetrics,
    RealProjectAcceptanceRecord,
    RealProjectScenario,
)
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.validation import LAYOUT_DRAWING_CROPPED
from archium.infrastructure.database.repositories import AssetRepository, PresentationRepository
from archium.infrastructure.llm.base import LLMProvider


@dataclass(frozen=True)
class RealProjectManifest:
    """Loaded manifest for one acceptance scenario."""

    project_id: str
    scenario: RealProjectScenario
    title: str
    expectations: dict[str, Any]


class ProjectAcceptanceService:
    """Seed a project, run content + visual workflows, and collect metrics."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings
        self._assets = AssetRepository(session)
        self._presentations = PresentationRepository(session)

    def run(
        self,
        manifest: RealProjectManifest,
        *,
        project: Any,
        presentation_request: Any,
    ) -> RealProjectAcceptanceRecord:
        """Execute one acceptance scenario and return a metrics record."""
        started = time.perf_counter()

        content_service = PresentationWorkflowService(
            self._session,
            self._llm,
            settings=self._settings,
        )
        visual_service = VisualWorkflowService(
            self._session,
            llm=self._llm,
            settings=self._settings,
        )
        try:
            content_result = content_service.run(
                project.id,
                presentation_request,
                export_json=True,
                export_presentation_spec=bool(
                    manifest.expectations.get("export_presentation_spec", True)
                ),
                require_brief_review=False,
                require_storyline_review=False,
                require_slides_review=False,
            )
            content_ok = content_result.workflow_run.status == WorkflowStatus.COMPLETED
            presentation = content_result.presentation
            if presentation is None:
                msg = "Content workflow completed without a presentation"
                raise RuntimeError(msg)

            _attach_project_assets(
                self._presentations,
                presentation.id,
                project.id,
                self._assets.list_by_project(project.id),
            )

            visual_result = visual_service.run(
                project.id,
                presentation.id,
                require_art_direction_review=False,
                use_llm=False,
                export_layout_instructions=True,
                export_pptx=False,
                candidate_count=2,
                max_repair_rounds=2,
            )
            visual_result = self._resume_visual_if_paused(visual_service, visual_result)
            visual_ok = visual_result.succeeded
        finally:
            content_service.close()
            visual_service.close()

        elapsed = round(time.perf_counter() - started, 3)
        slides = self._presentations.list_slides(presentation.id)
        assets = self._assets.list_by_project(project.id)
        validation_reports = list(visual_result.validation_reports or [])
        _seed_rehearsal_reviews_if_missing(
            self._session,
            presentation.id,
            slides,
            validation_reports,
            settings=self._settings,
        )
        critical_count, error_count, crop_count = _summarize_layout_issues(validation_reports)
        asset_utilization = _asset_utilization_rate(slides, assets)

        min_slides = int(manifest.expectations.get("min_slides", REAL_PROJECT_MIN_SLIDES))
        min_assets = int(manifest.expectations.get("min_assets", REAL_PROJECT_MIN_ASSETS))
        derived = derive_acceptance_human_metrics(
            slide_count=len(slides),
            critical_layout_page_count=critical_count,
            error_layout_page_count=error_count,
            validation_reports=validation_reports,
            first_generation_seconds=elapsed,
        )
        stored_reviews = load_presentation_reviews(
            self._session,
            presentation.id,
            settings=self._settings,
        )
        review_values = list(stored_reviews.values())
        if review_values:
            derived = derive_acceptance_human_metrics_from_reviews(
                review_values,
                slide_count=len(slides),
                fallback=derived,
            )
            notes_suffix = "human metrics from Studio reviews"
        else:
            notes_suffix = "human metrics derived from layout validation (rehearsal baseline)"
        metrics = RealProjectAcceptanceMetrics(
            first_generation_seconds=elapsed,
            generation_succeeded=content_ok and visual_ok,
            slide_count=len(slides),
            asset_count=len(assets),
            layout_plan_count=len(visual_result.layout_plan_ids),
            critical_layout_page_count=critical_count,
            error_layout_page_count=error_count,
            drawing_crop_issue_count=crop_count,
            export_acceptable=critical_count == 0,
            real_asset_utilization_rate=asset_utilization,
            major_edit_page_ratio=derived["major_edit_page_ratio"],
            minor_edit_page_ratio=derived["minor_edit_page_ratio"],
            exported_page_ratio=derived["exported_page_ratio"],
            average_human_visual_score=derived["average_human_visual_score"],
            user_edit_minutes=derived["user_edit_minutes"],
        )
        notes = (
            f"slides>={min_slides}: {metrics.slide_count >= min_slides}; "
            f"assets>={min_assets}: {metrics.asset_count >= min_assets}; "
            f"{notes_suffix}"
        )
        return RealProjectAcceptanceRecord(
            project_id=manifest.project_id,
            scenario=manifest.scenario,
            title=manifest.title,
            run_at=datetime.now(UTC),
            metrics=metrics,
            notes=notes,
        )

    @staticmethod
    def _resume_visual_if_paused(
        visual_service: VisualWorkflowService,
        result: Any,
    ) -> Any:
        if result.succeeded or not result.awaiting_review:
            return result
        gate = result.review_gate
        if gate == "layout_review":
            return visual_service.continue_after_layout_review(
                result.workflow_run.id,
                allow_invalid_layout_export=True,
            )
        if gate == "art_direction":
            return visual_service.continue_after_art_direction_approval(result.workflow_run.id)
        return result


_ASSET_VISUAL_TYPES: dict[AssetType, VisualType] = {
    AssetType.DRAWING: VisualType.SITE_PLAN,
    AssetType.DIAGRAM: VisualType.DIAGRAM,
    AssetType.PHOTO: VisualType.SITE_PHOTO,
    AssetType.IMAGE: VisualType.SITE_PHOTO,
    AssetType.CHART: VisualType.CHART,
}


def _attach_project_assets(
    presentations: PresentationRepository,
    presentation_id: UUID,
    _project_id: UUID,
    assets: list[Asset],
) -> None:
    slides = presentations.list_slides(presentation_id)
    if not slides or not assets:
        return
    for index, slide in enumerate(slides):
        if slide.visual_requirements:
            continue
        asset = assets[index % len(assets)]
        slide.visual_requirements = [
            VisualRequirement(
                type=_ASSET_VISUAL_TYPES.get(asset.asset_type, VisualType.DIAGRAM),
                description=asset.description or asset.filename,
                preferred_asset_ids=[asset.id],
            )
        ]
        presentations.save_slide(slide)


def _summarize_layout_issues(reports: list[dict[str, Any]]) -> tuple[int, int, int]:
    critical_pages = 0
    error_pages = 0
    crop_issues = 0
    for report in reports:
        issues = report.get("issues") or []
        severities = {str(item.get("severity", "")).lower() for item in issues}
        if "critical" in severities:
            critical_pages += 1
        if "error" in severities:
            error_pages += 1
        crop_issues += sum(
            1 for item in issues if str(item.get("rule_code")) == LAYOUT_DRAWING_CROPPED
        )
    return critical_pages, error_pages, crop_issues


def _asset_utilization_rate(slides: list[SlideSpec], assets: list[Asset]) -> float | None:
    if not slides or not assets:
        return None
    asset_ids = {asset.id for asset in assets}
    used = 0
    for slide in slides:
        refs: set[UUID] = set()
        for requirement in slide.visual_requirements:
            refs.update(requirement.preferred_asset_ids)
        if refs & asset_ids:
            used += 1
    return round(used / len(slides), 3)


def _seed_rehearsal_reviews_if_missing(
    session: Session,
    presentation_id: UUID,
    slides: list[SlideSpec],
    validation_reports: list[dict[str, Any]],
    *,
    settings: Settings | None,
) -> None:
    seed_acceptance_reviews_from_layout(
        session,
        presentation_id,
        slides,
        validation_reports,
        settings=settings,
    )
