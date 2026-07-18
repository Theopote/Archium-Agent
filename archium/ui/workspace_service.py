"""UI-facing service helpers for the Streamlit workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_service import ChunkService
from archium.application.ingestion_service import ImportItemResult, IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.workflow_models import WorkflowRunResult
from archium.config.llm_config import get_effective_settings
from archium.config.settings import Settings
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import PresentationType, ProjectType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.database.session import get_session
from archium.infrastructure.llm.factory import create_llm_provider
from archium.ui.workflow_resources import get_workflow_checkpointer_manager


def _resolve_runtime_settings(settings: Settings | None) -> Settings:
    if settings is not None:
        return settings
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx() is not None:
            from archium.ui.llm_settings import get_ui_effective_settings

            return get_ui_effective_settings()
    except Exception:
        pass
    return get_effective_settings()


def _create_workflow_service(
    session: Session,
    llm: object,
    settings: Settings,
) -> PresentationWorkflowService:
    return PresentationWorkflowService(
        session,
        llm,  # type: ignore[arg-type]
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


@dataclass(frozen=True)
class ProjectOverview:
    """Summary counts for a project workspace view."""

    project: Project
    document_count: int
    chunk_count: int
    presentation_count: int


def list_projects(session: Session) -> list[Project]:
    return ProjectRepository(session).list_all()


def create_project(
    session: Session,
    *,
    name: str,
    project_type: ProjectType,
    description: str = "",
) -> Project:
    project = Project(
        name=name.strip(),
        project_type=project_type,
        description=description.strip() or None,
    )
    return ProjectRepository(session).create(project)


def get_project_overview(session: Session, project_id: UUID) -> ProjectOverview | None:
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return None
    documents = DocumentRepository(session).list_by_project(project_id)
    chunks = DocumentRepository(session).list_chunks_by_project(project_id)
    presentations = PresentationRepository(session).list_by_project(project_id)
    return ProjectOverview(
        project=project,
        document_count=len(documents),
        chunk_count=len(chunks),
        presentation_count=len(presentations),
    )


def _parse_required_sections(required_sections_text: str) -> list[str]:
    text = required_sections_text.strip()
    if not text:
        return []
    lines = [part.strip() for part in text.splitlines() if part.strip()]
    if len(lines) > 1:
        return lines
    single = lines[0] if lines else text
    for separator in ("、", "，", ","):
        if separator in single:
            return [part.strip() for part in single.split(separator) if part.strip()]
    return [single]


def list_project_documents(session: Session, project_id: UUID) -> list[SourceDocument]:
    return DocumentRepository(session).list_by_project(project_id)


def list_document_chunks(session: Session, document_id: UUID) -> list[DocumentChunk]:
    return ChunkService(session).list_document_chunks(document_id)


def update_document_chunk(
    session: Session,
    chunk_id: UUID,
    *,
    content: str,
    section_title: str | None = None,
) -> DocumentChunk:
    return ChunkService(session).update_chunk(
        chunk_id,
        content=content,
        section_title=section_title,
    )


def list_project_presentations(session: Session, project_id: UUID) -> list[Presentation]:
    return PresentationRepository(session).list_by_project(project_id)


def import_uploaded_file(
    session: Session,
    project_id: UUID,
    *,
    filename: str,
    data: bytes,
    settings: Settings | None = None,
) -> ImportItemResult:
    suffix = Path(filename).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(data)
        temp_path = Path(temp_file.name)
    try:
        return IngestionService(session, settings=settings).import_file(project_id, temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_presentation_request(
    *,
    title: str,
    audience: str,
    purpose: str,
    core_message: str,
    target_slide_count: int,
    required_sections_text: str,
    presentation_type: PresentationType = PresentationType.CLIENT_REVIEW,
) -> PresentationRequest:
    sections = _parse_required_sections(required_sections_text)
    return PresentationRequest(
        title=title.strip(),
        audience=audience.strip(),
        purpose=purpose.strip(),
        core_message=core_message.strip(),
        target_slide_count=target_slide_count,
        required_sections=sections,
        presentation_type=presentation_type,
    )


def run_presentation_workflow(
    session: Session,
    project_id: UUID,
    request: PresentationRequest,
    *,
    export_json: bool = True,
    export_marp: bool = True,
    export_presentation_spec: bool = False,
    export_editable_pptx: bool = False,
    export_pptx: bool = False,
    export_pdf: bool = False,
    export_preview_images: bool | None = None,
    require_brief_review: bool = False,
    require_storyline_review: bool = False,
    require_slides_review: bool = False,
    settings: Settings | None = None,
) -> WorkflowRunResult:
    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    service = _create_workflow_service(session, llm, resolved_settings)
    resolved_preview_images = (
        export_preview_images
        if export_preview_images is not None
        else export_marp and resolved_settings.marp_preview_images_enabled
    )
    return service.run(
        project_id,
        request,
        export_json=export_json,
        export_presentation_spec=export_presentation_spec,
        export_editable_pptx=export_editable_pptx,
        export_marp=export_marp,
        export_pptx=export_pptx,
        export_pdf=export_pdf,
        export_preview_images=resolved_preview_images,
        require_brief_review=require_brief_review,
        require_storyline_review=require_storyline_review,
        require_slides_review=require_slides_review,
    )


def continue_workflow_after_review(
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> WorkflowRunResult:
    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        service = _create_workflow_service(session, llm, resolved_settings)
        return service.continue_after_review(workflow_run_id)


def resume_workflow(
    workflow_run_id: UUID,
    *,
    settings: Settings | None = None,
) -> WorkflowRunResult:
    """Resume or retry a workflow from its LangGraph checkpoint."""
    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        service = _create_workflow_service(session, llm, resolved_settings)
        return service.resume(workflow_run_id)


def regenerate_brief(
    presentation_id: UUID,
    *,
    workflow_run_id: UUID | None = None,
    settings: Settings | None = None,
) -> PresentationBrief:
    from archium.application.regeneration_service import RegenerationService

    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        return RegenerationService(session, llm, settings=resolved_settings).regenerate_brief(
            presentation_id,
            workflow_run_id=workflow_run_id,
        )


def regenerate_storyline(
    presentation_id: UUID,
    *,
    workflow_run_id: UUID | None = None,
    settings: Settings | None = None,
) -> Storyline:
    from archium.application.regeneration_service import RegenerationService

    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        return RegenerationService(session, llm, settings=resolved_settings).regenerate_storyline(
            presentation_id,
            workflow_run_id=workflow_run_id,
        )


def regenerate_slide_plan(
    presentation_id: UUID,
    *,
    workflow_run_id: UUID | None = None,
    settings: Settings | None = None,
) -> list[SlideSpec]:
    from archium.application.regeneration_service import RegenerationService

    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        return RegenerationService(session, llm, settings=resolved_settings).regenerate_slide_plan(
            presentation_id,
            workflow_run_id=workflow_run_id,
        )
