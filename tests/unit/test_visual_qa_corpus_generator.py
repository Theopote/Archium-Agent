"""Tests for synthetic Visual QA corpus generation and corpus service."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual_qa_calibration import run_calibration
from archium.application.visual_qa_corpus_service import VisualQACorpusService, validate_sample
from archium.infrastructure.vision.corpus_generator import generate_corpus

pytest.importorskip("PIL")


def test_generate_corpus_writes_expected_sample_count(tmp_path: Path) -> None:
    samples = generate_corpus(
        tmp_path,
        category_targets={"site_plan": 2, "photo": 1},
        overwrite_images=True,
    )
    assert len(samples) == 3
    for sample in samples:
        assert (tmp_path / sample.relative_path).is_file()
        assert sample.labels["drawing_type"] == sample.category


def test_seed_synthetic_corpus_updates_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    service = VisualQACorpusService(manifest_path=manifest_path, corpus_root=tmp_path)
    result = service.seed_synthetic_corpus(overwrite_images=True)
    manifest = service.load()
    assert result["generated_count"] == 260
    assert len(manifest["samples"]) == 260
    assert manifest.get("corpus_kind") == "synthetic_bootstrap"


def test_corpus_service_import_and_calibrate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    service = VisualQACorpusService(manifest_path=manifest_path, corpus_root=tmp_path)
    service.seed_synthetic_corpus(overwrite_images=True)
    report = service.calibrate()
    assert report["corpus_progress"]["total_current"] == 260
    assert service.report_path.is_file()
    assert "checks" in report


def test_validate_sample_rejects_invalid_category() -> None:
    errors = validate_sample(
        {
            "id": "bad",
            "path": "images/bad.png",
            "category": "unknown",
            "labels": {"drawing_type": "unknown"},
        }
    )
    assert any("category" in error for error in errors)


def test_run_calibration_on_seeded_corpus(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    service = VisualQACorpusService(manifest_path=manifest_path, corpus_root=tmp_path)
    service.seed_synthetic_corpus(overwrite_images=True)
    report = run_calibration(manifest_path, corpus_root=tmp_path)
    dim = report["checks"]["VISUAL.DIMENSIONS_TOO_SMALL"]
    assert dim["evaluated"] > 0
