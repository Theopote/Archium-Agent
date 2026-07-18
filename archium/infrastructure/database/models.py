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

    documents: Mapped[list[SourceDocumentORM]] = relationship(back_populates="project")
    presentations: Mapped[list[PresentationORM]] = relationship(back_populates="project")
    facts: Mapped[list[ProjectFactORM]] = relationship(back_populates="project")
    assets: Mapped[list[AssetORM]] = relationship(back_populates="project")


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
    chunks: Mapped[list[DocumentChunkORM]] = relationship(back_populates="document")


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
    briefs: Mapped[list[PresentationBriefORM]] = relationship(back_populates="presentation")
    storylines: Mapped[list[StorylineORM]] = relationship(back_populates="presentation")
    slides: Mapped[list[SlideORM]] = relationship(back_populates="presentation")
    review_issues: Mapped[list[ReviewIssueORM]] = relationship(back_populates="presentation")


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

    presentation: Mapped[PresentationORM] = relationship(back_populates="review_issues")


class WorkflowRunORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    state_json: Mapped[dict[str, object]] = mapped_column("state", JSON, default=dict)
    errors_json: Mapped[list[str]] = mapped_column("errors", JSON, default=list)
    output_files_json: Mapped[list[str]] = mapped_column("output_files", JSON, default=list)


class UserPreferenceORM(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("key", "project_id", name="uq_pref_key_project"),)

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[object] = mapped_column("value", JSON, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    description: Mapped[str | None] = mapped_column(Text)
