"""Spatial intent & design rules — concept → architecture translation layer.

Not free-text only: typed relationships and executable-ish rules that can be
evaluated, prompted, and carried into Mission DesignIntent.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class SpatialIntent(DomainModel):
    """How design intent becomes space (not a slogan)."""

    spatial_relationships: str = Field(
        default="",
        description="Building–landscape / figure–ground / interior–exterior relations.",
    )
    movement_experience: str = Field(
        default="",
        description="Path, pace, sequence of movement.",
    )
    public_private_structure: str = Field(
        default="",
        description="Public / shared / private layering.",
    )
    light_strategy: str = Field(
        default="",
        description="Daylight, shadow, seasonal light attitude.",
    )
    landscape_relation: str = Field(
        default="",
        description="Embed / terrace / courtyard / overlook / permeate…",
    )

    def is_empty(self) -> bool:
        return not any(
            part.strip()
            for part in (
                self.spatial_relationships,
                self.movement_experience,
                self.public_private_structure,
                self.light_strategy,
                self.landscape_relation,
            )
        )

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        lines = ["【空间意图 SpatialIntent】"]
        if self.spatial_relationships.strip():
            lines.append(f"空间关系：{self.spatial_relationships.strip()}")
        if self.movement_experience.strip():
            lines.append(f"动线体验：{self.movement_experience.strip()}")
        if self.public_private_structure.strip():
            lines.append(f"公私结构：{self.public_private_structure.strip()}")
        if self.light_strategy.strip():
            lines.append(f"光策略：{self.light_strategy.strip()}")
        if self.landscape_relation.strip():
            lines.append(f"景观关系：{self.landscape_relation.strip()}")
        return "\n".join(lines)


class DesignRule(DomainModel):
    """One transferable rule derived from a concept (spatial + formal + evaluation)."""

    principle: str = Field(default="", description="Core design principle in one line.")
    spatial_translation: str = Field(
        default="",
        description="How the principle becomes space / organization.",
    )
    formal_translation: str = Field(
        default="",
        description="How the principle becomes massing / form language.",
    )
    evaluation_method: str = Field(
        default="",
        description="How to judge success (question or metric cue).",
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    def is_empty(self) -> bool:
        return not any(
            part.strip()
            for part in (
                self.principle,
                self.spatial_translation,
                self.formal_translation,
                self.evaluation_method,
            )
        )

    def to_prompt_line(self) -> str:
        bits = [self.principle.strip()]
        if self.spatial_translation.strip():
            bits.append(f"空间→{self.spatial_translation.strip()}")
        if self.formal_translation.strip():
            bits.append(f"形式→{self.formal_translation.strip()}")
        if self.evaluation_method.strip():
            bits.append(f"评价：{self.evaluation_method.strip()}")
        return " · ".join(part for part in bits if part)


class DesignDecision(DomainModel):
    """One recorded design decision (IntentEvolution payload / history unit)."""

    decision: str = Field(default="", description="What was decided.")
    alternatives: list[str] = Field(default_factory=list)
    chosen: str = Field(default="", description="Chosen option label.")
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    impact: str = Field(
        default="",
        description="What changes in space / program / expression.",
    )
    direction_id: str = ""
    direction_title: str = ""

    def is_empty(self) -> bool:
        return not (self.decision.strip() or self.chosen.strip() or self.reason.strip())

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        lines = ["【设计决策 DesignDecision】"]
        if self.decision.strip():
            lines.append(f"决策：{self.decision.strip()}")
        if self.chosen.strip():
            lines.append(f"选定：{self.chosen.strip()}")
        if self.alternatives:
            lines.append(
                "备选：\n"
                + "\n".join(f"- {item}" for item in self.alternatives if item.strip())
            )
        if self.reason.strip():
            lines.append(f"原因：{self.reason.strip()}")
        if self.evidence:
            lines.append(
                "证据：\n" + "\n".join(f"- {item}" for item in self.evidence if item.strip())
            )
        if self.impact.strip():
            lines.append(f"影响：{self.impact.strip()}")
        return "\n".join(lines)

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
