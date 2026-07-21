"""Convert between ORM models and Pydantic domain models."""

from __future__ import annotations

from uuid import UUID

from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.cultural_narrative import (
    CULTURAL_NARRATIVE_LOGICAL_KEY,
    CulturalNarrativePlan,
)
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    ApprovalStatus,
    AssetType,
    DocumentType,
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    OutlineAudienceMode,
    PlanningSessionStatus,
    PresentationStatus,
    PresentationType,
    ProcessingStatus,
    ProjectStage,
    ProjectStatus,
    ProjectType,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    RevisionEntityType,
    RevisionSource,
    SlideStatus,
    SlideType,
    VerificationStatus,
    WorkflowStatus,
)
from archium.domain.fact import FactValue, ProjectFact
from archium.domain.memory import UserPreference
from archium.domain.outline import OUTLINE_LOGICAL_KEY, OutlinePlan, OutlineSection
from archium.domain.planning_session import PlanningSession
from archium.domain.presentation import (
    BRIEF_LOGICAL_KEY,
    STORYLINE_LOGICAL_KEY,
    Chapter,
    Presentation,
    PresentationBrief,
    Storyline,
)
from archium.domain.narrative_arc import NarrativeArc
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.reference_style import (
    REFERENCE_STYLE_PROFILE_LOGICAL_KEY,
    ReferenceStyleProfile,
)
from archium.domain.renovation_issue import RENOVATION_ISSUE_MAP_LOGICAL_KEY, RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec, VisualRequirement, build_slide_logical_key
from archium.domain.visual_qa import VisualQAReport
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.models import (
    AssetORM,
    ChapterORM,
    CulturalNarrativePlanORM,
    DocumentChunkORM,
    OutlinePlanORM,
    PlanningSessionORM,
    PresentationBriefORM,
    PresentationManuscriptORM,
    PresentationORM,
    ProjectFactORM,
    ProjectKnowledgeItemORM,
    ProjectORM,
    ReferenceStyleProfileORM,
    RenovationIssueMapORM,
    ReviewIssueORM,
    SlideORM,
    SlideRevisionORM,
    SourceDocumentORM,
    StorylineORM,
    UserPreferenceORM,
    VisualQAReportORM,
    WorkflowRunORM,
)


def citations_to_json(citations: list[Citation]) -> list[dict[str, object]]:
    return [c.model_dump(mode="json") for c in citations]


def citations_from_json(data: list[dict[str, object]]) -> list[Citation]:
    return [Citation.model_validate(item) for item in data]


def source_citations_to_json(citations: list[SourceCitation]) -> list[dict[str, object]]:
    return [c.model_dump(mode="json") for c in citations]


def source_citations_from_json(data: list[dict[str, object]]) -> list[SourceCitation]:
    return [SourceCitation.model_validate(item) for item in data]


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
        conflict_group=orm.conflict_group,
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
    target.conflict_group = domain.conflict_group
    target.source_citations_json = citations_to_json(domain.source_citations)
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── ProjectKnowledgeItem ───────────────────────────────────────


def project_knowledge_item_to_domain(orm: ProjectKnowledgeItemORM) -> ProjectKnowledgeItem:
    return ProjectKnowledgeItem(
        id=orm.id,
        project_id=orm.project_id,
        statement=orm.statement,
        origin=InformationOrigin(orm.origin),
        reliability=InformationReliability(orm.reliability),
        source_citations=source_citations_from_json(orm.source_citations_json),
        applies_to_current_project=orm.applies_to_current_project,
        requires_user_confirmation=orm.requires_user_confirmation,
        conflict_group=orm.conflict_group,
        status=KnowledgeItemStatus(orm.status),
        category=orm.category,
        linked_fact_id=orm.linked_fact_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_knowledge_item_to_orm(
    domain: ProjectKnowledgeItem,
    orm: ProjectKnowledgeItemORM | None = None,
) -> ProjectKnowledgeItemORM:
    target = orm or ProjectKnowledgeItemORM(id=domain.id)
    target.project_id = domain.project_id
    target.statement = domain.statement
    target.origin = domain.origin.value
    target.reliability = domain.reliability.value
    target.source_citations_json = source_citations_to_json(domain.source_citations)
    target.applies_to_current_project = domain.applies_to_current_project
    target.requires_user_confirmation = domain.requires_user_confirmation
    target.conflict_group = domain.conflict_group
    target.status = domain.status.value
    target.category = domain.category
    target.linked_fact_id = domain.linked_fact_id
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
        current_outline_id=orm.current_outline_id,
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
    target.current_outline_id = domain.current_outline_id
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── PresentationBrief ──────────────────────────────────────────


def presentation_brief_to_domain(orm: PresentationBriefORM) -> PresentationBrief:
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or BRIEF_LOGICAL_KEY
    return PresentationBrief(
        id=orm.id,
        project_id=orm.project_id,
        presentation_id=orm.presentation_id,
        lineage_id=lineage_id,
        logical_key=logical_key,
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
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
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
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or STORYLINE_LOGICAL_KEY
    arc_payload = getattr(orm, "narrative_arc_json", None)
    narrative_arc = NarrativeArc.model_validate(arc_payload) if arc_payload else None
    return Storyline(
        id=orm.id,
        presentation_id=orm.presentation_id,
        lineage_id=lineage_id,
        logical_key=logical_key,
        thesis=orm.thesis,
        narrative_pattern=orm.narrative_pattern,
        narrative_arc=narrative_arc,
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
    target.narrative_arc_json = (
        domain.narrative_arc.model_dump(mode="json") if domain.narrative_arc else None
    )
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    target.chapters = [chapter_to_orm(ch, domain.id) for ch in domain.chapters]
    return target


# ── OutlinePlan ────────────────────────────────────────────────


def _outline_sections_to_json(sections: list[OutlineSection]) -> list[dict[str, object]]:
    return [section.model_dump(mode="json") for section in sections]


def _outline_sections_from_json(data: list[dict[str, object]]) -> list[OutlineSection]:
    return [OutlineSection.model_validate(item) for item in data]


def outline_plan_to_domain(orm: OutlinePlanORM) -> OutlinePlan:
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or OUTLINE_LOGICAL_KEY
    return OutlinePlan(
        id=orm.id,
        presentation_id=orm.presentation_id,
        manuscript_id=getattr(orm, "manuscript_id", None),
        lineage_id=lineage_id,
        logical_key=logical_key,
        title=orm.title,
        thesis=orm.thesis,
        audience=orm.audience,
        purpose=orm.purpose,
        target_slide_count=orm.target_slide_count,
        audience_mode=OutlineAudienceMode(orm.audience_mode),
        sections=_outline_sections_from_json(orm.sections_json),
        version=orm.version,
        approval_status=ApprovalStatus(orm.approval_status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def outline_plan_to_orm(domain: OutlinePlan, orm: OutlinePlanORM | None = None) -> OutlinePlanORM:
    target = orm or OutlinePlanORM(id=domain.id)
    target.presentation_id = domain.presentation_id
    target.manuscript_id = domain.manuscript_id
    target.title = domain.title
    target.thesis = domain.thesis
    target.audience = domain.audience
    target.purpose = domain.purpose
    target.target_slide_count = domain.target_slide_count
    target.audience_mode = domain.audience_mode.value
    target.sections_json = _outline_sections_to_json(domain.sections)
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


def presentation_manuscript_to_domain(orm: PresentationManuscriptORM) -> PresentationManuscript:
    payload = dict(orm.payload_json or {})
    payload.update(
        {
            "id": orm.id,
            "project_id": orm.project_id,
            "presentation_id": orm.presentation_id,
            "title": orm.title,
            "status": orm.status,
            "version": orm.version,
            "lineage_id": orm.lineage_id,
            "logical_key": orm.logical_key,
            "created_at": orm.created_at,
            "updated_at": orm.updated_at,
        }
    )
    return PresentationManuscript.model_validate(payload)


def presentation_manuscript_to_orm(
    domain: PresentationManuscript,
    orm: PresentationManuscriptORM | None = None,
) -> PresentationManuscriptORM:
    target = orm or PresentationManuscriptORM(id=domain.id)
    target.project_id = domain.project_id
    target.presentation_id = domain.presentation_id
    target.title = domain.title
    target.status = domain.status.value
    target.version = domain.version
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    payload = domain.model_dump(mode="json")
    for key in (
        "id",
        "project_id",
        "presentation_id",
        "title",
        "status",
        "version",
        "lineage_id",
        "logical_key",
        "created_at",
        "updated_at",
    ):
        payload.pop(key, None)
    target.payload_json = payload
    return target


    return target


# ── CulturalNarrativePlan ─────────────────────────────────────


def _cultural_narrative_payload_from_domain(plan: CulturalNarrativePlan) -> dict[str, object]:
    data = plan.model_dump(mode="json")
    for key in (
        "id",
        "project_id",
        "version",
        "approval_status",
        "lineage_id",
        "logical_key",
        "created_at",
        "updated_at",
    ):
        data.pop(key, None)
    return data


def cultural_narrative_plan_to_domain(orm: CulturalNarrativePlanORM) -> CulturalNarrativePlan:
    payload = dict(orm.payload_json or {})
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or CULTURAL_NARRATIVE_LOGICAL_KEY
    return CulturalNarrativePlan.model_validate(
        {
            **payload,
            "id": orm.id,
            "project_id": orm.project_id,
            "version": orm.version,
            "approval_status": orm.approval_status,
            "lineage_id": lineage_id,
            "logical_key": logical_key,
            "created_at": orm.created_at,
            "updated_at": orm.updated_at,
        }
    )


def cultural_narrative_plan_to_orm(
    domain: CulturalNarrativePlan,
    orm: CulturalNarrativePlanORM | None = None,
) -> CulturalNarrativePlanORM:
    target = orm or CulturalNarrativePlanORM(id=domain.id)
    target.project_id = domain.project_id
    target.payload_json = _cultural_narrative_payload_from_domain(domain)
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── RenovationIssueMap ─────────────────────────────────────────


def _renovation_issue_map_payload_from_domain(plan: RenovationIssueMap) -> dict[str, object]:
    data = plan.model_dump(mode="json")
    for key in (
        "id",
        "project_id",
        "version",
        "approval_status",
        "lineage_id",
        "logical_key",
        "created_at",
        "updated_at",
    ):
        data.pop(key, None)
    return data


def renovation_issue_map_to_domain(orm: RenovationIssueMapORM) -> RenovationIssueMap:
    payload = dict(orm.payload_json or {})
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or RENOVATION_ISSUE_MAP_LOGICAL_KEY
    return RenovationIssueMap.model_validate(
        {
            **payload,
            "id": orm.id,
            "project_id": orm.project_id,
            "version": orm.version,
            "approval_status": orm.approval_status,
            "lineage_id": lineage_id,
            "logical_key": logical_key,
            "created_at": orm.created_at,
            "updated_at": orm.updated_at,
        }
    )


def renovation_issue_map_to_orm(
    domain: RenovationIssueMap,
    orm: RenovationIssueMapORM | None = None,
) -> RenovationIssueMapORM:
    target = orm or RenovationIssueMapORM(id=domain.id)
    target.project_id = domain.project_id
    target.payload_json = _renovation_issue_map_payload_from_domain(domain)
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── ReferenceStyleProfile ──────────────────────────────────────


def _reference_style_profile_payload_from_domain(
    profile: ReferenceStyleProfile,
) -> dict[str, object]:
    data = profile.model_dump(mode="json")
    for key in (
        "id",
        "project_id",
        "version",
        "approval_status",
        "lineage_id",
        "logical_key",
        "created_at",
        "updated_at",
    ):
        data.pop(key, None)
    return data


def reference_style_profile_to_domain(orm: ReferenceStyleProfileORM) -> ReferenceStyleProfile:
    payload = dict(orm.payload_json or {})
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or REFERENCE_STYLE_PROFILE_LOGICAL_KEY
    return ReferenceStyleProfile.model_validate(
        {
            **payload,
            "id": orm.id,
            "project_id": orm.project_id,
            "version": orm.version,
            "approval_status": orm.approval_status,
            "lineage_id": lineage_id,
            "logical_key": logical_key,
            "created_at": orm.created_at,
            "updated_at": orm.updated_at,
        }
    )


def reference_style_profile_to_orm(
    domain: ReferenceStyleProfile,
    orm: ReferenceStyleProfileORM | None = None,
) -> ReferenceStyleProfileORM:
    target = orm or ReferenceStyleProfileORM(id=domain.id)
    target.project_id = domain.project_id
    target.payload_json = _reference_style_profile_payload_from_domain(domain)
    target.version = domain.version
    target.approval_status = domain.approval_status.value
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── SlideSpec ──────────────────────────────────────────────────


def slide_to_domain(orm: SlideORM) -> SlideSpec:
    lineage_id = orm.lineage_id or orm.id
    logical_key = orm.logical_key or build_slide_logical_key(orm.chapter_id, orm.order)
    return SlideSpec(
        id=orm.id,
        presentation_id=orm.presentation_id,
        lineage_id=lineage_id,
        logical_key=logical_key,
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
        visual_intent_id=getattr(orm, "visual_intent_id", None),
        layout_plan_id=getattr(orm, "layout_plan_id", None),
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
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key or build_slide_logical_key(domain.chapter_id, domain.order)
    target.visual_intent_id = domain.visual_intent_id
    target.layout_plan_id = domain.layout_plan_id
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
        reviewer_layer=ReviewLayer(getattr(orm, "reviewer_layer", ReviewLayer.CONTENT.value)),
        category=ReviewCategory(orm.category),
        severity=ReviewSeverity(orm.severity),
        rule_code=getattr(orm, "rule_code", "LEGACY.UNSPECIFIED"),
        title=orm.title,
        description=orm.description,
        suggestion=orm.suggestion,
        auto_fixable=orm.auto_fixable,
        status=ReviewStatus(orm.status),
        confidence=orm.confidence,
        detection_method=orm.detection_method,
        requires_confirmation=orm.requires_confirmation,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def review_issue_to_orm(domain: ReviewIssue, orm: ReviewIssueORM | None = None) -> ReviewIssueORM:
    target = orm or ReviewIssueORM(id=domain.id)
    target.presentation_id = domain.presentation_id
    target.slide_id = domain.slide_id
    target.reviewer_layer = domain.reviewer_layer.value
    target.category = domain.category.value
    target.severity = domain.severity.value
    target.rule_code = domain.rule_code
    target.title = domain.title
    target.description = domain.description
    target.suggestion = domain.suggestion
    target.auto_fixable = domain.auto_fixable
    target.status = domain.status.value
    target.confidence = domain.confidence
    target.detection_method = domain.detection_method
    target.requires_confirmation = domain.requires_confirmation
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


def visual_qa_report_to_domain(orm: VisualQAReportORM) -> VisualQAReport:
    payload = dict(orm.report_json)
    payload.setdefault("analyzer_version", orm.analyzer_version)
    payload.setdefault("file_hash", orm.file_hash)
    return VisualQAReport.model_validate(payload)


def visual_qa_report_to_orm(
    report: VisualQAReport,
    *,
    file_hash: str,
    analyzer_version: str,
    orm: VisualQAReportORM | None = None,
) -> VisualQAReportORM:
    target = orm or VisualQAReportORM()
    target.asset_id = report.asset_id
    target.file_hash = file_hash
    target.analyzer_version = analyzer_version
    target.report_json = report.model_dump(mode="json")
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


def planning_session_to_domain(orm: PlanningSessionORM) -> PlanningSession:
    return PlanningSession(
        id=orm.id,
        project_id=orm.project_id,
        status=PlanningSessionStatus(orm.status),
        current_mission_id=orm.current_mission_id,
        workflow_run_id=orm.workflow_run_id,
        presentation_id=orm.presentation_id,
        user_task_description=orm.user_task_description or "",
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def planning_session_to_orm(
    domain: PlanningSession,
    orm: PlanningSessionORM | None = None,
) -> PlanningSessionORM:
    target = orm or PlanningSessionORM(id=domain.id)
    target.project_id = domain.project_id
    target.status = domain.status.value
    target.current_mission_id = domain.current_mission_id
    target.workflow_run_id = domain.workflow_run_id
    target.presentation_id = domain.presentation_id
    target.user_task_description = domain.user_task_description
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


def entity_revision_to_domain(orm: SlideRevisionORM) -> EntityRevision:
    return EntityRevision(
        id=orm.id,
        entity_type=RevisionEntityType(orm.entity_type),
        entity_id=orm.entity_id,
        lineage_id=orm.lineage_id,
        presentation_id=orm.presentation_id,
        revision_number=orm.revision_number,
        change_source=RevisionSource(orm.change_source),
        snapshot=dict(orm.snapshot_json),
        note=orm.note,
        actor=orm.actor,
        created_at=orm.created_at,
    )


def entity_revision_to_orm(
    domain: EntityRevision,
    orm: SlideRevisionORM | None = None,
) -> SlideRevisionORM:
    target = orm or SlideRevisionORM(id=domain.id)
    target.entity_type = domain.entity_type.value
    target.entity_id = domain.entity_id
    target.lineage_id = domain.lineage_id
    target.presentation_id = domain.presentation_id
    target.revision_number = domain.revision_number
    target.change_source = domain.change_source.value
    target.snapshot_json = dict(domain.snapshot)
    target.note = domain.note
    target.actor = domain.actor
    if domain.created_at is not None:
        target.created_at = domain.created_at
    return target


slide_revision_to_domain = entity_revision_to_domain
slide_revision_to_orm = entity_revision_to_orm
