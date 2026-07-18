"""Asset matching score adjustments from cached visual QA reports."""

from __future__ import annotations

from archium.application.visual_qa_policy import DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE
from archium.domain.enums import VisualType
from archium.domain.slide import VisualRequirement
from archium.domain.visual_qa import VisualQAReport

_DRAWING_MATCH_BONUS = 0.3
_DRAWING_MISMATCH_PENALTY = 0.25

_VISUAL_TYPE_TO_DRAWING: dict[VisualType, str] = {
    VisualType.SITE_PLAN: "site_plan",
    VisualType.FLOOR_PLAN: "floor_plan",
    VisualType.SECTION: "section",
    VisualType.ELEVATION: "elevation",
    VisualType.DIAGRAM: "diagram",
    VisualType.MAP: "site_plan",
    VisualType.SITE_PHOTO: "photo",
    VisualType.RENDERING: "photo",
}


def drawing_type_match_adjustment(
    requirement: VisualRequirement,
    report: VisualQAReport | None,
) -> float:
    """Return a score bonus/penalty from drawing_classifier when confidence is high enough."""
    if report is None or report.drawing_type is None:
        return 0.0

    expected = _VISUAL_TYPE_TO_DRAWING.get(requirement.type)
    if expected is None:
        return 0.0

    confidence = report.drawing_type_confidence or 0.0
    if confidence < DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE:
        return 0.0

    if report.drawing_type == expected:
        return _DRAWING_MATCH_BONUS * confidence
    return -_DRAWING_MISMATCH_PENALTY * confidence
