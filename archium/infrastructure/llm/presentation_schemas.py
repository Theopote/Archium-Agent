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


class OutlineSectionDraft(BaseModel):
    id: str
    title: str
    purpose: str
    key_message: str
    estimated_slide_count: int = Field(default=1, ge=0)
    evidence_requirements: list[str] = Field(default_factory=list)
    required_assets: list[str] = Field(default_factory=list)
    required: bool = True
    expanded: bool = True
    order: int = Field(ge=0)
    category: str = "general"


class OutlinePlanDraft(BaseModel):
    title: str
    thesis: str
    audience: str
    purpose: str
    target_slide_count: int = Field(default=20, ge=1, le=200)
    audience_mode: str = "government"
    sections: list[OutlineSectionDraft] = Field(default_factory=list)


class NarrativeEventDraft(BaseModel):
    id: str
    year_or_period: str
    event: str
    origin: str = "user_upload"
    is_legend: bool = False


class CulturalCharacterDraft(BaseModel):
    id: str
    name: str
    role: str
    significance: str
    origin: str = "user_upload"
    is_legend: bool = False


class CulturalPlaceDraft(BaseModel):
    id: str
    name: str
    significance: str
    space_type: str = "public_space"
    asset_refs: list[str] = Field(default_factory=list)


class CulturalRitualDraft(BaseModel):
    id: str
    name: str
    description: str
    season: str | None = None
    origin: str = "user_upload"
    is_legend: bool = False


class ArchitecturalSymbolDraft(BaseModel):
    id: str
    name: str
    building_type: str = "traditional"
    cultural_meaning: str
    asset_refs: list[str] = Field(default_factory=list)


class CommunicationThemeDraft(BaseModel):
    id: str
    theme: str
    linked_characters: list[str] = Field(default_factory=list)
    linked_places: list[str] = Field(default_factory=list)
    linked_rituals: list[str] = Field(default_factory=list)
    linked_buildings: list[str] = Field(default_factory=list)


class CulturalNarrativePlanDraft(BaseModel):
    central_story: str
    identity_keywords: list[str] = Field(default_factory=list)
    historical_timeline: list[NarrativeEventDraft] = Field(default_factory=list)
    characters: list[CulturalCharacterDraft] = Field(default_factory=list)
    places: list[CulturalPlaceDraft] = Field(default_factory=list)
    rituals: list[CulturalRitualDraft] = Field(default_factory=list)
    architectural_symbols: list[ArchitecturalSymbolDraft] = Field(default_factory=list)
    emotional_arc: list[str] = Field(default_factory=list)
    visitor_storyline: list[str] = Field(default_factory=list)
    communication_themes: list[CommunicationThemeDraft] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


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
    reviewer_layer: str = "architectural"
    slide_order: int | None = Field(default=None, ge=0)
    category: str
    severity: str
    rule_code: str | None = None
    title: str
    description: str
    suggestion: str | None = None


class ProfessionalReviewDraft(BaseModel):
    issues: list[ReviewIssueDraft] = Field(default_factory=list)


class BriefAlignmentDraft(BaseModel):
    aligned: bool
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    gap_summary: str = ""
    suggestion: str | None = None


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


class SlideSplitPageDraft(BaseModel):
    """One page in an LLM-proposed slide split."""

    title: str
    message: str
    key_points: list[str] = Field(default_factory=list, max_length=5)
    citation_indices: list[int] = Field(default_factory=list)
    visual_indices: list[int] = Field(default_factory=list)


class SlideSplitDraft(BaseModel):
    """LLM proposal for splitting one overcrowded slide into two narrative pages."""

    narrative_reason: str = Field(min_length=1)
    source: SlideSplitPageDraft
    continuation: SlideSplitPageDraft
