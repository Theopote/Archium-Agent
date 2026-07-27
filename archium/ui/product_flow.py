"""Product-facing five-stage workflow (Work Package I)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.ui import icons

# ---------------------------------------------------------------------------
# Studio page-key contract (UI Architecture V1)
#
# - ``edit``  — formal product-flow stage key (制作 → 工作室). Use this for
#   ``st.page_link`` / ``st.switch_page`` / stage navigation.
# - ``studio`` — legacy hidden deep-link only (``url_path=studio``). It still
#   registers ``pages/studio.py`` for bookmarks and internal embeds, but MUST
#   NOT appear in sidebar navigation. New product chrome must not navigate to
#   ``studio``; call ``product_studio_page_key()`` / ``"edit"`` instead.
# ---------------------------------------------------------------------------
PRODUCT_STUDIO_PAGE_KEY = "edit"
LEGACY_STUDIO_PAGE_KEY = "studio"


@dataclass(frozen=True)
class ProductStage:
    """One primary product-flow stage shown in the main navigation."""

    id: str
    title: str
    caption: str
    page_key: str
    icon: str


PRIMARY_STAGES: tuple[ProductStage, ...] = (
    ProductStage(
        id="materials",
        title="资料",
        caption="可选：上传资料 enrich 任务理解，整理事实与素材。",
        page_key="materials",
        icon=icons.MATERIALS,
    ),
    ProductStage(
        id="outline",
        title="大纲",
        caption="描述设计意图，确认结构、页数与必须出现的内容。",
        page_key="outline",
        icon=icons.OUTLINE,
    ),
    ProductStage(
        id="generate",
        title="生成",
        caption="运行内容管线，生成页面文字与结构；版式在工作室补做。",
        page_key="generate",
        icon=icons.GENERATE,
    ),
    ProductStage(
        id="edit",
        title="工作室",
        caption="故事线 · 页面 · 修改建议，和 AI 一起打磨表达。",
        page_key=PRODUCT_STUDIO_PAGE_KEY,
        icon=icons.STUDIO,
    ),
    ProductStage(
        id="deliver",
        title="交付",
        caption="导出 PPTX/PDF、查看质量检查与评审状态。",
        page_key="deliver",
        icon=icons.DELIVER,
    ),
)

# Contextual and developer-only pages (not in primary sidebar).
# ``studio`` redirects to ``edit`` (bookmark compatibility only).
# ``workspace`` is a developer deep tool (also linked from 设置 → 开发者与验收).
# Concept exploration and mission stay reachable from the current-project UI.
HIDDEN_PAGE_KEYS: tuple[str, ...] = (
    "workspace",
    LEGACY_STUDIO_PAGE_KEY,
    "template-studio",
    "template-induction",
    "concept-exploration",
    "project-mission",
)

# Backward-compatible alias used by older tests/imports.
ADVANCED_PAGE_KEYS: tuple[str, ...] = HIDDEN_PAGE_KEYS

PROJECT_SECTION = "项目"
MAKE_SECTION = "制作"
RESOURCE_SECTION = "资源"
SYSTEM_SECTION = "系统"

# Backward-compatible aliases (old two-section IA).
PRIMARY_SECTION = MAKE_SECTION
ADVANCED_SECTION = SYSTEM_SECTION


def product_studio_page_key() -> str:
    """Page key for product navigation into the Studio workbench (``edit``)."""
    return PRODUCT_STUDIO_PAGE_KEY


def primary_stages() -> tuple[ProductStage, ...]:
    return PRIMARY_STAGES


def primary_stage_ids() -> tuple[str, ...]:
    return tuple(stage.id for stage in PRIMARY_STAGES)


def primary_page_keys() -> tuple[str, ...]:
    return tuple(stage.page_key for stage in PRIMARY_STAGES)


def advanced_page_keys() -> tuple[str, ...]:
    return HIDDEN_PAGE_KEYS


def hidden_page_keys() -> tuple[str, ...]:
    return HIDDEN_PAGE_KEYS


def get_stage(stage_id: str) -> ProductStage:
    for stage in PRIMARY_STAGES:
        if stage.id == stage_id:
            return stage
    msg = f"Unknown product stage: {stage_id}"
    raise KeyError(msg)


def next_stage(stage_id: str) -> ProductStage | None:
    ids = primary_stage_ids()
    if stage_id not in ids:
        raise KeyError(stage_id)
    index = ids.index(stage_id)
    if index >= len(PRIMARY_STAGES) - 1:
        return None
    return PRIMARY_STAGES[index + 1]


def previous_stage(stage_id: str) -> ProductStage | None:
    ids = primary_stage_ids()
    if stage_id not in ids:
        raise KeyError(stage_id)
    index = ids.index(stage_id)
    if index <= 0:
        return None
    return PRIMARY_STAGES[index - 1]


def product_flow_chain() -> str:
    """User-facing five-stage chain label."""
    return " → ".join(stage.title for stage in PRIMARY_STAGES)


def product_flow_home_steps() -> list[str]:
    """Markdown step lines for the home page (without numbering prefix)."""
    return [
        f"**{stage.title}** — {stage.caption}"
        for stage in PRIMARY_STAGES
    ]
