"""Per-page design brief — user-readable design decisions before layout generation."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class BriefStatus(StrEnum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    CHANGES_PENDING = "changes_pending"


BRIEF_STATUS_LABELS_ZH: dict[BriefStatus, str] = {
    BriefStatus.DRAFT: "草稿",
    BriefStatus.READY_FOR_REVIEW: "待确认",
    BriefStatus.APPROVED: "已批准",
    BriefStatus.CHANGES_PENDING: "待重新确认",
}


class DrawingDisplayPolicy(DomainModel):
    """Rules for architectural drawing display on a page."""

    fit_mode: Literal["contain", "safe_crop"] = "contain"
    preserve_aspect_ratio: bool = True
    preserve_annotations: bool = True
    forbid_cover_crop: bool = True
    show_north_arrow: bool = True
    show_scale_bar: bool = True
    show_legend: bool = True


class ImageDisplayPolicy(DomainModel):
    """Rules for photo / reference image display."""

    fit_mode: Literal["contain", "cover"] = "cover"
    preserve_aspect_ratio: bool = True
    allow_reference_case: bool = False
    forbid_ai_as_fact: bool = True


_DRAWING_PAGE_TYPES = frozenset(
    {
        "drawing_focus",
        "site_plan",
        "floor_plan",
        "elevation",
        "section",
        "general",
    }
)

_PHOTO_PAGE_TYPES = frozenset(
    {
        "photo_evidence_grid",
        "hero_image",
        "comparison",
    }
)


def default_drawing_policy() -> DrawingDisplayPolicy:
    return DrawingDisplayPolicy()


def default_image_policy(*, allow_reference: bool = False) -> ImageDisplayPolicy:
    return ImageDisplayPolicy(allow_reference_case=allow_reference)


def default_protection_rules_for_page(
    *,
    primary_visual_type: str,
    drawing_policy: DrawingDisplayPolicy | None,
) -> list[str]:
    rules: list[str] = []
    if primary_visual_type == "drawing" or drawing_policy is not None:
        rules.extend(
            [
                "完整显示图纸",
                "保留指北针和比例尺",
                "禁止 cover 裁剪",
            ]
        )
    rules.extend(
        [
            "参考案例不得替代项目图纸",
            "AI 生成效果图不得冒充项目现场事实",
        ]
    )
    return rules


def infer_primary_visual_type(expected_layout: str) -> str:
    key = (expected_layout or "").strip().lower()
    if key in _DRAWING_PAGE_TYPES or "drawing" in key or "plan" in key:
        return "drawing"
    if key in _PHOTO_PAGE_TYPES or "photo" in key:
        return "photo"
    if key in {"data", "metric_dashboard"}:
        return "metric"
    if key in {"title", "closing"}:
        return "title"
    if key == "comparison":
        return "comparison"
    return "content"


class SlideDesignBrief(DomainModel):
    """User-readable per-page design summary between SlideIntent and LayoutPlan."""

    slide_id: UUID | None = None
    page_order: int = Field(ge=0)

    page_task: str = Field(min_length=1, max_length=500)
    central_claim: str = Field(default="", max_length=1000)

    primary_visual_type: str = Field(default="content", max_length=80)
    primary_asset_ids: list[UUID] = Field(default_factory=list)

    supporting_asset_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)

    layout_family: str = Field(default="", max_length=120)
    expected_density: Literal["low", "medium", "high"] = "medium"

    drawing_policy: DrawingDisplayPolicy | None = None
    image_policy: ImageDisplayPolicy | None = None

    required_content: list[str] = Field(default_factory=list)
    forbidden_content: list[str] = Field(default_factory=list)
    protection_rules: list[str] = Field(default_factory=list)

    status: BriefStatus = BriefStatus.DRAFT

    def approve(self) -> None:
        self.status = BriefStatus.APPROVED

    def mark_changes_pending(self) -> None:
        if self.status == BriefStatus.APPROVED:
            self.status = BriefStatus.CHANGES_PENDING

    def mark_ready_for_review(self) -> None:
        if self.status == BriefStatus.DRAFT:
            self.status = BriefStatus.READY_FOR_REVIEW

    @property
    def is_approved(self) -> bool:
        return self.status == BriefStatus.APPROVED


def index_design_briefs(briefs: list[SlideDesignBrief]) -> dict[int, SlideDesignBrief]:
    return {brief.page_order: brief for brief in briefs}


def format_design_brief_card(brief: SlideDesignBrief) -> str:
    """Human-readable block for UI and prompts."""
    lines = [
        f"第 {brief.page_order + 1:02d} 页设计摘要",
        "",
        "页面任务：",
        brief.page_task,
    ]
    if brief.central_claim.strip():
        lines.extend(["", "中心结论：", brief.central_claim.strip()])
    lines.extend(
        [
            "",
            f"中心视觉：{brief.primary_visual_type}",
            f"构图：{brief.layout_family or '—'}",
            f"密度：{brief.expected_density}",
        ]
    )
    if brief.primary_asset_ids:
        lines.append("主视觉素材：" + "、".join(str(aid) for aid in brief.primary_asset_ids[:4]))
    if brief.supporting_asset_ids:
        lines.append(
            "辅助素材：" + "、".join(str(aid) for aid in brief.supporting_asset_ids[:4])
        )
    if brief.drawing_policy is not None:
        lines.extend(
            [
                "",
                "图纸规则：",
                "完整显示",
                "保留指北针和比例尺" if brief.drawing_policy.show_north_arrow else "",
                "禁止 cover 裁剪" if brief.drawing_policy.forbid_cover_crop else "",
            ]
        )
    if brief.forbidden_content:
        lines.extend(["", "禁止："] + [f"- {item}" for item in brief.forbidden_content])
    if brief.protection_rules:
        lines.extend(["", "保护规则："] + [f"- {item}" for item in brief.protection_rules])
    lines.append("")
    lines.append(f"状态：{BRIEF_STATUS_LABELS_ZH.get(brief.status, brief.status.value)}")
    return "\n".join(line for line in lines if line is not None)
