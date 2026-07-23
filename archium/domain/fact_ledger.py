"""Standard fact keys and conflict groups for the project fact ledger."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactKeyDefinition:
    key: str
    label: str
    category: str
    # Deprecated catalog field — do not pre-stamp on facts. Runtime conflict_group
    # is set only when validation/upsert detects an actual conflict (alias:/key:/empty:).
    conflict_group: str | None = None


STANDARD_FACT_KEYS: tuple[FactKeyDefinition, ...] = (
    FactKeyDefinition("project_name", "项目名称", "identity"),
    FactKeyDefinition("location", "项目位置", "identity"),
    FactKeyDefinition("client", "甲方", "identity"),
    FactKeyDefinition("project_stage", "项目阶段", "identity"),
    FactKeyDefinition("site_area", "用地面积", "area"),
    FactKeyDefinition("building_area", "建筑面积", "area"),
    FactKeyDefinition("plot_ratio", "容积率", "ratio"),
    FactKeyDefinition("building_density", "建筑密度", "ratio"),
    FactKeyDefinition("green_ratio", "绿地率", "ratio"),
    FactKeyDefinition("height", "建筑高度", "dimension"),
    FactKeyDefinition("floors", "层数", "dimension"),
    FactKeyDefinition("bed_count", "床位数", "capacity"),
    FactKeyDefinition("parking_count", "停车数", "capacity"),
    FactKeyDefinition("main_function", "主要功能", "program"),
    FactKeyDefinition("client_requirements", "甲方要求", "constraints"),
    FactKeyDefinition("constraints", "限制条件", "constraints"),
    FactKeyDefinition("key_decisions", "关键决策", "decisions"),
)

STANDARD_FACT_KEY_MAP = {item.key: item for item in STANDARD_FACT_KEYS}

# Keys that represent the same metric under different names.
SEMANTIC_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("plot_ratio", "far"),
    ("site_area", "land_area"),
    ("building_area", "gross_floor_area"),
    ("floors", "floor_count"),
    ("bed_count", "beds"),
)
