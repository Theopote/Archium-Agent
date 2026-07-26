"""DOM-024 — ConceptDirection ↔ DesignIntent sync contract."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_intent_from_direction import design_intent_from_direction
from archium.application.direction_intent_sync import (
    diff_direction_intent,
    is_direction_intent_aligned,
    source_direction_matches,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.spatial_design import DesignRule, SpatialIntent


def _direction(**overrides: object) -> ConceptDirection:
    base = {
        "project_id": uuid4(),
        "title": "生态共生",
        "theme": "生态共生",
        "summary": "以聚落肌理回应山地",
        "experience_focus": "步行可达的院落序列",
        "design_rationale": DesignRationale(
            statement="保留主轴线",
            strategy="轴线承载分期",
            observation="轴线清晰",
        ),
        "spatial_intent": SpatialIntent(
            spatial_relationships="院落串联",
            movement_experience="低层退台步行",
        ),
        "design_rules": [
            DesignRule(
                principle="主入口朝南",
                spatial_translation="南向入口院",
            ),
        ],
    }
    base.update(overrides)
    return ConceptDirection(**base)  # type: ignore[arg-type]


def test_projection_stamps_source_direction_and_aligns() -> None:
    direction = _direction()
    intent = design_intent_from_direction(direction)
    assert source_direction_matches(intent, direction.id)
    assert intent.source_direction_id == direction.id
    assert is_direction_intent_aligned(direction, intent)
    assert diff_direction_intent(direction, intent).display_line() == "方向与意图一致"


def test_diff_reports_theme_and_rationale_drift() -> None:
    direction = _direction()
    intent = design_intent_from_direction(direction)
    drifted = intent.model_copy(
        update={
            "theme": "完全不同的主题",
            "design_rationale": DesignRationale(statement="另一判断"),
        }
    )
    diff = diff_direction_intent(direction, drifted)
    assert diff.aligned is False
    assert "theme" in diff.fields
    assert "design_rationale" in diff.fields


def test_source_direction_id_mismatch_is_drift() -> None:
    direction = _direction()
    intent = design_intent_from_direction(direction).model_copy(
        update={"source_direction_id": uuid4()}
    )
    assert "source_direction_id" in diff_direction_intent(direction, intent).fields


def test_unlinked_intent_without_shared_payload_is_aligned() -> None:
    """Intent-only overlays with empty direction shared fields do not false-alarm."""
    direction = ConceptDirection(
        project_id=uuid4(),
        title="空方向",
        theme="",
        summary="",
    )
    intent = DesignIntent(theme="仅意图主题", social_background="甲方诉求")
    assert is_direction_intent_aligned(direction, intent)
