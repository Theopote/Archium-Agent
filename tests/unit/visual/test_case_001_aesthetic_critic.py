"""Aesthetic Critic gate on Case 001 demo-tour pages."""

from __future__ import annotations

from archium.application.visual.showcase_case_001 import (
    AESTHETIC_GATE_MIN_SCORE,
    AESTHETIC_GATE_TITLES,
    build_case_001_render_bundle,
    evaluate_case_001_aesthetic_gate,
)
from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.visual.critic import VisualCriticReport


def test_case_001_aesthetic_critic_runs_on_all_pages() -> None:
    bundle = build_case_001_render_bundle()
    critic = VisualCriticService()
    reports = critic.evaluate_deck(bundle.plans)
    assert len(reports) == len(bundle.plans)
    for report in reports:
        assert isinstance(report, VisualCriticReport)
        assert report.dimensions.balance is not None
        assert report.dimensions.whitespace is not None
        assert report.dimensions.alignment is not None
        assert report.dimensions.visual_noise is not None
        assert report.dimensions.tension is not None


def test_case_001_aesthetic_gate_covers_required_titles() -> None:
    bundle = build_case_001_render_bundle()
    reports = VisualCriticService().evaluate_deck(bundle.plans)
    gate = evaluate_case_001_aesthetic_gate(reports, bundle.slides)
    assert gate["missing"] == []
    for title in AESTHETIC_GATE_TITLES:
        assert title in gate["pages"], f"Gate page missing: {title}"
        page = gate["pages"][title]
        assert "score" in page
        assert "passed" in page


def test_cover_page_passes_aesthetic_gate() -> None:
    bundle = build_case_001_render_bundle()
    cover_idx = next(i for i, s in enumerate(bundle.slides) if s.title == "封面")
    plan = bundle.plans[cover_idx]
    report = VisualCriticService().evaluate_plan(plan)
    assert report.total_score is not None
    assert report.total_score >= AESTHETIC_GATE_MIN_SCORE, (
        f"Cover page score {report.total_score:.3f} < gate {AESTHETIC_GATE_MIN_SCORE}; "
        f"findings: {report.finding_codes}"
    )


def test_conflict_page_has_aesthetic_dimensions() -> None:
    bundle = build_case_001_render_bundle()
    idx = next(i for i, s in enumerate(bundle.slides) if s.title == "流线冲突")
    plan = bundle.plans[idx]
    report = VisualCriticService().evaluate_plan(plan)
    d = report.dimensions
    assert d.balance is not None and d.balance >= 0.0
    assert d.whitespace is not None
    assert d.visual_noise is not None
    for f in report.findings:
        if f.suggestion:
            assert len(f.suggestion) > 10
