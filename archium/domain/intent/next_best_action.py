"""Next-best-action suggestions from context intelligence."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class NextBestActionType(StrEnum):
    RESEARCH = "research"
    ASK = "ask"
    EXPLORE_DIRECTIONS = "explore_directions"
    UPLOAD_MATERIALS = "upload_materials"
    GENERATE_MISSION = "generate_mission"
    OPEN_MISSION = "open_mission"


class NextBestAction(DomainModel):
    action: NextBestActionType
    reason: str = ""
    question: str | None = None
    priority: int = 0
    # Explainable NBA card fields (optional; UI fills defaults when empty).
    why_now: str = ""
    affects: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    reversible: bool | None = None
