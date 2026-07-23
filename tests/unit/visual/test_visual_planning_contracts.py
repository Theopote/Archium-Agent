"""Visual planning contracts: capacity warnings + DesignBrief → Intent."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.design_brief_intent import (
    apply_design_brief_to_intent,
    resolve_brief_layout_family,
)
from archium.application.visual.layout_planning_service import (
    capacity_blocker_messages,
    format_layout_decision_warnings,
)
from archium.domain.slide_design_brief import BriefStatus, SlideDesignBrief
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.slide_capacity_budget import (
    CAPACITY_IMPOSSIBLE_RULE,
    CAPACITY_OVERLOAD_RULE,
)
from archium.domain.visual.visual_intent import VisualIntent


def test_format_layout_decision_warnings_includes_capacity() -> None:
    lines = format_layout_decision_warnings(
        [
            {
                "code": CAPACITY_OVERLOAD_RULE,
                "severity": "major",
                "detail": "capacity_ratio=1.40",
                "recommended_action": "adapt_content",
            },
            {"code": "OTHER.IGNORED", "detail": "skip"},
        ]
    )
    assert len(lines) == 1
    assert CAPACITY_OVERLOAD_RULE in lines[0]
    assert "adapt_content" in lines[0]


def test_capacity_blocker_messages_only_impossible() -> None:
    messages = capacity_blocker_messages(
        [
            {"code": CAPACITY_OVERLOAD_RULE, "detail": "overloaded"},
            {
                "code": CAPACITY_IMPOSSIBLE_RULE,
                "detail": "drawing exceeds canvas",
            },
        ]
    )
    assert len(messages) == 1
    assert CAPACITY_IMPOSSIBLE_RULE in messages[0]
    assert "drawing exceeds canvas" in messages[0]


def test_photo_evidence_grid_aliases_to_evidence_board() -> None:
    assert resolve_brief_layout_family("photo_evidence_grid") == LayoutFamily.EVIDENCE_BOARD
    assert resolve_brief_layout_family("evidence_board") == LayoutFamily.EVIDENCE_BOARD


def test_apply_design_brief_overrides_intent_preferences() -> None:
    slide_id = uuid4()
    presentation_id = uuid4()
    intent = VisualIntent(
        slide_id=slide_id,
        presentation_id=presentation_id,
        preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT],
        density_level=DensityLevel.BALANCED,
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        visual_priority="title > body",
        audience_takeaway="old",
        communication_goal="old goal",
    )
    brief = SlideDesignBrief(
        page_order=0,
        page_task="展示现场证据",
        central_claim="现状问题清晰可见",
        primary_visual_type="photo",
        layout_family="photo_evidence_grid",
        expected_density="high",
        status=BriefStatus.APPROVED,
    )
    updated = apply_design_brief_to_intent(intent, brief)
    assert updated.preferred_layout_families[0] == LayoutFamily.EVIDENCE_BOARD
    assert updated.density_level == DensityLevel.COMPACT
    assert updated.dominant_content_type == VisualContentType.PHOTO_EVIDENCE
    assert updated.audience_takeaway == "现状问题清晰可见"
    assert updated.communication_goal == "展示现场证据"
