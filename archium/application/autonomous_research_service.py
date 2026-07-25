"""Autonomous research — bounded loop: topic → search → write → light reassess."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.design_knowledge_mapping import design_knowledge_from_finding
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.application.research_topics import (
    collect_mission_research_questions,
    collect_mission_research_topic_candidates,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.intent.research_run import (
    ResearchRun,
    ResearchRunStopReason,
    ResearchStep,
    ResearchStepStatus,
)
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.call import generate_structured as llm_generate_structured
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.research_schemas import AutonomousResearchDraft, ResearchFindingDraft
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService
from archium.logging import get_logger
from archium.prompts.autonomous_research import (
    AUTONOMOUS_RESEARCH_SYSTEM_PROMPT,
    PROMPT_VERSION as RESEARCH_PROMPT_VERSION,
    build_autonomous_research_user_prompt,
)

logger = get_logger(__name__, operation="autonomous_research")


@dataclass
class AutonomousResearchResult:
    project_id: UUID
    mission_id: UUID | None = None
    topics: list[str] = field(default_factory=list)
    questions: list = field(default_factory=list)
    items: list[ProjectKnowledgeItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    search_hit_count: int = 0
    search_provider: str | None = None
    run: ResearchRun | None = None
    critique: object | None = None


class AutonomousResearchService:
    """Synthesize PUBLIC_RESEARCH knowledge via a bounded Research loop.

    Not an Agent class: Service owns Goal (fill design-impact gaps) /
    Context (topics + KS) / Strategy (stop conditions) / Action (search+write).
    """

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        web_research: WebResearchSearchService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._web_research = web_research or WebResearchSearchService(self._settings)
        self._projects = ProjectRepository(session)
        self._missions = MissionRepository(session)
        self._knowledge = ProjectKnowledgeService(session)

    def research_for_mission(self, mission_id: UUID) -> AutonomousResearchResult:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        project = self._require_project(mission.project_id)
        candidates = collect_mission_research_topic_candidates(
            mission,
            knowledge_state=project.knowledge_state,
        )
        topics = [c.text for c in candidates]
        questions = [
            c.question
            for c in candidates
            if c.question is not None
        ] or collect_mission_research_questions(
            mission,
            knowledge_state=project.knowledge_state,
        )
        if not topics:
            raise WorkflowError("当前任务没有待研究项，无法启动自主研究")
        design_context = self._design_context_text(mission)
        if questions:
            q_block = "\n".join(q.to_prompt_line() for q in questions[:6])
            design_context = (
                f"{design_context}\n\n【研究问题 ResearchQuestions】\n{q_block}"
            ).strip()
            from archium.application.architecture_case_library import (
                ArchitectureCaseLibraryService,
            )

            library = ArchitectureCaseLibraryService()
            case_block = library.format_prompt_block(
                library.search_for_questions(list(questions), limit=2)
            )
            if case_block.strip():
                design_context = f"{design_context}\n\n{case_block}".strip()
        result = self._run_bounded(
            project,
            topics=topics,
            design_context=design_context,
            mission_id=mission.id,
        )
        result.questions = list(questions)
        return result

    def research_topics(
        self,
        project_id: UUID,
        topics: list[str],
        *,
        design_context: str = "",
    ) -> AutonomousResearchResult:
        cleaned = [topic.strip() for topic in topics if topic.strip()]
        if not cleaned:
            raise WorkflowError("请至少提供一个研究主题")
        project = self._require_project(project_id)
        return self._run_bounded(
            project,
            topics=cleaned,
            design_context=design_context,
            mission_id=None,
        )

    def _run_bounded(
        self,
        project: Project,
        *,
        topics: list[str],
        design_context: str,
        mission_id: UUID | None,
    ) -> AutonomousResearchResult:
        loop_enabled = bool(self._settings.autonomous_research_loop_enabled)
        max_steps = max(1, int(self._settings.autonomous_research_max_steps))
        topics_per_step = max(1, int(self._settings.autonomous_research_topics_per_step))
        stop_need = float(self._settings.autonomous_research_stop_research_need)

        need_before = self._current_research_need(project)
        run = ResearchRun(
            project_id=project.id,
            mission_id=mission_id,
            planned_topics=list(topics),
            research_need_before=need_before,
            max_steps=max_steps if loop_enabled else 1,
            loop_enabled=loop_enabled,
        )

        if not loop_enabled:
            batch_result = self._synthesize_batch(
                project,
                topics=topics,
                design_context=design_context,
            )
            run.steps.append(
                ResearchStep(
                    index=0,
                    topics=list(topics),
                    status=(
                        ResearchStepStatus.OK
                        if batch_result.items
                        else ResearchStepStatus.EMPTY
                    ),
                    finding_count=len(batch_result.items),
                    search_hit_count=batch_result.search_hit_count,
                    research_need_before=need_before,
                    research_need_after=need_before,
                    knowledge_item_ids=[item.id for item in batch_result.items],
                    warning="; ".join(batch_result.warnings),
                )
            )
            run.completed_topics = list(topics)
            run.stop_reason = ResearchRunStopReason.BATCH
            run.research_need_after = need_before
            run.touch_completed()
            batch_result.run = run
            batch_result.mission_id = mission_id
            return self._attach_research_critique(
                batch_result,
                design_context=design_context,
            )

        queue = list(topics)
        all_items: list[ProjectKnowledgeItem] = []
        warnings: list[str] = []
        total_hits = 0
        provider: str | None = None
        stop_reason = ResearchRunStopReason.TOPICS_EXHAUSTED

        if not queue:
            run.stop_reason = ResearchRunStopReason.NO_TOPICS
            run.research_need_after = need_before
            run.touch_completed()
            return AutonomousResearchResult(
                project_id=project.id,
                mission_id=mission_id,
                topics=[],
                warnings=["没有可执行的研究主题"],
                run=run,
            )

        step_index = 0
        while queue and step_index < max_steps:
            batch = queue[:topics_per_step]
            queue = queue[topics_per_step:]
            need_step_before = self._current_research_need(project)

            logger.info(
                "research loop step=%s topics=%s need=%.2f",
                step_index,
                batch,
                need_step_before if need_step_before is not None else -1.0,
            )

            try:
                step_result = self._synthesize_batch(
                    project,
                    topics=batch,
                    design_context=design_context,
                )
            except Exception as exc:  # noqa: BLE001 — one step must not kill the run
                logger.exception("research step failed: %s", exc)
                run.steps.append(
                    ResearchStep(
                        index=step_index,
                        topics=list(batch),
                        status=ResearchStepStatus.FAILED,
                        research_need_before=need_step_before,
                        warning=str(exc),
                    )
                )
                warnings.append(f"步骤 {step_index + 1} 失败：{exc}")
                stop_reason = ResearchRunStopReason.EMPTY_FINDINGS
                break

            provider = step_result.search_provider or provider
            total_hits += step_result.search_hit_count
            all_items.extend(step_result.items)
            warnings.extend(step_result.warnings)
            run.completed_topics.extend(batch)

            need_step_after = self._light_reassess_research_need(
                project,
                items_written=len(step_result.items),
                previous_need=need_step_before,
            )

            status = (
                ResearchStepStatus.OK
                if step_result.items
                else ResearchStepStatus.EMPTY
            )
            run.steps.append(
                ResearchStep(
                    index=step_index,
                    topics=list(batch),
                    status=status,
                    finding_count=len(step_result.items),
                    search_hit_count=step_result.search_hit_count,
                    research_need_before=need_step_before,
                    research_need_after=need_step_after,
                    knowledge_item_ids=[item.id for item in step_result.items],
                    warning="; ".join(step_result.warnings),
                )
            )

            if not step_result.items:
                stop_reason = ResearchRunStopReason.EMPTY_FINDINGS
                break

            if need_step_after is not None and need_step_after <= stop_need:
                stop_reason = ResearchRunStopReason.RESEARCH_NEED_MET
                break

            step_index += 1
        else:
            if queue:
                stop_reason = ResearchRunStopReason.MAX_STEPS
            else:
                stop_reason = ResearchRunStopReason.TOPICS_EXHAUSTED

        need_after = self._current_research_need(project)
        if need_after is None and run.steps:
            need_after = run.steps[-1].research_need_after

        run.stop_reason = stop_reason
        run.research_need_after = need_after
        run.touch_completed()

        return self._attach_research_critique(
            AutonomousResearchResult(
                project_id=project.id,
                mission_id=mission_id,
                topics=list(run.completed_topics),
                items=all_items,
                warnings=warnings,
                search_hit_count=total_hits,
                search_provider=provider,
                run=run,
            ),
            design_context=design_context,
        )

    def _attach_research_critique(
        self,
        result: AutonomousResearchResult,
        *,
        design_context: str,
    ) -> AutonomousResearchResult:
        from archium.application.review.research_critique_service import (
            ResearchCritiqueService,
        )
        from archium.domain.research_critique import ResearchCritiqueVerdict

        mode = (self._settings.research_critique_mode or "warn").strip().lower()
        if mode == "off":
            return result
        try:
            report = ResearchCritiqueService(
                self._session,
                self._llm,
                settings=self._settings,
            ).critique_items(
                result.items,
                project_id=result.project_id,
                mission_id=result.mission_id,
                design_context=design_context,
                use_llm=bool(self._settings.research_critique_llm),
            )
        except Exception as exc:  # noqa: BLE001 — critique must not fail research
            logger.warning("research critique failed: %s", exc)
            return result

        result.critique = report
        for line in report.display_warnings()[:6]:
            if line and line not in result.warnings:
                result.warnings.append(line)
        if mode == "block" and report.verdict == ResearchCritiqueVerdict.WEAK:
            result.warnings.insert(
                0,
                "研究批判阻断提示：validity/design_relevance 偏低，请人工确认后再用于概念固化。",
            )
        return result

    def _synthesize_batch(
        self,
        project: Project,
        *,
        topics: list[str],
        design_context: str,
    ) -> AutonomousResearchResult:
        search_hits, search_provider = self._web_research.search_topics(topics)
        warnings: list[str] = []
        if self._web_research.enabled and not search_hits:
            if not self._web_research.configured:
                warnings.append(
                    "联网检索未配置或未返回结果，本次仅基于 LLM 归纳（无真实 URL 引用）"
                )
            else:
                warnings.append("联网检索未返回可用结果，本次摘要可能缺少外部来源")

        draft = llm_generate_structured(
            self._llm,
            LLMRequest(
                system_prompt=AUTONOMOUS_RESEARCH_SYSTEM_PROMPT,
                user_prompt=build_autonomous_research_user_prompt(
                    project_name=project.name,
                    design_context=design_context,
                    research_topics=topics,
                    web_search_results=search_hits,
                ),
                temperature=0.35,
                json_mode=True,
                metadata={"prompt_version": RESEARCH_PROMPT_VERSION},
            ),
            AutonomousResearchDraft,
            capability=LLMCapability.RESEARCH_SYNTHESIS,
            project_id=project.id,
            session=self._session,
            settings=self._settings,
        )
        if not draft.findings:
            warnings.append("模型未返回研究结果，请稍后重试或缩小研究范围")

        search_index = {
            hit.url.strip().lower(): hit for hit in search_hits if hit.url.strip()
        }
        items: list[ProjectKnowledgeItem] = []
        for finding in draft.findings:
            items.append(self._persist_finding(project.id, finding, search_index))

        return AutonomousResearchResult(
            project_id=project.id,
            topics=list(topics),
            items=items,
            warnings=warnings,
            search_hit_count=len(search_hits),
            search_provider=search_provider,
        )

    def _light_reassess_research_need(
        self,
        project: Project,
        *,
        items_written: int,
        previous_need: float | None,
    ) -> float | None:
        """Cheap Learn step: claim-index refresh + heuristic need decay.

        Full LLM reassess stays with NBA / ContextAnalyzer after the run.
        """
        from archium.application.context.knowledge_reassess import (
            ReassessMode,
            best_effort_reassess_knowledge,
        )

        assessment = best_effort_reassess_knowledge(
            self._session,
            project.id,
            llm=self._llm,
            settings=self._settings,
            reason="research_step",
            mode=ReassessMode.INDEX,
        )
        # Refresh local project snapshot for subsequent need reads
        refreshed = self._projects.get_by_id(project.id)
        if refreshed is not None:
            project.knowledge_state = refreshed.knowledge_state

        if assessment is not None and assessment.knowledge_state is not None:
            return float(
                assessment.knowledge_state.effective_dimensions().research_need
            )

        if previous_need is None:
            return None
        # Each written finding modestly reduces estimated research need.
        return max(0.0, float(previous_need) - 0.12 * max(0, items_written))

    def _current_research_need(self, project: Project) -> float | None:
        state = project.knowledge_state
        if state is None:
            refreshed = self._projects.get_by_id(project.id)
            state = refreshed.knowledge_state if refreshed is not None else None
        if state is None:
            return None
        return float(state.effective_dimensions().research_need)

    def _persist_finding(
        self,
        project_id: UUID,
        finding: ResearchFindingDraft,
        search_index: dict[str, WebSearchResult],
    ) -> ProjectKnowledgeItem:
        knowledge = design_knowledge_from_finding(finding)
        statement_parts: list[str] = []
        if knowledge.has_substance:
            statement_parts.extend(knowledge.to_statement_sections())
        else:
            statement_parts.append(finding.summary.strip())
            if finding.key_points:
                statement_parts.append(
                    "要点：\n"
                    + "\n".join(
                        f"- {point.strip()}"
                        for point in finding.key_points
                        if point.strip()
                    )
                )
            if finding.relevance.strip():
                statement_parts.append(f"项目关联：{finding.relevance.strip()}")
        statement = "\n\n".join(part for part in statement_parts if part)
        if not statement.strip():
            statement = finding.summary.strip() or finding.topic.strip()

        citations = self._build_citations(finding, search_index)

        return self._knowledge.create_item(
            project_id,
            statement=statement,
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.UNVERIFIED,
            source_citations=citations,
            requires_user_confirmation=True,
            category="research",
            design_knowledge=knowledge if knowledge.has_substance else None,
        )

    def _build_citations(
        self,
        finding: ResearchFindingDraft,
        search_index: dict[str, WebSearchResult],
    ) -> list[SourceCitation]:
        now = datetime.now(UTC)
        citations: list[SourceCitation] = []
        seen_urls: set[str] = set()

        for source in finding.suggested_sources:
            url = (source.url or "").strip()
            if not url:
                continue
            indexed = search_index.get(url.lower())
            if indexed is None:
                continue
            key = indexed.url.lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            citations.append(
                SourceCitation(
                    url=indexed.url,
                    source_title=indexed.title,
                    quote=(source.note or indexed.snippet or indexed.title).strip(),
                    accessed_at=now,
                )
            )

        if citations or not search_index:
            return citations

        for hit in search_index.values():
            key = hit.url.lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            citations.append(
                SourceCitation(
                    url=hit.url,
                    source_title=hit.title,
                    quote=(hit.snippet or hit.title).strip(),
                    accessed_at=now,
                )
            )
            if len(citations) >= 2:
                break
        return citations

    @staticmethod
    def _design_context_text(mission: ProjectMission) -> str:
        parts = [mission.task_statement.strip()]
        if mission.design_intent is not None:
            block = mission.design_intent.to_prompt_block()
            if block.strip():
                parts.append(block)
        if mission.project_context.strip():
            parts.append(mission.project_context.strip())
        return "\n\n".join(part for part in parts if part)

    def _require_project(self, project_id: UUID) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"项目 {project_id} 不存在")
        return project
