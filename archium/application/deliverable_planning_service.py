"""Dynamic deliverable planning for project missions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import to_json
from archium.application.deliverable_parser import (
    parse_deliverable_plan_draft,
    validate_deliverable_plan_draft,
)
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.mission_history_service import DeliverablePlanHistoryService
from archium.application.project_mission_service import ensure_mission_approval_current
from archium.config.settings import Settings, get_settings
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import ApprovalStatus, DeliverableType, RevisionSource
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.deliverable_schemas import DeliverablePlanDraft
from archium.prompts.deliverable_plan import (
    DELIVERABLE_PLAN_SYSTEM_PROMPT,
    build_deliverable_plan_user_prompt,
)


@dataclass
class DeliverablePlanResult:
    mission: ProjectMission
    plan: DeliverablePlan
    workstreams: list[Workstream] = field(default_factory=list)
    planning_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def selected_deliverables(self) -> list[PlannedDeliverable]:
        return self.plan.selected_deliverables()

    @property
    def presentation_deliverables(self) -> list[PlannedDeliverable]:
        return [
            item
            for item in self.plan.deliverables
            if item.selected and item.deliverable_type == DeliverableType.PRESENTATION
        ]


class DeliverablePlanningService:
    """Generate and manage dynamic deliverable plans for a mission."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        clarification_service: MissionClarificationService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._history = DeliverablePlanHistoryService(session)
        self._clarification = clarification_service or MissionClarificationService(
            session, llm, settings=self._settings
        )

    def plan_deliverables(
        self,
        mission_id: UUID,
        *,
        selected_workstream_ids: list[UUID] | None = None,
        require_ready: bool = True,
    ) -> DeliverablePlanResult:
        mission = self._require_mission(mission_id)
        if require_ready:
            ensure_mission_approval_current(mission)
            self._clarification.ensure_can_continue(mission_id)

        workstreams = self._missions.list_workstreams(mission_id)
        if not workstreams:
            raise WorkflowError("请先完成工作路径规划，再规划成果")

        if selected_workstream_ids is not None:
            selected_set = set(selected_workstream_ids)
            planning_workstreams = [item for item in workstreams if item.id in selected_set]
            if not planning_workstreams:
                raise WorkflowError("未找到已选工作路径")
        else:
            planning_workstreams = [item for item in workstreams if item.selected] or workstreams

        previous_plans = self._missions.list_deliverable_plans(mission_id)
        previous = previous_plans[0] if previous_plans else None
        if previous is not None:
            self._history.archive_before_regeneration(previous)

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=DELIVERABLE_PLAN_SYSTEM_PROMPT,
                user_prompt=build_deliverable_plan_user_prompt(
                    mission_json=to_json(mission),
                    workstreams_summary=self._format_workstreams(planning_workstreams),
                    decisions_summary=self._format_list(mission.decisions_required),
                    audience_summary=self._format_audience(mission),
                    stage_summary=self._format_stage(mission),
                ),
                temperature=0.3,
                json_mode=True,
            ),
            DeliverablePlanDraft,
        )

        errors = validate_deliverable_plan_draft(draft)
        if errors:
            raise WorkflowError("; ".join(errors))

        parsed = parse_deliverable_plan_draft(
            draft,
            project_id=mission.project_id,
            mission_id=mission.id,
            workstreams=planning_workstreams,
            previous=previous,
        )
        saved = self._missions.save_deliverable_plan(parsed.plan)
        change_source = (
            RevisionSource.REGENERATION if previous is not None else RevisionSource.GENERATED
        )
        self._history.record_snapshot(saved, change_source)
        mission = self._sync_recommended_ids(mission, saved)
        return DeliverablePlanResult(
            mission=mission,
            plan=saved,
            workstreams=planning_workstreams,
            planning_notes=draft.planning_notes,
            warnings=parsed.warnings,
        )

    def get_plan(self, mission_id: UUID) -> DeliverablePlan | None:
        plans = self._missions.list_deliverable_plans(mission_id)
        return plans[0] if plans else None

    def get_plan_result(self, mission_id: UUID) -> DeliverablePlanResult:
        mission = self._require_mission(mission_id)
        plan = self.get_plan(mission_id)
        if plan is None:
            raise WorkflowError("尚未生成成果规划")
        return DeliverablePlanResult(
            mission=mission,
            plan=plan,
            workstreams=self._missions.list_workstreams(mission_id),
        )

    def set_deliverable_selection(
        self,
        plan_id: UUID,
        selected_ids: list[str],
    ) -> DeliverablePlan:
        plan = self._require_plan(plan_id)
        selected_set = set(selected_ids)
        changed = False
        for item in plan.deliverables:
            should_select = item.id in selected_set
            if item.selected == should_select:
                continue
            changed = True
            if should_select:
                item.select()
            else:
                item.deselect()
        if not changed:
            return plan
        self._invalidate_plan_approval_if_needed(plan)
        plan.touch()
        return self._missions.save_deliverable_plan(plan)

    def select_deliverable(self, plan_id: UUID, deliverable_id: str) -> DeliverablePlan:
        plan = self._require_plan(plan_id)
        target = self._find_deliverable(plan, deliverable_id)
        if target.selected:
            return plan
        target.select()
        self._invalidate_plan_approval_if_needed(plan)
        plan.touch()
        return self._missions.save_deliverable_plan(plan)

    def deselect_deliverable(self, plan_id: UUID, deliverable_id: str) -> DeliverablePlan:
        plan = self._require_plan(plan_id)
        target = self._find_deliverable(plan, deliverable_id)
        if target.required:
            raise WorkflowError(f"必要成果「{target.title}」不能取消选择")
        if not target.selected:
            return plan
        target.deselect()
        self._invalidate_plan_approval_if_needed(plan)
        plan.touch()
        return self._missions.save_deliverable_plan(plan)

    def approve_deliverable_plan(
        self,
        plan_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> DeliverablePlan:
        """Mark the deliverable plan approved (domain action only — does not resume workflow)."""
        plan = self._require_plan(plan_id)
        if not plan.selected_deliverables():
            raise WorkflowError("请至少选择一项成果后再批准")
        plan.approve()
        saved = self._missions.save_deliverable_plan(plan)
        history_note = note or "批准成果规划"
        if user_id:
            history_note = f"{history_note} · by {user_id}"
        self._history.record_snapshot(
            saved,
            RevisionSource.APPROVAL,
            note=history_note,
            actor=user_id,
        )
        return saved

    def approve_plan(
        self,
        plan_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> DeliverablePlan:
        """Alias for :meth:`approve_deliverable_plan`."""
        return self.approve_deliverable_plan(plan_id, user_id=user_id, note=note)

    def reject_plan(
        self,
        plan_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> DeliverablePlan:
        plan = self._require_plan(plan_id)
        plan.reject()
        saved = self._missions.save_deliverable_plan(plan)
        history_note = note or "驳回成果规划"
        if user_id:
            history_note = f"{history_note} · by {user_id}"
        self._history.record_snapshot(
            saved,
            RevisionSource.APPROVAL,
            note=history_note,
            actor=user_id,
        )
        return saved

    def _sync_recommended_ids(
        self,
        mission: ProjectMission,
        plan: DeliverablePlan,
    ) -> ProjectMission:
        ids = [item.id for item in plan.deliverables if item.required or item.selected]
        updated = mission.model_copy(update={"recommended_deliverable_ids": ids})
        updated.touch()
        return self._missions.save_mission(updated)

    def _format_workstreams(self, workstreams: list[Workstream]) -> str:
        lines = []
        for index, item in enumerate(workstreams):
            flag = "selected" if item.selected else "proposed"
            lines.append(
                f"[{index}] {item.title} ({item.workstream_type.value}) "
                f"| {flag} | objective={item.objective}"
            )
        return "\n".join(lines)

    def _format_list(self, values: list[str]) -> str:
        return "\n".join(f"- {item}" for item in values)

    def _format_audience(self, mission: ProjectMission) -> str:
        parts = [f"目的：{mission.task_statement}"]
        if mission.stakeholders:
            names = "、".join(f"{s.name}（{s.role}）" for s in mission.stakeholders)
            parts.append(f"利益相关方：{names}")
        if mission.desired_changes:
            parts.append("期望改变：" + "、".join(mission.desired_changes))
        return "\n".join(parts)

    def _format_stage(self, mission: ProjectMission) -> str:
        depths = "、".join(item.value for item in mission.requested_service_depths) or "未指定"
        natures = "、".join(item.value for item in mission.task_natures) or "未指定"
        return f"任务性质：{natures}\n服务深度：{depths}\n范围外：{'、'.join(mission.out_of_scope) or '无'}"

    def _find_deliverable(self, plan: DeliverablePlan, deliverable_id: str) -> PlannedDeliverable:
        for item in plan.deliverables:
            if item.id == deliverable_id:
                return item
        raise WorkflowError(f"成果 {deliverable_id} 不存在")

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        return mission

    def _require_plan(self, plan_id: UUID) -> DeliverablePlan:
        plan = self._missions.get_deliverable_plan(plan_id)
        if plan is None:
            raise WorkflowError(f"成果规划 {plan_id} 不存在")
        return plan

    @staticmethod
    def _invalidate_plan_approval_if_needed(plan: DeliverablePlan) -> None:
        if plan.approval_status == ApprovalStatus.APPROVED:
            plan.invalidate_approval()
