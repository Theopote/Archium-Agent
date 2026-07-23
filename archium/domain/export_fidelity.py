"""Export fidelity contract — explicit degradation levels and deck manifest."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.powerpoint_capability import PowerPointFidelity


class ExportFidelityLevel(StrEnum):
    """Per-slide export editability level."""

    FULLY_EDITABLE = "fully_editable"
    HYBRID_EDITABLE = "hybrid_editable"
    TEXT_EDITABLE = "text_editable"
    RASTER_FALLBACK = "raster_fallback"
    FAILED = "failed"


class ChartExportMode(StrEnum):
    """Dual strategy for charts and tables in PPTX delivery.

    Inspired by ppt-master's default shape/SVG route vs ``--native-charts-and-tables``:

    - ``CROSS_APP_STABLE`` — shapes / images / text grids that render consistently
      across PowerPoint, Keynote, LibreOffice, and WPS (no embedded workbook).
    - ``NATIVE_DATA_BACKED`` — real PowerPoint Chart / Table objects with editable
      data (PptxGenJS embeds an Excel workbook for charts).
    """

    CROSS_APP_STABLE = "cross_app_stable"
    NATIVE_DATA_BACKED = "native_data_backed"


CHART_EXPORT_MODE_LABELS_ZH: dict[ChartExportMode, str] = {
    ChartExportMode.CROSS_APP_STABLE: "跨应用稳定（形状/图片）",
    ChartExportMode.NATIVE_DATA_BACKED: "原生数据图表（Chart/Table + 内嵌工作簿）",
}


_FIDELITY_RANK: dict[ExportFidelityLevel, int] = {
    ExportFidelityLevel.FULLY_EDITABLE: 0,
    ExportFidelityLevel.HYBRID_EDITABLE: 1,
    ExportFidelityLevel.TEXT_EDITABLE: 2,
    ExportFidelityLevel.RASTER_FALLBACK: 3,
    ExportFidelityLevel.FAILED: 4,
}

FIDELITY_LABELS_ZH: dict[ExportFidelityLevel, str] = {
    ExportFidelityLevel.FULLY_EDITABLE: "支持范围内可编辑",
    ExportFidelityLevel.HYBRID_EDITABLE: "混合可编辑",
    ExportFidelityLevel.TEXT_EDITABLE: "文字可编辑",
    ExportFidelityLevel.RASTER_FALLBACK: "图片降级",
    ExportFidelityLevel.FAILED: "失败",
}


def fidelity_rank(level: ExportFidelityLevel) -> int:
    return _FIDELITY_RANK[level]


def worst_fidelity(levels: list[ExportFidelityLevel]) -> ExportFidelityLevel:
    if not levels:
        return ExportFidelityLevel.FAILED
    return max(levels, key=fidelity_rank)


class ExportPolicy(DomainModel):
    """User-selected export degradation policy."""

    required_fidelity: ExportFidelityLevel = ExportFidelityLevel.FULLY_EDITABLE

    allow_slide_level_fallback: bool = False
    allow_hybrid_editable: bool = True
    allow_text_editable_background: bool = False
    allow_raster_fallback: bool = False

    fail_on_missing_fonts: bool = False
    fail_on_unresolved_assets: bool = True
    fail_on_reference_leakage: bool = True
    fail_on_drawing_crop: bool = True

    chart_export_mode: ChartExportMode = ChartExportMode.CROSS_APP_STABLE


class SlideExportResult(DomainModel):
    """Per-slide export fidelity assessment."""

    slide_id: UUID
    fidelity_level: ExportFidelityLevel

    native_text_count: int = Field(default=0, ge=0)
    native_shape_count: int = Field(default=0, ge=0)
    native_chart_count: int = Field(default=0, ge=0)
    native_table_count: int = Field(default=0, ge=0)
    bitmap_asset_count: int = Field(default=0, ge=0)
    powerpoint_capability_counts: dict[PowerPointFidelity, int] = Field(default_factory=dict)
    powerpoint_capability_limitations: list[str] = Field(default_factory=list)

    emission_count: int = Field(default=0, ge=0)
    closure_valid: bool = True
    unsupported_node_ids: list[str] = Field(default_factory=list)
    bake_required_node_ids: list[str] = Field(default_factory=list)
    emission_object_type_mismatches: list[str] = Field(default_factory=list)

    font_substitutions: list[str] = Field(default_factory=list)
    unresolved_assets: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class DeckExportManifest(DomainModel):
    """Full-deck export outcome with explicit fidelity disclosure."""

    presentation_id: UUID
    revision_id: UUID | None = None
    export_format: str = Field(min_length=1, max_length=40)

    requested_policy: ExportPolicy
    final_fidelity: ExportFidelityLevel

    slides: list[SlideExportResult] = Field(default_factory=list)
    file_uri: str | None = None
    file_hash: str | None = None

    qa_status: str = "unknown"
    fallback_used: bool = False
    fallback_reason: str | None = None
    closure_valid: bool = True
    capability_gate_valid: bool = True
    total_emission_count: int = Field(default=0, ge=0)

    @property
    def fidelity_counts(self) -> dict[ExportFidelityLevel, int]:
        counts = {level: 0 for level in ExportFidelityLevel}
        for slide in self.slides:
            counts[slide.fidelity_level] += 1
        return counts

    @property
    def powerpoint_capability_counts(self) -> dict[PowerPointFidelity, int]:
        counts = {level: 0 for level in PowerPointFidelity}
        for slide in self.slides:
            for level, count in slide.powerpoint_capability_counts.items():
                counts[level] += count
        return counts

    @property
    def native_chart_count(self) -> int:
        return sum(slide.native_chart_count for slide in self.slides)

    @property
    def native_table_count(self) -> int:
        return sum(slide.native_table_count for slide in self.slides)

    def summary_lines_zh(self) -> list[str]:
        """Human-readable per-level counts for delivery UI."""
        lines: list[str] = []
        for level in ExportFidelityLevel:
            count = self.fidelity_counts[level]
            if count:
                lines.append(f"{FIDELITY_LABELS_ZH[level]}：{count} 页")
        mode = self.requested_policy.chart_export_mode
        lines.append(f"图表/表格策略：{CHART_EXPORT_MODE_LABELS_ZH[mode]}")
        if self.native_chart_count:
            lines.append(f"原生图表：{self.native_chart_count}")
        if self.native_table_count:
            lines.append(f"原生表格：{self.native_table_count}")
        for capability_level, count in self.powerpoint_capability_counts.items():
            if count:
                lines.append(f"PowerPoint {capability_level.value}: {count} objects")
        if self.total_emission_count:
            lines.append(f"Renderer emissions：{self.total_emission_count}")
        if not self.closure_valid:
            lines.append("Closure：未通过")
        if not self.capability_gate_valid:
            lines.append("Capability gate：存在 unsupported 节点")
        return lines


def policy_allows_fidelity(policy: ExportPolicy, level: ExportFidelityLevel) -> bool:
    """Whether ``level`` is permitted under ``policy``."""
    if level == ExportFidelityLevel.FAILED:
        return False
    if level == ExportFidelityLevel.FULLY_EDITABLE:
        return True
    if level == ExportFidelityLevel.HYBRID_EDITABLE:
        return policy.allow_hybrid_editable
    if level == ExportFidelityLevel.TEXT_EDITABLE:
        return policy.allow_text_editable_background
    if level == ExportFidelityLevel.RASTER_FALLBACK:
        return policy.allow_raster_fallback
    return False
