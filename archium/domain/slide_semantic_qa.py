"""Per-slide architectural semantic QA — image-text alignment and provenance."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class SlideSemanticCheckCode:
    """Stable identifiers for architecture slide semantic checks."""

    DRAWING_TOO_SMALL = "SEMANTIC.DRAWING_TOO_SMALL"
    DRAWING_CROP_RISK = "SEMANTIC.DRAWING_CROP_RISK"
    REFERENCE_ASSET_USED_AS_PROJECT_ASSET = "SEMANTIC.REFERENCE_ASSET_USED_AS_PROJECT_ASSET"
    PROJECT_ASSET_WITHOUT_SOURCE = "SEMANTIC.PROJECT_ASSET_WITHOUT_SOURCE"
    TEXT_NOT_EXPLAINING_VISUAL = "SEMANTIC.TEXT_NOT_EXPLAINING_VISUAL"
    VISUAL_WITHOUT_CAPTION = "SEMANTIC.VISUAL_WITHOUT_CAPTION"
    TOO_MANY_EQUAL_WEIGHT_IMAGES = "SEMANTIC.TOO_MANY_EQUAL_WEIGHT_IMAGES"
    BEFORE_AFTER_MISMATCH = "SEMANTIC.BEFORE_AFTER_MISMATCH"
    ISSUE_WITHOUT_EVIDENCE = "SEMANTIC.ISSUE_WITHOUT_EVIDENCE"
    STRATEGY_WITHOUT_TARGET = "SEMANTIC.STRATEGY_WITHOUT_TARGET"
    METRIC_WITHOUT_UNIT = "SEMANTIC.METRIC_WITHOUT_UNIT"
    EXTERNAL_FACT_WITHOUT_CITATION = "SEMANTIC.EXTERNAL_FACT_WITHOUT_CITATION"


class SlideSemanticFinding(DomainModel):
    """One explainable semantic QA finding for a slide."""

    check_code: str = Field(min_length=1)
    slide_order: int = Field(ge=0)
    slide_id: UUID | None = None
    severity: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    suggestion: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class ArchitectureSlideSemanticQA(DomainModel):
    """Aggregated semantic QA for a presentation deck."""

    presentation_id: UUID
    project_id: UUID | None = None
    findings: list[SlideSemanticFinding] = Field(default_factory=list)
    checked_slide_count: int = Field(default=0, ge=0)
    analyzer_version: str = Field(default="1.0.0", min_length=1)

    @property
    def issue_count(self) -> int:
        return len(self.findings)
