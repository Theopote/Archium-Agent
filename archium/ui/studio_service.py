"""UI-facing facade for Presentation Studio."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.slide_preview_service import SlidePreviewService
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.render import RenderResult
from archium.ui.visual_service import (
    PresentationVisualSnapshot,
    SlideVisualSnapshot,
    export_presentation_pptx_from_layout_plans,
    get_presentation_visual_snapshot,
    presentation_has_visual_layout,
)
from archium.ui.workspace_service import (
    _resolve_runtime_settings,
    get_project_overview,
    list_project_presentations,
    list_projects,
)


@dataclass(frozen=True)
class StudioPresentationContext:
    """Loaded context for the Studio three-column layout."""

    project: Project
    presentation: Presentation
    snapshot: PresentationVisualSnapshot
    ready_for_export: bool
    slide_count: int
    layout_ready_count: int
    preview_ready_count: int


def list_studio_projects(session: Session) -> list[Project]:
    return list_projects(session)


def list_studio_presentations(session: Session, project_id: UUID) -> list[Presentation]:
    return list_project_presentations(session, project_id)


def load_studio_context(
    session: Session,
    project_id: UUID,
    presentation_id: UUID,
    *,
    visual_critic_reports: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    preview_paths: list[str] | None = None,
    workflow_output_dir: str | Path | None = None,
) -> StudioPresentationContext | None:
    overview = get_project_overview(session, project_id)
    if overview is None:
        return None

    presentations = list_project_presentations(session, project_id)
    presentation = next((item for item in presentations if item.id == presentation_id), None)
    if presentation is None:
        return None

    snapshot = get_presentation_visual_snapshot(
        session,
        presentation_id,
        visual_critic_reports=visual_critic_reports,
        deck_qa_report=deck_qa_report,
        preview_paths=preview_paths,
    )
    settings = _resolve_runtime_settings(None)
    preview_service = SlidePreviewService(settings)
    existing_preview_by_index = {
        index: item.preview_image for index, item in enumerate(snapshot.slides)
    }
    resolutions = preview_service.resolve_previews(
        presentation_id=presentation_id,
        layout_plans=[item.layout_plan for item in snapshot.slides],
        existing_preview_by_index=existing_preview_by_index,
        render_paths=list(preview_paths or []),
        workflow_output_dir=workflow_output_dir,
    )
    enriched_slides: list[SlideVisualSnapshot] = []
    for item, resolution in zip(snapshot.slides, resolutions, strict=True):
        enriched_slides.append(
            replace(
                item,
                preview_image=resolution.path,
                preview_kind=resolution.kind,
            )
        )
    snapshot = replace(snapshot, slides=enriched_slides)

    layout_ready_count = sum(1 for item in snapshot.slides if item.layout_plan is not None)
    preview_ready_count = sum(
        1
        for item in snapshot.slides
        if item.preview_image and Path(item.preview_image).is_file()
    )
    ready_for_export = presentation_has_visual_layout(session, presentation_id)

    return StudioPresentationContext(
        project=overview.project,
        presentation=presentation,
        snapshot=snapshot,
        ready_for_export=ready_for_export,
        slide_count=len(snapshot.slides),
        layout_ready_count=layout_ready_count,
        preview_ready_count=preview_ready_count,
    )


def get_selected_slide_snapshot(
    context: StudioPresentationContext,
    slide_index: int,
) -> SlideVisualSnapshot | None:
    slides = context.snapshot.slides
    if not slides:
        return None
    index = max(0, min(slide_index, len(slides) - 1))
    return slides[index]


def export_presentation_from_studio(
    session: Session,
    presentation_id: UUID,
    *,
    settings: object | None = None,
) -> RenderResult:
    return export_presentation_pptx_from_layout_plans(
        session,
        presentation_id,
        settings=settings,  # type: ignore[arg-type]
    )


def studio_readiness_label(context: StudioPresentationContext) -> str:
    if context.slide_count == 0:
        return "empty"
    if context.ready_for_export:
        return "ready"
    if context.layout_ready_count > 0:
        return "has_issues"
    return "needs_visual"
