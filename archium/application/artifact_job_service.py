"""Persist and run non-presentation artifact generation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_executors import (
    ArtifactOutput,
    CaseStudyExecutor,
    ChecklistExecutor,
    MemoExecutor,
    QuestionListExecutor,
    ReportExecutor,
    WorkPlanExecutor,
    artifact_output_dir,
)
from archium.application.deliverable_execution import (
    DeliverableExecutionRouter,
    supports_auto_generation,
)
from archium.config.settings import Settings, get_settings
from archium.domain.artifact_job import ArtifactJob
from archium.domain.deliverable import PlannedDeliverable
from archium.domain.enums import ArtifactJobStatus, DeliverableType
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ArtifactJobRepository, FactRepository


@dataclass
class ArtifactJobRunResult:
    job: ArtifactJob
    output: ArtifactOutput | None = None


_KIND_BY_TYPE: dict[DeliverableType, str] = {
    DeliverableType.QUESTION_LIST: "question_list",
    DeliverableType.WORK_PLAN: "work_plan",
    DeliverableType.IMPLEMENTATION_ROADMAP: "work_plan",
    DeliverableType.REPORT: "report",
    DeliverableType.TECHNICAL_PROPOSAL: "report",
    DeliverableType.MEMO: "memo",
    DeliverableType.CHECKLIST: "checklist",
    DeliverableType.CASE_STUDY: "case_study",
}


class ArtifactJobService:
    """Create, run, and persist ArtifactJob rows for text deliverables."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._jobs = ArtifactJobRepository(session)
        self._missions = MissionRepository(session)
        self._router = DeliverableExecutionRouter()

    def list_jobs_for_mission(self, mission_id: UUID, *, limit: int = 50) -> list[ArtifactJob]:
        return self._jobs.list_by_mission(mission_id, limit=limit)

    def run_for_deliverable(
        self,
        mission_id: UUID,
        deliverable_id: str,
    ) -> ArtifactJobRunResult:
        mission = self._require_mission(mission_id)
        deliverable = self._require_deliverable(mission_id, deliverable_id)
        if deliverable.deliverable_type == DeliverableType.PRESENTATION:
            raise WorkflowError("汇报类成果请走 Presentation 主链，不创建 ArtifactJob")
        if not supports_auto_generation(deliverable.deliverable_type):
            raise WorkflowError(
                f"成果「{deliverable.title}」类型 {deliverable.deliverable_type.value} "
                "当前不支持自动生成"
            )

        plan = self._router.route(mission, deliverable)
        job = ArtifactJob(
            project_id=mission.project_id,
            mission_id=mission.id,
            deliverable_id=deliverable.id,
            deliverable_title=deliverable.title,
            deliverable_type=deliverable.deliverable_type,
            request_kind=plan.request_kind,
            status=ArtifactJobStatus.PLANNED,
            message=plan.message,
            warnings=list(plan.warnings),
            plan_json=plan.to_dict(),
        )
        job.mark_ready()
        job = self._jobs.create(job)
        self._session.commit()

        job.mark_running()
        job = self._jobs.update(job)
        self._session.commit()

        try:
            output = self._execute(mission, deliverable)
            job.mark_completed(
                title=output.title,
                payload=output.payload,
                markdown=output.markdown,
                json_path=str(output.json_path) if output.json_path else None,
                markdown_path=str(output.markdown_path) if output.markdown_path else None,
                docx_path=str(output.docx_path) if output.docx_path else None,
            )
            job = self._jobs.update(job)
            self._session.commit()
            return ArtifactJobRunResult(job=job, output=output)
        except Exception as exc:
            job.mark_failed(str(exc))
            job = self._jobs.update(job)
            self._session.commit()
            raise WorkflowError(f"成果生成失败：{exc}") from exc

    def _execute(
        self,
        mission: ProjectMission,
        deliverable: PlannedDeliverable,
    ) -> ArtifactOutput:
        kind = _KIND_BY_TYPE.get(deliverable.deliverable_type, "other")
        out_dir = artifact_output_dir(
            self._settings.output_path,
            mission_id=mission.id,
            kind=kind,
        )
        if kind == "question_list":
            return QuestionListExecutor().execute(
                mission,
                gaps=self._missions.list_knowledge_gaps(mission.id),
                questions=self._missions.list_clarifying_questions(mission.id),
                assumptions=self._missions.list_assumptions(mission.id),
                facts=FactRepository(self._session).list_by_project(mission.project_id),
                deliverable=deliverable,
                output_dir=out_dir,
            )
        if kind == "work_plan":
            plans = self._missions.list_deliverable_plans(mission.id)
            return WorkPlanExecutor().execute(
                mission,
                workstreams=self._missions.list_workstreams(mission.id),
                deliverable_plan=plans[0] if plans else None,
                deliverable=deliverable,
                output_dir=out_dir,
            )
        if kind == "report":
            return ReportExecutor().execute(
                mission, deliverable=deliverable, output_dir=out_dir
            )
        if kind == "memo":
            return MemoExecutor().execute(
                mission, deliverable=deliverable, output_dir=out_dir
            )
        if kind == "checklist":
            return ChecklistExecutor().execute(
                mission, deliverable=deliverable, output_dir=out_dir
            )
        if kind == "case_study":
            return CaseStudyExecutor().execute(
                mission, deliverable=deliverable, output_dir=out_dir
            )
        raise WorkflowError(f"未知成果类型：{deliverable.deliverable_type.value}")

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        return mission

    def _require_deliverable(
        self,
        mission_id: UUID,
        deliverable_id: str,
    ) -> PlannedDeliverable:
        plans = self._missions.list_deliverable_plans(mission_id)
        if not plans:
            raise WorkflowError("尚未生成成果计划")
        for item in plans[0].deliverables:
            if item.id == deliverable_id:
                return item
        raise WorkflowError(f"成果 {deliverable_id} 不存在于交付计划中")
