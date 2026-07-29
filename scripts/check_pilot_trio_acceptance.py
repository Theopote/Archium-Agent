#!/usr/bin/env python3
"""Pre-human acceptance checks for the architectural benchmark pilot trio."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.application.asset_presentation_readiness_service import (  # noqa: E402
    analyze_and_cache_asset_presentation_readiness,
    evaluate_asset_presentation_readiness,
)
from archium.application.visual.layout_validation_service import LayoutValidationService  # noqa: E402
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual import default_presentation_design_system
from archium.infrastructure.layout.geometry import safe_area
from tests.benchmark.architectural_slides.artifacts import case_dir  # noqa: E402
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case  # noqa: E402
from tests.benchmark.architectural_slides.curated_assets import count_case_asset_provenance  # noqa: E402

PILOT_CASES = (
    "case_001_site_plan",
    "case_002_site_photos",
    "case_006_project_hero",
)

_CRITERIA = {
    "case_001_site_plan": "site_plan_readable_drawing",
    "case_002_site_photos": "evidence_hierarchy",
    "case_006_project_hero": "hero_dominance",
}


def _load_manifest(case_id: str) -> dict[str, object] | None:
    path = case_dir(case_id) / "render_manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _pixel_readiness(asset_path: Path, *, asset_type: AssetType) -> dict[str, object]:
    asset = Asset(
        project_id=uuid4(),
        filename=asset_path.name,
        path=str(asset_path),
        asset_type=asset_type,
    )
    analyzed = analyze_and_cache_asset_presentation_readiness(asset)
    readiness = evaluate_asset_presentation_readiness(
        analyzed,
        image_path=asset_path,
        intended_slot="hero" if asset_type == AssetType.DRAWING else "evidence",
    )
    acceptable = (
        readiness.pixel_analyzed
        and not readiness.is_placeholder
        and readiness.visual_information_density >= 0.12
    )
    return {
        "pixel_analyzed": readiness.pixel_analyzed,
        "presentation_ready": readiness.presentation_ready,
        "pixel_acceptable": acceptable,
        "is_placeholder": readiness.is_placeholder,
        "density": readiness.visual_information_density,
        "reasons": list(readiness.reasons),
    }


def _asset_type_for_case(case_id: str) -> AssetType:
    if case_id == "case_001_site_plan":
        return AssetType.DRAWING
    if case_id == "case_002_site_photos":
        return AssetType.PHOTO
    return AssetType.IMAGE


def check_case(case_id: str) -> dict[str, object]:
    result = build_benchmark_case(case_id)
    design = default_presentation_design_system()
    report = LayoutValidationService().validate(
        result.plan,
        design,
        drawing_hero=case_id == "case_001_site_plan",
    )
    safe = safe_area(design)
    hero = (
        result.plan.element_by_id(result.plan.hero_element_id)
        if result.plan.hero_element_id
        else None
    )
    hero_ratio = round(hero.area / safe.area, 3) if hero else 0.0
    photos = sorted(
        [el for el in result.plan.elements if el.id.startswith("photo_")],
        key=lambda item: -item.area,
    )
    manifest = _load_manifest(case_id)
    assets_root = case_dir(case_id)
    total, curated, placeholder = count_case_asset_provenance(assets_root)
    asset_type = _asset_type_for_case(case_id)
    asset_checks = [
        _pixel_readiness(path, asset_type=asset_type)
        for path in sorted((assets_root / "assets").glob("*.png"))
    ]

    automation_pass = {
        "layout_valid": report.valid,
        "hero_ratio_ge_0_65": hero_ratio >= 0.65 if case_id != "case_002_site_photos" else True,
        "evidence_primary_larger": (
            photos[0].area > photos[1].area if len(photos) >= 2 else True
        ),
        "render_valid": bool(manifest and manifest.get("render_valid")),
        "fresh_screenshot": bool(
            manifest
            and manifest.get("pptx_screenshot_generated")
            and not manifest.get("pptx_screenshot_reused")
        ),
        "placeholder_assets_zero": placeholder == 0,
        "assets_pixel_acceptable": all(item.get("pixel_acceptable") for item in asset_checks),
    }

    suggested_reporting_ready = "do_not_use"
    if automation_pass["render_valid"] and automation_pass["fresh_screenshot"]:
        if (
            automation_pass["layout_valid"]
            and automation_pass["placeholder_assets_zero"]
            and automation_pass["assets_pixel_acceptable"]
            and automation_pass["evidence_primary_larger"]
            and automation_pass["hero_ratio_ge_0_65"]
        ):
            suggested_reporting_ready = "ready_with_minor_edits"
        else:
            suggested_reporting_ready = "needs_review"

    return {
        "case_id": case_id,
        "criterion": _CRITERIA[case_id],
        "layout_family": result.plan.layout_family.value,
        "layout_variant": result.plan.layout_variant,
        "hero_safe_area_ratio": hero_ratio,
        "layout_issue_codes": sorted({issue.rule_code for issue in report.issues}),
        "asset_provenance": {
            "total": total,
            "curated": curated,
            "placeholder": placeholder,
        },
        "asset_readiness": asset_checks,
        "render_manifest": manifest,
        "automation_pass": automation_pass,
        "suggested_reporting_ready": suggested_reporting_ready,
        "human_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_PROJECT_ROOT
        / "docs/rehearsal/sessions/2026-07-29-pilot-trio-rerender/automation-precheck.json",
    )
    args = parser.parse_args(argv)

    results = [check_case(case_id) for case_id in PILOT_CASES]
    payload = {"cases": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in results:
        print(
            f"{item['case_id']}: layout_valid={item['automation_pass']['layout_valid']} "
            f"hero_ratio={item['hero_safe_area_ratio']} "
            f"suggested={item['suggested_reporting_ready']}"
        )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
