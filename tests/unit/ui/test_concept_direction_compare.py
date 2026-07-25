"""Unit tests for ConceptDirection compare card field extraction."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.spatial_design import DesignRule, SpatialIntent
from archium.ui.components.concept_direction_compare import compare_card_fields


def test_compare_card_fields_prefer_architect_language() -> None:
    direction = ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="自然共生",
        theme="建筑融入山体",
        summary="长摘要不应抢核心理念栏",
        spatial_strategy="低体量 · 连续屋顶 · 地景化入口",
        formal_language="折线屋面与夯土",
        differentiator="对秦岭地形的最小扰动",
        experience_focus="慢行文化漫游",
        risks=["施工难度", "造价偏高"],
        status=ConceptDirectionStatus.DRAFT,
    )
    fields = compare_card_fields(direction)
    assert fields["core"] == "建筑融入山体"
    assert "低体量" in fields["spatial"]
    assert "折线屋面" in fields["form"]
    assert "最小扰动" in fields["advantage"]
    assert "施工难度" in fields["risks"]
    assert fields["suited"] == "慢行文化漫游"
    assert fields["badge"] == "草稿"


def test_compare_card_fields_fall_back_to_spatial_intent() -> None:
    direction = ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="文化转译",
        spatial_intent=SpatialIntent(
            spatial_relationships="院落串联公共厅",
            landscape_relation="嵌入坡地",
        ),
        design_rules=[
            DesignRule(
                principle="转译地方建造",
                formal_translation="坡屋顶阵列",
            )
        ],
        status=ConceptDirectionStatus.SELECTED,
    )
    fields = compare_card_fields(direction)
    assert fields["badge"] == "已选中"
    assert "院落" in fields["spatial"]
    assert "坡屋顶" in fields["form"]
