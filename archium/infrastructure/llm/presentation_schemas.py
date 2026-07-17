"""Structured LLM output schemas for presentation pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from archium.domain.enums import PresentationType, SlideType, VisualType


class BriefDraft(BaseModel):
    title: str
    presentation_type: PresentationType = PresentationType.CLIENT_REVIEW
    audience: str
    purpose: str
    duration_minutes: int = Field(default=20, ge=1, le=480)
    target_slide_count: int = Field(default=20, ge=1, le=200)
    core_message: str
    decisions_required: list[str] = Field(default_factory=list)
    audience_concerns: list[str] = Field(default_factory=list)
    tone: str = "professional"
    required_sections: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    language: str = "zh-CN"


class ChapterDraft(BaseModel):
    id: str
    title: str
    purpose: str
    key_message: str
    order: int = Field(ge=0)
    estimated_slide_count: int = Field(default=1, ge=1)


class StorylineDraft(BaseModel):
    thesis: str
    narrative_pattern: str = "problem_solution"
    chapters: list[ChapterDraft] = Field(default_factory=list)


class CitationDraft(BaseModel):
    document_name: str
    page_number: int | None = None
    chunk_id: str | None = None
    quote: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class VisualRequirementDraft(BaseModel):
    type: VisualType = VisualType.TEXT_ONLY
    description: str
    required: bool = True


class SlideDraft(BaseModel):
    chapter_id: str
    order: int = Field(ge=0)
    title: str
    message: str
    slide_type: SlideType = SlideType.CONTENT
    layout_id: str = "default"
    key_points: list[str] = Field(default_factory=list)
    visual_requirements: list[VisualRequirementDraft] = Field(default_factory=list)
    source_citations: list[CitationDraft] = Field(default_factory=list)
    speaker_notes: str | None = None


class SlidePlanDraft(BaseModel):
    slides: list[SlideDraft] = Field(default_factory=list)


class ReviewIssueDraft(BaseModel):
    slide_order: int | None = Field(default=None, ge=0)
    category: str
    severity: str
    title: str
    description: str
    suggestion: str | None = None


class ProfessionalReviewDraft(BaseModel):
    issues: list[ReviewIssueDraft] = Field(default_factory=list)


class FactDraft(BaseModel):
    key: str
    label: str
    value: str
    unit: str | None = None
    category: str = "general"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    chunk_id: str | None = None
    quote: str | None = None


class FactExtractionDraft(BaseModel):
    facts: list[FactDraft] = Field(default_factory=list)


class SlideRepairDraft(BaseModel):
    title: str
    message: str
    key_points: list[str] = Field(default_factory=list, max_length=5)
