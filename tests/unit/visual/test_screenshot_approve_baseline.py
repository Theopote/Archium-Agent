"""Candidate → approve-baseline helpers for pptx_visual_regression."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from tests.golden.visual.composition.case_builders import CompositionCaseResult
from tests.golden.visual.composition.screenshot_baseline import (
    approve_candidate_baseline,
    candidate_screenshot_path,
    save_screenshot_candidate,
    screenshot_baseline_path,
)


def _tiny_case() -> CompositionCaseResult:
    design = default_presentation_design_system()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="c",
        order=0,
        title="t",
        message="m",
        slide_type=SlideType.CONTENT,
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        communication_goal="g",
        audience_takeaway="t",
        visual_priority="p",
        dominant_content_type=VisualContentType.METRICS,
        preferred_layout_families=[LayoutFamily.METRIC_DASHBOARD],
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=intent.id,
        layout_family=LayoutFamily.METRIC_DASHBOARD,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
    )
    return CompositionCaseResult(
        case_id="tmp_approve",
        slide=slide,
        intent=intent,
        design=design,
        plan=plan,
        report=LayoutValidationReport(score=1.0, issues=[]),
    )


def test_approve_promotes_candidate(tmp_path: Path) -> None:
    case_dir = tmp_path / "v_test"
    png = tmp_path / "shot.png"
    Image.new("RGB", (64, 36), color=(12, 34, 56)).save(png)
    case = _tiny_case()
    save_screenshot_candidate(case_dir, case=case, screenshot_path=png)
    assert candidate_screenshot_path(case_dir).is_file()
    assert not screenshot_baseline_path(case_dir).is_file()

    approved = approve_candidate_baseline(case_dir)
    assert approved == screenshot_baseline_path(case_dir)
    assert approved.is_file()
    manifest = case_dir / "pptx_screenshot_manifest.json"
    assert manifest.is_file()
    text = manifest.read_text(encoding="utf-8")
    assert "pptx_screenshot.png" in text
    assert "font_manifest_hash" in text
    assert "font_platform" in text


def test_approve_without_candidate_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        approve_candidate_baseline(tmp_path / "missing")
