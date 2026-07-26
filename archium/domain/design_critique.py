"""Architectural design critique — challenge a concept before it hardens into Mission.

Critic role artifact: read-only findings. Does not rewrite the direction.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, TimestampedModel, utc_now


class DesignCritiqueVerdict(StrEnum):
    """Overall stance for gate wiring (warn / block)."""

    PROCEED = "proceed"
    CAUTION = "caution"
    REJECT = "reject"


class DesignCritiqueChallenge(StrEnum):
    """Which architectural question a finding primarily asks."""

    WHY = "why"
    EVIDENCE = "evidence"
    PROBLEM_FIT = "problem_fit"
    ALTERNATIVE = "alternative"
    FORM_ONLY = "form_only"
    CHAIN = "chain"


class DesignCritiqueItem(DomainModel):
    """One critique bullet (strength, weakness, gap, or alternative)."""

    text: str = Field(min_length=1, max_length=500)
    challenge: DesignCritiqueChallenge = DesignCritiqueChallenge.WHY
    severity: str = Field(
        default="suggestion",
        description="critical | high | medium | suggestion",
        max_length=20,
    )


class DesignCritiqueReport(TimestampedModel):
    """Independent second opinion on a ConceptDirection / DesignIntent.

    Output contract for Architectural Critic (not slide/visual QA).
    """

    direction_id: UUID | None = None
    project_id: UUID | None = None
    reasoning_id: UUID | None = None
    verdict: DesignCritiqueVerdict = DesignCritiqueVerdict.CAUTION
    summary: str = ""
    strengths: list[DesignCritiqueItem] = Field(default_factory=list)
    weaknesses: list[DesignCritiqueItem] = Field(default_factory=list)
    missing_evidence: list[DesignCritiqueItem] = Field(default_factory=list)
    alternative_directions: list[DesignCritiqueItem] = Field(default_factory=list)
    form_only_risk: bool = False
    chain_incomplete: bool = False
    source: str = Field(default="mixed", max_length=40)  # llm | rules | mixed

    def touch_completed(self) -> None:
        self.updated_at = utc_now()

    @property
    def blocks_selection(self) -> bool:
        return self.verdict == DesignCritiqueVerdict.REJECT

    def as_dict(self) -> dict[str, object]:
        return {
            "direction_id": str(self.direction_id) if self.direction_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "reasoning_id": str(self.reasoning_id) if self.reasoning_id else None,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "form_only_risk": self.form_only_risk,
            "chain_incomplete": self.chain_incomplete,
            "source": self.source,
            "strengths": [item.model_dump() for item in self.strengths],
            "weaknesses": [item.model_dump() for item in self.weaknesses],
            "missing_evidence": [item.model_dump() for item in self.missing_evidence],
            "alternative_directions": [
                item.model_dump() for item in self.alternative_directions
            ],
        }

    def display_warnings(self) -> list[str]:
        lines: list[str] = []
        if self.summary.strip():
            lines.append(self.summary.strip())
        if self.chain_incomplete:
            lines.append("推理链不完整：缺少假设或策略，不宜直接 proceed。")
        if self.form_only_risk:
            lines.append("形式风险偏高：论证更偏形式语言，问题/证据链偏弱。")
        for item in self.weaknesses[:3]:
            lines.append(f"弱点：{item.text}")
        for item in self.missing_evidence[:3]:
            lines.append(f"缺证据：{item.text}")
        for item in self.alternative_directions[:2]:
            lines.append(f"替代可能：{item.text}")
        return lines
