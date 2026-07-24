"""Intent evidence — provenance for design-intent statements."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class IntentEvidenceSourceType(StrEnum):
    USER_INPUT = "user_input"
    DOCUMENT = "document"
    PUBLIC_RESEARCH = "public_research"
    AI_INFERENCE = "ai_inference"
    ARCHITECT_ASSUMPTION = "architect_assumption"
    DIRECTION_SELECTION = "direction_selection"


class IntentEvidence(DomainModel):
    """One claimed design statement and where it came from."""

    statement: str = Field(min_length=1, max_length=800)
    source_type: IntentEvidenceSourceType
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_by: str = Field(default="system", max_length=40)
    field_hint: str = Field(default="", max_length=80)
    supporting_materials: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=400)

    def source_label(self) -> str:
        return {
            IntentEvidenceSourceType.USER_INPUT: "用户输入",
            IntentEvidenceSourceType.DOCUMENT: "项目资料",
            IntentEvidenceSourceType.PUBLIC_RESEARCH: "公开研究",
            IntentEvidenceSourceType.AI_INFERENCE: "AI 推理",
            IntentEvidenceSourceType.ARCHITECT_ASSUMPTION: "建筑师假设",
            IntentEvidenceSourceType.DIRECTION_SELECTION: "选定方向",
        }.get(self.source_type, self.source_type.value)
