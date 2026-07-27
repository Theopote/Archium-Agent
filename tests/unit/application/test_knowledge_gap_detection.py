"""Knowledge gap detection — project-type aware required keys."""

from __future__ import annotations

from uuid import uuid4

from archium.application.knowledge_gap_detection import (
    detect_knowledge_gaps,
    resolve_required_fact_keys,
)
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact


def test_resolve_required_fact_keys_excludes_bed_count_for_temple() -> None:
    keys = resolve_required_fact_keys(
        facts=[],
        project_name="陕西三原县清凉寺重建",
        project_description="原址重建寺庙",
    )
    assert "bed_count" not in keys
    assert "location" in keys


def test_lightweight_mode_skips_blocking_missing_metrics() -> None:
    project_id = uuid4()
    report = detect_knowledge_gaps(
        project_id,
        facts=[],
        required_fact_keys=("plot_ratio", "bed_count"),
        lightweight_mode=True,
    )
    assert report.gap_count == 2
    assert report.blocking_gaps == []
