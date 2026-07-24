"""Recommended next workflow — what Archium should prioritize now."""

from __future__ import annotations

from enum import StrEnum


class RecommendedWorkflow(StrEnum):
    """Primary workflow emphasis derived from knowledge state and next actions."""

    EXPLORE = "explore"
    RESEARCH = "research"
    MATERIALS = "materials"
    MISSION = "mission"
    DESIGN = "design"
    DELIVER = "deliver"
