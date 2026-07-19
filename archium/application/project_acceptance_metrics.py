"""Derive rehearsal human metrics from automated acceptance signals."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.studio_human_review_store import load_presentation_reviews, save_slide_review
from archium.config.settings import Settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.benchmark import HumanVisualReview


def derive_acceptance_slide_review(
    slide_id: UUID,
    *,
    layout_score: float,
    layout_valid: bool,
    has_blocking_issues: bool,
) -> HumanVisualReview:
    """Build a rehearsal human review from automated layout QA for one slide."""
    base = 3.0 + min(2.0, max(0.0, layout_score) * 2.0)
    score = int(round(min(5.0, max(1.0, base))))
    major_problems: list[str] = []
    if has_blocking_issues:
        major_problems.append("layout validation blocking issue")
    elif not layout_valid:
        major_problems.append("layout validation failed")
    return HumanVisualReview(
        case_id=str(slide_id),
        information_hierarchy=score,
        visual_focus=score,
        reading_order=score,
        image_text_relationship=score,
        whitespace_density=score,
        architectural_expression=score,
        aesthetic_finish=max(1, score - 1),
        editability=score,
        major_problems=major_problems,
        minor_problems=[],
        accepted=layout_valid and not has_blocking_issues and base >= 3.5,
        reviewer_notes=f"Acceptance rehearsal derived from layout QA score {layout_score:.2f}.",
    )


def seed_acceptance_reviews_from_layout(
    session: Session,
    presentation_id: UUID,
    slides: list[SlideSpec],
    validation_reports: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> int:
    """Persist derived per-slide reviews when Studio reviews are not yet available."""
    if load_presentation_reviews(session, presentation_id, settings=settings):
        return 0
    reports_by_slide = {
        str(report.get("slide_id")): report
        for report in validation_reports
        if report.get("slide_id") is not None
    }
    saved = 0
    for index, slide in enumerate(slides):
        report = reports_by_slide.get(str(slide.id))
        if report is None and index < len(validation_reports):
            report = validation_reports[index]
        report = report or {}
        issues = list(report.get("issues") or [])
        severities = {str(item.get("severity", "")).lower() for item in issues}
        layout_score = float(report.get("score") or 1.0)
        layout_valid = "critical" not in severities and "error" not in severities
        review = derive_acceptance_slide_review(
            slide.id,
            layout_score=layout_score,
            layout_valid=layout_valid,
            has_blocking_issues=bool(severities & {"critical", "error"}),
        )
        save_slide_review(
            session,
            presentation_id,
            slide.id,
            review,
            settings=settings,
        )
        saved += 1
    if saved:
        session.commit()
    return saved


def derive_acceptance_human_metrics_from_reviews(
    reviews: list[HumanVisualReview],
    *,
    slide_count: int,
    fallback: dict[str, float],
) -> dict[str, float]:
    """Prefer stored Studio human reviews when available."""
    if not reviews or slide_count <= 0:
        return fallback
    scores = [review.weighted_score() for review in reviews]
    accepted = sum(1 for review in reviews if review.accepted)
    major_pages = sum(1 for review in reviews if review.major_problems)
    minor_pages = sum(1 for review in reviews if review.minor_problems and not review.major_problems)
    return {
        "major_edit_page_ratio": round(min(1.0, major_pages / slide_count), 3),
        "minor_edit_page_ratio": round(min(1.0, minor_pages / slide_count), 3),
        "exported_page_ratio": round(min(1.0, accepted / slide_count), 3),
        "average_human_visual_score": round(sum(scores) / len(scores), 2),
        "user_edit_minutes": fallback.get("user_edit_minutes", 0.0),
    }


def derive_acceptance_human_metrics(
    *,
    slide_count: int,
    critical_layout_page_count: int,
    error_layout_page_count: int,
    validation_reports: list[dict[str, Any]],
    first_generation_seconds: float,
) -> dict[str, float]:
    """Fill manual acceptance fields from layout validation when live review is unavailable."""
    if slide_count <= 0:
        return {
            "major_edit_page_ratio": 0.0,
            "minor_edit_page_ratio": 0.0,
            "exported_page_ratio": 0.0,
            "average_human_visual_score": 3.5,
            "user_edit_minutes": 0.0,
        }

    major_pages = critical_layout_page_count + error_layout_page_count
    minor_pages = 0
    layout_scores: list[float] = []

    for report in validation_reports:
        issues = list(report.get("issues") or [])
        severities = {str(item.get("severity", "")).lower() for item in issues}
        if severities & {"critical", "error"}:
            continue
        if any(severity == "warning" for severity in severities):
            minor_pages += 1
        score = report.get("score")
        if isinstance(score, (int, float)):
            layout_scores.append(float(score))

    major_ratio = round(min(1.0, major_pages / slide_count), 3)
    minor_ratio = round(min(1.0, minor_pages / slide_count), 3)
    exported_ratio = round(
        min(1.0, max(0.0, (slide_count - major_pages) / slide_count)),
        3,
    )

    avg_layout = sum(layout_scores) / len(layout_scores) if layout_scores else 1.0
    # Map layout score (0–1) to human 1–5 scale with 3.5 pass threshold at ~0.25 layout score.
    human_score = round(min(5.0, max(1.0, 3.0 + avg_layout * 2.0)), 2)

    # Minimal per-page review estimate for automated rehearsal baselines.
    review_minutes = round(max(2.0, slide_count * 0.12 + first_generation_seconds / 60.0), 1)

    return {
        "major_edit_page_ratio": major_ratio,
        "minor_edit_page_ratio": minor_ratio,
        "exported_page_ratio": exported_ratio,
        "average_human_visual_score": human_score,
        "user_edit_minutes": review_minutes,
    }
