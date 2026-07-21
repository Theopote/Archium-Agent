"""Per-page pipeline status — human-readable progress beyond “正在生成…”.

Maps SlideSpec / layout / scene / QA signals into concrete page lines such as:
「第 3 页：正在绑定现场照片」「第 6 页：Drawing QA 未通过」。
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class PagePipelinePhase(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    CONTENT_READY = "content_ready"
    TEMPLATE_MATCHED = "template_matched"
    FREE_COMPOSITION = "free_composition"
    BINDING_ASSETS = "binding_assets"
    ASSET_MISSING = "asset_missing"
    COMPILING_SCENE = "compiling_scene"
    SCENE_READY = "scene_ready"
    DRAWING_QA_FAILED = "drawing_qa_failed"
    FALLBACK = "fallback"
    RENDER_FAILED = "render_failed"
    SCHEMA_BLOCKED = "schema_blocked"
    SKIPPED = "skipped"
    COMPLETE = "complete"


PAGE_PHASE_LABELS: dict[PagePipelinePhase, str] = {
    PagePipelinePhase.QUEUED: "排队中",
    PagePipelinePhase.GENERATING: "正在生成内容",
    PagePipelinePhase.CONTENT_READY: "内容已生成",
    PagePipelinePhase.TEMPLATE_MATCHED: "模板匹配成功",
    PagePipelinePhase.FREE_COMPOSITION: "使用自由构图",
    PagePipelinePhase.BINDING_ASSETS: "正在绑定现场照片",
    PagePipelinePhase.ASSET_MISSING: "缺少指标来源",
    PagePipelinePhase.COMPILING_SCENE: "正在编译 RenderScene",
    PagePipelinePhase.SCENE_READY: "RenderScene 已就绪",
    PagePipelinePhase.DRAWING_QA_FAILED: "Drawing QA 未通过",
    PagePipelinePhase.FALLBACK: "使用回退页",
    PagePipelinePhase.RENDER_FAILED: "渲染失败",
    PagePipelinePhase.SCHEMA_BLOCKED: "版式契约受阻",
    PagePipelinePhase.SKIPPED: "已跳过",
    PagePipelinePhase.COMPLETE: "完成",
}


class PageStatusAction(StrEnum):
    RETRY = "retry"
    CHANGE_TEMPLATE = "change_template"
    REBIND_ASSETS = "rebind_assets"
    OPEN_STUDIO = "open_studio"
    SKIP = "skip"
    UNSKIP = "unskip"


PAGE_ACTION_LABELS: dict[PageStatusAction, str] = {
    PageStatusAction.RETRY: "重试当前页",
    PageStatusAction.CHANGE_TEMPLATE: "更换模板",
    PageStatusAction.REBIND_ASSETS: "重新绑定素材",
    PageStatusAction.OPEN_STUDIO: "打开 Studio",
    PageStatusAction.SKIP: "跳过该页",
    PageStatusAction.UNSKIP: "取消跳过",
}


class PagePipelineStatus(DomainModel):
    """One row in the per-page status board."""

    slide_id: UUID | None = None
    order: int = Field(ge=0)
    title: str = ""
    phase: PagePipelinePhase = PagePipelinePhase.QUEUED
    status_label: str = ""
    detail: str = ""
    severity: str = "info"  # info | warn | error | success
    actions: list[PageStatusAction] = Field(default_factory=list)

    def display_line(self) -> str:
        label = self.status_label or PAGE_PHASE_LABELS.get(self.phase, self.phase.value)
        return f"第 {self.order + 1} 页：{label}"


class PageStatusBoard(DomainModel):
    """Deck-wide page status snapshot for workflow / review UI."""

    presentation_id: UUID
    current_workflow_step: str | None = None
    rows: list[PagePipelineStatus] = Field(default_factory=list)
    summary: str = ""

    @property
    def attention_count(self) -> int:
        return sum(1 for row in self.rows if row.severity in {"warn", "error"})
