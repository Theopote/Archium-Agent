"""Visual QA calibration metrics against a labeled image corpus."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from archium.domain.review_rules import ReviewRuleCode
from archium.domain.visual_qa import VisualQAReport
from archium.infrastructure.vision.analyzer import analyze_image
from archium.infrastructure.vision.analyzer_version import ANALYZER_VERSION

DEFAULT_MANIFEST_PATH = Path("tests/calibration/visual_qa/corpus/manifest.json")
DEFAULT_REPORT_PATH = Path("tests/calibration/visual_qa/corpus/calibration_report.json")

CORPUS_CATEGORY_TARGETS: dict[str, int] = {
    "site_plan": 50,
    "floor_plan": 50,
    "section": 30,
    "elevation": 30,
    "diagram": 50,
    "photo": 50,
}

PRECISION_TARGETS: dict[str, float] = {
    ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND: 0.99,
    ReviewRuleCode.VISUAL_ASSET_UNREADABLE: 0.99,
    ReviewRuleCode.VISUAL_ASSET_FORMAT_UNSUPPORTED: 0.99,
    ReviewRuleCode.VISUAL_ASSET_DECODE_FAILED: 0.99,
    ReviewRuleCode.VISUAL_ASSET_PERMISSION_DENIED: 0.99,
    ReviewRuleCode.VISUAL_ASSET_RECORD_MISSING: 0.99,
    ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL: 0.95,
    ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH: 0.85,
    ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW: 0.85,
    ReviewRuleCode.VISUAL_MISSING_LEGEND: 0.80,
    ReviewRuleCode.VISUAL_CONTENT_CLIPPED: 0.75,
    ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY: 0.75,
    ReviewRuleCode.VISUAL_EXCESSIVE_MARGINS: 0.75,
    ReviewRuleCode.VISUAL_LOW_COLOR_CONTRAST: 0.75,
}

ALWAYS_FORMAL_RULE_CODES: frozenset[str] = frozenset(
    {
        ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND,
        ReviewRuleCode.VISUAL_ASSET_UNREADABLE,
        ReviewRuleCode.VISUAL_ASSET_FORMAT_UNSUPPORTED,
        ReviewRuleCode.VISUAL_ASSET_DECODE_FAILED,
        ReviewRuleCode.VISUAL_ASSET_PERMISSION_DENIED,
        ReviewRuleCode.VISUAL_ASSET_RECORD_MISSING,
    }
)

DEFAULT_FORMAL_EMIT_RULE_CODES: frozenset[str] = ALWAYS_FORMAL_RULE_CODES | frozenset(
    {ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL}
)


@dataclass(frozen=True)
class BinaryCheckSpec:
    """Maps one analyzer output to a binary calibration metric."""

    rule_code: str
    check_name: str
    ground_truth_positive: Callable[[dict[str, Any]], bool | None]
    predicted_positive: Callable[[VisualQAReport], bool]


@dataclass
class ConfusionCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    skipped: int = 0

    @property
    def evaluated(self) -> int:
        return self.true_positive + self.false_positive + self.false_negative + self.true_negative


@dataclass
class CheckMetrics:
    rule_code: str
    check_name: str
    counts: ConfusionCounts = field(default_factory=ConfusionCounts)
    target_precision: float | None = None
    drawing_type_correct: int = 0
    drawing_type_total: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.counts.true_positive + self.counts.false_positive
        if denom == 0:
            return None
        return self.counts.true_positive / denom

    @property
    def recall(self) -> float | None:
        denom = self.counts.true_positive + self.counts.false_negative
        if denom == 0:
            return None
        return self.counts.true_positive / denom

    @property
    def false_positive_rate(self) -> float | None:
        denom = self.counts.false_positive + self.counts.true_negative
        if denom == 0:
            return None
        return self.counts.false_positive / denom

    @property
    def false_negative_rate(self) -> float | None:
        denom = self.counts.true_positive + self.counts.false_negative
        if denom == 0:
            return None
        return self.counts.false_negative / denom

    @property
    def drawing_type_accuracy(self) -> float | None:
        if self.drawing_type_total == 0:
            return None
        return self.drawing_type_correct / self.drawing_type_total

    @property
    def score(self) -> float | None:
        if self.check_name == "drawing_classifier":
            return self.drawing_type_accuracy
        return self.precision

    @property
    def meets_target(self) -> bool | None:
        if self.target_precision is None:
            return None
        score = self.score
        if score is None:
            return None
        return score >= self.target_precision

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_code": self.rule_code,
            "check_name": self.check_name,
            "true_positive": self.counts.true_positive,
            "false_positive": self.counts.false_positive,
            "false_negative": self.counts.false_negative,
            "true_negative": self.counts.true_negative,
            "skipped": self.counts.skipped,
            "evaluated": self.counts.evaluated,
            "precision": _round_or_none(self.precision),
            "recall": _round_or_none(self.recall),
            "false_positive_rate": _round_or_none(self.false_positive_rate),
            "false_negative_rate": _round_or_none(self.false_negative_rate),
            "drawing_type_accuracy": _round_or_none(self.drawing_type_accuracy),
            "target_precision": self.target_precision,
            "meets_target": self.meets_target,
            "formal_emit_eligible": self.meets_target is True,
        }


def _round_or_none(value: float | None, *, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _label_bool(labels: dict[str, Any], key: str) -> bool | None:
    if key not in labels or labels[key] is None:
        return None
    return bool(labels[key])


def _check_failed(report: VisualQAReport, check_name: str) -> bool:
    check = report.check(check_name)
    if check is None:
        return False
    return not check.passed


BINARY_CHECK_SPECS: tuple[BinaryCheckSpec, ...] = (
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL,
        check_name="image_dimensions",
        ground_truth_positive=lambda labels: _label_bool(labels, "is_low_resolution"),
        predicted_positive=lambda report: _check_failed(report, "image_dimensions"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_EXCESSIVE_MARGINS,
        check_name="blank_margins",
        ground_truth_positive=lambda labels: _label_bool(labels, "excessive_margins"),
        predicted_positive=lambda report: _check_failed(report, "blank_margins"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_LOW_COLOR_CONTRAST,
        check_name="dominant_colors",
        ground_truth_positive=lambda labels: _label_bool(labels, "low_contrast"),
        predicted_positive=lambda report: _check_failed(report, "dominant_colors"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_CONTENT_CLIPPED,
        check_name="edge_clipping",
        ground_truth_positive=lambda labels: _label_bool(labels, "is_clipped"),
        predicted_positive=lambda report: _check_failed(report, "edge_clipping"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY,
        check_name="text_density",
        ground_truth_positive=lambda labels: _label_bool(labels, "high_text_density"),
        predicted_positive=lambda report: _check_failed(report, "text_density"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW,
        check_name="north_arrow",
        ground_truth_positive=lambda labels: (
            False if _label_bool(labels, "has_north_arrow") is True else True
            if _label_bool(labels, "has_north_arrow") is False
            else None
        ),
        predicted_positive=lambda report: _check_failed(report, "north_arrow"),
    ),
    BinaryCheckSpec(
        rule_code=ReviewRuleCode.VISUAL_MISSING_LEGEND,
        check_name="legend_region",
        ground_truth_positive=lambda labels: (
            False if _label_bool(labels, "has_legend") is True else True
            if _label_bool(labels, "has_legend") is False
            else None
        ),
        predicted_positive=lambda report: _check_failed(report, "legend_region"),
    ),
)


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "samples" not in payload:
        raise ValueError(f"Manifest missing 'samples': {path}")
    return cast(dict[str, Any], payload)


def corpus_progress(manifest: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {key: 0 for key in CORPUS_CATEGORY_TARGETS}
    for sample in manifest.get("samples", []):
        category = str(sample.get("category", "")).strip()
        if category in counts:
            counts[category] += 1
    return {
        "targets": dict(CORPUS_CATEGORY_TARGETS),
        "current": counts,
        "remaining": {key: max(0, CORPUS_CATEGORY_TARGETS[key] - counts[key]) for key in counts},
        "total_target": sum(CORPUS_CATEGORY_TARGETS.values()),
        "total_current": sum(counts.values()),
    }


def analyze_sample_image(image_path: Path) -> VisualQAReport:
    from PIL import Image

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        return analyze_image(uuid4(), str(image_path), rgb)


def run_calibration(
    manifest_path: Path,
    *,
    corpus_root: Path | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    root = corpus_root or manifest_path.parent
    metrics_by_rule: dict[str, CheckMetrics] = {}

    for spec in BINARY_CHECK_SPECS:
        metrics_by_rule[spec.rule_code] = CheckMetrics(
            rule_code=spec.rule_code,
            check_name=spec.check_name,
            target_precision=PRECISION_TARGETS.get(spec.rule_code),
        )
    drawing_metrics = CheckMetrics(
        rule_code=ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH,
        check_name="drawing_classifier",
        target_precision=PRECISION_TARGETS[ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH],
    )

    missing_files: list[str] = []
    for sample in manifest.get("samples", []):
        rel_path = str(sample["path"])
        image_path = root / rel_path
        if not image_path.is_file():
            missing_files.append(rel_path)
            continue

        report = analyze_sample_image(image_path)
        labels = dict(sample.get("labels", {}))

        for spec in BINARY_CHECK_SPECS:
            gt_positive = spec.ground_truth_positive(labels)
            if gt_positive is None:
                metrics_by_rule[spec.rule_code].counts.skipped += 1
                continue
            predicted = spec.predicted_positive(report)
            counts = metrics_by_rule[spec.rule_code].counts
            if gt_positive and predicted:
                counts.true_positive += 1
            elif not gt_positive and predicted:
                counts.false_positive += 1
            elif gt_positive and not predicted:
                counts.false_negative += 1
            else:
                counts.true_negative += 1

        expected_type = labels.get("drawing_type")
        if expected_type is not None and report.drawing_type is not None:
            drawing_metrics.drawing_type_total += 1
            if report.drawing_type == expected_type:
                drawing_metrics.drawing_type_correct += 1

    checks = {code: metric.to_dict() for code, metric in metrics_by_rule.items()}
    checks[drawing_metrics.rule_code] = drawing_metrics.to_dict()

    formal_emit_eligible = sorted(
        rule_code
        for rule_code, payload in checks.items()
        if payload.get("formal_emit_eligible")
    )
    formal_emit_eligible.extend(sorted(ALWAYS_FORMAL_RULE_CODES))
    formal_emit_eligible = sorted(set(formal_emit_eligible))

    return {
        "analyzer_version": ANALYZER_VERSION,
        "manifest_path": str(manifest_path),
        "corpus_progress": corpus_progress(manifest),
        "missing_files": missing_files,
        "checks": checks,
        "formal_emit_eligible_rule_codes": formal_emit_eligible,
    }


def write_calibration_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_calibration_report(path: Path = DEFAULT_REPORT_PATH) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def formal_emit_rule_codes(report_path: Path = DEFAULT_REPORT_PATH) -> frozenset[str]:
    """Rule codes allowed to emit formal (non-suspected) issues after calibration."""
    report = load_calibration_report(report_path)
    if report is None:
        return DEFAULT_FORMAL_EMIT_RULE_CODES

    eligible = set(ALWAYS_FORMAL_RULE_CODES)
    for rule_code, payload in report.get("checks", {}).items():
        if payload.get("formal_emit_eligible"):
            eligible.add(rule_code)
    for rule_code in report.get("formal_emit_eligible_rule_codes", []):
        eligible.add(rule_code)
    return frozenset(eligible)
