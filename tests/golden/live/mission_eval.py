"""Run mission golden cases with a real LLM and produce live-eval artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from archium.application.deliverable_execution import (
    ArtifactExecutionPlan,
    DeliverableExecutionRouter,
)
from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_to_presentation_request import (
    MissionPresentationBridge,
    build_presentation_bridge,
)
from archium.application.mission_validation_service import MissionValidationService
from archium.application.project_mission_service import (
    MissionGenerationResult,
    ProjectMissionService,
)
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.config.settings import Settings
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import DeliverableType, ServiceDepth, TaskNature
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.base import LLMProvider
from sqlalchemy.orm import Session
from tests.golden.live.mission_rubric import MissionScorecard
from tests.golden.mission.loader import MissionGoldenCase, seed_mission_case

_ARTIFACTS_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "live_mission"


@dataclass
class MissionLiveEvalResult:
    case: MissionGoldenCase
    generation: MissionGenerationResult
    workstreams: list[Workstream]
    plan: DeliverablePlan
    execution_plans: list[ArtifactExecutionPlan]
    bridge: MissionPresentationBridge | None
    validation: dict[str, Any]
    auto_flags: list[str] = field(default_factory=list)
    auto_notes: list[str] = field(default_factory=list)
    scorecard: MissionScorecard | None = None
    artifact_dir: Path | None = None

    @property
    def has_critical_flags(self) -> bool:
        critical = {
            "fabricated_metrics",
            "consulting_as_full_design",
        }
        return bool(critical & set(self.auto_flags))


def live_artifacts_root() -> Path:
    return _ARTIFACTS_ROOT


def run_mission_live_case(
    session: Session,
    llm: LLMProvider,
    settings: Settings,
    case_path: Path,
    *,
    run_id: str | None = None,
    write_artifacts: bool = True,
) -> MissionLiveEvalResult:
    """Generate mission/workstreams/deliverables with a real provider."""
    case, project = seed_mission_case(session, case_path)
    resolved_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]

    mission_service = ProjectMissionService(session, llm, settings=settings)
    workstream_service = WorkstreamPlanningService(session, llm, settings=settings)
    deliverable_service = DeliverablePlanningService(session, llm, settings=settings)

    generation = mission_service.generate_mission(project.id, case.task_description)
    workstream_result = workstream_service.plan_workstreams(
        generation.mission.id,
        require_ready=False,
    )
    deliverable_result = deliverable_service.plan_deliverables(
        generation.mission.id,
        require_ready=False,
    )
    execution_plans = DeliverableExecutionRouter().route_plan(
        deliverable_result.mission,
        deliverable_result.plan,
        workstreams=deliverable_result.workstreams,
    )
    bridge: MissionPresentationBridge | None = None
    has_presentation = any(
        item.supported and item.deliverable_type == DeliverableType.PRESENTATION
        for item in execution_plans
    )
    if has_presentation:
        try:
            bridge = build_presentation_bridge(
                deliverable_result.mission,
                plan=deliverable_result.plan,
                workstreams=deliverable_result.workstreams,
            )
        except WorkflowError as exc:
            # Keep going; scorecard will capture bridge failure as a note.
            bridge_error = str(exc)
        else:
            bridge_error = None
    else:
        bridge_error = None

    validation = MissionValidationService().validate(
        generation.mission,
        knowledge_gaps=generation.knowledge_gaps,
        clarifying_questions=generation.clarifying_questions,
    ).to_dict()

    flags, notes = collect_auto_observations(
        case=case,
        generation=generation,
        workstreams=workstream_result.workstreams,
        plan=deliverable_result.plan,
        validation=validation,
        bridge_error=bridge_error,
    )

    scorecard = MissionScorecard(
        case_id=case.id,
        case_name=case.name,
        model=settings.llm_model,
        run_id=resolved_run_id,
        auto_flags=flags,
        auto_notes=notes,
    )
    scorecard.ensure_scaffold()
    _prefill_observation_hints(scorecard, flags)

    result = MissionLiveEvalResult(
        case=case,
        generation=generation,
        workstreams=workstream_result.workstreams,
        plan=deliverable_result.plan,
        execution_plans=execution_plans,
        bridge=bridge,
        validation=validation,
        auto_flags=flags,
        auto_notes=notes,
        scorecard=scorecard,
    )

    if write_artifacts:
        result.artifact_dir = write_live_case_artifacts(result, settings=settings)

    return result


def collect_auto_observations(
    *,
    case: MissionGoldenCase,
    generation: MissionGenerationResult,
    workstreams: list[Workstream],
    plan: DeliverablePlan,
    validation: dict[str, Any],
    bridge_error: str | None = None,
) -> tuple[list[str], list[str]]:
    """Heuristic flags for human review — not a substitute for scoring."""
    mission = generation.mission
    flags: list[str] = []
    notes: list[str] = []
    expectations = case.expectations
    natures = {item.value for item in mission.task_natures}
    depths = set(mission.requested_service_depths)
    blob = " ".join(
        [
            mission.title,
            mission.task_statement,
            " ".join(c.name + c.value for c in mission.known_constraints),
            " ".join(mission.key_unknowns),
            " ".join(gap.question for gap in generation.knowledge_gaps),
            " ".join(q.question for q in generation.clarifying_questions),
        ]
    )

    for needle in expectations.get("forbidden_fabricated_substrings") or []:
        if needle in blob:
            flags.append("fabricated_metrics")
            notes.append(f"疑似编造指标片段出现：{needle}")

    # Generic numeric area fabrication when case says area is unknown.
    if "area" in {
        gap.category.value for gap in generation.knowledge_gaps
    } or any("面积" in u for u in mission.key_unknowns):
        for constraint in mission.known_constraints:
            if any(token in constraint.name + constraint.value for token in ("面积", "建筑面积")):
                if any(ch.isdigit() for ch in constraint.value):
                    flags.append("fabricated_metrics")
                    notes.append(
                        f"面积仍未知，但约束含数值：「{constraint.name}={constraint.value}」"
                    )

    consulting_signal = bool(
        natures
        & {
            TaskNature.CONSULTING.value,
            TaskNature.TECHNICAL_STUDY.value,
            TaskNature.ASSESSMENT.value,
            TaskNature.STRATEGY.value,
        }
    ) or any(token in case.task_description for token in ("专项", "咨询", "建议"))
    full_design_depth = bool(
        depths
        & {
            ServiceDepth.CONCEPT_DESIGN,
            ServiceDepth.SCHEMATIC_SUPPORT,
        }
    )
    if consulting_signal and (
        TaskNature.NEW_BUILD.value in natures
        or full_design_depth
        or any("完整建筑设计" in item.title and item.selected for item in plan.deliverables)
    ):
        flags.append("consulting_as_full_design")
        notes.append("专项/咨询信号下出现新建性质、方案深度或完整设计类已选成果")

    max_q = int(expectations.get("max_clarifying_questions") or 5)
    if len(generation.clarifying_questions) > max_q:
        flags.append("low_value_questions")
        notes.append(
            f"澄清问题 {len(generation.clarifying_questions)} 个，超过建议上限 {max_q}"
        )
    elif len(generation.clarifying_questions) >= 4 and not any(
        q.blocking for q in generation.clarifying_questions
    ):
        flags.append("low_value_questions")
        notes.append("多个澄清问题且无一标记为 blocking，需人工判断价值")

    # Template smell: project_type echoed as sole nature / generic template titles.
    project_type = case.project_type.value
    if natures == {project_type} or any(
        token in " ".join(ws.title for ws in workstreams)
        for token in ("美丽乡村模板", "标准方案模板", "固定模板")
    ):
        flags.append("project_type_template")
        notes.append("工作路径或任务性质疑似被项目类型模板牵引")

    # Scope overreach: in_scope mentions excluded topics from task/out_of_scope.
    out_tokens = list(expectations.get("out_of_scope_contains_any") or [])
    in_scope_text = " ".join(mission.in_scope)
    for token in out_tokens:
        if token in in_scope_text:
            flags.append("scope_overreach")
            notes.append(f"in_scope 含本应排除内容：{token}")

    min_stakeholders = expectations.get("stakeholder_min_count")
    if min_stakeholders is not None and len(mission.stakeholders) < int(min_stakeholders):
        flags.append("missing_stakeholders")
        notes.append(
            f"利益相关方仅 {len(mission.stakeholders)} 个，期望至少 {min_stakeholders}"
        )
    elif mission.decisions_required and not mission.stakeholders:
        flags.append("missing_stakeholders")
        notes.append("已列决策但无利益相关方")

    if validation.get("errors"):
        notes.append("MissionValidation errors: " + "; ".join(validation["errors"]))
    if validation.get("warnings"):
        notes.extend("MissionValidation: " + w for w in validation["warnings"][:5])
    if bridge_error:
        notes.append(f"Presentation bridge: {bridge_error}")

    # Deduplicate flags while preserving order.
    flags = list(dict.fromkeys(flags))
    return flags, notes


def _prefill_observation_hints(scorecard: MissionScorecard, flags: list[str]) -> None:
    flag_set = set(flags)
    for item in scorecard.observations:
        if item.check_id in flag_set:
            item.observed = True
            item.notes = "自动标记：请人工确认是否属实"


def write_live_case_artifacts(
    result: MissionLiveEvalResult,
    *,
    settings: Settings,
) -> Path:
    assert result.scorecard is not None
    out_dir = live_artifacts_root() / result.scorecard.run_id / result.case.id
    out_dir.mkdir(parents=True, exist_ok=True)

    mission = result.generation.mission
    payload = {
        "case_id": result.case.id,
        "case_name": result.case.name,
        "task_description": result.case.task_description,
        "model": settings.llm_model,
        "provider": settings.llm_provider,
        "run_id": result.scorecard.run_id,
        "auto_flags": result.auto_flags,
        "auto_notes": result.auto_notes,
        "mission": mission.model_dump(mode="json"),
        "knowledge_gaps": [g.model_dump(mode="json") for g in result.generation.knowledge_gaps],
        "clarifying_questions": [
            q.model_dump(mode="json") for q in result.generation.clarifying_questions
        ],
        "assumptions": [a.model_dump(mode="json") for a in result.generation.assumptions],
        "workstreams": [w.model_dump(mode="json") for w in result.workstreams],
        "deliverable_plan": result.plan.model_dump(mode="json"),
        "execution_plans": [
            {
                "deliverable_id": p.deliverable_id,
                "deliverable_type": p.deliverable_type.value,
                "supported": p.supported,
                "message": p.message,
            }
            for p in result.execution_plans
        ],
        "presentation_request": (
            result.bridge.request.model_dump(mode="json") if result.bridge else None
        ),
        "validation": result.validation,
    }
    (out_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "scorecard.json").write_text(
        json.dumps(result.scorecard.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "SCORECARD.md").write_text(
        render_scorecard_markdown(result.scorecard),
        encoding="utf-8",
    )
    return out_dir


def render_scorecard_markdown(scorecard: MissionScorecard) -> str:
    from tests.golden.live.mission_rubric import (
        MISSION_LIVE_RUBRIC,
        OBSERVATION_CHECKS,
        TOTAL_MAX_SCORE,
    )

    scorecard.ensure_scaffold()
    lines = [
        f"# Mission Live Scorecard — {scorecard.case_name}",
        "",
        f"- Case: `{scorecard.case_id}`",
        f"- Model: `{scorecard.model}`",
        f"- Run: `{scorecard.run_id}`",
        f"- Reviewer: {scorecard.reviewer or '_（填写）_'}",
        "",
        "## 自动观察标记",
        "",
    ]
    if scorecard.auto_flags:
        for flag in scorecard.auto_flags:
            lines.append(f"- `{flag}`")
    else:
        lines.append("- （无自动标记）")
    if scorecard.auto_notes:
        lines.extend(["", "### 自动备注", ""])
        for note in scorecard.auto_notes:
            lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## 人工评分（满分 100）",
            "",
            "| 指标 | 满分 | 得分 | 备注 |",
            "|------|------|------|------|",
        ]
    )
    for criterion in MISSION_LIVE_RUBRIC:
        scored = next(
            (c for c in scorecard.criteria if c.criterion_id == criterion.id),
            None,
        )
        score = "" if scored is None or scored.score is None else str(scored.score)
        notes = "" if scored is None else scored.notes
        lines.append(
            f"| {criterion.label} | {criterion.max_score} | {score} | {notes} |"
        )
    total = scorecard.total_score if scorecard.total_score is not None else ""
    lines.append(
        f"| **合计** | **{TOTAL_MAX_SCORE}** | **{total}** | 及格线 {scorecard.pass_threshold} |"
    )

    lines.extend(["", "## 特别观察（人工勾选）", ""])
    labels = dict(OBSERVATION_CHECKS)
    for item in scorecard.observations:
        mark = "☐"
        if item.observed is True:
            mark = "☑"
        elif item.observed is False:
            mark = "☒"
        lines.append(f"- {mark} {labels.get(item.check_id, item.check_id)} {item.notes}")

    lines.extend(
        [
            "",
            "## 评审说明",
            "",
            scorecard.review_notes or "_（填写主要返工点与是否可用于内部继续编辑）_",
            "",
        ]
    )
    return "\n".join(lines)


def write_run_summary(run_dir: Path, results: list[MissionLiveEvalResult]) -> Path:
    lines = [
        f"# Mission Live Evaluation Summary — `{run_dir.name}`",
        "",
        "| Case | 自动标记 | Critical | Scorecard |",
        "|------|----------|----------|-----------|",
    ]
    for result in results:
        flags = ", ".join(result.auto_flags) if result.auto_flags else "—"
        critical = "YES" if result.has_critical_flags else "no"
        scorecard_path = (
            result.artifact_dir / "SCORECARD.md" if result.artifact_dir else Path(".")
        )
        rel = scorecard_path.relative_to(run_dir) if result.artifact_dir else "—"
        lines.append(
            f"| {result.case.id} ({result.case.name}) | {flags} | {critical} | `{rel}` |"
        )
    lines.extend(
        [
            "",
            "填写各 case 的 `scorecard.json` / `SCORECARD.md` 后，合计 ≥70 视为该 case 通过人工门槛。",
            "",
            "Critical 标记（`fabricated_metrics` / `consulting_as_full_design`）出现时，即使总分及格也应优先复盘。",
            "",
        ]
    )
    path = run_dir / "SUMMARY.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
