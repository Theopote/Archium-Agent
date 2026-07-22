"""Tests for SceneRevisionSummary domain helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.domain.scene_revision_summary import (
    SceneRevisionSummary,
    map_scene_revision_source,
)


def test_map_scene_revision_source_known_values() -> None:
    assert map_scene_revision_source("manual") == "manual_edit"
    assert map_scene_revision_source("ai_proposal") == "ai_proposal"
    assert map_scene_revision_source("automatic_repair") == "qa_repair"
    assert map_scene_revision_source("template_application") == "layout_replan"


def test_map_scene_revision_source_passthrough_timeline_values() -> None:
    assert map_scene_revision_source("asset_rebind") == "asset_rebind"
    assert map_scene_revision_source("import_recovery") == "import_recovery"


def test_map_scene_revision_source_unknown_defaults_manual_edit() -> None:
    assert map_scene_revision_source("legacy") == "manual_edit"


def test_scene_revision_summary_defaults() -> None:
    summary = SceneRevisionSummary(
        revision_id=uuid4(),
        scene_id=uuid4(),
        version=12,
        source="manual_edit",
        summary="用户编辑：修改中心结论",
        created_at=datetime.now(UTC),
    )
    assert summary.accepted is True
    assert summary.is_current is False
    assert summary.qa_status == "unknown"
