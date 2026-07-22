"""Presentation Technology Radar — external AI PPT / slides system profiles."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel, utc_now

SystemCategory = Literal[
    "saas",
    "open_source",
    "research",
    "office_addin",
    "slides_as_code",
]

ArchiumRelevance = Literal["adopt", "trial", "assess", "hold"]


class RelevanceLevel(StrEnum):
    ADOPT = "adopt"
    TRIAL = "trial"
    ASSESS = "assess"
    HOLD = "hold"


RELEVANCE_LABELS_ZH: dict[ArchiumRelevance, str] = {
    "adopt": "采纳",
    "trial": "试验",
    "assess": "评估",
    "hold": "暂缓",
}

CATEGORY_LABELS_ZH: dict[SystemCategory, str] = {
    "saas": "SaaS",
    "open_source": "开源",
    "research": "研究",
    "office_addin": "Office 插件",
    "slides_as_code": "Slides as Code",
}


class ExternalPresentationSystem(DomainModel):
    """Observed external presentation / AI-deck system for Archium tech radar."""

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)

    repository_url: str | None = None
    product_url: str | None = None

    category: SystemCategory = "open_source"
    input_modes: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=list)

    editable_pptx: bool = False
    local_llm: bool = False
    agentic_workflow: bool = False
    document_grounding: bool = False
    office_integration: bool = False

    page_model: str = ""
    layout_engine: str = ""
    template_system: str = ""
    edit_model: str = ""
    qa_model: str = ""

    archium_relevance: ArchiumRelevance = "assess"
    concepts_to_adopt: list[str] = Field(default_factory=list)
    concepts_to_avoid: list[str] = Field(default_factory=list)
    notes: str = ""

    last_reviewed_at: datetime = Field(default_factory=utc_now)

    def relevance_label_zh(self) -> str:
        return RELEVANCE_LABELS_ZH.get(self.archium_relevance, self.archium_relevance)

    def category_label_zh(self) -> str:
        return CATEGORY_LABELS_ZH.get(self.category, self.category)

    def capability_badges(self) -> list[str]:
        badges: list[str] = []
        if self.editable_pptx:
            badges.append("原生 PPTX")
        if self.local_llm:
            badges.append("本地 LLM")
        if self.agentic_workflow:
            badges.append("Agent 工作流")
        if self.document_grounding:
            badges.append("文档接地")
        if self.office_integration:
            badges.append("Office 集成")
        return badges

    def summary_lines_zh(self) -> list[str]:
        lines = [
            f"{self.name} · {self.relevance_label_zh()} · {self.category_label_zh()}",
        ]
        if self.input_modes:
            lines.append(f"输入：{', '.join(self.input_modes)}")
        if self.output_formats:
            lines.append(f"输出：{', '.join(self.output_formats)}")
        badges = self.capability_badges()
        if badges:
            lines.append(f"能力：{', '.join(badges)}")
        return lines
