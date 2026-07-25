"""DesignReflection — structured pause-for-thought after research / critique.

Critic / Planning seat artifact. Not an Agent; does not rewrite decks.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class DesignReflection(DomainModel):
    """Answers: why / unverified / risks / next adjustments."""

    why: str = Field(default="", description="Why the current direction or step.")
    unverified_assumptions: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    next_adjustments: list[str] = Field(default_factory=list)
    source: str = Field(
        default="context",
        description="context | research | critique | direction",
        max_length=40,
    )

    def is_empty(self) -> bool:
        return not (
            self.why.strip()
            or self.unverified_assumptions
            or self.top_risks
            or self.next_adjustments
        )

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        lines = ["【设计反思 DesignReflection】"]
        if self.why.strip():
            lines.append(f"为何：{self.why.strip()}")
        if self.unverified_assumptions:
            lines.append(
                "未验证假设：\n"
                + "\n".join(f"- {item}" for item in self.unverified_assumptions)
            )
        if self.top_risks:
            lines.append(
                "主要风险：\n" + "\n".join(f"- {item}" for item in self.top_risks)
            )
        if self.next_adjustments:
            lines.append(
                "下一步调整：\n"
                + "\n".join(f"- {item}" for item in self.next_adjustments)
            )
        return "\n".join(lines)
