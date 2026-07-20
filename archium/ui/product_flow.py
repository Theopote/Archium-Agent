"""Product-facing five-stage workflow (Work Package I)."""

from __future__ import annotations

from dataclasses import dataclass


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
        caption="上传文件、整理事实与素材，确认资料缺口。",
        page_key="materials",
        icon="📁",
    ),
    ProductStage(
        id="outline",
        title="大纲",
        caption="描述汇报任务，确认结构、页数与必须出现的内容。",
        page_key="outline",
        icon="🧭",
    ),
    ProductStage(
        id="generate",
        title="生成",
        caption="生成页面内容与版式预览，处理错误与进度。",
        page_key="generate",
        icon="⚡",
    ),
    ProductStage(
        id="edit",
        title="编辑",
        caption="在汇报工作室调整页面、版式与图文。",
        page_key="edit",
        icon="🎬",
    ),
    ProductStage(
        id="deliver",
        title="交付",
        caption="导出 PPTX/PDF、查看质量检查与评审状态。",
        page_key="deliver",
        icon="📦",
    ),
)

ADVANCED_PAGE_KEYS: tuple[str, ...] = (
    "project-management",
    "project-mission",
    "workspace",
    "visual-design",
    "template-studio",
    "command-center",
    "settings",
)

PRIMARY_SECTION = "主流程"
ADVANCED_SECTION = "进阶"


def primary_stages() -> tuple[ProductStage, ...]:
    return PRIMARY_STAGES


def primary_stage_ids() -> tuple[str, ...]:
    return tuple(stage.id for stage in PRIMARY_STAGES)


def primary_page_keys() -> tuple[str, ...]:
    return tuple(stage.page_key for stage in PRIMARY_STAGES)


def advanced_page_keys() -> tuple[str, ...]:
    return ADVANCED_PAGE_KEYS


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
