"""Structured design knowledge from research (not free-text dumps).

Consumed by Concept / Critique / Mission enrichment as typed insights.
Aligned with ArchitectureCase slots: problem → strategy → spatial → material
→ precedent → applicability.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from archium.domain._base import DomainModel
from archium.domain.case_ref import normalize_precedent_ref


class DesignKnowledge(DomainModel):
    """One transferable design insight grounded in research evidence."""

    topic: str = ""
    problem: str = Field(
        default="",
        description="Design problem / contradiction this insight addresses.",
    )
    insight: str = Field(
        default="",
        description="Why this finding matters for design (not a case list).",
    )
    strategy: str = Field(
        default="",
        description="Core architectural strategy (one line).",
    )
    principle: str = Field(
        default="",
        description="Transferable design principle.",
    )
    spatial_translation: str = Field(
        default="",
        description="How the principle becomes space (courtyard, axis, embed…).",
    )
    material_strategy: str = Field(
        default="",
        description="Material / tectonic attitude when applicable.",
    )
    project_link: str = Field(
        default="",
        description="Relevance to the current project / DesignIntent.",
    )
    applicability: str = Field(
        default="",
        description="When this applies / boundaries (climate, scale, culture).",
    )
    precedent_ref: str | None = Field(
        default=None,
        description="Canonical ArchitectureCase ref, e.g. case:ningbo_museum.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Short evidence labels (titles, URLs, notes) — not fabricated facts.",
    )

    @field_validator("precedent_ref", mode="before")
    @classmethod
    def _normalize_precedent_ref(cls, value: object) -> str | None:
        if value is None:
            return None
        return normalize_precedent_ref(str(value))

    @property
    def has_substance(self) -> bool:
        return any(
            part.strip()
            for part in (
                self.problem,
                self.insight,
                self.strategy,
                self.principle,
                self.spatial_translation,
                self.material_strategy,
                self.project_link,
            )
        )

    def to_prompt_block(self) -> str:
        lines: list[str] = []
        topic = (self.topic or "").strip()
        if topic:
            lines.append(f"主题：{topic}")
        if self.problem.strip():
            lines.append(f"设计问题：{self.problem.strip()}")
        if self.insight.strip():
            lines.append(f"洞察：{self.insight.strip()}")
        if self.strategy.strip():
            lines.append(f"策略：{self.strategy.strip()}")
        if self.principle.strip():
            lines.append(f"原则：{self.principle.strip()}")
        if self.spatial_translation.strip():
            lines.append(f"空间转译：{self.spatial_translation.strip()}")
        if self.material_strategy.strip():
            lines.append(f"材料/构造：{self.material_strategy.strip()}")
        if self.project_link.strip():
            lines.append(f"项目关联：{self.project_link.strip()}")
        if self.applicability.strip():
            lines.append(f"适用边界：{self.applicability.strip()}")
        if self.precedent_ref:
            lines.append(f"先例：{self.precedent_ref}")
        if self.evidence:
            ev = "；".join(item.strip() for item in self.evidence if item.strip())
            if ev:
                lines.append(f"证据：{ev}")
        return "\n".join(lines)

    def to_statement_sections(self) -> list[str]:
        """Human-readable sections for ProjectKnowledgeItem.statement."""
        sections: list[str] = []
        lead = (self.insight or self.problem or "").strip()
        if lead:
            sections.append(lead)
        bullets: list[str] = []
        if self.problem.strip() and self.problem.strip() != lead:
            bullets.append(f"问题：{self.problem.strip()}")
        if self.strategy.strip():
            bullets.append(f"策略：{self.strategy.strip()}")
        if self.principle.strip():
            bullets.append(f"原则：{self.principle.strip()}")
        if self.spatial_translation.strip():
            bullets.append(f"空间：{self.spatial_translation.strip()}")
        if self.material_strategy.strip():
            bullets.append(f"材料：{self.material_strategy.strip()}")
        if self.project_link.strip():
            bullets.append(f"关联：{self.project_link.strip()}")
        if self.applicability.strip():
            bullets.append(f"适用：{self.applicability.strip()}")
        if self.precedent_ref:
            bullets.append(f"先例：{self.precedent_ref}")
        if bullets:
            sections.append("设计知识：\n" + "\n".join(f"- {b}" for b in bullets))
        return sections
