"""Unit tests for DesignRationale domain and concept direction mapping."""

from __future__ import annotations

from uuid import uuid4

from archium.application.concept_direction_mapping import (
    concept_direction_from_draft,
    design_rationale_from_draft,
)
from archium.domain.design_rationale import DesignRationale
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionDraft,
    DesignRationaleAlternativeDraft,
    DesignRationaleDraft,
)


def test_design_rationale_from_draft() -> None:
    draft = DesignRationaleDraft(
        statement="采用院落式组织，保留历史轴线",
        reasons=["西安气候需要内向院落", "医院改造需分阶段施工"],
        evidence=["用户描述：老院区南北向布局", "已确认地点：西安"],
        confidence=0.72,
        alternatives=[
            DesignRationaleAlternativeDraft(
                label="整体拆除重建",
                note="资料不足且拆迁范围未定",
            )
        ],
        observation="老院区南北向布局，气候干燥",
        interpretation="需要内向院落与分阶段施工",
        problem="在保留轴线的前提下完成更新",
        hypothesis="院落组织可兼顾气候与轴线",
        strategy="保留南北主轴线，院落式点状加建",
        risks=["施工分期边界不清"],
    )
    rationale = design_rationale_from_draft(draft)
    assert rationale is not None
    assert "院落" in rationale.statement
    assert rationale.has_reasoning_chain()
    assert rationale.observation.startswith("老院区")
    assert "内向院落" in rationale.interpretation
    assert "更新" in rationale.problem
    assert "院落组织" in rationale.hypothesis
    assert "主轴线" in rationale.strategy
    assert rationale.risks == ["施工分期边界不清"]
    assert len(rationale.reasons) == 2
    assert rationale.confidence == 0.72
    block = rationale.to_prompt_block()
    assert "设计判断" in block
    assert "观察" in block
    assert "释义" in block
    assert "未选方案" in block or "权衡" in block


def test_design_rationale_empty_returns_none() -> None:
    assert design_rationale_from_draft(DesignRationaleDraft()) is None


def test_concept_direction_carries_design_rationale() -> None:
    draft = ConceptDirectionDraft(
        title="微创更新",
        summary="保留立面",
        design_rationale=DesignRationaleDraft(
            statement="最小干预更新",
            reasons=["保留历史立面"],
            evidence=["简介提到1998年门诊楼"],
            confidence=0.65,
            observation="1998年门诊楼立面仍可用",
            problem="更新需求与立面保护冲突",
            hypothesis="最小干预可兼顾使用与保护",
            strategy="保留立面，内部局部置换",
        ),
    )
    direction = concept_direction_from_draft(draft, project_id=uuid4())
    assert direction.design_rationale is not None
    assert "最小干预" in direction.design_rationale.statement
    assert direction.design_rationale.has_reasoning_chain()
    assert "设计判断" in direction.to_prompt_block()
    assert "问题" in direction.to_prompt_block()


def test_design_rationale_model_empty() -> None:
    assert DesignRationale().is_empty()
    assert not DesignRationale().has_reasoning_chain()
    assert DesignRationale(observation="坡地").has_reasoning_chain()
    assert not DesignRationale(observation="坡地").is_empty()
