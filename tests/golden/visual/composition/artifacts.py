"""Helpers for visual composition golden artifacts (plan / report / PNG / PPTX)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from archium.config.settings import Settings
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.validation import LayoutValidationReport
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
    SlideContentBundle,
)
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from archium.infrastructure.visual.layout_preview_renderer import render_layout_preview_png

UPDATE_ENV = "UPDATE_VISUAL_COMPOSITION_GOLDENS"


def fingerprint_plan(plan: LayoutPlan) -> dict[str, Any]:
    """Stable geometry fingerprint — strips volatile UUIDs/timestamps."""
    elements = []
    for element in sorted(plan.elements, key=lambda el: el.id):
        elements.append(
            {
                "id": element.id,
                "role": element.role.value,
                "content_type": element.content_type.value,
                "x": round(element.x, 3),
                "y": round(element.y, 3),
                "w": round(element.width, 3),
                "h": round(element.height, 3),
                "fit_mode": element.fit_mode.value if element.fit_mode else None,
                "crop_policy": element.crop_policy.value if element.crop_policy else None,
            }
        )
    return {
        "layout_family": plan.layout_family.value,
        "layout_variant": plan.layout_variant,
        "page_width": plan.page_width,
        "page_height": plan.page_height,
        "hero_element_id": plan.hero_element_id,
        "reading_order": list(plan.reading_order),
        "balance_strategy": plan.balance_strategy,
        "whitespace_ratio": round(plan.whitespace_ratio, 4),
        "elements": elements,
    }


def fingerprint_report(report: LayoutValidationReport) -> dict[str, Any]:
    return {
        "valid": report.valid,
        "score": round(report.score, 4),
        "has_critical": report.has_critical(),
        "rule_codes": sorted({issue.rule_code for issue in report.issues}),
    }


def score_baseline(report: LayoutValidationReport) -> dict[str, Any]:
    """Layout Quality Score baseline — not a Visual Quality Score."""
    return {
        "score_kind": "layout_quality",
        "score": round(report.score, 4),
        "valid": report.valid,
        "has_critical": report.has_critical(),
        "blocking_error_count": sum(
            1
            for issue in report.issues
            if issue.severity.value in {"error", "critical"}
        ),
    }


def maybe_export_pptx(
    plan: LayoutPlan,
    design: DesignSystem,
    output_path: Path,
    *,
    title: str,
    content_bundle: SlideContentBundle | None = None,
) -> Path | None:
    """Export PPTX via PptxGenJS when Node runtime is available; else return None."""
    import tempfile

    if shutil.which("node") is None:
        return None
    runner = PptxGenCliRunner(Settings())
    if not runner.is_available() or not runner.layout_plan_script_path.exists():
        return None
    bundle = _bundle_with_icon_asset_paths(plan, content_bundle or SlideContentBundle(page_number=1))
    deck = PptxLayoutPlanAdapter().render_deck(
        title=title,
        slides=[(plan, design, bundle)],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        deck_path = Path(tmp) / "deck.layout_instructions.json"
        deck_path.write_text(
            json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return runner.render_layout_instructions(deck_path, output_path)


def _bundle_with_icon_asset_paths(
    plan: LayoutPlan,
    bundle: SlideContentBundle,
) -> SlideContentBundle:
    """Resolve bundled architectural icon refs for golden PPTX export."""
    from archium.application.visual.architectural_icon_registry import (
        load_default_architectural_icon_registry,
    )

    asset_paths = dict(bundle.asset_paths)
    icon_refs = {
        el.content_ref
        for el in plan.elements
        if el.content_type == LayoutContentType.IMAGE
        and el.content_ref
        and str(el.content_ref).startswith("icon:")
    }
    if not icon_refs:
        return bundle

    registry = load_default_architectural_icon_registry()
    for ref in sorted(icon_refs):
        if ref in asset_paths:
            continue
        icon_key = str(ref).split(":", 1)[1].strip()
        if not icon_key:
            continue
        icon = registry.get_by_name(icon_key)
        if icon is None:
            continue
        svg_path = registry.resolve_svg_path(icon)
        if svg_path.is_file():
            asset_paths[ref] = str(svg_path.resolve())
    return SlideContentBundle(
        asset_paths=asset_paths,
        asset_origins=dict(bundle.asset_origins),
        page_number=bundle.page_number,
        speaker_notes=bundle.speaker_notes,
    )


def assert_or_update_baseline(
    case_dir: Path,
    *,
    plan: LayoutPlan,
    report: LayoutValidationReport,
    design: DesignSystem,
    title: str,
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    plan_fp = fingerprint_plan(plan)
    report_fp = fingerprint_report(report)
    score_fp = score_baseline(report)
    plan_path = case_dir / "layout_plan.json"
    report_path = case_dir / "validation_report.json"
    score_path = case_dir / "score_baseline.json"
    png_path = case_dir / "preview.png"
    pptx_path = case_dir / "deck.pptx"

    if os.environ.get(UPDATE_ENV) == "1":
        plan_path.write_text(
            json.dumps(plan_fp, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            json.dumps(report_fp, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        score_path.write_text(
            json.dumps(score_fp, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        render_layout_preview_png(plan, png_path)
        maybe_export_pptx(plan, design, pptx_path, title=title)
        return

    assert plan_path.exists(), f"Missing golden baseline: {plan_path}"
    assert report_path.exists(), f"Missing golden baseline: {report_path}"
    assert score_path.exists(), f"Missing golden baseline: {score_path}"
    assert png_path.exists(), f"Missing golden preview PNG: {png_path}"

    expected_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    expected_report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_score = json.loads(score_path.read_text(encoding="utf-8"))
    assert plan_fp == expected_plan, (
        f"LayoutPlan fingerprint drift in {case_dir.name}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
    assert report_fp == expected_report, (
        f"Validation fingerprint drift in {case_dir.name}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
    assert score_fp == expected_score, (
        f"Score baseline drift in {case_dir.name}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
