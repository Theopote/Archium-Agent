"""Concept direction drafts — exploration branches (pre- or post-Mission)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.enums import ConceptDirectionStatus


class ConceptDirection(IdentifiedModel, TimestampedModel):
    """One conceptual design direction draft under an ExplorationSession."""

    project_id: UUID
    exploration_session_id: UUID | None = None
    mission_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""
    theme: str = ""
    spatial_idea: str = ""
    spatial_strategy: str = ""
    formal_language: str = ""
    material_strategy: str = ""
    reference_dna: list[str] = Field(default_factory=list)
    visual_prompt: ConceptVisualPrompt | None = None
    experience_focus: str = ""
    differentiator: str = ""
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    status: ConceptDirectionStatus = ConceptDirectionStatus.DRAFT
    sort_order: int = 0
    source: str = Field(default="generated", max_length=40)

    def select(self) -> None:
        self.status = ConceptDirectionStatus.SELECTED
        self.touch()

    def mark_draft(self) -> None:
        self.status = ConceptDirectionStatus.DRAFT
        self.touch()

    def archive(self) -> None:
        self.status = ConceptDirectionStatus.ARCHIVED
        self.touch()

    def to_prompt_block(self) -> str:
        """Compact text for Brief / Storyline / Outline generation context."""
        sections: list[str] = [f"方向：{self.title}"]
        if self.theme.strip():
            sections.append(f"主题：{self.theme.strip()}")
        if self.summary.strip():
            sections.append(f"摘要：{self.summary.strip()}")
        if self.spatial_idea.strip():
            sections.append(f"空间想法：{self.spatial_idea.strip()}")
        if self.spatial_strategy.strip():
            sections.append(f"空间策略：{self.spatial_strategy.strip()}")
        if self.formal_language.strip():
            sections.append(f"形式语言：{self.formal_language.strip()}")
        if self.material_strategy.strip():
            sections.append(f"材料策略：{self.material_strategy.strip()}")
        if self.reference_dna:
            sections.append(
                "参照基因："
                + "；".join(item for item in self.reference_dna if item.strip())
            )
        if self.visual_prompt is not None:
            block = self.visual_prompt.to_prompt_block()
            if block:
                sections.append(block)
        if self.experience_focus.strip():
            sections.append(f"体验焦点：{self.experience_focus.strip()}")
        if self.differentiator.strip():
            sections.append(f"差异点：{self.differentiator.strip()}")
        if self.open_questions:
            sections.append(
                "开放问题：\n"
                + "\n".join(f"- {item}" for item in self.open_questions if item.strip())
            )
        if self.risks:
            sections.append(
                "风险：\n" + "\n".join(f"- {item}" for item in self.risks if item.strip())
            )
        return "\n".join(sections)
