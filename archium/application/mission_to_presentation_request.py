"""Adapt approved ProjectMission + deliverable plan into PresentationRequest."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from uuid import UUID

from archium.application.presentation_models import PresentationRequest
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import DeliverableType, PresentationType, ServiceDepth, TaskNature
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError


@dataclass(frozen=True)
class PresentationOverrides:
    """Optional user edits applied after mission → request mapping."""

    title: str | None = None
    audience: str | None = None
    purpose: str | None = None
    duration_minutes: int | None = None
    target_slide_count: int | None = None
    core_message: str | None = None
    presentation_type: PresentationType | None = None
    decisions_required: list[str] | None = None
    audience_concerns: list[str] | None = None
    required_sections: list[str] | None = None
    excluded_topics: list[str] | None = None
    tone: str | None = None
    language: str | None = None
    user_notes: str | None = None


@dataclass(frozen=True)
class MissionPresentationBridge:
    """PresentationRequest plus lineage back to planning artifacts."""

    request: PresentationRequest
    mission_id: UUID
    deliverable_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_draft(self) -> dict:
        """Serialize for WorkflowRun / planning state persistence."""
        req = self.request
        return {
            "title": req.title,
            "audience": req.audience,
            "purpose": req.purpose,
            "duration_minutes": req.duration_minutes,
            "target_slide_count": req.target_slide_count,
            "core_message": req.core_message,
            "presentation_type": req.presentation_type.value,
            "decisions_required": list(req.decisions_required),
            "audience_concerns": list(req.audience_concerns),
            "required_sections": list(req.required_sections),
            "excluded_topics": list(req.excluded_topics),
            "tone": req.tone,
            "language": req.language,
            "user_notes": req.user_notes,
            "mission_id": str(self.mission_id),
            "deliverable_id": self.deliverable_id,
            "warnings": list(self.warnings),
        }


def build_presentation_request(
    mission: ProjectMission,
    deliverable: PlannedDeliverable | None = None,
    *,
    workstreams: list[Workstream] | None = None,
    user_overrides: PresentationOverrides | None = None,
) -> PresentationRequest:
    """Map mission (+ optional presentation deliverable) to PresentationRequest.

    Selected workstreams inform generation context via ``user_notes`` only.
    They are never copied wholesale into ``required_sections`` as chapter titles;
    Storyline still decides final chapters from the Brief.
    """
    if deliverable is not None and deliverable.deliverable_type != DeliverableType.PRESENTATION:
        raise WorkflowError(
            f"成果「{deliverable.title}」类型为 {deliverable.deliverable_type.value}，"
            "不能构建 PresentationRequest。请使用 DeliverableExecutionRouter。"
        )
    primary = deliverable

    title = (primary.title if primary and primary.title.strip() else mission.title).strip()
    audience = _resolve_audience(mission, primary)
    purpose = mission.task_statement.strip()
    if mission.design_intent is not None and mission.design_intent.problem_statement.strip():
        purpose = mission.design_intent.problem_statement.strip()
    core_message = (
        mission.desired_changes[0].strip()
        if mission.desired_changes
        else (mission.decision_context.strip() or mission.title)
    )
    if mission.design_intent is not None:
        if mission.design_intent.desired_experience.strip():
            core_message = mission.design_intent.desired_experience.strip()
        elif mission.design_intent.theme.strip():
            core_message = mission.design_intent.theme.strip()
    decisions = list(mission.decisions_required)
    concerns = [
        concern
        for stakeholder in mission.stakeholders
        for concern in stakeholder.concerns
        if concern.strip()
    ]
    required_sections = _resolve_required_sections(mission, primary)
    excluded = list(mission.out_of_scope)
    user_notes = _build_user_notes(mission, workstreams or [], primary)
    presentation_type = infer_presentation_type(mission, primary)
    slide_count, duration = _infer_length(primary)

    request = PresentationRequest(
        title=title,
        audience=audience,
        purpose=purpose,
        duration_minutes=duration,
        target_slide_count=slide_count,
        core_message=core_message,
        presentation_type=presentation_type,
        decisions_required=decisions,
        audience_concerns=concerns,
        required_sections=required_sections,
        excluded_topics=excluded,
        tone="professional",
        language="zh-CN",
        user_notes=user_notes,
    )
    return apply_presentation_overrides(request, user_overrides)


def build_presentation_bridge(
    mission: ProjectMission,
    *,
    plan: DeliverablePlan | None = None,
    deliverable: PlannedDeliverable | None = None,
    deliverable_id: str | None = None,
    workstreams: list[Workstream] | None = None,
    user_overrides: PresentationOverrides | None = None,
) -> MissionPresentationBridge:
    """Build PresentationRequest only for PRESENTATION deliverables.

    Non-presentation deliverables must go through :class:`DeliverableExecutionRouter`.
    This function never silently converts REPORT/MEMO/etc. into a PPT request.
    """
    from archium.application.deliverable_execution import DeliverableExecutionRouter

    warnings: list[str] = []
    primary = deliverable
    if primary is None and plan is not None:
        execution = DeliverableExecutionRouter().require_presentation_plan(
            mission,
            plan,
            workstreams=workstreams,
            deliverable_id=deliverable_id,
            user_overrides=user_overrides,
        )
        assert execution.presentation_request is not None
        return MissionPresentationBridge(
            request=execution.presentation_request,
            mission_id=mission.id,
            deliverable_id=execution.deliverable_id,
            warnings=list(execution.warnings),
        )
    if primary is None:
        raise WorkflowError(
            "未指定 presentation 成果，无法构建 PresentationRequest。"
            "非汇报成果请使用 DeliverableExecutionRouter，禁止静默退化成 PPT。"
        )
    if primary.deliverable_type != DeliverableType.PRESENTATION:
        raise WorkflowError(
            f"成果「{primary.title}」类型为 {primary.deliverable_type.value}，"
            "不能转换为 PresentationRequest。"
        )
    if not primary.selected:
        raise WorkflowError(f"成果「{primary.title}」未选中，无法作为汇报来源")

    request = build_presentation_request(
        mission,
        primary,
        workstreams=workstreams,
        user_overrides=user_overrides,
    )
    return MissionPresentationBridge(
        request=request,
        mission_id=mission.id,
        deliverable_id=primary.id,
        warnings=warnings,
    )


def select_presentation_deliverable(
    plan: DeliverablePlan,
    *,
    deliverable_id: str | None = None,
) -> tuple[PlannedDeliverable | None, list[str]]:
    """Pick a selected PRESENTATION deliverable. Never falls back to other types."""
    warnings: list[str] = []
    if deliverable_id:
        for item in plan.deliverables:
            if item.id == deliverable_id:
                if not item.selected:
                    raise WorkflowError(f"成果「{item.title}」未选中，无法作为汇报来源")
                if item.deliverable_type != DeliverableType.PRESENTATION:
                    raise WorkflowError(
                        f"成果「{item.title}」不是 presentation 类型，"
                        "不能作为汇报来源（禁止静默退化成 PPT）"
                    )
                return item, warnings
        raise WorkflowError(f"成果 {deliverable_id} 不存在于交付计划中")

    presentations = [
        item
        for item in plan.selected_deliverables()
        if item.deliverable_type == DeliverableType.PRESENTATION
    ]
    if presentations:
        return presentations[0], warnings
    return None, warnings


def apply_presentation_overrides(
    request: PresentationRequest,
    overrides: PresentationOverrides | None,
) -> PresentationRequest:
    if overrides is None:
        return request
    updates: dict = {}
    for name in (
        "title",
        "audience",
        "purpose",
        "duration_minutes",
        "target_slide_count",
        "core_message",
        "presentation_type",
        "decisions_required",
        "audience_concerns",
        "required_sections",
        "excluded_topics",
        "tone",
        "language",
        "user_notes",
    ):
        value = getattr(overrides, name)
        if value is not None:
            updates[name] = value
    return replace(request, **updates) if updates else request


def infer_presentation_type(
    mission: ProjectMission,
    deliverable: PlannedDeliverable | None = None,
) -> PresentationType:
    if mission.design_intent is not None and (
        mission.design_intent.theme.strip() or mission.design_intent.problem_statement.strip()
    ):
        return PresentationType.CONCEPT

    title = ((deliverable.title if deliverable else "") + " " + mission.title).lower()
    depths = set(mission.requested_service_depths)
    natures = set(mission.task_natures)

    if "竞赛" in title or "competition" in title:
        return PresentationType.COMPETITION
    if "内部" in title or "internal" in title:
        return PresentationType.INTERNAL
    if any(
        depth
        in {
            ServiceDepth.CONCEPT_PLANNING,
            ServiceDepth.PRELIMINARY_RESEARCH,
            ServiceDepth.PRESENTATION_PRODUCTION,
        }
        for depth in depths
    ) or TaskNature.RESEARCH in natures:
        if "方案" in title or "schematic" in title:
            return PresentationType.SCHEMATIC
        return PresentationType.CONCEPT
    if "扩初" in title or "design_development" in title:
        return PresentationType.DESIGN_DEVELOPMENT
    if "方案" in title or "schematic" in title:
        return PresentationType.SCHEMATIC
    return PresentationType.CLIENT_REVIEW


def bridge_from_draft(draft: dict) -> MissionPresentationBridge:
    """Restore a bridge from planning-state draft dict."""
    presentation_type = draft.get("presentation_type", PresentationType.CLIENT_REVIEW.value)
    if isinstance(presentation_type, PresentationType):
        ptype = presentation_type
    else:
        ptype = PresentationType(str(presentation_type))
    request = PresentationRequest(
        title=str(draft.get("title") or "未命名汇报"),
        audience=str(draft.get("audience") or "甲方"),
        purpose=str(draft.get("purpose") or ""),
        duration_minutes=int(draft.get("duration_minutes") or 20),
        target_slide_count=int(draft.get("target_slide_count") or 20),
        core_message=str(draft.get("core_message") or ""),
        presentation_type=ptype,
        decisions_required=list(draft.get("decisions_required") or []),
        audience_concerns=list(draft.get("audience_concerns") or []),
        required_sections=list(draft.get("required_sections") or []),
        excluded_topics=list(draft.get("excluded_topics") or []),
        tone=str(draft.get("tone") or "professional"),
        language=str(draft.get("language") or "zh-CN"),
        user_notes=str(draft.get("user_notes") or ""),
    )
    mission_raw = draft.get("mission_id")
    if not mission_raw:
        raise WorkflowError("presentation draft 缺少 mission_id")
    return MissionPresentationBridge(
        request=request,
        mission_id=UUID(str(mission_raw)),
        deliverable_id=str(draft["deliverable_id"]) if draft.get("deliverable_id") else None,
        warnings=list(draft.get("warnings") or []),
    )


def _resolve_audience(
    mission: ProjectMission,
    deliverable: PlannedDeliverable | None,
) -> str:
    if deliverable is not None and deliverable.audience.strip():
        return deliverable.audience.strip()
    if mission.stakeholders:
        primary = mission.stakeholders[0]
        if primary.role.strip():
            return f"{primary.name}（{primary.role}）"
        return primary.name
    return "甲方"


def _resolve_required_sections(
    mission: ProjectMission,
    deliverable: PlannedDeliverable | None,
) -> list[str]:
    if deliverable is not None and deliverable.content_scope:
        return [item for item in deliverable.content_scope if item.strip()]
    return [item for item in mission.in_scope if item.strip()]


def _build_user_notes(
    mission: ProjectMission,
    workstreams: list[Workstream],
    deliverable: PlannedDeliverable | None,
) -> str:
    sections: list[str] = []

    if mission.design_intent is not None:
        block = mission.design_intent.to_prompt_block()
        if block.strip():
            sections.append("设计使命:\n" + block)

    if mission.project_context.strip():
        sections.append("项目语境:\n" + mission.project_context.strip())

    if mission.design_questions:
        sections.append(
            "设计命题:\n" + "\n".join(f"- {item}" for item in mission.design_questions if item.strip())
        )
    if mission.research_questions:
        sections.append(
            "研究问题:\n"
            + "\n".join(f"- {item}" for item in mission.research_questions if item.strip())
        )
    if mission.key_unknowns:
        sections.append(
            "关键未知:\n" + "\n".join(f"- {item}" for item in mission.key_unknowns if item.strip())
        )

    selected = [item for item in workstreams if item.selected]
    if selected:
        lines = []
        for item in selected:
            objective = item.objective.strip() if item.objective else ""
            line = f"- {item.title}"
            if objective:
                line += f"：{objective}"
            lines.append(line)
        sections.append(
            "相关工作路径（生成上下文，非汇报章节大纲）:\n" + "\n".join(lines)
        )

    if deliverable is not None and deliverable.purpose.strip():
        sections.append(f"成果目的: {deliverable.purpose.strip()}")
    if deliverable is not None and deliverable.notes and deliverable.notes.strip():
        sections.append(f"成果备注: {deliverable.notes.strip()}")
    if mission.decision_context.strip():
        sections.append(f"决策语境: {mission.decision_context.strip()}")

    return "\n\n".join(sections)


_LENGTH_RANGE = re.compile(
    r"(?P<low>\d+)\s*[-~～到至]\s*(?P<high>\d+)\s*(?P<unit>页|页数|分钟|min|mins)?",
    re.IGNORECASE,
)
_LENGTH_SINGLE = re.compile(
    r"(?P<value>\d+)\s*(?P<unit>页|页数|分钟|min|mins)",
    re.IGNORECASE,
)


def _infer_length(
    deliverable: PlannedDeliverable | None,
) -> tuple[int, int]:
    """Return (target_slide_count, duration_minutes)."""
    default_slides, default_duration = 20, 20
    if deliverable is None or not deliverable.expected_length:
        return default_slides, default_duration

    text = deliverable.expected_length.strip()
    match = _LENGTH_RANGE.search(text)
    if match:
        low = int(match.group("low"))
        high = int(match.group("high"))
        mid = max(1, (low + high) // 2)
        unit = (match.group("unit") or "页").lower()
        if "分" in unit or "min" in unit:
            return default_slides, mid
        return mid, max(default_duration, mid)
    single = _LENGTH_SINGLE.search(text)
    if single:
        value = int(single.group("value"))
        unit = single.group("unit").lower()
        if "分" in unit or "min" in unit:
            return default_slides, value
        return value, max(default_duration, value)
    return default_slides, default_duration
