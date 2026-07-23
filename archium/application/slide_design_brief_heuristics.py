"""Design-brief heuristics and UI formatting (DOM-014: relocated from domain)."""

from __future__ import annotations

from archium.domain.slide_design_brief import (
    BRIEF_STATUS_LABELS_ZH,
    DrawingDisplayPolicy,
    SlideDesignBrief,
)

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
        "evidence_board",
        "evidence_grid",
        "hero_image",
        "comparison",
    }
)


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


def format_design_brief_card(brief: SlideDesignBrief) -> str:
    """Human-readable block for UI and prompts."""
    from archium.application.visual.visual_grammar_labels import (
        archetype_label,
        grammar_evidence_hints,
    )

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
            f"构图：{(brief.layout_family.value if brief.layout_family else None) or '—'}",
            f"密度：{brief.expected_density}",
            f"视觉语法：{archetype_label(brief.page_archetype)}",
        ]
    )
    slot_hints = grammar_evidence_hints(brief.page_archetype)
    if slot_hints:
        lines.extend(["", "证据槽位："] + [f"- {item}" for item in slot_hints])
    if brief.required_content:
        lines.extend(
            ["", "必须内容："] + [f"- {item}" for item in brief.required_content[:8]]
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
