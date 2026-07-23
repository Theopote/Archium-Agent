"""Input models for Brief and Storyline human review."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.domain.deck_delivery import DeckDeliveryReport, aggregate_deck_delivery
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.domain.workflow import WorkflowRun


@dataclass(frozen=True)
class BriefUpdate:
    title: str
    audience: str
    purpose: str
    core_message: str
    duration_minutes: int = 20
    target_slide_count: int = 20
    tone: str = "professional"
    language: str = "zh-CN"
    required_sections: list[str] = field(default_factory=list)
    decisions_required: list[str] = field(default_factory=list)
    audience_concerns: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterUpdate:
    id: str
    title: str
    purpose: str
    key_message: str
    order: int
    estimated_slide_count: int = 1


@dataclass(frozen=True)
class NarrativeArcUpdate:
    opening_context: str
    central_problem: str
    turning_point: str
    proposed_resolution: str
    tension_building: list[str] = field(default_factory=list)
    final_decision: str | None = None


@dataclass(frozen=True)
class StorylineUpdate:
    thesis: str
    narrative_pattern: str = "problem_solution"
    chapters: list[ChapterUpdate] = field(default_factory=list)
    narrative_arc: NarrativeArcUpdate | None = None


@dataclass(frozen=True)
class NarrativePositionUpdate:
    stage: str = "context"
    advances_from_previous: str = ""
    prepares_for_next: str = ""


@dataclass(frozen=True)
class OutlineSectionUpdate:
    id: str
    title: str
    purpose: str
    key_message: str
    order: int
    estimated_slide_count: int = 1
    evidence_requirements: list[str] = field(default_factory=list)
    required_assets: list[str] = field(default_factory=list)
    required: bool = True
    expanded: bool = True
    category: str = "general"
    narrative_position: NarrativePositionUpdate | None = None


@dataclass(frozen=True)
class SlideIntentUpdate:
    """Editable Slide Intent Card for one planned page."""

    order: int
    page_task: str
    chapter_id: str = ""
    central_conclusion: str = ""
    required_evidence: list[str] = field(default_factory=list)
    required_assets: list[str] = field(default_factory=list)
    forbidden_content: list[str] = field(default_factory=list)
    expected_layout: str = ""
    page_archetype: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class SlideAssetBindingUpdate:
    """Editable page→asset binding (page_materials)."""

    page_order: int
    asset_id: str
    binding_role: str = "project_photo"
    user_description: str = ""
    required: bool = True
    slide_id: str | None = None


@dataclass(frozen=True)
class SlideDesignBriefUpdate:
    """Editable per-page design brief."""

    page_order: int
    page_task: str
    central_claim: str = ""
    primary_visual_type: str = "content"
    primary_asset_ids: list[UUID] = field(default_factory=list)
    supporting_asset_ids: list[UUID] = field(default_factory=list)
    evidence_ids: list[UUID] = field(default_factory=list)
    layout_family: str = ""
    expected_density: str = "medium"
    page_archetype: str | None = None
    drawing_policy: dict[str, object] | None = None
    image_policy: dict[str, object] | None = None
    required_content: list[str] = field(default_factory=list)
    forbidden_content: list[str] = field(default_factory=list)
    protection_rules: list[str] = field(default_factory=list)
    template_usage_brief_id: UUID | None = None
    template_usage_brief_version: int | None = None
    status: str = "draft"


@dataclass(frozen=True)
class OutlineUpdate:
    title: str
    thesis: str
    audience: str
    purpose: str
    target_slide_count: int = 20
    audience_mode: str = "government"
    sections: list[OutlineSectionUpdate] = field(default_factory=list)
    page_intents: list[SlideIntentUpdate] = field(default_factory=list)
    page_asset_bindings: list[SlideAssetBindingUpdate] = field(default_factory=list)
    page_design_briefs: list[SlideDesignBriefUpdate] = field(default_factory=list)
    expected_version: int | None = None


@dataclass(frozen=True)
class SlideUpdate:
    chapter_id: str
    order: int
    title: str
    message: str
    slide_type: str
    layout_id: str = "default"
    key_points: list[str] = field(default_factory=list)
    speaker_notes: str | None = None


@dataclass(frozen=True)
class PresentationReviewContext:
    presentation: Presentation
    brief: PresentationBrief | None
    storyline: Storyline | None
    outline: OutlinePlan | None
    manuscript: PresentationManuscript | None = None
    slides: list[SlideSpec] = field(default_factory=list)
    review_issues: list[ReviewIssue] = field(default_factory=list)
    workflow_run: WorkflowRun | None = None

    @property
    def review_gate(self) -> str | None:
        if self.workflow_run is None:
            return None
        return self.workflow_run.state.get("review_gate")

    @property
    def awaiting_review(self) -> bool:
        if self.workflow_run is None:
            return False
        from archium.domain.enums import WorkflowStatus

        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW

    @property
    def slides_pending_review(self) -> bool:
        from archium.domain.enums import SlideStatus

        if not self.slides:
            return False
        return any(slide.status != SlideStatus.APPROVED for slide in self.slides)

    @property
    def open_critical_issues(self) -> list[ReviewIssue]:
        from archium.domain.enums import ReviewSeverity, ReviewStatus

        return [
            issue
            for issue in self.review_issues
            if issue.severity == ReviewSeverity.CRITICAL and issue.status == ReviewStatus.OPEN
        ]

    @property
    def deck_delivery(self) -> DeckDeliveryReport:
        return aggregate_deck_delivery(
            self.slides,
            needs_review=self.slides_pending_review,
        )

    @property
    def allows_preview(self) -> bool:
        return self.deck_delivery.allows_preview

    @property
    def allows_draft_export(self) -> bool:
        return self.deck_delivery.allows_draft_export


def parse_multiline_items(text: str) -> list[str]:
    value = text.strip()
    if not value:
        return []
    lines = [part.strip() for part in value.splitlines() if part.strip()]
    if len(lines) > 1:
        return lines
    single = lines[0] if lines else value
    for separator in ("、", "，", ","):
        if separator in single:
            return [part.strip() for part in single.split(separator) if part.strip()]
    return [single]
