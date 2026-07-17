"""Standard fact keys and conflict groups for the project fact ledger."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactKeyDefinition:
    key: str
    label: str
    category: str
    conflict_group: str | None = None


STANDARD_FACT_KEYS: tuple[FactKeyDefinition, ...] = (
    FactKeyDefinition("project_name", "项目名称", "identity"),
    FactKeyDefinition("location", "项目位置", "identity"),
    FactKeyDefinition("client", "甲方", "identity"),
    FactKeyDefinition("project_stage", "项目阶段", "identity"),
    FactKeyDefinition("site_area", "用地面积", "area", conflict_group="area"),
    FactKeyDefinition("building_area", "建筑面积", "area", conflict_group="area"),
    FactKeyDefinition("plot_ratio", "容积率", "ratio", conflict_group="plot_ratio"),
    FactKeyDefinition("building_density", "建筑密度", "ratio", conflict_group="density"),
    FactKeyDefinition("green_ratio", "绿地率", "ratio", conflict_group="density"),
    FactKeyDefinition("height", "建筑高度", "dimension", conflict_group="height"),
    FactKeyDefinition("floors", "层数", "dimension", conflict_group="floors"),
    FactKeyDefinition("bed_count", "床位数", "capacity", conflict_group="capacity"),
    FactKeyDefinition("parking_count", "停车数", "capacity", conflict_group="capacity"),
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
