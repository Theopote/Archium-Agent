"""Entry orientation — route users before creating a Project."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import ProjectOriginMode


class EntryOrientation(StrEnum):
    """Primary entry orientation (not a claim that materials are complete/absent)."""

    CONCEPT_EXPLORATION = ProjectOriginMode.CONCEPT_EXPLORATION.value
    EXISTING_PROJECT = ProjectOriginMode.EXISTING_PROJECT.value
    RESEARCH_PROGRAMMING = ProjectOriginMode.RESEARCH_PROGRAMMING.value

    def to_origin_mode(self) -> ProjectOriginMode:
        return ProjectOriginMode(self.value)


class EntryIntentResult(DomainModel):
    """Classifier output for genesis routing."""

    orientation: EntryOrientation
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    rationale: str = ""
    suggested_next: str = ""
    raw_input: str = ""
    needs_confirmation: bool = False

    @classmethod
    def uncertain(cls, raw_input: str, *, rationale: str = "") -> EntryIntentResult:
        return cls(
            orientation=EntryOrientation.CONCEPT_EXPLORATION,
            confidence=0.0,
            rationale=rationale or "无法自动判断主路径，请手动选择。",
            suggested_next="请选择：以想法为主、以现有资料为主，或策划与可研。",
            raw_input=raw_input.strip(),
            needs_confirmation=True,
        )

    def with_confirmation_flag(self, *, threshold: float = 0.55) -> EntryIntentResult:
        needs = self.confidence < threshold
        if needs == self.needs_confirmation:
            return self
        return self.model_copy(update={"needs_confirmation": needs})
