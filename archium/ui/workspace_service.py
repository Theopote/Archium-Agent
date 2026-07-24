"""UI-facing service helpers for the Streamlit workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_vision_rag_service import (
    AssetVisionBackfillResult,
    AssetVisionBackfillService,
)
from archium.application.chunk_models import ProjectContextBundle
from archium.application.chunk_service import ChunkService
from archium.application.export_service import PresentationExportService
from archium.application.ingestion_service import ImportItemResult, IngestionService
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.workflow_models import WorkflowRunResult
from archium.application.llm_settings_resolver import get_effective_settings
from archium.config.settings import Settings
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import PresentationType, ProjectOriginMode, ProjectType
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.render import RenderResult
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
    except (ImportError, RuntimeError):
        # Streamlit not available or not in Streamlit context
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
    origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT,
) -> Project:
    project = Project(
        name=name.strip(),
        project_type=project_type,
        description=description.strip() or None,
        origin_mode=origin_mode,
    )
    return ProjectRepository(session).create(project)


def get_project_overview(session: Session, project_id: UUID) -> ProjectOverview | None:
    documents = DocumentRepository(session)
    presentations = PresentationRepository(session)
    project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return None
    return ProjectOverview(
        project=project,
        document_count=documents.count_by_project(project_id),
        chunk_count=documents.count_chunks_by_project(project_id),
        presentation_count=presentations.count_by_project(project_id),
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


@dataclass(frozen=True)
class UploadKnowledgeTip:
    """UI-facing snapshot after materials import refreshes KnowledgeState."""

    summary_line: str
    understanding_summary: str = ""
    missing_information: tuple[str, ...] = ()
    next_action_labels: tuple[str, ...] = ()
    primary_action: str | None = None
    primary_action_label: str = ""


def import_uploaded_file(
    session: Session,
    project_id: UUID,
    *,
    filename: str,
    data: bytes,
    settings: Settings | None = None,
    reassess: bool = True,
) -> ImportItemResult:
    suffix = Path(filename).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(data)
        temp_path = Path(temp_file.name)
    try:
        result = IngestionService(session, settings=settings).import_file(
            project_id, temp_path
        )
    finally:
        temp_path.unlink(missing_ok=True)
    if reassess:
        reassess_knowledge_after_upload(session, project_id, settings=settings)
    return result


def reassess_knowledge_after_upload(
    session: Session,
    project_id: UUID,
    *,
    settings: Settings | None = None,
) -> UploadKnowledgeTip | None:
    """Refresh KnowledgeState after new evidence; never fail the import path."""
    try:
        from archium.application.context_intelligence_service import (
            ContextIntelligenceService,
        )
        from archium.infrastructure.llm.factory import create_llm_provider

        resolved = _resolve_runtime_settings(settings)
        llm = create_llm_provider(resolved)
        assessment = ContextIntelligenceService(
            session, llm, settings=resolved
        ).reassess(project_id)
    except Exception:
        return None

    actions = sorted(assessment.actions, key=lambda item: item.priority)
    labels: list[str] = []
    primary_action: str | None = None
    primary_label = ""
    for item in actions[:3]:
        if item.action.value == "upload_materials":
            continue
        dispatch = ContextIntelligenceService.resolve_action_target(item.action)
        label = dispatch.label or item.action.value
        if item.reason.strip():
            labels.append(f"{label}（{item.reason.strip()[:48]}）")
        else:
            labels.append(label)
        if primary_action is None:
            primary_action = item.action.value
            primary_label = label
    return UploadKnowledgeTip(
        summary_line=assessment.knowledge_state.summary_line(),
        understanding_summary=assessment.understanding_summary.strip(),
        missing_information=tuple(
            assessment.knowledge_state.missing_information[:5]
        ),
        next_action_labels=tuple(labels),
        primary_action=primary_action,
        primary_action_label=primary_label,
    )

def backfill_project_asset_vision(
    session: Session,
    project_id: UUID,
    *,
    settings: Settings | None = None,
) -> AssetVisionBackfillResult:
    resolved = _resolve_runtime_settings(settings)
    return AssetVisionBackfillService(session, settings=resolved).backfill_project(project_id)


def preview_project_retrieval(
    session: Session,
    project_id: UUID,
    query: str,
    *,
    settings: Settings | None = None,
    max_chunks: int = 12,
) -> ProjectContextBundle:
    from archium.agents._helpers import build_project_context_bundle

    resolved = _resolve_runtime_settings(settings)
    return build_project_context_bundle(
        session,
        project_id,
        query=query,
        max_chunks=max_chunks,
        settings=resolved,
    )


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
        use_manuscript_pipeline=True,
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
    require_outline_review: bool = True,
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
        require_outline_review=require_outline_review,
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


def regenerate_outline_plan(
    presentation_id: UUID,
    *,
    workflow_run_id: UUID | None = None,
    settings: Settings | None = None,
) -> OutlinePlan:
    from archium.application.regeneration_service import RegenerationService

    resolved_settings = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved_settings)
    with get_session() as session:
        return RegenerationService(session, llm, settings=resolved_settings).regenerate_outline_plan(
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


def export_presentation_pptx_legacy(
    session: Session,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> RenderResult:
    """Export editable PPTX via FormalPptxExportService (Scene preferred; Spec fallback)."""
    resolved_settings = _resolve_runtime_settings(settings)
    return PresentationExportService(session, settings=resolved_settings).reexport(
        presentation_id,
        export_json=False,
        export_marp=False,
        export_editable_pptx=True,
    )
