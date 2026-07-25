"""Unified human-in-the-loop gate labels for orchestration + subgraph pauses."""

from __future__ import annotations

from enum import StrEnum

from archium.domain._base import DomainModel
from archium.domain.orchestration.models import OrchestrationStage


class HumanGateKind(StrEnum):
    """Architect must confirm before the process continues."""

    CONCEPT_SELECTION = "concept_selection"
    MATERIALS = "materials"
    MISSION_CONFIRM = "mission_confirm"
    PLAN_APPROVAL = "plan_approval"
    STRATEGY_CONFIRM = "strategy_confirm"
    PRESENTATION_REVIEW = "presentation_review"
    ART_DIRECTION = "art_direction"
    DELIVER = "deliver"
    OTHER = "other"


class HumanGate(DomainModel):
    """Product-facing pause: one vocabulary for orchestration and LangGraph interrupt."""

    kind: HumanGateKind = HumanGateKind.OTHER
    label: str = ""
    stage: str = ""
    page_key: str | None = None
    review_gate: str = ""
    prompt: str = ""

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


_STAGE_GATES: dict[OrchestrationStage, tuple[HumanGateKind, str, str]] = {
    OrchestrationStage.EXPLORE: (
        HumanGateKind.CONCEPT_SELECTION,
        "选定概念方向",
        "请选择一个概念方向后再继续。",
    ),
    OrchestrationStage.MATERIALS: (
        HumanGateKind.MATERIALS,
        "补充 / 确认资料",
        "请上传或确认项目资料后再继续。",
    ),
    OrchestrationStage.MISSION_PLANNING: (
        HumanGateKind.MISSION_CONFIRM,
        "确认任务使命",
        "请确认或修正 Mission 后再继续。",
    ),
    OrchestrationStage.WORKSTREAM_EXECUTION: (
        HumanGateKind.STRATEGY_CONFIRM,
        "确认设计策略 / 工作路径",
        "请确认空间策略与工作路径结果后再继续。",
    ),
    OrchestrationStage.PRESENTATION: (
        HumanGateKind.PRESENTATION_REVIEW,
        "确认汇报稿",
        "请审阅汇报结构 / 页面后再继续。",
    ),
    OrchestrationStage.VISUAL: (
        HumanGateKind.ART_DIRECTION,
        "确认视觉方向",
        "请确认艺术方向或版式后再继续。",
    ),
    OrchestrationStage.DELIVER: (
        HumanGateKind.DELIVER,
        "确认交付",
        "请确认导出与交付物。",
    ),
    OrchestrationStage.RESEARCH: (
        HumanGateKind.OTHER,
        "研究阶段",
        "研究通常自动执行；若暂停请检查结果后继续。",
    ),
}


def human_gate_for_stage(
    stage: OrchestrationStage,
    *,
    page_key: str | None = None,
    awaiting_review: bool = False,
) -> HumanGate:
    kind, label, prompt = _STAGE_GATES.get(
        stage,
        (HumanGateKind.OTHER, label_fallback(stage), "请确认后继续。"),
    )
    if awaiting_review and stage == OrchestrationStage.MISSION_PLANNING:
        kind = HumanGateKind.MISSION_CONFIRM
        label = "确认任务 / 计划"
    if awaiting_review and stage == OrchestrationStage.PRESENTATION:
        kind = HumanGateKind.PRESENTATION_REVIEW
    if awaiting_review and stage == OrchestrationStage.VISUAL:
        kind = HumanGateKind.ART_DIRECTION
    review = f"orchestration:{stage.value}"
    return HumanGate(
        kind=kind,
        label=label,
        stage=stage.value,
        page_key=page_key,
        review_gate=review,
        prompt=prompt,
    )


def label_fallback(stage: OrchestrationStage) -> str:
    from archium.domain.orchestration.plan_builder import label_for_stage

    return label_for_stage(stage)
