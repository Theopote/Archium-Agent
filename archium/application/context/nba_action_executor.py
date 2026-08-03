"""Execute NextBestAction with real services — not only page navigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.context.knowledge_reassess import best_effort_reassess_knowledge
from archium.application.context.next_action_selector import resolve_action_target
from archium.application.context.types import ActionDispatch
from archium.config.settings import Settings, get_settings
from archium.domain.intent.next_best_action import NextBestActionType
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger

logger = get_logger(__name__, operation="nba_action_executor")


@dataclass
class NbaExecutionResult:
    """Outcome of one-click NBA execution (may still require navigation)."""

    action: NextBestActionType
    executed: bool
    success: bool
    message: str = ""
    page_key: str | None = None
    mission_step: int | None = None
    focus: str | None = None
    warnings: list[str] = field(default_factory=list)
    reassessed: bool = False
    orchestration_action: str = "none"
    stage_hint: str | None = None
    stay_after_execute: bool = False
    """When True, UI should refresh NBA in place (Act→Learn→Reassess) instead of leaving."""

    @property
    def should_navigate(self) -> bool:
        if self.stay_after_execute and self.success and self.executed:
            return False
        return bool(self.page_key)


class NbaActionExecutor:
    """Run durable work for NBA types that can execute without further UI forms.

    Navigate-only actions (upload materials, open mission, ask-without-pending)
    return ``executed=False`` with a page target. Side effects always best-effort
    reassess KnowledgeState when work succeeded.
    """

    def __init__(
        self,
        session: SessionLike,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()

    def execute(
        self,
        project_id: UUID,
        action: NextBestActionType,
        *,
        user_task_description: str = "",
        pending_fact_count: int = 0,
        conflict_fact_count: int = 0,
    ) -> NbaExecutionResult:
        target = resolve_action_target(
            action,
            pending_fact_count=pending_fact_count,
            conflict_fact_count=conflict_fact_count,
        )
        if action == NextBestActionType.RESEARCH:
            return self._execute_research(project_id, target)
        if action == NextBestActionType.EXPLORE_DIRECTIONS:
            return self._execute_explore(
                project_id,
                target,
                user_task_description=user_task_description,
            )
        if action == NextBestActionType.GENERATE_MISSION:
            return self._execute_generate_mission(
                project_id,
                target,
                user_task_description=user_task_description,
            )
        if action == NextBestActionType.ASK:
            return self._execute_ask(project_id, target, pending_fact_count, conflict_fact_count)
        # UPLOAD_MATERIALS / OPEN_MISSION — navigate (+ optional orchestration)
        return self._navigate_only(action, target, message=f"请在界面完成：{target.label or action.value}")

    def _navigate_only(
        self,
        action: NextBestActionType,
        target: ActionDispatch,
        *,
        message: str,
        executed: bool = False,
        success: bool = True,
        warnings: list[str] | None = None,
        reassessed: bool = False,
    ) -> NbaExecutionResult:
        return NbaExecutionResult(
            action=action,
            executed=executed,
            success=success,
            message=message,
            page_key=target.page_key,
            mission_step=target.mission_step,
            focus=target.focus,
            warnings=list(warnings or []),
            reassessed=reassessed,
            orchestration_action=target.orchestration_action,
            stage_hint=target.stage_hint,
        )

    def _reassess(self, project_id: UUID, reason: str) -> bool:
        return (
            best_effort_reassess_knowledge(
                self._session,
                project_id,
                llm=self._llm,
                settings=self._settings,
                reason=reason,
            )
            is not None
        )

    def _idea_text(self, project_id: UUID, user_task_description: str) -> str:
        from archium.infrastructure.database.repositories import ProjectRepository

        text = (user_task_description or "").strip()
        if text:
            return text
        project = ProjectRepository(self._session).get_by_id(project_id)
        if project is None:
            return ""
        return (project.description or project.name or "").strip()

    def _execute_research(
        self,
        project_id: UUID,
        target: ActionDispatch,
    ) -> NbaExecutionResult:
        from archium.application.context.context_analyzer import ContextAnalyzer

        ok, message = ContextAnalyzer(
            self._session, self._llm, settings=self._settings
        ).try_execute_research(project_id)
        if not ok:
            return self._navigate_only(
                NextBestActionType.RESEARCH,
                target,
                message=message,
                executed=True,
                success=False,
                warnings=[message],
            )
        # Stay so UI can show refreshed KnowledgeState / new NBA (Learn→Reassess).
        # Skip orchestration kickoff here — research already ran; avoid double Act.
        return NbaExecutionResult(
            action=NextBestActionType.RESEARCH,
            executed=True,
            success=True,
            message=message,
            page_key=target.page_key,
            mission_step=target.mission_step or 2,
            orchestration_action="none",
            stage_hint=target.stage_hint,
            reassessed=True,
            stay_after_execute=True,
        )

    def _execute_explore(
        self,
        project_id: UUID,
        target: ActionDispatch,
        *,
        user_task_description: str,
    ) -> NbaExecutionResult:
        from archium.application.exploration_service import ExplorationService

        idea = self._idea_text(project_id, user_task_description)
        if not idea:
            return self._navigate_only(
                NextBestActionType.EXPLORE_DIRECTIONS,
                target,
                message="缺少想法描述，请先填写项目描述再推演方向。",
                executed=False,
                success=False,
                warnings=["缺少想法描述"],
            )

        service = ExplorationService(self._session, self._llm, settings=self._settings)
        warnings: list[str] = []
        try:
            latest = service.get_latest_for_project(project_id)
            from archium.domain.enums import ExplorationSessionStatus

            if latest is None or latest.status == ExplorationSessionStatus.COMMITTED:
                started = service.start_session(
                    project_id, idea, source="nba_execute", enrich=True
                )
                exploration = started.exploration
                warnings.extend(started.warnings)
            else:
                exploration = latest

            existing = service.list_directions(exploration.id)
            if not existing:
                generated = service.generate_directions(exploration.id, count=3)
                warnings.extend(generated.warnings)
                direction_count = len(generated.directions)
            else:
                direction_count = len(existing)

            reassessed = self._reassess(project_id, "nba_explore")
            return NbaExecutionResult(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                executed=True,
                success=True,
                message=f"已准备概念探索：{direction_count} 个方向可审阅。",
                page_key=target.page_key,
                warnings=warnings,
                reassessed=reassessed,
                orchestration_action="none",
                stage_hint=target.stage_hint,
                stay_after_execute=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("NBA explore execute failed: %s", exc)
            return self._navigate_only(
                NextBestActionType.EXPLORE_DIRECTIONS,
                target,
                message=f"自动推演未完成：{exc}。已打开概念探索页供手动继续。",
                executed=True,
                success=False,
                warnings=[str(exc)],
            )

    def _execute_generate_mission(
        self,
        project_id: UUID,
        target: ActionDispatch,
        *,
        user_task_description: str,
    ) -> NbaExecutionResult:
        from archium.application.project_mission_service import ProjectMissionService
        from archium.infrastructure.database.mission_repositories import MissionRepository

        missions = MissionRepository(self._session).list_missions_by_project(project_id)
        if missions:
            return self._navigate_only(
                NextBestActionType.GENERATE_MISSION,
                target,
                message="项目已有任务理解，已打开任务页。",
                executed=False,
                success=True,
            )

        idea = self._idea_text(project_id, user_task_description)
        if not idea:
            return self._navigate_only(
                NextBestActionType.GENERATE_MISSION,
                target,
                message="缺少任务描述，请先填写后再生成 Mission。",
                executed=False,
                success=False,
                warnings=["缺少任务描述"],
            )

        try:
            result = ProjectMissionService(
                self._session, self._llm, settings=self._settings
            ).generate_mission(project_id, idea)
            self._session.commit()
            reassessed = self._reassess(project_id, "nba_generate_mission")
            title = result.mission.title if result.mission else "任务"
            refresh = (
                "知识状态已刷新，下一步行动已更新。"
                if reassessed
                else "任务已写入；可稍后刷新知识状态。"
            )
            return NbaExecutionResult(
                action=NextBestActionType.GENERATE_MISSION,
                executed=True,
                success=True,
                message=f"已生成任务理解「{title}」。{refresh}",
                page_key=target.page_key,
                mission_step=target.mission_step or 1,
                warnings=list(result.warnings),
                reassessed=reassessed,
                orchestration_action="none",
                stage_hint=target.stage_hint,
                stay_after_execute=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("NBA generate mission failed: %s", exc)
            return self._navigate_only(
                NextBestActionType.GENERATE_MISSION,
                target,
                message=f"自动生成任务失败：{exc}。请在任务页手动分析。",
                executed=True,
                success=False,
                warnings=[str(exc)],
            )

    def _execute_ask(
        self,
        project_id: UUID,
        target: ActionDispatch,
        pending_fact_count: int,
        conflict_fact_count: int,
    ) -> NbaExecutionResult:
        """ASK cannot invent answers — focus pending facts or clarification UI."""
        _ = project_id
        if pending_fact_count > 0 or conflict_fact_count > 0:
            count = pending_fact_count + conflict_fact_count
            return self._navigate_only(
                NextBestActionType.ASK,
                target,
                message=f"请确认 {count} 条待核实/冲突事实（确认后会刷新知识状态）。",
                executed=False,
                success=True,
            )
        return self._navigate_only(
            NextBestActionType.ASK,
            target,
            message="请在任务页回答关键澄清问题。",
            executed=False,
            success=True,
        )


def nba_execute_label(
    action: NextBestActionType,
    *,
    has_pending_facts: bool = False,
    reason: str = "",
) -> str:
    """Verb-first labels for one-click buttons (Action, not soft recommendation)."""
    reason_l = (reason or "").strip()
    if action == NextBestActionType.RESEARCH:
        if any(token in reason_l for token in ("文化", "礼仪", "地域", "先例", "背景")):
            return "开始文化研究"
        return "开始研究"
    if action == NextBestActionType.EXPLORE_DIRECTIONS:
        return "开始推演方向"
    if action == NextBestActionType.GENERATE_MISSION:
        return "生成任务理解"
    if action == NextBestActionType.ASK:
        return "确认待核实事实" if has_pending_facts else "前往澄清问题"
    if action == NextBestActionType.UPLOAD_MATERIALS:
        return "前往上传资料"
    if action == NextBestActionType.OPEN_MISSION:
        return "打开项目任务"
    return action.value
