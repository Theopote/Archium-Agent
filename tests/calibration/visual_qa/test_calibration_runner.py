"""Calibration sprint integration tests (run when corpus images are present)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual_qa_calibration import (
    DEFAULT_MANIFEST_PATH,
    corpus_progress,
    load_manifest,
    run_calibration,
)

pytestmark = pytest.mark.calibration

_CORPUS_ROOT = Path(__file__).resolve().parent / "corpus"
_MANIFEST = _CORPUS_ROOT / "manifest.json"


def test_corpus_manifest_is_valid() -> None:
    manifest = load_manifest(_MANIFEST)
    progress = corpus_progress(manifest)
    assert progress["total_target"] == 260
    assert isinstance(manifest.get("samples"), list)


@pytest.mark.skipif(
    not _MANIFEST.is_file() or len(load_manifest(_MANIFEST).get("samples", [])) == 0,
    reason="No labeled calibration samples yet",
)
def test_calibration_report_meets_minimum_corpus() -> None:
    report = run_calibration(_MANIFEST)
    progress = report["corpus_progress"]
    assert progress["total_current"] >= 10, "Need at least 10 labeled samples for smoke calibration"
