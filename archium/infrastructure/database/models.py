"""SQLAlchemy ORM models — separate from Pydantic domain models."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from archium.infrastructure.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class ProjectORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="concept")
    location: Mapped[str | None] = mapped_column(String(500))
    client: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")

    documents: Mapped[list[SourceDocumentORM]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    presentations: Mapped[list[PresentationORM]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    facts: Mapped[list[ProjectFactORM]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    assets: Mapped[list[AssetORM]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    missions: Mapped[list[ProjectMissionORM]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class SourceDocumentORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("project_id", "file_hash", name="uq_doc_project_hash"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    project: Mapped[ProjectORM] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunkORM]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunkORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    document: Mapped[SourceDocumentORM] = relationship(back_populates="chunks")


class ProjectFactORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_facts"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_fact_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    value_json: Mapped[object] = mapped_column("value", JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="extracted")
    conflict_group: Mapped[str | None] = mapped_column(String(100))
    source_citations_json: Mapped[list[dict[str, object]]] = mapped_column(
        "source_citations", JSON, default=list
    )

    project: Mapped[ProjectORM] = relationship(back_populates="facts")


class PresentationORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "presentations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text)
    current_brief_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    current_storyline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    project: Mapped[ProjectORM] = relationship(back_populates="presentations")
    briefs: Mapped[list[PresentationBriefORM]] = relationship(
        back_populates="presentation",
        cascade="all, delete-orphan",
    )
    storylines: Mapped[list[StorylineORM]] = relationship(
        back_populates="presentation",
        cascade="all, delete-orphan",
    )
    slides: Mapped[list[SlideORM]] = relationship(
        back_populates="presentation",
        cascade="all, delete-orphan",
    )
    review_issues: Mapped[list[ReviewIssueORM]] = relationship(
        back_populates="presentation",
        cascade="all, delete-orphan",
    )


class PresentationBriefORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "presentation_briefs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    presentation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    audience: Mapped[str] = mapped_column(String(500), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    target_slide_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    core_message: Mapped[str] = mapped_column(Text, nullable=False)
    decisions_required_json: Mapped[list[str]] = mapped_column("decisions_required", JSON, default=list)
    audience_concerns_json: Mapped[list[str]] = mapped_column("audience_concerns", JSON, default=list)
    tone: Mapped[str] = mapped_column(String(100), nullable=False, default="professional")
    required_sections_json: Mapped[list[str]] = mapped_column("required_sections", JSON, default=list)
    excluded_topics_json: Mapped[list[str]] = mapped_column("excluded_topics", JSON, default=list)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh-CN")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False, default="presentation-brief")

    presentation: Mapped[PresentationORM] = relationship(back_populates="briefs")


class StorylineORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "storylines"

    presentation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False
    )
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    narrative_pattern: Mapped[str] = mapped_column(String(100), nullable=False, default="problem_solution")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False, default="presentation-storyline")

    presentation: Mapped[PresentationORM] = relationship(back_populates="storylines")
    chapters: Mapped[list[ChapterORM]] = relationship(
        back_populates="storyline", order_by="ChapterORM.order"
    )


class ChapterORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chapters"

    storyline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("storylines.id", ondelete="CASCADE"), nullable=False
    )
    chapter_key: Mapped[str] = mapped_column("chapter_id", String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    key_message: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_slide_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    storyline: Mapped[StorylineORM] = relationship(back_populates="chapters")


class SlideORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "slides"

    presentation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    slide_type: Mapped[str] = mapped_column(String(30), nullable=False, default="content")
    layout_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    key_points_json: Mapped[list[str]] = mapped_column("key_points", JSON, default=list)
    visual_requirements_json: Mapped[list[dict[str, object]]] = mapped_column(
        "visual_requirements", JSON, default=list
    )
    source_citations_json: Mapped[list[dict[str, object]]] = mapped_column(
        "source_citations", JSON, default=list
    )
    speaker_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    visual_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    layout_plan_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    presentation: Mapped[PresentationORM] = relationship(back_populates="slides")


class SlideRevisionORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "entity_revisions"

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="slide")
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("presentations.id", ondelete="CASCADE"),
        nullable=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_source: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_json: Mapped[dict[str, object]] = mapped_column("snapshot", JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


EntityRevisionORM = SlideRevisionORM


class AssetORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_documents.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column("tags", JSON, default=list)
    quality_score: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    project: Mapped[ProjectORM] = relationship(back_populates="assets")


class CitationORM(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "citations"

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_facts.id", ondelete="CASCADE")
    )
    slide_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slides.id", ondelete="CASCADE")
    )


class ReviewIssueORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_issues"
    __table_args__ = (
        Index("ix_review_issues_rule_code", "rule_code"),
        Index("ix_review_issues_presentation_rule_code", "presentation_id", "rule_code"),
    )

    presentation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False
    )
    slide_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewer_layer: Mapped[str] = mapped_column(String(30), nullable=False, default="content")
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False, default="LEGACY.UNSPECIFIED")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text)
    auto_fixable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    confidence: Mapped[float | None] = mapped_column(Float)
    detection_method: Mapped[str | None] = mapped_column(String(100))
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    presentation: Mapped[PresentationORM] = relationship(back_populates="review_issues")


class VisualQAReportORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "visual_qa_reports"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "file_hash",
            "analyzer_version",
            name="uq_visual_qa_asset_hash_version",
        ),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class WorkflowRunORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    state_json: Mapped[dict[str, object]] = mapped_column("state", JSON, default=dict)
    errors_json: Mapped[list[str]] = mapped_column("errors", JSON, default=list)
    output_files_json: Mapped[list[str]] = mapped_column("output_files", JSON, default=list)


class PlanningSessionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_sessions"
    __table_args__ = (
        Index("ix_planning_sessions_project_id", "project_id"),
        Index("ix_planning_sessions_workflow_run_id", "workflow_run_id"),
        Index("ix_planning_sessions_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    current_mission_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_missions.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("presentations.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_task_description: Mapped[str] = mapped_column(Text, nullable=False, default="")



class UserPreferenceORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("key", "project_id", name="uq_pref_key_project"),)

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[object] = mapped_column("value", JSON, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    description: Mapped[str | None] = mapped_column(Text)


class ProjectMissionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_missions"
    __table_args__ = (
        Index("ix_project_missions_project_id", "project_id"),
        Index("ix_project_missions_lineage_id", "lineage_id"),
        Index("ix_project_missions_approval_status", "approval_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False, default="project-mission")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    task_statement: Mapped[str] = mapped_column(Text, nullable=False)
    task_natures_json: Mapped[list[str]] = mapped_column("task_natures", JSON, default=list)
    domains_json: Mapped[list[str]] = mapped_column("domains", JSON, default=list)
    intervention_scales_json: Mapped[list[str]] = mapped_column("intervention_scales", JSON, default=list)
    requested_service_depths_json: Mapped[list[str]] = mapped_column(
        "requested_service_depths", JSON, default=list
    )
    project_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_situation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    primary_problems_json: Mapped[list[str]] = mapped_column("primary_problems", JSON, default=list)
    desired_changes_json: Mapped[list[str]] = mapped_column("desired_changes", JSON, default=list)
    in_scope_json: Mapped[list[str]] = mapped_column("in_scope", JSON, default=list)
    out_of_scope_json: Mapped[list[str]] = mapped_column("out_of_scope", JSON, default=list)
    stakeholders_json: Mapped[list[dict[str, object]]] = mapped_column("stakeholders", JSON, default=list)
    decision_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decisions_required_json: Mapped[list[str]] = mapped_column("decisions_required", JSON, default=list)
    known_constraints_json: Mapped[list[dict[str, object]]] = mapped_column(
        "known_constraints", JSON, default=list
    )
    key_unknowns_json: Mapped[list[str]] = mapped_column("key_unknowns", JSON, default=list)
    research_questions_json: Mapped[list[str]] = mapped_column("research_questions", JSON, default=list)
    design_question_summaries_json: Mapped[list[str]] = mapped_column(
        "design_question_summaries", JSON, default=list
    )
    evaluation_criteria_json: Mapped[list[dict[str, object]]] = mapped_column(
        "evaluation_criteria", JSON, default=list
    )
    recommended_workstream_ids_json: Mapped[list[str]] = mapped_column(
        "recommended_workstream_ids", JSON, default=list
    )
    recommended_deliverable_ids_json: Mapped[list[str]] = mapped_column(
        "recommended_deliverable_ids", JSON, default=list
    )
    uncertainty_level: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[ProjectORM] = relationship(back_populates="missions")
    knowledge_gaps: Mapped[list[KnowledgeGapORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    assumptions: Mapped[list[ProjectAssumptionORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    clarifying_questions: Mapped[list[ClarifyingQuestionORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    design_questions: Mapped[list[DesignQuestionORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    workstreams: Mapped[list[WorkstreamORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    deliverable_plans: Mapped[list[DeliverablePlanORM]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )


class KnowledgeGapORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_gaps"
    __table_args__ = (
        Index("ix_knowledge_gaps_project_id", "project_id"),
        Index("ix_knowledge_gaps_mission_id", "mission_id"),
        Index("ix_knowledge_gaps_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    impact_if_unresolved: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution_methods_json: Mapped[list[str]] = mapped_column("resolution_methods", JSON, default=list)
    suggested_owner: Mapped[str | None] = mapped_column(String(200))
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(Text)

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="knowledge_gaps")


class ProjectAssumptionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_assumptions"
    __table_args__ = (
        Index("ix_project_assumptions_project_id", "project_id"),
        Index("ix_project_assumptions_mission_id", "mission_id"),
        Index("ix_project_assumptions_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scope_of_use: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    related_gap_ids_json: Mapped[list[str]] = mapped_column("related_gap_ids", JSON, default=list)
    evidence_refs_json: Mapped[list[str]] = mapped_column("evidence_refs", JSON, default=list)

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="assumptions")


class ClarifyingQuestionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clarifying_questions"
    __table_args__ = (
        Index("ix_clarifying_questions_project_id", "project_id"),
        Index("ix_clarifying_questions_mission_id", "mission_id"),
        Index("ix_clarifying_questions_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_gap_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_gaps.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    why_asked: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    options_json: Mapped[list[str]] = mapped_column("options", JSON, default=list)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_assume: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    suggested_assumption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_json: Mapped[object | None] = mapped_column("answer", JSON)
    answer_source: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="clarifying_questions")


class DesignQuestionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "design_questions"
    __table_args__ = (
        Index("ix_design_questions_project_id", "project_id"),
        Index("ix_design_questions_mission_id", "mission_id"),
        Index("ix_design_questions_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    related_problem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    constraints_json: Mapped[list[str]] = mapped_column("constraints", JSON, default=list)
    desired_outcome: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="design_questions")


class WorkstreamORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workstreams"
    __table_args__ = (
        Index("ix_workstreams_project_id", "project_id"),
        Index("ix_workstreams_mission_id", "mission_id"),
        Index("ix_workstreams_lineage_id", "lineage_id"),
        Index("ix_workstreams_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    workstream_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    questions_json: Mapped[list[str]] = mapped_column("questions", JSON, default=list)
    inputs_required_json: Mapped[list[str]] = mapped_column("inputs_required", JSON, default=list)
    activities_json: Mapped[list[str]] = mapped_column("activities", JSON, default=list)
    outputs_json: Mapped[list[str]] = mapped_column("outputs", JSON, default=list)
    dependencies_json: Mapped[list[str]] = mapped_column("dependencies", JSON, default=list)
    blocking_gaps_json: Mapped[list[str]] = mapped_column("blocking_gaps", JSON, default=list)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    effort_level: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="workstreams")


class DesignSystemORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "design_systems"
    __table_args__ = (
        Index("ix_design_systems_name", "name"),
        Index("ix_design_systems_approval_status", "approval_status"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="approved")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="builtin")
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)


class ArtDirectionORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "art_directions"
    __table_args__ = (
        Index("ix_art_directions_project_id", "project_id"),
        Index("ix_art_directions_presentation_id", "presentation_id"),
        Index("ix_art_directions_approval_status", "approval_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="SET NULL"), nullable=True
    )
    deliverable_id: Mapped[str | None] = mapped_column(String(200))
    design_system_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)


class VisualIntentORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "visual_intents"
    __table_args__ = (
        Index("ix_visual_intents_slide_id", "slide_id"),
        Index("ix_visual_intents_presentation_id", "presentation_id"),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slides.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="SET NULL"), nullable=True
    )
    art_direction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)


class LayoutPlanORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "layout_plans"
    __table_args__ = (
        Index("ix_layout_plans_slide_id", "slide_id"),
        Index("ix_layout_plans_visual_intent_id", "visual_intent_id"),
        Index("ix_layout_plans_layout_family", "layout_family"),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("slides.id", ondelete="CASCADE"), nullable=False
    )
    design_system_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    visual_intent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    layout_family: Mapped[str] = mapped_column(String(50), nullable=False)
    layout_variant: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)


class DeliverablePlanORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deliverable_plans"
    __table_args__ = (
        Index("ix_deliverable_plans_project_id", "project_id"),
        Index("ix_deliverable_plans_mission_id", "mission_id"),
        Index("ix_deliverable_plans_lineage_id", "lineage_id"),
        Index("ix_deliverable_plans_approval_status", "approval_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_missions.id", ondelete="CASCADE"), nullable=False
    )
    lineage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(200), nullable=False, default="deliverable-plan")
    deliverables_json: Mapped[list[dict[str, object]]] = mapped_column("deliverables", JSON, default=list)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    mission: Mapped[ProjectMissionORM] = relationship(back_populates="deliverable_plans")
