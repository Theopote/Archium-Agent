"""Design-iteration progress helpers for Mission UI / planning."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import ConceptDirectionStatus
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    VisualConceptBriefRepository,
)

_VISUAL_STATUS_LABELS = {
    "draft": "草稿",
    "ready": "文字简报就绪",
    "imaged": "已示意出图",
    "failed": "出图失败（文字仍可用）",
}


@dataclass(frozen=True)
class DesignIterationProgress:
    direction_count: int
    selected_title: str | None
    visual_status: str | None
    visual_title: str | None
    injectable: bool

    def summary_line(self) -> str:
        parts = [f"方向 {self.direction_count} 个"]
        if self.selected_title:
            parts.append(f"已选「{self.selected_title}」")
        else:
            parts.append("尚未选中方向")
        if self.visual_status:
            label = _VISUAL_STATUS_LABELS.get(self.visual_status, self.visual_status)
            title = f"「{self.visual_title}」" if self.visual_title else ""
            parts.append(f"视觉简报{title}：{label}")
        else:
            parts.append("尚无视觉简报")
        if self.injectable:
            parts.append("可注入 Brief / 汇报请求")
        return " · ".join(parts)


def visual_brief_status_label(status: str | None) -> str:
    if not status:
        return "无"
    return _VISUAL_STATUS_LABELS.get(status, status)


def format_vision_user_warning(warning: str) -> str:
    """Turn technical vision warnings into actionable Mission-panel copy."""
    text = (warning or "").strip()
    if not text:
        return text
    lowered = text.lower()
    if "vision_image_generation_enabled" in lowered:
        return (
            "示意出图未执行：请在设置中开启 Vision 图像生成"
            "（vision_image_generation_enabled）。文字视觉简报已保存。"
        )
    if "vision_auto_fulfill" in lowered:
        return "自动出图已关闭（vision_auto_fulfill_image_requests=false）。"
    if "unavailable" in lowered or "失败" in text or "failed" in lowered:
        return f"示意出图失败（文字简报已保留）：{text}"
    return text


def summarize_design_iteration(
    session: Session,
    mission_id: UUID,
) -> DesignIterationProgress:
    directions = ConceptDirectionRepository(session).list_by_mission(mission_id)
    selected = next(
        (item for item in directions if item.status == ConceptDirectionStatus.SELECTED),
        None,
    )
    brief: VisualConceptBrief | None = None
    if selected is not None:
        brief = VisualConceptBriefRepository(session).get_latest_for_direction(selected.id)
    injectable = bool(
        selected is not None
        and brief is not None
        and brief.status in {"ready", "imaged"}
    )
    return DesignIterationProgress(
        direction_count=len(directions),
        selected_title=selected.title if selected is not None else None,
        visual_status=brief.status if brief is not None else None,
        visual_title=brief.title if brief is not None else None,
        injectable=injectable,
    )
