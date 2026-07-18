"""Unit tests for programmatic diagram generation."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.domain.enums import VisualType
from archium.infrastructure.renderers.diagram_generator import (
    can_generate_diagram,
    generate_fallback_diagram,
)


def test_can_generate_diagram_for_plan_and_timeline() -> None:
    assert can_generate_diagram(VisualType.SITE_PLAN) is True
    assert can_generate_diagram(VisualType.TIMELINE) is True
    assert can_generate_diagram(VisualType.RENDERING) is False


def test_generate_fallback_diagram_writes_png(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    output = tmp_path / "fallback.png"
    path = generate_fallback_diagram(
        output,
        title="交通组织示意",
        visual_type=VisualType.DIAGRAM,
        description="流线关系示意",
        key_points=["人行主入口", "车行环路", "后勤通道"],
        message="通过分流改善院区交通",
    )
    assert path.exists()
    assert path.stat().st_size > 500
