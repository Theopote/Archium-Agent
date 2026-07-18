"""Route planned deliverables to typed artifact execution plans.

Presentation, Question List, and Work Plan are auto-generatable today.
Other types receive typed request stubs and an explicit unsupported message —
never a silent PresentationRequest fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from archium.application.mission_to_presentation_request import (
    PresentationOverrides,
    build_presentation_request,
)
from archium.application.presentation_models import PresentationRequest
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import DeliverableType
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError

UNSUPPORTED_GENERATION_MESSAGE = "该成果已完成规划，但当前版本尚未支持自动生成。"
SUPPORTED_GENERATION_MESSAGE = "可生成本地 Markdown / JSON 成果。"

ArtifactRequestKind = Literal[
    "presentation",
    "report",
    "memo",
    "checklist",
    "question_list",
    "case_study",
    "work_plan",
    "other",
]


@dataclass(frozen=True)
class ReportRequest:
    title: str
    purpose: str
    audience: str
    content_scope: list[str] = field(default_factory=list)
    format: str = "markdown"
    expected_length: str = ""
    notes: str = ""


@dataclass(frozen=True)
class MemoRequest:
    title: str
    purpose: str
    audience: str
    content_scope: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class ChecklistRequest:
    title: str
    purpose: str
    audience: str
    items: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class QuestionListRequest:
    """Intent for QuestionListExecutor — items come from mission bundle at execute time."""

    title: str
    purpose: str
    audience: str
    notes: str = ""
    # Preview hints only; executor rebuilds from gaps/questions/assumptions/facts.
    preview_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaseStudyRequest:
    title: str
    purpose: str
    audience: str
    content_scope: list[str] = field(default_factory=list)
    expected_length: str = ""
    notes: str = ""


@dataclass(frozen=True)
class WorkPlanRequest:
    title: str
    purpose: str
    audience: str
    content_scope: list[str] = field(default_factory=list)
    expected_length: str = ""
    notes: str = ""


@dataclass
class ArtifactExecutionPlan:
    """Execution intent for one selected planned deliverable."""

    mission_id: UUID
    deliverable_id: str
    deliverable_title: str
    deliverable_type: DeliverableType
    request_kind: ArtifactRequestKind
    supported: bool
    message: str = ""
    presentation_request: PresentationRequest | None = None
    report_request: ReportRequest | None = None
    memo_request: MemoRequest | None = None
    checklist_request: ChecklistRequest | None = None
    question_list_request: QuestionListRequest | None = None
    case_study_request: CaseStudyRequest | None = None
    work_plan_request: WorkPlanRequest | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_presentation(self) -> bool:
        return self.deliverable_type == DeliverableType.PRESENTATION

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mission_id": str(self.mission_id),
            "deliverable_id": self.deliverable_id,
            "deliverable_title": self.deliverable_title,
            "deliverable_type": self.deliverable_type.value,
            "request_kind": self.request_kind,
            "supported": self.supported,
            "message": self.message,
            "warnings": list(self.warnings),
        }
        if self.presentation_request is not None:
            payload["presentation_request"] = {
                "title": self.presentation_request.title,
                "audience": self.presentation_request.audience,
                "purpose": self.presentation_request.purpose,
                "duration_minutes": self.presentation_request.duration_minutes,
                "target_slide_count": self.presentation_request.target_slide_count,
                "core_message": self.presentation_request.core_message,
                "presentation_type": self.presentation_request.presentation_type.value,
                "decisions_required": list(self.presentation_request.decisions_required),
                "audience_concerns": list(self.presentation_request.audience_concerns),
                "required_sections": list(self.presentation_request.required_sections),
                "excluded_topics": list(self.presentation_request.excluded_topics),
                "tone": self.presentation_request.tone,
                "language": self.presentation_request.language,
                "user_notes": self.presentation_request.user_notes,
            }
        if self.report_request is not None:
            payload["report_request"] = self.report_request.__dict__
        if self.memo_request is not None:
            payload["memo_request"] = self.memo_request.__dict__
        if self.checklist_request is not None:
            payload["checklist_request"] = self.checklist_request.__dict__
        if self.question_list_request is not None:
            payload["question_list_request"] = self.question_list_request.__dict__
        if self.case_study_request is not None:
            payload["case_study_request"] = self.case_study_request.__dict__
        if self.work_plan_request is not None:
            payload["work_plan_request"] = self.work_plan_request.__dict__
        return payload


_TYPE_TO_KIND: dict[DeliverableType, ArtifactRequestKind] = {
    DeliverableType.PRESENTATION: "presentation",
    DeliverableType.REPORT: "report",
    DeliverableType.MEMO: "memo",
    DeliverableType.CHECKLIST: "checklist",
    DeliverableType.QUESTION_LIST: "question_list",
    DeliverableType.CASE_STUDY: "case_study",
    DeliverableType.WORK_PLAN: "work_plan",
    DeliverableType.IMPLEMENTATION_ROADMAP: "work_plan",
    DeliverableType.TASK_BRIEF: "other",
    DeliverableType.DESIGN_BRIEF: "other",
    DeliverableType.TECHNICAL_PROPOSAL: "report",
    DeliverableType.RISK_REGISTER: "other",
    DeliverableType.OTHER: "other",
}

_SUPPORTED_KINDS = frozenset({"presentation", "question_list", "work_plan"})


def supports_auto_generation(deliverable_type: DeliverableType) -> bool:
    """Return True when this deliverable type can be auto-generated today."""
    kind = _TYPE_TO_KIND.get(deliverable_type, "other")
    return kind in _SUPPORTED_KINDS


class DeliverableExecutionRouter:
    """Map each planned deliverable to a typed execution plan."""

    def route(
        self,
        mission: ProjectMission,
        deliverable: PlannedDeliverable,
        *,
        workstreams: list[Workstream] | None = None,
        user_overrides: PresentationOverrides | None = None,
    ) -> ArtifactExecutionPlan:
        kind = _TYPE_TO_KIND.get(deliverable.deliverable_type, "other")
        if deliverable.deliverable_type == DeliverableType.PRESENTATION:
            request = build_presentation_request(
                mission,
                deliverable,
                workstreams=workstreams,
                user_overrides=user_overrides,
            )
            return ArtifactExecutionPlan(
                mission_id=mission.id,
                deliverable_id=deliverable.id,
                deliverable_title=deliverable.title,
                deliverable_type=deliverable.deliverable_type,
                request_kind="presentation",
                supported=True,
                presentation_request=request,
            )

        supported = supports_auto_generation(deliverable.deliverable_type)
        plan = ArtifactExecutionPlan(
            mission_id=mission.id,
            deliverable_id=deliverable.id,
            deliverable_title=deliverable.title,
            deliverable_type=deliverable.deliverable_type,
            request_kind=kind,
            supported=supported,
            message="" if supported else UNSUPPORTED_GENERATION_MESSAGE,
        )
        if supported:
            plan.message = SUPPORTED_GENERATION_MESSAGE

        if kind == "report":
            plan.report_request = _build_report_request(deliverable)
        elif kind == "memo":
            plan.memo_request = _build_memo_request(deliverable)
        elif kind == "checklist":
            plan.checklist_request = _build_checklist_request(deliverable)
        elif kind == "question_list":
            plan.question_list_request = _build_question_list_request(mission, deliverable)
        elif kind == "case_study":
            plan.case_study_request = _build_case_study_request(deliverable)
        elif kind == "work_plan":
            plan.work_plan_request = _build_work_plan_request(deliverable)
        return plan

    def route_plan(
        self,
        mission: ProjectMission,
        plan: DeliverablePlan,
        *,
        workstreams: list[Workstream] | None = None,
        user_overrides: PresentationOverrides | None = None,
        selected_only: bool = True,
    ) -> list[ArtifactExecutionPlan]:
        items = plan.selected_deliverables() if selected_only else list(plan.deliverables)
        return [
            self.route(
                mission,
                item,
                workstreams=workstreams,
                user_overrides=user_overrides,
            )
            for item in items
        ]

    def require_presentation_plan(
        self,
        mission: ProjectMission,
        plan: DeliverablePlan,
        *,
        workstreams: list[Workstream] | None = None,
        deliverable_id: str | None = None,
        user_overrides: PresentationOverrides | None = None,
    ) -> ArtifactExecutionPlan:
        """Return the PRESENTATION execution plan or raise — never fall back."""
        if deliverable_id is not None:
            for item in plan.deliverables:
                if item.id != deliverable_id:
                    continue
                if not item.selected:
                    raise WorkflowError(f"成果「{item.title}」未选中，无法作为汇报来源")
                if item.deliverable_type != DeliverableType.PRESENTATION:
                    raise WorkflowError(
                        f"成果「{item.title}」类型为 {item.deliverable_type.value}，"
                        "不能转换为 PresentationRequest。禁止将非汇报成果静默退化成 PPT。"
                    )
                return self.route(
                    mission,
                    item,
                    workstreams=workstreams,
                    user_overrides=user_overrides,
                )
            raise WorkflowError(f"成果 {deliverable_id} 不存在于交付计划中")

        presentations = [
            item
            for item in plan.selected_deliverables()
            if item.deliverable_type == DeliverableType.PRESENTATION
        ]
        if not presentations:
            selected = plan.selected_deliverables()
            if selected:
                titles = "、".join(f"{item.title}（{item.deliverable_type.value}）" for item in selected)
                raise WorkflowError(
                    "当前已选成果中没有「汇报 / Presentation」类型。"
                    f"已选：{titles}。"
                    "非汇报成果不会自动转换成 PresentationRequest。"
                )
            raise WorkflowError("未找到已选中的 presentation 成果，无法构建 PresentationRequest")

        return self.route(
            mission,
            presentations[0],
            workstreams=workstreams,
            user_overrides=user_overrides,
        )


def _build_report_request(deliverable: PlannedDeliverable) -> ReportRequest:
    return ReportRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        content_scope=list(deliverable.content_scope),
        format=deliverable.format or "markdown",
        expected_length=deliverable.expected_length or "",
        notes=deliverable.notes or "",
    )


def _build_memo_request(deliverable: PlannedDeliverable) -> MemoRequest:
    return MemoRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        content_scope=list(deliverable.content_scope),
        notes=deliverable.notes or "",
    )


def _build_checklist_request(deliverable: PlannedDeliverable) -> ChecklistRequest:
    return ChecklistRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        items=list(deliverable.content_scope),
        notes=deliverable.notes or "",
    )


def _build_question_list_request(
    mission: ProjectMission,
    deliverable: PlannedDeliverable,
) -> QuestionListRequest:
    hints = list(deliverable.content_scope)
    if not hints and mission.decisions_required:
        hints = list(mission.decisions_required[:5])
    return QuestionListRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        notes=deliverable.notes or "",
        preview_hints=hints,
    )


def _build_case_study_request(deliverable: PlannedDeliverable) -> CaseStudyRequest:
    return CaseStudyRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        content_scope=list(deliverable.content_scope),
        expected_length=deliverable.expected_length or "",
        notes=deliverable.notes or "",
    )


def _build_work_plan_request(deliverable: PlannedDeliverable) -> WorkPlanRequest:
    return WorkPlanRequest(
        title=deliverable.title,
        purpose=deliverable.purpose,
        audience=deliverable.audience,
        content_scope=list(deliverable.content_scope),
        expected_length=deliverable.expected_length or "",
        notes=deliverable.notes or "",
    )
