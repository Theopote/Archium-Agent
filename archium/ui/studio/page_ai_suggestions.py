"""Page-level AI suggestions for Studio (partner language, not scores)."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole


def page_partner_suggestions(slide: SlideSpec) -> list[str]:
    """Deterministic, architect-facing suggestions for the current page."""
    suggestions: list[str] = []
    message = (slide.message or "").strip()
    points = list(slide.key_points or [])
    title = (slide.title or "").strip() or "本页"

    if len(points) > 5 or len(message) > 120:
        suggestions.append(f"「{title}」信息过多 — 建议减少文字，保留单一核心结论")
    if len(points) == 0 and len(message) < 20:
        suggestions.append(f"「{title}」叙事偏空 — 补一句页意图或关键论据")

    role = slide.slide_role
    strategy = slide.visual_strategy
    analysis_roles = {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
    }
    if role in analysis_roles:
        diagram = ""
        if strategy is not None:
            diagram = (strategy.recommended_diagram or "").strip()
        if not diagram:
            suggestions.append(
                f"「{title}」是分析/策略页 — 建议增加剖面、流线或关系图，而非装饰图"
            )
        else:
            suggestions.append(f"「{title}」推荐图解：{diagram}")

    if role in {SlideRole.EXPERIENCE, SlideRole.VISION, SlideRole.CONCEPT}:
        suggestions.append(f"「{title}」体验/概念页 — 可用氛围示意，避免堆砌数据表格")

    if strategy is not None and not strategy.is_empty():
        if (strategy.image_requirement or "").strip():
            suggestions.append(f"图像需求：{strategy.image_requirement.strip()}")
        if (strategy.graphic_language or "").strip():
            suggestions.append(f"图面语言：{strategy.graphic_language.strip()}")
    elif role is None or role == SlideRole.OTHER:
        suggestions.append(f"「{title}」尚未标注页角色 — 补 SlideRole 有助版式与图解选择")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in suggestions:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:5]
