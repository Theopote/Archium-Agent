"""Stable machine identifiers for automated review findings."""


class ReviewRuleCode:
    """Rule codes used for review-issue fingerprinting and deduplication."""

    # Content
    CONTENT_MISSING_TITLE = "CONTENT.MISSING_TITLE"
    CONTENT_MISSING_MESSAGE = "CONTENT.MISSING_MESSAGE"
    CONTENT_MESSAGE_TOO_SHORT = "CONTENT.MESSAGE_TOO_SHORT"
    CONTENT_DUPLICATE_TITLE = "CONTENT.DUPLICATE_TITLE"
    CONTENT_BRIEF_CORE_NOT_REFLECTED = "CONTENT.BRIEF_CORE_NOT_REFLECTED"
    CONTENT_BRIEF_ALIGNMENT_GAP = "CONTENT.BRIEF_ALIGNMENT_GAP"

    # Evidence
    EVIDENCE_MISSING_CITATION = "EVIDENCE.MISSING_CITATION"
    EVIDENCE_NUMERIC_CLAIM_UNCITED = "EVIDENCE.NUMERIC_CLAIM_UNCITED"
    EVIDENCE_VISUAL_EVIDENCE_UNCONFIRMED = "EVIDENCE.VISUAL_EVIDENCE_UNCONFIRMED"
    EVIDENCE_MISSING_VISUAL_EVIDENCE = "EVIDENCE.MISSING_VISUAL_EVIDENCE"
    EVIDENCE_WEAK_VISUAL_ALIGNMENT = "EVIDENCE.WEAK_VISUAL_ALIGNMENT"

    # Architectural
    ARCH_SLIDE_COUNT_DEVIATION = "ARCH.SLIDE_COUNT_DEVIATION"
    ARCH_REQUIRED_SECTION_MISSING = "ARCH.REQUIRED_SECTION_MISSING"
    ARCH_CHAPTER_WITHOUT_SLIDES = "ARCH.CHAPTER_WITHOUT_SLIDES"
    ARCH_INCONSISTENT_AREA_UNITS = "ARCH.INCONSISTENT_AREA_UNITS"
    ARCH_CONCEPT_HAS_CONSTRUCTION_DETAIL = "ARCH.CONCEPT_HAS_CONSTRUCTION_DETAIL"
    ARCH_PLAN_MISSING_NORTH_ARROW = "ARCH.PLAN_MISSING_NORTH_ARROW"
    ARCH_PLAN_MISSING_FLOOR_LABEL = "ARCH.PLAN_MISSING_FLOOR_LABEL"
    ARCH_FLOW_DIAGRAM_MISSING_LEGEND = "ARCH.FLOW_DIAGRAM_MISSING_LEGEND"

    # Layout
    LAYOUT_HIGH_TEXT_DENSITY = "LAYOUT.HIGH_TEXT_DENSITY"
    LAYOUT_BULLET_TOO_LONG = "LAYOUT.BULLET_TOO_LONG"
    LAYOUT_TOO_MANY_BULLETS = "LAYOUT.TOO_MANY_BULLETS"
    LAYOUT_MESSAGE_TOO_LONG = "LAYOUT.MESSAGE_TOO_LONG"
    LAYOUT_MISSING_ASSET = "LAYOUT.MISSING_ASSET"
    LAYOUT_LOW_RESOLUTION_ASSET = "LAYOUT.LOW_RESOLUTION_ASSET"
    LAYOUT_EXTREME_ASPECT_RATIO = "LAYOUT.EXTREME_ASPECT_RATIO"
    LAYOUT_MANUAL_LAYOUT_CONFIRMATION = "LAYOUT.MANUAL_LAYOUT_CONFIRMATION"

    # Visual QA (image-level, explainable)
    VISUAL_DIMENSIONS_TOO_SMALL = "VISUAL.DIMENSIONS_TOO_SMALL"
    VISUAL_EXCESSIVE_MARGINS = "VISUAL.EXCESSIVE_MARGINS"
    VISUAL_LOW_COLOR_CONTRAST = "VISUAL.LOW_COLOR_CONTRAST"
    VISUAL_CONTENT_CLIPPED = "VISUAL.CONTENT_CLIPPED"
    VISUAL_HIGH_TEXT_DENSITY = "VISUAL.HIGH_TEXT_DENSITY"
    VISUAL_MISSING_NORTH_ARROW = "VISUAL.MISSING_NORTH_ARROW"
    VISUAL_MISSING_LEGEND = "VISUAL.MISSING_LEGEND"
    VISUAL_DRAWING_TYPE_MISMATCH = "VISUAL.DRAWING_TYPE_MISMATCH"

    LEGACY_UNSPECIFIED = "LEGACY.UNSPECIFIED"


# Backfill mapping for legacy rows keyed by historical display title.
TITLE_TO_RULE_CODE: dict[str, str] = {
    "缺少标题": ReviewRuleCode.CONTENT_MISSING_TITLE,
    "缺少核心信息": ReviewRuleCode.CONTENT_MISSING_MESSAGE,
    "结论表述过于简略": ReviewRuleCode.CONTENT_MESSAGE_TOO_SHORT,
    "标题重复": ReviewRuleCode.CONTENT_DUPLICATE_TITLE,
    "Brief 核心信息未体现": ReviewRuleCode.CONTENT_BRIEF_CORE_NOT_REFLECTED,
    "Brief 语义对齐不足": ReviewRuleCode.CONTENT_BRIEF_ALIGNMENT_GAP,
    "缺少引用来源": ReviewRuleCode.EVIDENCE_MISSING_CITATION,
    "数值结论缺少依据": ReviewRuleCode.EVIDENCE_NUMERIC_CLAIM_UNCITED,
    "视觉证据未确认": ReviewRuleCode.EVIDENCE_VISUAL_EVIDENCE_UNCONFIRMED,
    "结论缺少视觉证据": ReviewRuleCode.EVIDENCE_MISSING_VISUAL_EVIDENCE,
    "视觉素材与结论关联性弱": ReviewRuleCode.EVIDENCE_WEAK_VISUAL_ALIGNMENT,
    "页数偏离目标": ReviewRuleCode.ARCH_SLIDE_COUNT_DEVIATION,
    "必要章节未覆盖": ReviewRuleCode.ARCH_REQUIRED_SECTION_MISSING,
    "章节缺少对应页面": ReviewRuleCode.ARCH_CHAPTER_WITHOUT_SLIDES,
    "面积单位表述不一致": ReviewRuleCode.ARCH_INCONSISTENT_AREA_UNITS,
    "概念汇报包含施工图级细节": ReviewRuleCode.ARCH_CONCEPT_HAS_CONSTRUCTION_DETAIL,
    "总平面图缺少方位标注提示": ReviewRuleCode.ARCH_PLAN_MISSING_NORTH_ARROW,
    "平面图缺少楼层标注提示": ReviewRuleCode.ARCH_PLAN_MISSING_FLOOR_LABEL,
    "交通流线图缺少颜色图例提示": ReviewRuleCode.ARCH_FLOW_DIAGRAM_MISSING_LEGEND,
    "页面信息密度过高": ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
    "单条要点过长": ReviewRuleCode.LAYOUT_BULLET_TOO_LONG,
    "要点过多": ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
    "核心结论过长": ReviewRuleCode.LAYOUT_MESSAGE_TOO_LONG,
    "缺少匹配素材": ReviewRuleCode.LAYOUT_MISSING_ASSET,
    "素材分辨率偏低": ReviewRuleCode.LAYOUT_LOW_RESOLUTION_ASSET,
    "素材宽高比极端": ReviewRuleCode.LAYOUT_EXTREME_ASPECT_RATIO,
    "需人工确认版面调整": ReviewRuleCode.LAYOUT_MANUAL_LAYOUT_CONFIRMATION,
    "图像分辨率不足": ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL,
    "图像空白边距过大": ReviewRuleCode.VISUAL_EXCESSIVE_MARGINS,
    "图像对比度偏低": ReviewRuleCode.VISUAL_LOW_COLOR_CONTRAST,
    "图像可能被裁切": ReviewRuleCode.VISUAL_CONTENT_CLIPPED,
    "图纸文字密度过高": ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY,
    "图像未检测到指北针": ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW,
    "图像未检测到图例区域": ReviewRuleCode.VISUAL_MISSING_LEGEND,
    "图像类型与页面需求不一致": ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH,
}


def resolve_rule_code_from_title(title: str) -> str:
    """Map a legacy display title to a stable rule code when possible."""
    return TITLE_TO_RULE_CODE.get(title.strip(), ReviewRuleCode.LEGACY_UNSPECIFIED)


class ReviewRepairStrategy:
    """Repair routing for automated review findings."""

    TIERED_LAYOUT = "tiered_layout"
    LLM_CONTENT = "llm_content"
    MANUAL = "manual"
    NONE = "none"


# Layout rules handled by deterministic tiered repair (see slide_repair_policy).
AUTO_FIXABLE_RULE_CODES: frozenset[str] = frozenset(
    {
        ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
        ReviewRuleCode.LAYOUT_BULLET_TOO_LONG,
        ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
        ReviewRuleCode.LAYOUT_MESSAGE_TOO_LONG,
    }
)

RULE_REPAIR_STRATEGIES: dict[str, str] = {
    ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY: ReviewRepairStrategy.TIERED_LAYOUT,
    ReviewRuleCode.LAYOUT_BULLET_TOO_LONG: ReviewRepairStrategy.TIERED_LAYOUT,
    ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS: ReviewRepairStrategy.TIERED_LAYOUT,
    ReviewRuleCode.LAYOUT_MESSAGE_TOO_LONG: ReviewRepairStrategy.TIERED_LAYOUT,
    ReviewRuleCode.LAYOUT_MANUAL_LAYOUT_CONFIRMATION: ReviewRepairStrategy.MANUAL,
    ReviewRuleCode.CONTENT_MISSING_TITLE: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.CONTENT_MISSING_MESSAGE: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.CONTENT_MESSAGE_TOO_SHORT: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.CONTENT_DUPLICATE_TITLE: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.CONTENT_BRIEF_CORE_NOT_REFLECTED: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.CONTENT_BRIEF_ALIGNMENT_GAP: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.EVIDENCE_MISSING_CITATION: ReviewRepairStrategy.LLM_CONTENT,
    ReviewRuleCode.EVIDENCE_NUMERIC_CLAIM_UNCITED: ReviewRepairStrategy.LLM_CONTENT,
}


def is_auto_fixable_rule(rule_code: str) -> bool:
    """Return True when a rule code has a deterministic auto-repair path."""
    return rule_code in AUTO_FIXABLE_RULE_CODES


def repair_strategy_for_rule(rule_code: str) -> str:
    """Map a rule code to a repair strategy identifier."""
    return RULE_REPAIR_STRATEGIES.get(rule_code, ReviewRepairStrategy.NONE)
