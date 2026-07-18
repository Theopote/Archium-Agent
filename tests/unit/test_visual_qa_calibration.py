"""Unit tests for visual QA calibration metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from archium.application.visual_qa_calibration import (
    ALWAYS_FORMAL_RULE_CODES,
    DEFAULT_FORMAL_EMIT_RULE_CODES,
    PRECISION_TARGETS,
    analyze_sample_image,
    formal_emit_rule_codes,
    load_manifest,
    run_calibration,
    write_calibration_report,
)
from archium.domain.review_rules import ReviewRuleCode
from PIL import Image, ImageDraw

pytest.importorskip("PIL")


def _write_site_plan(path: Path, *, with_north: bool, with_legend: bool, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, size[0] - 80, size[1] - 80), outline=(30, 30, 30), width=3)
    if with_north:
        corner = size[0] - 80
        draw.polygon([(corner + 40, 10), (corner + 10, 85), (corner + 70, 85)], fill=(10, 10, 10))
    if with_legend:
        base_y = size[1] - 70
        for index, color in enumerate([(220, 30, 30), (30, 120, 220), (40, 180, 80)]):
            x = 40 + index * 90
            draw.rectangle((x, base_y, x + 50, base_y + 20), fill=color)
    image.save(path, format="PNG")


def _write_manifest(path: Path, samples: list[dict[str, object]]) -> None:
    payload = {"version": 1, "samples": samples}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class TestVisualQACalibrationMetrics:
    def test_run_calibration_computes_confusion_matrix(self, tmp_path: Path) -> None:
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        good = images_dir / "good_plan.png"
        small = images_dir / "small_plan.png"
        _write_site_plan(good, with_north=True, with_legend=True, size=(1200, 900))
        _write_site_plan(small, with_north=False, with_legend=False, size=(640, 480))

        manifest_path = tmp_path / "manifest.json"
        _write_manifest(
            manifest_path,
            [
                {
                    "id": "good",
                    "path": "images/good_plan.png",
                    "category": "site_plan",
                    "labels": {
                        "drawing_type": "site_plan",
                        "has_north_arrow": True,
                        "has_legend": True,
                        "is_low_resolution": False,
                    },
                },
                {
                    "id": "small",
                    "path": "images/small_plan.png",
                    "category": "site_plan",
                    "labels": {
                        "drawing_type": "site_plan",
                        "has_north_arrow": False,
                        "has_legend": False,
                        "is_low_resolution": True,
                    },
                },
            ],
        )

        report = run_calibration(manifest_path)
        dim = report["checks"][ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL]
        assert dim["true_positive"] == 1
        assert dim["false_positive"] == 0
        assert dim["false_negative"] == 0
        assert dim["true_negative"] == 1

        north = report["checks"][ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW]
        assert north["evaluated"] == 2

    def test_formal_emit_defaults_without_report(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing_report.json"
        codes = formal_emit_rule_codes(missing)
        assert ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL in codes
        assert ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW not in codes
        assert codes >= ALWAYS_FORMAL_RULE_CODES
        assert codes == formal_emit_rule_codes(missing)

    def test_formal_emit_reads_calibration_report(self, tmp_path: Path) -> None:
        report_path = tmp_path / "calibration_report.json"
        write_calibration_report(
            {
                "analyzer_version": "1.0.0",
                "checks": {
                    ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW: {
                        "meets_target": True,
                        "formal_emit_eligible": True,
                    }
                },
                "formal_emit_eligible_rule_codes": [
                    ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW,
                ],
            },
            report_path,
        )
        codes = formal_emit_rule_codes(report_path)
        assert ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW in codes

    def test_analyze_sample_image_returns_report(self, tmp_path: Path) -> None:
        image_path = tmp_path / "plan.png"
        _write_site_plan(image_path, with_north=True, with_legend=True, size=(1200, 900))
        report = analyze_sample_image(image_path)
        assert report.check("north_arrow") is not None
        assert report.asset_path == str(image_path)

    def test_precision_targets_match_sprint_goals(self) -> None:
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL] == 0.95
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH] == 0.85
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW] == 0.85
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_MISSING_LEGEND] == 0.80
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_CONTENT_CLIPPED] == 0.75
        assert PRECISION_TARGETS[ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY] == 0.75
        assert ALWAYS_FORMAL_RULE_CODES | {
            ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL
        } == DEFAULT_FORMAL_EMIT_RULE_CODES

    def test_load_manifest_requires_samples(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="samples"):
            load_manifest(bad)
