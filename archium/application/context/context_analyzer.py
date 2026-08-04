"""Context analyzer — orchestrates assess, persist, reassess, and evolution."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.context.knowledge_assessor import KnowledgeAssessor
from archium.application.context.project_context_builder import build_project_context
from archium.application.context.project_context_composer import (
    compose_project_context,
    enrich_knowledge_state_counts,
    finalize_assessment_context,
)
from archium.application.context.types import ContextAssessment
from archium.application.context_evidence import gather_project_evidence
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.context.project_context import ProjectContext
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider


class ContextAnalyzer:
    """Judge what the project knows and what to do next (not content generation)."""

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
        self._projects = ProjectRepository(session)
        self._assessor = KnowledgeAssessor(llm)

    def assess_text(self, user_text: str, **kwargs: Any) -> ContextAssessment:
        return self._assessor.assess_text(user_text, **kwargs)

    def assess_and_persist(
        self,
        project_id: UUID,
        user_text: str,
        *,
        write_evolution: bool = True,
        history_reason: str = "initial_assess",
    ) -> ContextAssessment:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")
        evidence = gather_project_evidence(self._session, project_id)
        assessment = self._assessor.assess_text(
            user_text,
            project_name=project.name,
            evidence=evidence,
        )
        if evidence.has_evidence and assessment.knowledge_state.source == "initial":
            assessment.knowledge_state = assessment.knowledge_state.model_copy(
                update={"source": "materials_aware"}
            )
        assessment.knowledge_state = enrich_knowledge_state_counts(
            assessment.knowledge_state,
            evidence,
        )
        assessment.project_context = compose_project_context(
            assessment,
            evidence=evidence,
            user_text=user_text.strip(),
        )
        finalize_assessment_context(assessment)
        if assessment.project_context is not None:
            pc = assessment.project_context
            assessment.knowledge_state = assessment.knowledge_state.model_copy(
                update={
                    "lifecycle_stage": pc.lifecycle_stage.value,
                    "recommended_workflow": pc.recommended_workflow.value,
                    "primary_page_key": pc.primary_page_key,
                }
            )
        project.knowledge_state = assessment.knowledge_state
        project.knowledge_state_history = project.knowledge_state_history.append_from_state(
            assessment.knowledge_state,
            reason=history_reason,
            reason_detail=user_text.strip()[:200],
        )
        project.origin_mode = assessment.suggested_origin_mode
        if write_evolution:
            evo = project.intent_evolution or IntentEvolution()
            evo = evo.append(
                IntentEvolutionKind.SEED,
                summary=user_text.strip()[:300],
            )
            if assessment.understanding_summary.strip():
                evo = evo.append(
                    IntentEvolutionKind.AI_UNDERSTANDING,
                    summary=assessment.understanding_summary.strip()[:500],
                )
            project.intent_evolution = evo
        project.touch()
        self._projects.update(project)
        self._session.commit()
        return assessment

    def reassess(
        self,
        project_id: UUID,
        *,
        user_text: str | None = None,
        history_reason: str = "refresh",
    ) -> ContextAssessment:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")
        text = (user_text or project.description or project.name or "").strip()
        if not text:
            raise WorkflowError("缺少可用于重评估的项目描述")
        assessment = self.assess_and_persist(
            project_id,
            text,
            write_evolution=False,
            history_reason=history_reason or "refresh",
        )
        if assessment.understanding_summary.strip():
            self.append_evolution(
                project_id,
                IntentEvolutionKind.AI_UNDERSTANDING,
                f"[刷新] {assessment.understanding_summary.strip()[:480]}",
            )
        assessment.knowledge_state = assessment.knowledge_state.model_copy(
            update={"source": "refresh"}
        )
        project = self._projects.get_by_id(project_id)
        if project is not None:
            project.knowledge_state = assessment.knowledge_state
            project.touch()
            self._projects.update(project)
            self._session.commit()
        if assessment.project_context is None:
            evidence = gather_project_evidence(self._session, project_id)
            assessment.project_context = compose_project_context(
                assessment,
                evidence=evidence,
                user_text=text,
            )
        return assessment

    def project_context_for(self, project_id: UUID) -> ProjectContext | None:
        return build_project_context(self._session, project_id)

    def try_execute_research(
        self,
        project_id: UUID,
    ) -> tuple[bool, str]:
        """Act: run AutonomousResearch → write knowledge → reassess (Learn).

        Works with or without Mission. Pre-mission uses project/KS-derived topics.
        """
        from archium.application.autonomous_research_service import AutonomousResearchService
        from archium.application.context.knowledge_reassess import (
            best_effort_reassess_knowledge,
        )
        from archium.application.research_topics import (
            collect_mission_research_topics,
            collect_project_research_topics,
        )
        from archium.infrastructure.database.mission_repositories import MissionRepository

        project = self._projects.get_by_id(project_id)
        if project is None:
            return False, f"Project {project_id} not found"

        missions = MissionRepository(self._session).list_missions_by_project(project_id)
        research = AutonomousResearchService(
            self._session,
            self._llm,
            settings=self._settings,
        )
        try:
            if missions:
                mission = missions[0]
                topics = collect_mission_research_topics(mission)
                if topics:
                    result = research.research_for_mission(mission.id)
                else:
                    # Mission exists but empty research list — still allow project topics
                    fallback = collect_project_research_topics(
                        project_name=project.name or "",
                        project_description=project.description or "",
                        knowledge_state=project.knowledge_state,
                        project_id=project_id,
                    )
                    if not fallback:
                        return False, "当前任务没有待研究项，且无法从项目描述推导研究主题。"
                    result = research.research_topics(
                        project_id,
                        fallback,
                        design_context=mission.task_statement or mission.title or "",
                    )
            else:
                topics = collect_project_research_topics(
                    project_name=project.name or "",
                    project_description=project.description or "",
                    knowledge_state=project.knowledge_state,
                    project_id=project_id,
                )
                if not topics:
                    return (
                        False,
                        "尚无足够线索推导研究主题。请补充项目描述中的地点/类型，或先生成任务理解。",
                    )
                result = research.research_topics(
                    project_id,
                    topics,
                    design_context=(project.description or project.name or "").strip(),
                )
            self._session.commit()
        except WorkflowError as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001
            return False, f"自主研究未能完成：{exc}"

        self.append_evolution(
            project_id,
            IntentEvolutionKind.RESEARCH,
            f"自主研究生成 {len(result.items)} 条公开摘要",
            trigger="自主研究",
            reason=(
                f"补充{result.topics[0][:80]}"
                if getattr(result, "topics", None)
                else "补充公开背景研究"
            ),
            new_summary=f"公开研究摘要 ×{len(result.items)}",
            evidence_refs=[
                item.statement.strip()[:200]
                for item in result.items
                if getattr(item, "statement", None) and str(item.statement).strip()
            ][:8],
        )
        reassessed = (
            best_effort_reassess_knowledge(
                self._session,
                project_id,
                llm=self._llm,
                settings=self._settings,
                reason="nba_research",
            )
            is not None
        )
        provider = (
            f"（来源：{result.search_provider}）" if result.search_provider else ""
        )
        loop_note = ""
        if result.run is not None:
            loop_note = f" {result.run.summary_line()}。"
        refresh = "知识状态已刷新，下一步建议已更新。" if reassessed else "知识已写入；完整再评估稍后可刷新。"
        return (
            True,
            f"已生成 {len(result.items)} 条公开研究摘要{provider}。{loop_note}{refresh}",
        )

    def append_evolution(
        self,
        project_id: UUID,
        kind: IntentEvolutionKind,
        summary: str,
        *,
        design_intent_snapshot: dict[str, object] | None = None,
        trigger: str | None = None,
        previous_summary: str | None = None,
        new_summary: str | None = None,
        reason: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")
        evo = project.intent_evolution or IntentEvolution()
        project.intent_evolution = evo.append(
            kind,
            summary,
            design_intent_snapshot=design_intent_snapshot,
            trigger=trigger,
            previous_summary=previous_summary,
            new_summary=new_summary,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        project.touch()
        updated = self._projects.update(project)
        self._session.commit()
        return updated
