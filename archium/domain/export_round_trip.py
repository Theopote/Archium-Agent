"""Export round-trip validation — PPTX re-render vs source RenderScene QA."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class RoundTripStatus(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


ROUND_TRIP_STATUS_LABELS_ZH: dict[RoundTripStatus, str] = {
    RoundTripStatus.PASS: "通过",
    RoundTripStatus.PASS_WITH_WARNINGS: "通过（有警告）",
    RoundTripStatus.NEEDS_REVIEW: "需人工复核",
    RoundTripStatus.BLOCKED: "阻塞",
}


class SlideRoundTripResult(DomainModel):
    """Per-slide round-trip metrics."""

    slide_id: UUID
    slide_order: int = Field(ge=0)

    text_match_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    geometry_match_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    similarity_score: float = Field(default=1.0, ge=-1.0, le=1.0)

    missing_text_nodes: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    font_substitutions: list[str] = Field(default_factory=list)
    drawing_integrity_issues: list[str] = Field(default_factory=list)
    citation_integrity_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExportRoundTripReport(DomainModel):
    """Deck-level export round-trip QA report."""

    presentation_id: UUID
    revision_id: UUID | None = None

    source_scene_hash: str = ""
    export_file_hash: str = ""
    rendered_preview_hash: str = ""

    similarity_score: float = Field(default=1.0, ge=-1.0, le=1.0)
    text_match_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    geometry_match_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    missing_text_nodes: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    changed_asset_origins: list[str] = Field(default_factory=list)
    font_substitutions: list[str] = Field(default_factory=list)

    drawing_integrity_issues: list[str] = Field(default_factory=list)
    citation_integrity_issues: list[str] = Field(default_factory=list)

    slides: list[SlideRoundTripResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    status: RoundTripStatus = RoundTripStatus.PASS
    screenshot_tools_available: bool = True

    def qa_status_value(self) -> str:
        return self.status.value

    def summary_lines_zh(self) -> list[str]:
        lines = [
            f"Round-trip QA：{ROUND_TRIP_STATUS_LABELS_ZH.get(self.status, self.status.value)}",
            f"文本召回率：{self.text_match_rate:.0%}",
            f"几何一致性：{self.geometry_match_rate:.0%}",
        ]
        if self.similarity_score >= 0:
            lines.append(f"视觉相似度：{self.similarity_score:.0%}")
        if self.drawing_integrity_issues:
            lines.append(f"图纸完整性问题：{len(self.drawing_integrity_issues)} 项")
        if self.blockers:
            lines.append(f"阻塞项：{len(self.blockers)}")
        return lines
