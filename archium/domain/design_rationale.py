"""Design rationale — why a direction or decision, not just what."""

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

    def is_empty(self) -> bool:
        return not (
            self.statement.strip()
            or self.reasons
            or self.evidence
            or self.alternatives
        )

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        sections: list[str] = []
        if self.statement.strip():
            sections.append(f"设计判断：{self.statement.strip()}")
        if self.reasons:
            sections.append(
                "理由：\n" + "\n".join(f"- {item}" for item in self.reasons if item.strip())
            )
        if self.evidence:
            sections.append(
                "依据：\n" + "\n".join(f"- {item}" for item in self.evidence if item.strip())
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
