"""Convert between ORM models and Pydantic domain models."""

from __future__ import annotations

from uuid import UUID

from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    ApprovalStatus,
    AssetType,
    DocumentType,
    PresentationStatus,
    PresentationType,
    ProcessingStatus,
    ProjectStage,
    ProjectStatus,
    ProjectType,
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    SlideStatus,
    SlideChangeSource,
    SlideType,
    VerificationStatus,
    WorkflowStatus,
)
from archium.domain.fact import FactValue, ProjectFact
from archium.domain.memory import UserPreference
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_history import SlideRevision
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.models import (
    AssetORM,
    ChapterORM,
    DocumentChunkORM,
    PresentationBriefORM,
    PresentationORM,
    ProjectFactORM,
    ProjectORM,
    ReviewIssueORM,
    SlideORM,
    SlideRevisionORM,
    SourceDocumentORM,
    StorylineORM,
    UserPreferenceORM,
    WorkflowRunORM,
)


def citations_to_json(citations: list[Citation]) -> list[dict[str, object]]:
    return [c.model_dump(mode="json") for c in citations]


def citations_from_json(data: list[dict[str, object]]) -> list[Citation]:
    return [Citation.model_validate(item) for item in data]


def visual_requirements_to_json(items: list[VisualRequirement]) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in items]


def visual_requirements_from_json(data: list[dict[str, object]]) -> list[VisualRequirement]:
    return [VisualRequirement.model_validate(item) for item in data]


# ── Project ──────────────────────────────────────────────────


def project_to_domain(orm: ProjectORM) -> Project:
    return Project(
        id=orm.id,
        name=orm.name,
        code=orm.code,
        description=orm.description,
        project_type=ProjectType(orm.project_type),
        stage=ProjectStage(orm.stage),
        location=orm.location,
        client=orm.client,
        status=ProjectStatus(orm.status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_to_orm(domain: Project, orm: ProjectORM | None = None) -> ProjectORM:
    target = orm or ProjectORM(id=domain.id)
    target.name = domain.name
    target.code = domain.code
    target.description = domain.description
    target.project_type = domain.project_type.value
    target.stage = domain.stage.value
    target.location = domain.location
    target.client = domain.client
    target.status = domain.status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── SourceDocument ───────────────────────────────────────────


def source_document_to_domain(orm: SourceDocumentORM) -> SourceDocument:
    return SourceDocument(
        id=orm.id,
        project_id=orm.project_id,
        filename=orm.filename,
        original_path=orm.original_path,
        stored_path=orm.stored_path,
        file_type=DocumentType(orm.file_type),
        file_hash=orm.file_hash,
        size_bytes=orm.size_bytes,
        page_count=orm.page_count,
        processing_status=ProcessingStatus(orm.processing_status),
        metadata=orm.metadata_json,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def source_document_to_orm(
    domain: SourceDocument, orm: SourceDocumentORM | None = None
) -> SourceDocumentORM:
    target = orm or SourceDocumentORM(id=domain.id)
    target.project_id = domain.project_id
    target.filename = domain.filename
    target.original_path = domain.original_path
    target.stored_path = domain.stored_path
    target.file_type = domain.file_type.value
    target.file_hash = domain.file_hash
    target.size_bytes = domain.size_bytes
    target.page_count = domain.page_count
    target.processing_status = domain.processing_status.value
    target.metadata_json = domain.metadata
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── DocumentChunk ────────────────────────────────────────────


def document_chunk_to_domain(orm: DocumentChunkORM) -> DocumentChunk:
    return DocumentChunk(
        id=orm.id,
        project_id=orm.project_id,
        document_id=orm.document_id,
        content=orm.content,
        page_number=orm.page_number,
        section_title=orm.section_title,
        content_type=orm.content_type,
        chunk_index=orm.chunk_index,
        metadata=orm.metadata_json,
    )


def document_chunk_to_orm(
    domain: DocumentChunk, orm: DocumentChunkORM | None = None
) -> DocumentChunkORM:
    target = orm or DocumentChunkORM(id=domain.id)
    target.project_id = domain.project_id
    target.document_id = domain.document_id
    target.content = domain.content
    target.page_number = domain.page_number
    target.section_title = domain.section_title
    target.content_type = domain.content_type
    target.chunk_index = domain.chunk_index
    target.metadata_json = domain.metadata
    return target


# ── ProjectFact ────────────────────────────────────────────────


def project_fact_to_domain(orm: ProjectFactORM) -> ProjectFact:
    value: FactValue = orm.value_json  # type: ignore[assignment]
    return ProjectFact(
        id=orm.id,
        project_id=orm.project_id,
        key=orm.key,
        label=orm.label,
        value=value,
        unit=orm.unit,
        category=orm.category,
        confidence=orm.confidence,
        verification_status=VerificationStatus(orm.verification_status),
        source_citations=citations_from_json(orm.source_citations_json),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_fact_to_orm(domain: ProjectFact, orm: ProjectFactORM | None = None) -> ProjectFactORM:
    target = orm or ProjectFactORM(id=domain.id)
    target.project_id = domain.project_id
    target.key = domain.key
    target.label = domain.label
    target.value_json = domain.value
    target.unit = domain.unit
    target.category = domain.category
    target.confidence = domain.confidence
    target.verification_status = domain.verification_status.value
    target.source_citations_json = citations_to_json(domain.source_citations)
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── Presentation ───────────────────────────────────────────────


def presentation_to_domain(orm: PresentationORM) -> Presentation:
    return Presentation(
        id=orm.id,
        project_id=orm.project_id,
        title=orm.title,
        status=PresentationStatus(orm.status),
        description=orm.description,
        current_brief_id=orm.current_brief_id,
        current_storyline_id=orm.current_storyline_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def presentation_to_orm(
    domain: Presentation, orm: PresentationORM | None = None
) -> PresentationORM:
    target = orm or PresentationORM(id=domain.id)
    target.project_id = domain.project_id
    target.title = domain.title
    target.status = domain.status.value
    target.description = domain.description
    target.current_brief_id = domain.current_brief_id
    target.current_storyline_id = domain.current_storyline_id
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── PresentationBrief ──────────────────────────────────────────


def presentation_brief_to_domain(orm: PresentationBriefORM) -> PresentationBrief:
    return PresentationBrief(
        id=orm.id,
        project_id=orm.project_id,
        presentation_id=orm.presentation_id,
        title=orm.title,
        presentation_type=PresentationType(orm.presentation_type),
        audience=orm.audience,
        purpose=orm.purpose,
        duration_minutes=orm.duration_minutes,
        target_slide_count=orm.target_slide_count,
        core_message=orm.core_message,
        decisions_required=list(orm.decisions_required_json),
        audience_concerns=list(orm.audience_concerns_json),
        tone=orm.tone,
        required_sections=list(orm.required_sections_json),
        excluded_topics=list(orm.excluded_topics_json),
        language=orm.language,
        version=orm.version,
        approval_status=ApprovalStatus(orm.approval_status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def presentation_brief_to_orm(
    domain: PresentationBrief, orm: PresentationBriefORM | None = None
) -> PresentationBriefORM:
    target = orm or PresentationBriefORM(id=domain.id)
    target.project_id = domain.project_id
    target.presentation_id = domain.presentation_id
    target.title = domain.title
    target.presentation_type = domain.presentation_type.value
    target.audience = domain.audience
    target.purpose = domain.purpose
    target.duration_minutes = domain.duration_minutes
    target.target_slide_count = domain.target_slide_count
    target.core_message = domain.core_message
    target.decisions_required_json = list(domain.decisions_required)
    target.audience_concerns_json = list(domain.audience_concerns)
    target.tone = domain.tone
    target.required_sections_json = list(domain.required_sections)
    target.excluded_topics_json = list(domain.excluded_topics)
    target.language = domain.language
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── Storyline & Chapter ────────────────────────────────────────


def chapter_to_domain(orm: ChapterORM) -> Chapter:
    return Chapter(
        id=orm.chapter_key,
        title=orm.title,
        purpose=orm.purpose,
        key_message=orm.key_message,
        order=orm.order,
        estimated_slide_count=orm.estimated_slide_count,
    )


def chapter_to_orm(domain: Chapter, storyline_id: UUID, orm: ChapterORM | None = None) -> ChapterORM:
    target = orm or ChapterORM()
    target.storyline_id = storyline_id
    target.chapter_key = domain.id
    target.title = domain.title
    target.purpose = domain.purpose
    target.key_message = domain.key_message
    target.order = domain.order
    target.estimated_slide_count = domain.estimated_slide_count
    return target


def storyline_to_domain(orm: StorylineORM) -> Storyline:
    return Storyline(
        id=orm.id,
        presentation_id=orm.presentation_id,
        thesis=orm.thesis,
        narrative_pattern=orm.narrative_pattern,
        chapters=[chapter_to_domain(ch) for ch in orm.chapters],
        version=orm.version,
        approval_status=ApprovalStatus(orm.approval_status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def storyline_to_orm(domain: Storyline, orm: StorylineORM | None = None) -> StorylineORM:
    target = orm or StorylineORM(id=domain.id)
    target.presentation_id = domain.presentation_id
    target.thesis = domain.thesis
    target.narrative_pattern = domain.narrative_pattern
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    target.chapters = [chapter_to_orm(ch, domain.id) for ch in domain.chapters]
    return target


# ── SlideSpec ──────────────────────────────────────────────────


def slide_to_domain(orm: SlideORM) -> SlideSpec:
    return SlideSpec(
        id=orm.id,
        presentation_id=orm.presentation_id,
        chapter_id=orm.chapter_id,
        order=orm.order,
        title=orm.title,
        message=orm.message,
        slide_type=SlideType(orm.slide_type),
        layout_id=orm.layout_id,
        key_points=list(orm.key_points_json),
        visual_requirements=visual_requirements_from_json(orm.visual_requirements_json),
        source_citations=citations_from_json(orm.source_citations_json),
        speaker_notes=orm.speaker_notes,
        status=SlideStatus(orm.status),
        version=orm.version,
    )


def slide_to_orm(domain: SlideSpec, orm: SlideORM | None = None) -> SlideORM:
    target = orm or SlideORM(id=domain.id)
    target.presentation_id = domain.presentation_id
    target.chapter_id = domain.chapter_id
    target.order = domain.order
    target.title = domain.title
    target.message = domain.message
    target.slide_type = domain.slide_type.value
    target.layout_id = domain.layout_id
    target.key_points_json = list(domain.key_points)
    target.visual_requirements_json = visual_requirements_to_json(domain.visual_requirements)
    target.source_citations_json = citations_to_json(domain.source_citations)
    target.speaker_notes = domain.speaker_notes
    target.status = domain.status.value
    target.version = domain.version
    return target


# ── Asset ──────────────────────────────────────────────────────


def asset_to_domain(orm: AssetORM) -> Asset:
    return Asset(
        id=orm.id,
        project_id=orm.project_id,
        document_id=orm.document_id,
        filename=orm.filename,
        path=orm.path,
        asset_type=AssetType(orm.asset_type),
        width=orm.width,
        height=orm.height,
        page_number=orm.page_number,
        description=orm.description,
        tags=list(orm.tags_json),
        quality_score=orm.quality_score,
        metadata=orm.metadata_json,
    )


def asset_to_orm(domain: Asset, orm: AssetORM | None = None) -> AssetORM:
    target = orm or AssetORM(id=domain.id)
    target.project_id = domain.project_id
    target.document_id = domain.document_id
    target.filename = domain.filename
    target.path = domain.path
    target.asset_type = domain.asset_type.value
    target.width = domain.width
    target.height = domain.height
    target.page_number = domain.page_number
    target.description = domain.description
    target.tags_json = list(domain.tags)
    target.quality_score = domain.quality_score
    target.metadata_json = domain.metadata
    return target


# ── ReviewIssue ────────────────────────────────────────────────


def review_issue_to_domain(orm: ReviewIssueORM) -> ReviewIssue:
    return ReviewIssue(
        id=orm.id,
        presentation_id=orm.presentation_id,
        slide_id=orm.slide_id,
        category=ReviewCategory(orm.category),
        severity=ReviewSeverity(orm.severity),
        title=orm.title,
        description=orm.description,
        suggestion=orm.suggestion,
        auto_fixable=orm.auto_fixable,
        status=ReviewStatus(orm.status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def review_issue_to_orm(domain: ReviewIssue, orm: ReviewIssueORM | None = None) -> ReviewIssueORM:
    target = orm or ReviewIssueORM(id=domain.id)
    target.presentation_id = domain.presentation_id
    target.slide_id = domain.slide_id
    target.category = domain.category.value
    target.severity = domain.severity.value
    target.title = domain.title
    target.description = domain.description
    target.suggestion = domain.suggestion
    target.auto_fixable = domain.auto_fixable
    target.status = domain.status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── UserPreference ─────────────────────────────────────────────


def user_preference_to_domain(orm: UserPreferenceORM) -> UserPreference:
    return UserPreference(
        id=orm.id,
        key=orm.key,
        value=orm.value_json,
        project_id=orm.project_id,
        description=orm.description,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def user_preference_to_orm(
    domain: UserPreference, orm: UserPreferenceORM | None = None
) -> UserPreferenceORM:
    target = orm or UserPreferenceORM(id=domain.id)
    target.key = domain.key
    target.value_json = domain.value
    target.project_id = domain.project_id
    target.description = domain.description
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── WorkflowRun ────────────────────────────────────────────────


def workflow_run_to_domain(orm: WorkflowRunORM) -> WorkflowRun:
    return WorkflowRun(
        id=orm.id,
        project_id=orm.project_id,
        presentation_id=orm.presentation_id,
        status=WorkflowStatus(orm.status),
        state=dict(orm.state_json),
        errors=list(orm.errors_json),
        output_files=list(orm.output_files_json),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def workflow_run_to_orm(domain: WorkflowRun, orm: WorkflowRunORM | None = None) -> WorkflowRunORM:
    target = orm or WorkflowRunORM(id=domain.id)
    target.project_id = domain.project_id
    target.presentation_id = domain.presentation_id
    target.status = domain.status.value
    target.state_json = dict(domain.state)
    target.errors_json = list(domain.errors)
    target.output_files_json = list(domain.output_files)
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


def slide_revision_to_domain(orm: SlideRevisionORM) -> SlideRevision:
    return SlideRevision(
        id=orm.id,
        slide_id=orm.slide_id,
        presentation_id=orm.presentation_id,
        revision_number=orm.revision_number,
        change_source=SlideChangeSource(orm.change_source),
        snapshot=dict(orm.snapshot_json),
        note=orm.note,
        created_at=orm.created_at,
    )


def slide_revision_to_orm(
    domain: SlideRevision,
    orm: SlideRevisionORM | None = None,
) -> SlideRevisionORM:
    target = orm or SlideRevisionORM(id=domain.id)
    target.slide_id = domain.slide_id
    target.presentation_id = domain.presentation_id
    target.revision_number = domain.revision_number
    target.change_source = domain.change_source.value
    target.snapshot_json = dict(domain.snapshot)
    target.note = domain.note
    if domain.created_at is not None:
        target.created_at = domain.created_at
    return target
