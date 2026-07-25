"""Design rationale — why a direction or decision, not just what.

Supports both claim–evidence skeleton and design-reasoning fields
(observation → problem → hypothesis → strategy → risks).
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class DesignRationaleAlternative(DomainModel):
    """Brief note on a rejected or deferred option."""

    label: str = ""
    note: str = ""


class DesignRationale(DomainModel):
    """Structured reasoning for an architectural choice."""

    statement: str = Field(
        default="",
        description="Primary design claim, e.g. courtyard layout strategy",
    )
    reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(
        default_factory=list,
        description="Supporting facts, constraints, or references cited",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    alternatives: list[DesignRationaleAlternative] = Field(default_factory=list)
    # Design reasoning chain (optional; complements statement/reasons)
    observation: str = Field(
        default="",
        description="What was observed in site / culture / typology.",
    )
    problem: str = Field(
        default="",
        description="Contradiction or need the design addresses.",
    )
    hypothesis: str = Field(
        default="",
        description="Working design hypothesis.",
    )
    strategy: str = Field(
        default="",
        description="Chosen architectural strategy.",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Known risks / failure modes of this rationale.",
    )

    def is_empty(self) -> bool:
        return not (
            self.statement.strip()
            or self.reasons
            or self.evidence
            or self.alternatives
            or self.observation.strip()
            or self.problem.strip()
            or self.hypothesis.strip()
            or self.strategy.strip()
            or self.risks
        )

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        sections: list[str] = []
        if self.statement.strip():
            sections.append(f"设计判断：{self.statement.strip()}")
        if self.observation.strip():
            sections.append(f"观察：{self.observation.strip()}")
        if self.problem.strip():
            sections.append(f"问题：{self.problem.strip()}")
        if self.hypothesis.strip():
            sections.append(f"假设：{self.hypothesis.strip()}")
        if self.strategy.strip():
            sections.append(f"策略：{self.strategy.strip()}")
        if self.reasons:
            sections.append(
                "理由：\n" + "\n".join(f"- {item}" for item in self.reasons if item.strip())
            )
        if self.evidence:
            sections.append(
                "依据：\n" + "\n".join(f"- {item}" for item in self.evidence if item.strip())
            )
        if self.risks:
            sections.append(
                "风险：\n" + "\n".join(f"- {item}" for item in self.risks if item.strip())
            )
        if self.alternatives:
            alt_lines = []
            for alt in self.alternatives:
                if not alt.label.strip() and not alt.note.strip():
                    continue
                if alt.note.strip():
                    alt_lines.append(f"- {alt.label.strip()}：{alt.note.strip()}")
                else:
                    alt_lines.append(f"- {alt.label.strip()}")
            if alt_lines:
                sections.append("未选方案 / 权衡：\n" + "\n".join(alt_lines))
        if self.confidence > 0:
            sections.append(f"把握度约 {int(round(self.confidence * 100))}%")
        return "\n".join(sections)
