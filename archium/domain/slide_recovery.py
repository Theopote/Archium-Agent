"""Slide Recovery spike — external page reconstruction domain models.

Technical validation only; not wired into the main generation pipeline.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import DomainModel
from archium.domain.export_fidelity import FIDELITY_LABELS_ZH, ExportFidelityLevel
from archium.domain.visual.render_scene import RenderScene

RegionType = Literal[
    "text",
    "image",
    "drawing",
    "table",
    "chart",
    "line",
    "shape",
    "background",
    "unknown",
]

# Spike acceptance thresholds (Phase 5).
TEXT_RECALL_TARGET = 0.98
TEXT_POSITION_ERROR_MAX = 0.02
LINE_RECALL_TARGET = 0.90
SIMILARITY_TARGET = 0.92


class SlideRecoveryPageKind(StrEnum):
    """Five page archetypes validated in the Phase 5 spike."""

    TITLE = "title"
    IMAGE_TEXT = "image_text"
    TABLE = "table"
    PHOTO = "photo"
    DRAWING_DOMINANT = "drawing_dominant"


PAGE_KIND_LABELS_ZH: dict[SlideRecoveryPageKind, str] = {
    SlideRecoveryPageKind.TITLE: "标题页",
    SlideRecoveryPageKind.IMAGE_TEXT: "图文页",
    SlideRecoveryPageKind.TABLE: "表格页",
    SlideRecoveryPageKind.PHOTO: "现场照片页",
    SlideRecoveryPageKind.DRAWING_DOMINANT: "图纸主导页",
}

REGION_TYPE_LABELS_ZH: dict[str, str] = {
    "text": "文字",
    "image": "图片",
    "drawing": "图纸",
    "table": "表格",
    "chart": "图表",
    "line": "线条",
    "shape": "形状",
    "background": "背景",
    "unknown": "未知",
}

REGION_TYPE_OPTIONS: tuple[RegionType, ...] = (
    "text",
    "image",
    "drawing",
    "table",
    "chart",
    "line",
    "shape",
    "background",
    "unknown",
)


class NormalizedBox(DomainModel):
    """Region bounding box in normalized page coordinates (0–1)."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _fits_page(self) -> NormalizedBox:
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("bbox must fit within the normalized page")
        return self

    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def position_error_ratio(self, other: NormalizedBox) -> float:
        """Max center offset as a fraction of page width/height."""
        cx, cy = self.center()
        ox, oy = other.center()
        return max(abs(cx - ox), abs(cy - oy))

    @classmethod
    def from_absolute(
        cls,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        page_width: float,
        page_height: float,
    ) -> NormalizedBox:
        if page_width <= 0 or page_height <= 0:
            raise ValueError("page dimensions must be positive")
        return cls(
            x=x / page_width,
            y=y / page_height,
            width=width / page_width,
            height=height / page_height,
        )


class RecoveredPageRegion(DomainModel):
    """One detected / recovered region on a source page."""

    id: UUID
    bbox: NormalizedBox

    region_type: RegionType
    semantic_role: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_asset_uri: str | None = None

    recovered_text: str | None = None
    keep_whole_drawing: bool = False
    bitmap_fallback: bool = False
    source_node_id: str | None = None


class SlideRecoveryMetrics(DomainModel):
    """Quantitative spike metrics vs ground-truth source scene."""

    text_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    text_position_error: float = Field(default=1.0, ge=0.0, le=1.0)
    line_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    drawing_integrity_ok: bool = False
    similarity_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    asset_identity_preserved: bool = False

    def meets_spike_targets(self) -> bool:
        return (
            self.text_recall >= TEXT_RECALL_TARGET
            and self.text_position_error <= TEXT_POSITION_ERROR_MAX
            and self.line_recall >= LINE_RECALL_TARGET
            and self.drawing_integrity_ok
            and self.similarity_score >= SIMILARITY_TARGET
            and self.asset_identity_preserved
        )

    def summary_lines_zh(self) -> list[str]:
        status = "达标" if self.meets_spike_targets() else "未达标"
        return [
            f"恢复指标：{status}",
            f"文本召回率：{self.text_recall:.0%}",
            f"文字位置误差：{self.text_position_error:.1%}",
            f"线条召回率：{self.line_recall:.0%}",
            f"图纸完整性：{'通过' if self.drawing_integrity_ok else '未通过'}",
            f"视觉相似度：{self.similarity_score:.0%}",
            f"素材身份：{'一致' if self.asset_identity_preserved else '混淆'}",
        ]


class HybridRenderScene(DomainModel):
    """RenderScene produced by slide recovery with explicit hybrid metadata."""

    scene: RenderScene
    recovery_source_id: str
    page_kind: SlideRecoveryPageKind

    regions: list[RecoveredPageRegion] = Field(default_factory=list)
    reconstruction_fidelity: ExportFidelityLevel = ExportFidelityLevel.HYBRID_EDITABLE
    hybrid_bitmap_region_ids: list[UUID] = Field(default_factory=list)
    metrics: SlideRecoveryMetrics | None = None

    def fidelity_label_zh(self) -> str:
        return FIDELITY_LABELS_ZH.get(
            self.reconstruction_fidelity,
            self.reconstruction_fidelity.value,
        )


class SlideRecoveryResult(DomainModel):
    """Outcome of a single-page recovery spike run."""

    source_page_id: str
    recovered_scene_id: UUID | None = None

    text_regions: list[RecoveredPageRegion] = Field(default_factory=list)
    visual_regions: list[RecoveredPageRegion] = Field(default_factory=list)
    native_shape_regions: list[RecoveredPageRegion] = Field(default_factory=list)

    reconstruction_fidelity: ExportFidelityLevel = ExportFidelityLevel.HYBRID_EDITABLE
    metrics: SlideRecoveryMetrics | None = None
    hybrid_scene: HybridRenderScene | None = None

    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    analysis_meta: dict[str, object] = Field(default_factory=dict)

    def summary_lines_zh(self) -> list[str]:
        lines = [
            f"页面恢复：{self.source_page_id}",
            f"可编辑级别：{FIDELITY_LABELS_ZH.get(self.reconstruction_fidelity, self.reconstruction_fidelity.value)}",
            f"文本区域 {len(self.text_regions)} · 视觉区域 {len(self.visual_regions)} · "
            f"原生形状 {len(self.native_shape_regions)}",
        ]
        if self.metrics is not None:
            lines.extend(self.metrics.summary_lines_zh())
        if self.warnings:
            lines.append(f"警告 {len(self.warnings)} 项")
        if self.blockers:
            lines.append(f"阻塞 {len(self.blockers)} 项")
        return lines


def infer_reconstruction_fidelity(metrics: SlideRecoveryMetrics) -> ExportFidelityLevel:
    """Map spike metrics to export fidelity — explicit degradation only."""
    if metrics.meets_spike_targets():
        return ExportFidelityLevel.FULLY_EDITABLE

    if (
        metrics.text_recall >= TEXT_RECALL_TARGET
        and metrics.drawing_integrity_ok
        and metrics.asset_identity_preserved
    ):
        return ExportFidelityLevel.HYBRID_EDITABLE

    if metrics.text_recall >= 0.90:
        return ExportFidelityLevel.TEXT_EDITABLE

    return ExportFidelityLevel.RASTER_FALLBACK
