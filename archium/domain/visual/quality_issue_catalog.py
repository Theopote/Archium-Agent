"""Stable quality-issue catalog for problem-driven gates (human checklist + auto maps)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.page_quality import IssueCategory, IssueSeverity


@dataclass(frozen=True)
class CatalogEntry:
    code: str
    severity: IssueSeverity
    category: IssueCategory
    label_zh: str
    veto: bool = False  # one-vote delivery block when selected by human


# --- Human checklist (A–E) -------------------------------------------------

HUMAN_CHECKLIST: tuple[CatalogEntry, ...] = (
    # A. Content & argument
    CatalogEntry("CONTENT.NO_CLEAR_CONCLUSION", IssueSeverity.MAJOR, IssueCategory.CONTENT, "页面没有明确结论"),
    CatalogEntry("CONTENT.TITLE_NOT_CONCLUSION", IssueSeverity.MINOR, IssueCategory.CONTENT, "标题不是结论，只是主题名称"),
    CatalogEntry("CONTENT.TEXT_PURPOSE_MISMATCH", IssueSeverity.MAJOR, IssueCategory.CONTENT, "文字与页面目的不一致"),
    CatalogEntry("CONTENT.CONCLUSION_WITHOUT_EVIDENCE", IssueSeverity.MAJOR, IssueCategory.CONTENT, "结论没有证据支持"),
    CatalogEntry("CONTENT.REPETITIVE", IssueSeverity.MINOR, IssueCategory.CONTENT, "信息重复"),
    CatalogEntry("CONTENT.TOO_VAGUE", IssueSeverity.MAJOR, IssueCategory.CONTENT, "内容过于空泛"),
    CatalogEntry("CONTENT.IMPORTANT_MISSING", IssueSeverity.MAJOR, IssueCategory.CONTENT, "重要内容缺失"),
    CatalogEntry(
        "CONTENT.SPECULATION_AS_FACT",
        IssueSeverity.BLOCKER,
        IssueCategory.CONTENT,
        "推测被写成事实",
        veto=True,
    ),
    CatalogEntry("CONTENT.METRIC_MISSING_UNIT", IssueSeverity.BLOCKER, IssueCategory.CONTENT, "数据缺少单位", veto=True),
    CatalogEntry("CONTENT.EXTERNAL_FACT_NO_CITATION", IssueSeverity.MAJOR, IssueCategory.CONTENT, "外部事实缺少引用"),
    # B. Image–text
    CatalogEntry("IMAGE_TEXT.NO_DIRECT_RELATION", IssueSeverity.MAJOR, IssueCategory.IMAGE_TEXT, "图片与文字无直接关系"),
    CatalogEntry("IMAGE_TEXT.DOES_NOT_SUPPORT_CONCLUSION", IssueSeverity.MAJOR, IssueCategory.IMAGE_TEXT, "图片不能支持页面结论"),
    CatalogEntry("IMAGE_TEXT.HERO_UNCLEAR", IssueSeverity.MAJOR, IssueCategory.IMAGE_TEXT, "主图不明确"),
    CatalogEntry("IMAGE_TEXT.EQUAL_WEIGHT_IMAGES", IssueSeverity.MINOR, IssueCategory.IMAGE_TEXT, "多张图片权重完全相同"),
    CatalogEntry("IMAGE_TEXT.DUPLICATE_IMAGES", IssueSeverity.MINOR, IssueCategory.IMAGE_TEXT, "图片之间重复"),
    CatalogEntry("IMAGE_TEXT.CAPTION_USELESS", IssueSeverity.MINOR, IssueCategory.IMAGE_TEXT, "图注无法说明图片"),
    CatalogEntry("IMAGE_TEXT.BAD_ORDER", IssueSeverity.MINOR, IssueCategory.IMAGE_TEXT, "图片顺序不合理"),
    CatalogEntry("IMAGE_TEXT.TEXT_ONLY_DESCRIBES", IssueSeverity.MINOR, IssueCategory.IMAGE_TEXT, "文字只是描述图片，没有形成判断"),
    # C. Architectural expression
    CatalogEntry("ARCH.DRAWING_TOO_SMALL", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "图纸过小"),
    CatalogEntry("ARCH.DRAWING_DISTORTED", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "图纸比例失真"),
    CatalogEntry(
        "ARCH.DRAWING_CRITICAL_CROP",
        IssueSeverity.BLOCKER,
        IssueCategory.ARCHITECTURAL,
        "图纸关键部分被不合理裁切",
        veto=True,
    ),
    CatalogEntry("ARCH.ANNOTATIONS_UNREADABLE", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "图纸标注无法阅读"),
    CatalogEntry("ARCH.SITE_PLAN_NO_ORIENTATION", IssueSeverity.MINOR, IssueCategory.ARCHITECTURAL, "总平面缺少方位"),
    CatalogEntry("ARCH.BEFORE_AFTER_MISMATCH", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "Before/After 不对应"),
    CatalogEntry("ARCH.PROBLEM_WITHOUT_EVIDENCE", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "现状问题没有证据"),
    CatalogEntry("ARCH.STRATEGY_DETACHED", IssueSeverity.MAJOR, IssueCategory.ARCHITECTURAL, "改造策略没有对应目标"),
    CatalogEntry(
        "ARCH.REFERENCE_AS_PROJECT",
        IssueSeverity.BLOCKER,
        IssueCategory.ARCHITECTURAL,
        "参考案例与本项目混淆 / 冒充本项目",
        veto=True,
    ),
    CatalogEntry(
        "ARCH.IMAGE_IDENTITY_UNCLEAR",
        IssueSeverity.BLOCKER,
        IssueCategory.ARCHITECTURAL,
        "效果图、现场照片和案例图片身份不明确",
        veto=True,
    ),
    CatalogEntry(
        "ARCH.AI_AS_SITE_PHOTO",
        IssueSeverity.BLOCKER,
        IssueCategory.ARCHITECTURAL,
        "AI 图片冒充现场照片",
        veto=True,
    ),
    # D. Layout & visual
    CatalogEntry("LAYOUT.OVERLAP", IssueSeverity.BLOCKER, IssueCategory.LAYOUT_VISUAL, "元素重叠", veto=True),
    CatalogEntry("LAYOUT.OUT_OF_BOUNDS", IssueSeverity.BLOCKER, IssueCategory.LAYOUT_VISUAL, "页面越界", veto=True),
    CatalogEntry("LAYOUT.TEXT_OVERFLOW", IssueSeverity.BLOCKER, IssueCategory.LAYOUT_VISUAL, "文字溢出 / 无法阅读", veto=True),
    CatalogEntry("LAYOUT.FONT_TOO_SMALL", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "字号过小"),
    CatalogEntry("LAYOUT.TITLE_HIERARCHY_WEAK", IssueSeverity.MINOR, IssueCategory.LAYOUT_VISUAL, "标题层级不明确"),
    CatalogEntry("LAYOUT.NO_VISUAL_FOCUS", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "缺少视觉中心"),
    CatalogEntry("LAYOUT.WHITESPACE_IMBALANCE", IssueSeverity.MINOR, IssueCategory.LAYOUT_VISUAL, "留白失衡"),
    CatalogEntry("LAYOUT.TOO_DENSE", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "页面过密"),
    CatalogEntry("LAYOUT.TOO_EMPTY", IssueSeverity.MINOR, IssueCategory.LAYOUT_VISUAL, "页面过空"),
    CatalogEntry("LAYOUT.WEAK_CONTRAST", IssueSeverity.MINOR, IssueCategory.LAYOUT_VISUAL, "色彩对比不足"),
    CatalogEntry("LAYOUT.FONT_SUBSTITUTION", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "字体替换"),
    CatalogEntry("LAYOUT.IMAGE_DISTORTED", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "图片变形"),
    CatalogEntry("LAYOUT.DECK_RHYTHM_REPEAT", IssueSeverity.MAJOR, IssueCategory.LAYOUT_VISUAL, "页面之间节奏重复"),
    CatalogEntry(
        "LAYOUT.BLANK_PAGE",
        IssueSeverity.BLOCKER,
        IssueCategory.LAYOUT_VISUAL,
        "页面空白",
        veto=True,
    ),
    # E. Delivery & editability
    CatalogEntry("EDIT.PAGE_RASTERIZED", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "页面被整页栅格化"),
    CatalogEntry("EDIT.TEXT_NOT_EDITABLE", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "文字不可编辑"),
    CatalogEntry("EDIT.IMAGE_NOT_REPLACEABLE", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "图片不可替换"),
    CatalogEntry("EDIT.HARD_TO_SELECT", IssueSeverity.MINOR, IssueCategory.DELIVERY_EDITABILITY, "元素选择困难"),
    CatalogEntry("EDIT.LAYER_CHAOS", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "图层关系混乱"),
    CatalogEntry(
        "EDIT.PPTX_MISALIGNED",
        IssueSeverity.BLOCKER,
        IssueCategory.DELIVERY_EDITABILITY,
        "打开 PowerPoint 后错位 / PPTX 与评审截图不一致",
        veto=True,
    ),
    CatalogEntry("EDIT.MISSING_FONT", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "字体缺失"),
    CatalogEntry("EDIT.EXPORT_PREVIEW_MISMATCH", IssueSeverity.MAJOR, IssueCategory.DELIVERY_EDITABILITY, "导出和预览不一致"),
)

HUMAN_CHECKLIST_BY_CODE: dict[str, CatalogEntry] = {entry.code: entry for entry in HUMAN_CHECKLIST}

# Auto / critic / post-render code → default severity (prefix or exact).
AUTO_SEVERITY_RULES: tuple[tuple[str, IssueSeverity], ...] = (
    ("POST_RENDER.BLANK_PAGE", IssueSeverity.BLOCKER),
    ("POST_RENDER.BLACK_BLOCK", IssueSeverity.BLOCKER),
    ("POST_RENDER.IMAGE_NOT_LOADED", IssueSeverity.BLOCKER),
    ("POST_RENDER.ALL_PAGES_IDENTICAL", IssueSeverity.MAJOR),
    ("POST_RENDER.DUPLICATE_PAGE", IssueSeverity.MAJOR),
    ("POST_RENDER.PNG_PPTX_DIFF", IssueSeverity.BLOCKER),
    ("POST_RENDER.", IssueSeverity.MAJOR),
    ("SEMANTIC.DRAWING_COVER_MODE_FORBIDDEN", IssueSeverity.MAJOR),
    ("SEMANTIC.AI_IMAGE_", IssueSeverity.BLOCKER),
    ("SEMANTIC.IMAGE_NOT_RENDERED", IssueSeverity.BLOCKER),
    ("SEMANTIC.TEXT_OVERFLOW", IssueSeverity.BLOCKER),
    ("SEMANTIC.FONT_TOO_SMALL", IssueSeverity.MAJOR),
    ("SEMANTIC.SCENE_PPTX_NODE_MISMATCH", IssueSeverity.BLOCKER),
    ("SEMANTIC.", IssueSeverity.MAJOR),
    ("LAYOUT.ELEMENT_OVERLAP", IssueSeverity.BLOCKER),
    ("LAYOUT.TEXT_OVERFLOW", IssueSeverity.BLOCKER),
    ("LAYOUT.OUT_OF_BOUNDS", IssueSeverity.BLOCKER),
    ("LAYOUT.", IssueSeverity.MAJOR),
    ("CRITIC.", IssueSeverity.MAJOR),
    ("DECK.", IssueSeverity.MINOR),
    ("PROVENANCE.", IssueSeverity.BLOCKER),
)


def default_severity_for_auto_code(code: str) -> IssueSeverity:
    """Map an automated rule/check code to IssueSeverity."""
    normalized = code.strip()
    for prefix, severity in AUTO_SEVERITY_RULES:
        if normalized == prefix.rstrip(".") or normalized.startswith(prefix):
            return severity
    return IssueSeverity.MAJOR


def checklist_grouped() -> dict[IssueCategory, list[CatalogEntry]]:
    grouped: dict[IssueCategory, list[CatalogEntry]] = {cat: [] for cat in IssueCategory}
    for entry in HUMAN_CHECKLIST:
        grouped[entry.category].append(entry)
    return grouped


CATEGORY_LABELS_ZH: dict[IssueCategory, str] = {
    IssueCategory.CONTENT: "A. 内容与论证",
    IssueCategory.IMAGE_TEXT: "B. 图文关系",
    IssueCategory.ARCHITECTURAL: "C. 建筑专业表达",
    IssueCategory.LAYOUT_VISUAL: "D. 版式与视觉",
    IssueCategory.DELIVERY_EDITABILITY: "E. 交付与可编辑性",
}
