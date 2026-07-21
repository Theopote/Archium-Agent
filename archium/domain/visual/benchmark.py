"""Architectural slide visual benchmark domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel

HUMAN_REVIEW_MIN_SCORE = 1
HUMAN_REVIEW_MAX_SCORE = 5
HUMAN_REVIEW_PASS_THRESHOLD = 3.5
HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD = 3.8  # experimental archive only — not a formal gate
HUMAN_REVIEW_FORMAL_MIN_ACCEPTED = 24
HUMAN_REVIEW_FORMAL_TOTAL_CASES = 30
HUMAN_REVIEW_FORMAL_MIN_EXCEPTION_REVIEWS = 3  # pilot exception reviews before deck gate
HUMAN_REVIEW_PENDING_LABEL = "待人工复核"
HUMAN_REVIEW_INVALIDATED_LABEL = "已作废（需重评）"
LAYOUT_REVIEW_PENDING_LABEL = "待几何评审"
LAYOUT_REVIEW_PASS_THRESHOLD = 3.5
BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER = (
    "正式人工异常复核须基于本轮重新生成的 pptx_render.png"
    "（output.pptx → PowerPoint/LibreOffice → 截图），"
    "且 render_valid=true、pptx_screenshot_generated=true；"
    "复用截图（pptx_screenshot_reused=true）仅可用于开发快速检查，"
    "不能用于最终质量门；也不能使用 LayoutPlan 线框图 wireframe.png。"
)
DEFAULT_INVALIDATION_REASON_WIREFRAME = (
    "Reviewed against wireframe preview rather than final rendered slide"
)

HUMAN_REVIEW_WEIGHTS: dict[str, float] = {
    "information_hierarchy": 0.15,
    "visual_focus": 0.15,
    "reading_order": 0.10,
    "image_text_relationship": 0.15,
    "whitespace_density": 0.10,
    "architectural_expression": 0.15,
    "aesthetic_finish": 0.10,
    "editability": 0.10,
}

VISUAL_REVIEW_WEIGHTS: dict[str, float] = {
    "information_hierarchy": 0.17,
    "visual_focus": 0.17,
    "reading_order": 0.11,
    "image_text_relationship": 0.17,
    "whitespace_density": 0.11,
    "architectural_expression": 0.17,
    "aesthetic_finish": 0.10,
}

from archium.domain.visual.enums import LayoutFamily  # noqa: E402
from archium.domain.visual.page_quality import (  # noqa: E402
    PageQualityStatus,
    QualityIssue,
    ReportingReady,
    ScoringMode,
    derive_page_quality_status,
    issues_from_free_text,
)
from archium.domain.visual.quality_issue_catalog import (  # noqa: E402
    HUMAN_CHECKLIST_BY_CODE,
)


class HumanVisualReviewSource(StrEnum):
    """Provenance for a visual review record."""

    MANUAL = "manual"
    PLACEHOLDER = "placeholder"
    LAYOUT_QA_DERIVED = "layout_qa_derived"
    INVALIDATED = "invalidated"


class ReviewValidity(StrEnum):
    """Whether a stored review may count toward delivery gates."""

    VALID = "valid"
    INVALID_RENDER_ARTIFACT = "invalid_render_artifact"
    SUPERSEDED = "superseded"


_DERIVED_REVIEW_NOTE_MARKERS = (
    "derived from layout",
    "acceptance rehearsal derived",
)
_PLACEHOLDER_REVIEW_NOTE_MARKERS = (
    "占位",
    "待真实",
    "template",
    "placeholder",
)


class ArchitecturalSlideCategory(StrEnum):
    """High-level benchmark page categories (A1–A5)."""

    DRAWING = "drawing"
    PHOTO_ANALYSIS = "photo_analysis"
    CASE_COMPARISON = "case_comparison"
    DATA_METRICS = "data_metrics"
    TEXT_NARRATIVE = "text_narrative"


class BenchmarkCaseDefinition(DomainModel):
    """Metadata describing one architectural slide benchmark case."""

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: ArchitecturalSlideCategory
    page_type: str = Field(min_length=1)
    page_task: str = Field(min_length=1)
    visual_focus: str = Field(min_length=1)
    expected_layout_family: LayoutFamily
    allowed_layout_variants: list[str] = Field(min_length=1)
    layout_variant: str = Field(min_length=1)
    chapter_id: str = Field(min_length=1)
    slide_order: int = Field(ge=1)


class HumanVisualReview(DomainModel):
    """Human exception review for one benchmark slide.

    Formal gate uses coded issues + reporting_ready / page_quality_status.
    Legacy 1–5 dimension scores are ``scoring_mode=experimental`` only.
    """

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    # --- Experimental 1–5 archive (not formal gate) ---
    information_hierarchy: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    visual_focus: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    reading_order: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    image_text_relationship: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    whitespace_density: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    architectural_expression: int = Field(
        ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4
    )
    aesthetic_finish: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    editability: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE, default=4)
    scoring_mode: ScoringMode = ScoringMode.EXPERIMENTAL
    # --- Problem-driven formal fields ---
    selected_issue_codes: list[str] = Field(default_factory=list)
    quality_issues: list[QualityIssue] = Field(default_factory=list)
    page_quality_status: PageQualityStatus | None = None
    worst_problem: str = ""
    system_missed: str = ""
    reporting_ready: ReportingReady = ReportingReady.UNSPECIFIED
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    review_completed: bool = False
    accepted_for_delivery: bool = False
    validity: ReviewValidity = ReviewValidity.VALID
    accepted: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""
    invalidation_reason: str = ""

    @field_validator(
        "information_hierarchy",
        "visual_focus",
        "reading_order",
        "image_text_relationship",
        "whitespace_density",
        "architectural_expression",
        "aesthetic_finish",
        "editability",
    )
    @classmethod
    def _validate_score_range(cls, value: int) -> int:
        if not HUMAN_REVIEW_MIN_SCORE <= value <= HUMAN_REVIEW_MAX_SCORE:
            msg = f"score must be between {HUMAN_REVIEW_MIN_SCORE} and {HUMAN_REVIEW_MAX_SCORE}"
            raise ValueError(msg)
        return value

    def collect_quality_issues(self) -> list[QualityIssue]:
        """Merge checklist codes, structured issues, and legacy free-text lists."""
        from archium.domain.visual.page_quality import (
            IssueSeverity,
            QualityIssueSource,
        )

        merged: list[QualityIssue] = list(self.quality_issues)
        seen = {issue.code for issue in merged}
        for code in self.selected_issue_codes:
            if code in seen:
                continue
            entry = HUMAN_CHECKLIST_BY_CODE.get(code)
            if entry is None:
                merged.append(
                    QualityIssue(
                        code=code,
                        severity=IssueSeverity.MAJOR,
                        message=code,
                        source=QualityIssueSource.HUMAN,
                    )
                )
            else:
                merged.append(
                    QualityIssue(
                        code=entry.code,
                        severity=entry.severity,
                        category=entry.category,
                        message=entry.label_zh,
                        source=QualityIssueSource.HUMAN,
                    )
                )
            seen.add(code)
        for issue in issues_from_free_text(
            major_problems=self.major_problems,
            minor_problems=self.minor_problems,
        ):
            if issue.code not in seen:
                merged.append(issue)
                seen.add(issue.code)
        return merged

    def derived_page_quality_status(self) -> PageQualityStatus:
        if self.page_quality_status is not None:
            return self.page_quality_status
        return derive_page_quality_status(self.collect_quality_issues())

    def has_blocker_issues(self) -> bool:
        from archium.domain.visual.page_quality import IssueSeverity

        return any(
            issue.severity == IssueSeverity.BLOCKER for issue in self.collect_quality_issues()
        )

    def weighted_score(self) -> float:
        """Experimental weighted average — not used by formal gates."""
        total = 0.0
        weights = VISUAL_REVIEW_WEIGHTS if self.is_manual_review() else HUMAN_REVIEW_WEIGHTS
        for field_name, weight in weights.items():
            if hasattr(self, field_name):
                total += getattr(self, field_name) * weight
        return round(total, 3)

    def passes_threshold(self, threshold: float = HUMAN_REVIEW_PASS_THRESHOLD) -> bool:
        """Legacy score helper — formal delivery uses issue status instead."""
        return self.weighted_score() >= threshold

    def human_score_label(self) -> str:
        """User-facing status; prefer problem-driven status over experimental scores."""
        if self.is_invalidated():
            return HUMAN_REVIEW_INVALIDATED_LABEL
        if self.is_scaffold_review():
            return HUMAN_REVIEW_PENDING_LABEL
        if self.is_manual_review() and (
            self.selected_issue_codes
            or self.quality_issues
            or self.reporting_ready != ReportingReady.UNSPECIFIED
            or self.review_completed
        ):
            return self.derived_page_quality_status().value
        return HUMAN_REVIEW_PENDING_LABEL

    def reportable_weighted_score(self) -> float | None:
        """Experimental only — never drives formal gates."""
        if self.is_scaffold_review() or self.is_invalidated():
            return None
        if self.scoring_mode != ScoringMode.EXPERIMENTAL:
            return self.weighted_score()
        return None

    @model_validator(mode="after")
    def _infer_invalidated_validity(self) -> Self:
        if self.source == HumanVisualReviewSource.INVALIDATED and self.validity == ReviewValidity.VALID:
            object.__setattr__(self, "validity", ReviewValidity.INVALID_RENDER_ARTIFACT)
        return self

    @model_validator(mode="after")
    def _sync_page_quality_status(self) -> Self:
        if self.is_scaffold_review() or self.is_invalidated():
            return self
        if not self.is_manual_review():
            return self
        status = derive_page_quality_status(self.collect_quality_issues())
        if self.reporting_ready == ReportingReady.DO_NOT_USE:
            status = PageQualityStatus.BLOCKED
        object.__setattr__(self, "page_quality_status", status)
        object.__setattr__(self, "scoring_mode", ScoringMode.EXPERIMENTAL)
        return self

    @model_validator(mode="after")
    def _enforce_review_consistency(self) -> Self:
        if self.is_invalidated() or self.validity == ReviewValidity.INVALID_RENDER_ARTIFACT:
            object.__setattr__(self, "accepted_for_delivery", False)
            object.__setattr__(self, "accepted", False)
            if not self.invalidation_reason.strip():
                object.__setattr__(
                    self,
                    "invalidation_reason",
                    DEFAULT_INVALIDATION_REASON_WIREFRAME,
                )
            return self
        if self.is_manual_review():
            if not self.review_completed and self.reviewed_at is not None:
                object.__setattr__(self, "review_completed", True)
            accepted_for_delivery = self.accepted_for_delivery
            accepted = self.accepted
            if self.accepted and not accepted_for_delivery:
                accepted_for_delivery = True
            if accepted_for_delivery and not accepted:
                accepted = True
            # Problem-driven: blockers / majors / do_not_use clear acceptance.
            status = self.page_quality_status or self.derived_page_quality_status()
            blocks_accept = (
                status in {PageQualityStatus.BLOCKED, PageQualityStatus.NEEDS_REVIEW}
                or self.has_blocker_issues()
                or bool(self.major_problems)
                or self.reporting_ready == ReportingReady.DO_NOT_USE
            )
            if accepted_for_delivery and blocks_accept:
                accepted_for_delivery = False
                accepted = False
            if accepted_for_delivery != self.accepted_for_delivery:
                object.__setattr__(self, "accepted_for_delivery", accepted_for_delivery)
            if accepted != self.accepted:
                object.__setattr__(self, "accepted", accepted)
        return self

    @model_validator(mode="after")
    def _infer_source_from_notes(self) -> Self:
        """Backfill provenance for legacy JSON without an explicit ``source`` field."""
        if self.source != HumanVisualReviewSource.MANUAL:
            return self
        notes = self.reviewer_notes.strip().lower()
        if any(marker in notes for marker in _DERIVED_REVIEW_NOTE_MARKERS):
            return self.model_copy(update={"source": HumanVisualReviewSource.LAYOUT_QA_DERIVED})
        if any(marker in notes for marker in _PLACEHOLDER_REVIEW_NOTE_MARKERS):
            return self.model_copy(update={"source": HumanVisualReviewSource.PLACEHOLDER})
        return self

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    def is_exception_review(self) -> bool:
        """True when this record is a completed problem-driven human exception review."""
        return (
            self.is_manual_review()
            and self.review_completed
            and not self.is_invalidated()
            and self.validity == ReviewValidity.VALID
        )

    def is_invalidated(self) -> bool:
        return (
            self.source == HumanVisualReviewSource.INVALIDATED
            or self.validity == ReviewValidity.INVALID_RENDER_ARTIFACT
        )

    def is_scaffold_review(self) -> bool:
        """Return True for placeholder templates and layout-QA-derived stand-ins."""
        return self.source in {
            HumanVisualReviewSource.PLACEHOLDER,
            HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        }


class BenchmarkRenderManifest(DomainModel):
    """Tracks whether a case has a valid final-render preview for visual review."""

    render_source: str = "pending"
    pptx_path: str = "output.pptx"
    image_path: str = "pptx_render.png"
    scene_path: str = "scene.json"
    scene_preview_path: str = "scene_preview.png"
    scene_id: str | None = None
    scene_hash: str = ""
    rendered_at: datetime | None = None
    renderer: str = ""
    asset_count: int = Field(ge=0, default=0)
    real_asset_count: int = Field(ge=0, default=0)
    placeholder_asset_count: int = Field(ge=0, default=0)
    font_fallbacks: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    render_valid: bool = False
    notes: str = ""
    # Structured evidence — do not rely on ``notes`` for acceptance state.
    screenshot_tools_available: bool = False
    pptx_screenshot_generated: bool = False
    pptx_screenshot_reused: bool = False
    pptx_screenshot_source_hash: str = ""
    render_attempt_id: UUID | None = None
    # Provenance — same-generation identity across scene / PPTX / screenshot.
    pptx_content_hash: str = ""
    post_render_qa_passed: bool = False
    post_render_qa_issues: list[str] = Field(default_factory=list)

    def scene_preview_valid(self) -> bool:
        """Return True when a RenderScene preview is ready for Phase 1–2 review."""
        return (
            self.render_valid
            and self.placeholder_asset_count == 0
            and not self.missing_assets
            and bool(self.scene_hash)
        )

    def visual_review_eligible(self) -> bool:
        """Formal human visual review — requires a freshly generated PPTX screenshot."""
        return (
            self.render_valid
            and self.placeholder_asset_count == 0
            and not self.missing_assets
            and self.pptx_screenshot_generated
            and not self.pptx_screenshot_reused
        )

    def eligibility_blockers(self) -> list[str]:
        blockers: list[str] = []
        if not self.render_valid:
            blockers.append("render_valid=false")
        if self.placeholder_asset_count > 0:
            blockers.append(
                f"placeholder_asset_count={self.placeholder_asset_count} > 0"
            )
        if self.missing_assets:
            blockers.append(f"missing_assets={len(self.missing_assets)}")
        if not self.scene_hash:
            blockers.append("scene_hash missing")
        if not self.pptx_screenshot_generated:
            blockers.append(
                "pptx_screenshot_generated=false"
                "（须本轮重新打开 output.pptx 生成截图，不可仅复用）"
            )
        if self.pptx_screenshot_reused:
            blockers.append(
                "pptx_screenshot_reused=true"
                "（复用截图不可用于正式人工视觉评审）"
            )
        return blockers


class EditabilityReview(DomainModel):
    """Manual PPTX editability review — separate from visual aesthetics."""

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    text_editable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    image_replaceable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    layer_independence: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    chart_editable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    font_usability: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    not_flattened: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    selection_ease: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    modification_ease: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    review_completed: bool = False
    passed: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""

    def weighted_score(self) -> float:
        weights = {
            "text_editable": 0.20,
            "image_replaceable": 0.15,
            "layer_independence": 0.15,
            "chart_editable": 0.10,
            "font_usability": 0.10,
            "not_flattened": 0.15,
            "selection_ease": 0.075,
            "modification_ease": 0.075,
        }
        total: float = sum(getattr(self, field) * weight for field, weight in weights.items())
        return round(total, 3)

    def passes_threshold(self, threshold: float = HUMAN_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    @model_validator(mode="after")
    def _enforce_pass_consistency(self) -> Self:
        if self.is_manual_review() and self.passed and (
            self.major_problems or not self.passes_threshold()
        ):
            object.__setattr__(self, "passed", False)
        return self


class HumanLayoutReview(DomainModel):
    """Manual layout-geometry review against wireframe.png (not final render)."""

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    information_hierarchy: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    reading_order: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    whitespace_density: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    spatial_balance: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    layout_clarity: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    accepted_for_geometry: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""

    def weighted_score(self) -> float:
        weights = {
            "information_hierarchy": 0.25,
            "reading_order": 0.25,
            "whitespace_density": 0.20,
            "spatial_balance": 0.15,
            "layout_clarity": 0.15,
        }
        total: float = sum(getattr(self, field) * weight for field, weight in weights.items())
        return round(total, 3)

    def passes_threshold(self, threshold: float = LAYOUT_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def human_score_label(self) -> str:
        if self.is_scaffold_review():
            return LAYOUT_REVIEW_PENDING_LABEL
        return f"{self.weighted_score():.2f}"

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    def is_scaffold_review(self) -> bool:
        return self.source in {
            HumanVisualReviewSource.PLACEHOLDER,
            HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        }

    @model_validator(mode="after")
    def _enforce_geometry_consistency(self) -> Self:
        if self.is_manual_review() and self.accepted_for_geometry and (
            self.major_problems or not self.passes_threshold()
        ):
            self.accepted_for_geometry = False
        return self


class BenchmarkPendingCase(DomainModel):
    """Case awaiting manual review — metadata only, no scores."""

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    page_type: str = Field(min_length=1)
    preview_png: str = ""


class BenchmarkHumanReviewExport(DomainModel):
    """Deck-level export bundle for benchmark manual reviews (backup / offline handoff)."""

    bundle_version: int = 1
    exported_at: datetime
    case_count: int = Field(ge=0)
    manual_review_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    reviews: list[HumanVisualReview] = Field(default_factory=list)
    pending_cases: list[BenchmarkPendingCase] = Field(default_factory=list)
    human_quality_gate_passed: bool = False
    human_average_weighted_score: float | None = None  # experimental only; non-gating
    human_quality_gate_reasons: list[str] = Field(default_factory=list)
    page_quality_status_counts: dict[str, int] = Field(default_factory=dict)
    formal_gate_mode: str = "problem_driven"


class BenchmarkRuleScore(DomainModel):
    """Automated rule-based score for a benchmark case."""

    case_id: str
    layout_valid: bool
    layout_score: float
    has_critical: bool
    blocking_issue_count: int
    rule_codes: list[str] = Field(default_factory=list)
    deck_qa_score: float | None = None
    passed: bool = False
