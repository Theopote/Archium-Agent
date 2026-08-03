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
from archium.application.unit_of_work import UnitOfWork
from archium.application.chunk_models import ProjectContextBundle
from archium.application.chunk_service import ChunkService
from archium.application.ingestion_service import ImportItemResult
from archium.application.llm_settings_resolver import get_effective_settings
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import PresentationType, ProjectOriginMode, ProjectType
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.render import RenderResult
from archium.domain.slide import SlideSpec
from archium.exceptions import ProjectNotFoundError
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


@dataclass(frozen=True)
class GenerationFormDefaults:
    """Prefill values for the presentation generation form (not placeholders)."""

    title: str
    audience: str
    purpose: str
    core_message: str
    sections: str
    target_slide_count: int


_HERITAGE_HINTS = ("寺", "庙", "庵", "观", "宗教", "文物", "古建", "遗产", "复原", "重建", "文化")
_HOSPITAL_HINTS = ("医院", "医疗", "院区", "hospital", "clinic")


def _looks_like_internal_assessment(text: str) -> bool:
    """Skip Brief fields that are knowledge-rule noise, not user-facing copy."""
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    if "规则评估" in cleaned and "%" in cleaned:
        return True
    return bool(cleaned.startswith("[刷新]"))


def _looks_like_placeholder_audience(text: str) -> bool:
    cleaned = (text or "").strip()
    return cleaned in {"", "汇报对象", "汇报对象待确认"}


def resolve_generation_form_defaults(session: Session, project_id: UUID) -> GenerationFormDefaults:
    """Project / Brief / Outline / Genesis-aware defaults for the generate form."""
    from archium.domain.intent.intent_evolution import IntentEvolutionKind

    base = GenerationFormDefaults(
        title="概念汇报",
        audience="汇报对象",
        purpose="确认方案方向与下一步",
        core_message="用一句话概括本页核心主张",
        sections="背景与语境\n设计策略\n空间与效果",
        target_slide_count=12,
    )
    project = None
    try:
        project = UnitOfWork.bind(session).api.project.get(project_id)
    except ProjectNotFoundError:
        return base

    title = (project.name or "").strip() or base.title
    audience = base.audience
    purpose = base.purpose
    core_message = base.core_message
    sections = base.sections
    target_slide_count = base.target_slide_count

    context = f"{title} {(project.description or '')}".lower()
    if any(hint in context for hint in _HERITAGE_HINTS):
        audience = "主管部门 / 专家委员会"
        purpose = "争取立项认可与下一步工作共识"
        core_message = "原址重建的文化价值、设计定位与实施路径"
        sections = "历史沿革与损毁\n重建定位\n空间策略\n实施计划"
        target_slide_count = 8
    elif any(hint in context for hint in _HOSPITAL_HINTS):
        audience = "医院管理层"
        purpose = "确认总体改造方向"
        core_message = "通过交通重组改善院区体验"
        sections = "现状分析\n改造策略\n实施计划"

    for event in project.intent_evolution.events:
        if event.kind == IntentEvolutionKind.SEED and (event.summary or "").strip():
            seed = event.summary.strip()
            if len(seed) > 20:
                core_message = seed[:400]
                if purpose == base.purpose or _looks_like_internal_assessment(purpose):
                    purpose = "形成前期策划与概念设计汇报，明确重建定位与决策路径"
            break


    deck_rows = list_project_presentations(session, project_id)
    if deck_rows:
        deck = max(deck_rows, key=lambda item: item.updated_at)
        briefs = UnitOfWork.bind(session).api.slides.list_briefs(deck.id)
        if briefs:
            brief = briefs[-1]
            if (brief.title or "").strip():
                title = brief.title.strip()
            if (brief.audience or "").strip() and not _looks_like_placeholder_audience(
                brief.audience
            ):
                audience = brief.audience.strip()
            if (brief.purpose or "").strip() and not _looks_like_internal_assessment(
                brief.purpose
            ):
                purpose = brief.purpose.strip()
            if (brief.core_message or "").strip() and not _looks_like_internal_assessment(
                brief.core_message
            ):
                core_message = brief.core_message.strip()
            if brief.required_sections:
                sections = "\n".join(
                    section.strip()
                    for section in brief.required_sections
                    if str(section).strip()
                )
            if brief.target_slide_count:
                target_slide_count = int(brief.target_slide_count)

        outline = None
        if deck.current_outline_id is not None:
            outline = presentations.get_outline(deck.current_outline_id)
        if outline is None:
            outlines = presentations.list_outlines(deck.id)
            outline = outlines[0] if outlines else None
        if outline is not None:
            section_titles = [
                section.title.strip()
                for section in outline.sections
                if getattr(section, "title", None) and str(section.title).strip()
            ]
            if section_titles:
                sections = "\n".join(section_titles)
            page_count = len(outline.page_intents) or len(outline.sections)
            if page_count > 0:
                target_slide_count = page_count

    return GenerationFormDefaults(
        title=title,
        audience=audience,
        purpose=purpose,
        core_message=core_message,
        sections=sections,
        target_slide_count=target_slide_count,
    )


def list_projects(session: Session, actor_id: str | None = None) -> list[Project]:
    """List projects visible to ``actor_id`` (default: session / local-user)."""
    from archium.application.project_access_service import ProjectAccessService
    from archium.domain.access import LOCAL_ACTOR_ID

    resolved = actor_id
    if resolved is None:
        try:
            from archium.ui.session_actor import get_current_actor_id

            resolved = get_current_actor_id()
        except Exception:
            resolved = LOCAL_ACTOR_ID
    return ProjectAccessService(session).list_visible_projects(resolved)


def create_project(
    session: Session,
    *,
    name: str,
    project_type: ProjectType,
    description: str = "",
    origin_mode: ProjectOriginMode = ProjectOriginMode.EXISTING_PROJECT,
    actor_id: str | None = None,
) -> Project:
    return UnitOfWork.bind(session).api.project.create(
        name.strip(),
        description.strip() or None,
        origin_mode=origin_mode,
        actor_id=actor_id,
        project_type=project_type,
    )


def get_project_overview(session: Session, project_id: UUID) -> ProjectOverview | None:
    api = UnitOfWork.bind(session).api
    try:
        project = api.project.get(project_id)
    except ProjectNotFoundError:
        return None
    return ProjectOverview(
        project=project,
        document_count=api.documents.count(project_id),
        chunk_count=api.documents.count_chunks(project_id),
        presentation_count=api.project.count_presentations(project_id),
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
    return UnitOfWork.bind(session).api.documents.list(project_id)


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
    return UnitOfWork.bind(session).api.project.list_presentations(project_id)


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
    attach_visual_idea_seed: bool = True,
) -> ImportItemResult:
    suffix = Path(filename).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(data)
        temp_path = Path(temp_file.name)
    try:
        from archium.application.api.documents import DocumentsApi
        from archium.ui.session_actor import get_current_actor_id

        result = DocumentsApi(session, settings=settings).upload_file(
            project_id, temp_path, actor_id=get_current_actor_id()
        )
        # Keep user-facing filename (temp path is opaque).
        result.source_path = Path(filename)
    finally:
        temp_path.unlink(missing_ok=True)

    if (
        attach_visual_idea_seed
        and result.error is None
        and not result.duplicate
        and result.assets
    ):
        try:
            from archium.application.visual_idea_seed import maybe_attach_visual_idea_seed

            seed_result = maybe_attach_visual_idea_seed(
                session,
                project_id,
                assets=result.assets,
                document=result.document,
                settings=settings,
            )
            if seed_result.attached:
                result.visual_idea_seed_message = seed_result.message
                if result.document is not None:
                    meta = dict(result.document.metadata or {})
                    meta["visual_idea_seed"] = {
                        "attached": True,
                        "created_session": seed_result.created_session,
                        "merged": seed_result.merged,
                        "exploration_id": (
                            str(seed_result.exploration_id)
                            if seed_result.exploration_id
                            else None
                        ),
                        "message": seed_result.message,
                        "source": seed_result.source,
                    }
                    result.document.metadata = meta
        except Exception:
            # Never fail the import path on weak-seed attach.
            pass

    if reassess:
        reassess_knowledge_after_upload(session, project_id, settings=settings)
    try:
        from archium.application.genesis_starter_service import sync_starter_deck_after_materials

        sync_starter_deck_after_materials(session, project_id, commit=True)
    except Exception:
        # Never fail the import path on starter-deck sync.
        pass
    return result


def reassess_knowledge_after_upload(
    session: Session,
    project_id: UUID,
    *,
    settings: Settings | None = None,
) -> UploadKnowledgeTip | None:
    """Refresh KnowledgeState after new evidence; never fail the import path."""
    from archium.application.context import best_effort_reassess_knowledge

    resolved = _resolve_runtime_settings(settings)
    assessment = best_effort_reassess_knowledge(
        session,
        project_id,
        settings=resolved,
        reason="document_uploaded",
    )
    if assessment is None:
        return None

    actions = sorted(assessment.actions, key=lambda item: item.priority)
    labels: list[str] = []
    primary_action: str | None = None
    primary_label = ""
    pending = 0
    conflicts = 0
    try:
        from archium.application.fact_ledger_service import FactLedgerService

        ledger = FactLedgerService(session).get_ledger(project_id)
        pending = ledger.pending_count
        conflicts = ledger.conflict_count
    except Exception:
        from archium.logging import get_logger

        get_logger(__name__).debug(
            'fact ledger unavailable for workspace actions',
            exc_info=True,
        )
    for item in actions[:3]:
        if item.action.value == "upload_materials":
            continue
        from archium.application.context import resolve_action_target

        dispatch = resolve_action_target(
            item.action,
            pending_fact_count=pending,
            conflict_fact_count=conflicts,
        )
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
    from archium.application._helpers import build_project_context_bundle

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
    from archium.ui.session_actor import get_current_actor_id

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
        actor_id=get_current_actor_id(),
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
    """Continue a presentation workflow from its LangGraph interrupt/checkpoint (WF-004)."""
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
    """Export editable PPTX via DeliveryApi (Scene preferred; Spec fallback)."""
    resolved_settings = _resolve_runtime_settings(settings)
    return UnitOfWork.bind(session).api.delivery.reexport(
        presentation_id,
        export_json=False,
        export_marp=False,
        export_editable_pptx=True,
        settings=resolved_settings,
    )
