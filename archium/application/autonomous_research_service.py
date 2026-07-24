"""Autonomous research — synthesize public background from mission research topics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.research_schemas import AutonomousResearchDraft, ResearchFindingDraft
from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.infrastructure.research.web_search.service import WebResearchSearchService
from archium.prompts.autonomous_research import (
    AUTONOMOUS_RESEARCH_SYSTEM_PROMPT,
    build_autonomous_research_user_prompt,
)


@dataclass
class AutonomousResearchResult:
    project_id: UUID
    mission_id: UUID | None = None
    topics: list[str] = field(default_factory=list)
    items: list[ProjectKnowledgeItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    search_hit_count: int = 0
    search_provider: str | None = None


class AutonomousResearchService:
    """Synthesize PUBLIC_RESEARCH knowledge items from mission research topics."""

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
        topics = self._collect_topics(mission)
        if not topics:
            raise WorkflowError("当前任务没有待研究项，无法启动自主研究")
        design_context = self._design_context_text(mission)
        project = self._require_project(mission.project_id)
        return self._run_research(
            project,
            topics=topics,
            design_context=design_context,
            mission_id=mission.id,
        )

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
        return self._run_research(
            project,
            topics=cleaned,
            design_context=design_context,
            mission_id=None,
        )

    def _run_research(
        self,
        project: Project,
        *,
        topics: list[str],
        design_context: str,
        mission_id: UUID | None,
    ) -> AutonomousResearchResult:
        search_hits, search_provider = self._web_research.search_topics(topics)
        warnings: list[str] = []
        if self._web_research.enabled and not search_hits:
            if not self._web_research.configured:
                warnings.append("联网检索未配置或未返回结果，本次仅基于 LLM 归纳（无真实 URL 引用）")
            else:
                warnings.append("联网检索未返回可用结果，本次摘要可能缺少外部来源")

        draft = self._llm.generate_structured(
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
            ),
            AutonomousResearchDraft,
        )
        if not draft.findings:
            warnings.append("模型未返回研究结果，请稍后重试或缩小研究范围")

        search_index = {hit.url.strip().lower(): hit for hit in search_hits if hit.url.strip()}
        items: list[ProjectKnowledgeItem] = []
        for finding in draft.findings:
            items.append(self._persist_finding(project.id, finding, search_index))

        return AutonomousResearchResult(
            project_id=project.id,
            mission_id=mission_id,
            topics=list(topics),
            items=items,
            warnings=warnings,
            search_hit_count=len(search_hits),
            search_provider=search_provider,
        )

    def _persist_finding(
        self,
        project_id: UUID,
        finding: ResearchFindingDraft,
        search_index: dict[str, WebSearchResult],
    ) -> ProjectKnowledgeItem:
        statement_parts = [finding.summary.strip()]
        if finding.key_points:
            statement_parts.append(
                "要点：\n" + "\n".join(f"- {point.strip()}" for point in finding.key_points if point.strip())
            )
        if finding.relevance.strip():
            statement_parts.append(f"项目关联：{finding.relevance.strip()}")
        statement = "\n\n".join(part for part in statement_parts if part)

        citations = self._build_citations(finding, search_index)

        return self._knowledge.create_item(
            project_id,
            statement=statement,
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.UNVERIFIED,
            source_citations=citations,
            requires_user_confirmation=True,
            category="research",
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
    def _collect_topics(mission: ProjectMission) -> list[str]:
        topics: list[str] = []
        seen: set[str] = set()
        if mission.design_intent is not None:
            for item in mission.design_intent.research_needed:
                key = item.strip()
                if key and key not in seen:
                    seen.add(key)
                    topics.append(key)
        for item in mission.research_questions:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                topics.append(key)
        return topics

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
