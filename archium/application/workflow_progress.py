"""Workflow step labels and progress helpers for UI polling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.workflow import WorkflowRun

STEP_LABELS: dict[str, str] = {
    WorkflowStep.INIT.value: "初始化工作流",
    WorkflowStep.LOAD_PROJECT.value: "加载项目与素材",
    WorkflowStep.VALIDATE_SOURCES.value: "校验项目资料",
    WorkflowStep.RETRIEVE_CONTEXT.value: "检索项目上下文（RAG）",
    WorkflowStep.EXTRACT_FACTS.value: "抽取结构化指标",
    WorkflowStep.VALIDATE_FACTS.value: "校验指标一致性",
    WorkflowStep.BRIEF.value: "生成 Brief",
    WorkflowStep.REVIEW_BRIEF.value: "等待 Brief 审核",
    WorkflowStep.STORYLINE.value: "正在梳理 Storyline…",
    WorkflowStep.REVIEW_STORYLINE.value: "等待 Storyline 审核",
    WorkflowStep.SLIDES.value: "正在生成 SlideSpec…",
    WorkflowStep.REVIEW_SLIDES.value: "等待 SlideSpec 审核",
    WorkflowStep.RESOLVE_CITATIONS.value: "解析引用与出处",
    WorkflowStep.MATCH_ASSETS.value: "匹配图档与素材",
    WorkflowStep.CONTENT_REVIEW.value: "内容质量审核",
    WorkflowStep.EVIDENCE_REVIEW.value: "证据链审核",
    WorkflowStep.ARCHITECTURAL_REVIEW.value: "专业表达审核",
    WorkflowStep.LAYOUT_REVIEW.value: "版面校验",
    WorkflowStep.PROFESSIONAL_REVIEW.value: "综合专业审核",
    WorkflowStep.REPAIR_SLIDES.value: "修复问题页",
    WorkflowStep.SLIDE_VALIDATION.value: "SlideSpec 校验",
    WorkflowStep.EXPORT.value: "导出 JSON",
    WorkflowStep.PRESENTATION_SPEC.value: "生成 PresentationSpec",
    WorkflowStep.MARP.value: "渲染 Marp / 预览",
    WorkflowStep.FINALIZE.value: "收尾与归档",
    WorkflowStep.FAILED.value: "工作流失败",
    WorkflowStep.PLANNING_LOAD_CONTEXT.value: "加载 Mission 上下文",
    WorkflowStep.PLANNING_ANALYZE_TASK.value: "理解任务与识别缺口",
    WorkflowStep.PLANNING_VALIDATE_MISSION.value: "校验任务理解",
    WorkflowStep.PLANNING_AWAIT_MISSION_CORRECTION.value: "等待修正任务理解",
    WorkflowStep.PLANNING_AWAIT_CLARIFICATION.value: "等待补充澄清",
    WorkflowStep.PLANNING_REVISE_MISSION.value: "修订 Mission",
    WorkflowStep.PLANNING_VALIDATE_REVISED_MISSION.value: "校验修订后的 Mission",
    WorkflowStep.PLANNING_AWAIT_MISSION_APPROVAL.value: "等待批准 Mission",
    WorkflowStep.PLANNING_WORKSTREAMS.value: "规划工作路径",
    WorkflowStep.PLANNING_DELIVERABLES.value: "规划成果清单",
    WorkflowStep.PLANNING_AWAIT_APPROVAL.value: "等待批准规划",
    WorkflowStep.PLANNING_PREPARE_ARTIFACTS.value: "准备汇报产物",
    WorkflowStep.PLANNING_PREPARE_PRESENTATION.value: "准备汇报产物",
    WorkflowStep.PLANNING_FINALIZE.value: "完成 Mission 规划",
    WorkflowStep.VISUAL_LOAD_CONTEXT.value: "加载汇报上下文",
    WorkflowStep.VISUAL_LOAD_DESIGN_SYSTEM.value: "加载设计系统",
    WorkflowStep.VISUAL_GENERATE_ART_DIRECTION.value: "生成视觉方向",
    WorkflowStep.VISUAL_AWAIT_ART_DIRECTION_APPROVAL.value: "等待视觉方向审核",
    WorkflowStep.VISUAL_GENERATE_INTENTS.value: "生成页面视觉意图",
    WorkflowStep.VISUAL_GENERATE_DECK_COMPOSITION.value: "规划整套视觉节奏",
    WorkflowStep.VISUAL_GENERATE_LAYOUT_CANDIDATES.value: "生成版式候选",
    WorkflowStep.VISUAL_SELECT_LAYOUTS.value: "选择版式方案",
    WorkflowStep.VISUAL_VALIDATE_LAYOUTS.value: "校验版式",
    WorkflowStep.VISUAL_REPAIR_LAYOUTS.value: "修复版式问题",
    WorkflowStep.VISUAL_APPLY_SAFE_FALLBACK.value: "应用安全回退版式",
    WorkflowStep.VISUAL_AWAIT_LAYOUT_REVIEW.value: "等待版式审核",
    WorkflowStep.VISUAL_RENDER.value: "渲染 PPTX",
    WorkflowStep.VISUAL_CRITIQUE.value: "整套一致性检查",
    WorkflowStep.VISUAL_FINALIZE.value: "完成视觉编排",
}

STATUS_LABELS: dict[WorkflowStatus, str] = {
    WorkflowStatus.RUNNING: "运行中",
    WorkflowStatus.AWAITING_REVIEW: "等待审核",
    WorkflowStatus.COMPLETED: "已完成",
    WorkflowStatus.FAILED: "失败",
    WorkflowStatus.CANCELLED: "已取消",
}


@dataclass(frozen=True)
class WorkflowProgressSnapshot:
    """UI-friendly view of a persisted workflow run."""

    workflow_run_id: str
    status: WorkflowStatus
    current_step: str | None
    current_step_label: str
    step_log: list[dict[str, str]]
    errors: list[str]
    is_terminal: bool


def append_step_log(state: dict[str, Any], *, max_entries: int = 80) -> None:
    """Append ``current_step`` to ``step_log`` when the step changes."""
    step = state.get("current_step")
    if not step:
        return
    log = list(state.get("step_log") or [])
    if log and log[-1].get("step") == step:
        return
    log.append({"step": str(step), "at": datetime.now(UTC).isoformat()})
    state["step_log"] = log[-max_entries:]


def label_for_step(step: str | None, *, state: dict[str, Any] | None = None) -> str:
    if not step:
        return "准备中…"
    label = STEP_LABELS.get(step, step)
    if step == WorkflowStep.LAYOUT_REVIEW.value and state:
        slide_index = state.get("layout_review_slide_index")
        if slide_index is not None:
            try:
                return f"正在校验第 {int(slide_index) + 1} 页版面…"
            except (TypeError, ValueError):
                pass
        slide_count = state.get("slide_count")
        if slide_count:
            return f"正在校验版面（共 {slide_count} 页）…"
    if step == WorkflowStep.VISUAL_VALIDATE_LAYOUTS.value and state:
        plans = state.get("layout_plans") or []
        if plans:
            return f"正在校验 {len(plans)} 页版式…"
    return label


def snapshot_from_run(run: WorkflowRun) -> WorkflowProgressSnapshot:
    state = dict(run.state or {})
    current_step = state.get("current_step")
    if isinstance(current_step, WorkflowStep):
        current_step = current_step.value
    status = run.status
    if isinstance(status, str):
        status = WorkflowStatus(status)
    return WorkflowProgressSnapshot(
        workflow_run_id=str(run.id),
        status=status,
        current_step=str(current_step) if current_step else None,
        current_step_label=label_for_step(
            str(current_step) if current_step else None,
            state=state,
        ),
        step_log=[dict(entry) for entry in state.get("step_log") or []],
        errors=list(run.errors or []),
        is_terminal=status
        in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        },
    )


def format_step_log_entry(entry: dict[str, str]) -> str:
    step = entry.get("step", "")
    label = label_for_step(step)
    at = entry.get("at", "")
    if at:
        try:
            ts = datetime.fromisoformat(at.replace("Z", "+00:00"))
            time_text = ts.astimezone().strftime("%H:%M:%S")
            return f"{time_text} · {label}"
        except ValueError:
            pass
    return label
