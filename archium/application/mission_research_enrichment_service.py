"""Write confirmed public research summaries back into ProjectMission."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application._helpers import to_json
from archium.application.mission_history_service import MissionHistoryService
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.application.project_mission_service import (
    MissionPatch,
    ProjectMissionService,
    is_mission_approval_current,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.user_preference_repository import UserPreferenceRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.mission_enrichment_schemas import (
    MissionResearchEnrichmentDraft,
    MissionResearchRevisionDraft,
)
from archium.infrastructure.llm.mock import MockLLMProvider
from archium.prompts.mission_research_enrichment import (
    MISSION_RESEARCH_ENRICHMENT_SYSTEM_PROMPT,
    MISSION_RESEARCH_REVISION_SYSTEM_PROMPT,
    build_mission_research_enrichment_prompt,
    build_mission_research_revision_prompt,
    format_confirmed_research_block,
)

_MISSION_ENRICHMENT_KEY = "archium.mission_research_enrichment"
_RESEARCH_SECTION_HEADER = "【已确认公开研究】"


@dataclass
class MissionResearchEnrichmentResult:
    mission: ProjectMission
    items_enriched: int = 0
    used_llm: bool = False
    warnings: list[str] = field(default_factory=list)
    needs_reapproval: bool = False
    mission_revised: bool = False


class MissionResearchEnrichmentService:
    """Merge confirmed autonomous research items into mission context."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider | None = None,
        *,
        settings: Settings | None = None,
        mission_service: ProjectMissionService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._knowledge = ProjectKnowledgeService(session)
        self._preferences = UserPreferenceRepository(session)
        self._history = MissionHistoryService(session)
        self._mission_service = mission_service or ProjectMissionService(
            session,
            llm or MockLLMProvider(),
            settings=self._settings,
        )

    def list_pending_items(self, mission_id: UUID) -> list[ProjectKnowledgeItem]:
        mission = self._require_mission(mission_id)
        enriched_ids = self.get_enriched_item_ids(mission_id)
        return [
            item
            for item in self._confirmed_research_items(mission.project_id)
            if str(item.id) not in enriched_ids
        ]

    def list_written_back_items(self, mission_id: UUID) -> list[ProjectKnowledgeItem]:
        mission = self._require_mission(mission_id)
        enriched_ids = self.get_enriched_item_ids(mission_id)
        return [
            item
            for item in self._confirmed_research_items(mission.project_id)
            if str(item.id) in enriched_ids
        ]

    def get_enriched_item_ids(self, mission_id: UUID) -> set[str]:
        return self._enriched_item_ids(mission_id)

    def enrich_mission(
        self,
        mission_id: UUID,
        *,
        item_ids: list[UUID] | None = None,
        prefer_llm: bool = True,
    ) -> MissionResearchEnrichmentResult:
        mission = self._require_mission(mission_id)
        pending = self._select_items(mission, item_ids)
        if not pending:
            raise WorkflowError("没有可写回的已确认公开研究")

        was_approved = is_mission_approval_current(mission)
        warnings: list[str] = []
        used_llm = False
        if prefer_llm and self._llm is not None and self._settings.llm_configured:
            try:
                mission = self._enrich_with_llm(mission, pending)
                used_llm = True
            except Exception as exc:
                warnings.append(f"AI 整合失败，已改用追加模式：{exc}")
                mission = self._append_research_block(mission, pending)
        else:
            mission = self._append_research_block(mission, pending)

        self._mark_enriched(mission_id, [item.id for item in pending])
        self._history.record_snapshot(
            mission,
            RevisionSource.CLARIFICATION,
            note=f"公开研究写回（{len(pending)} 条）",
        )
        needs_reapproval = was_approved
        return MissionResearchEnrichmentResult(
            mission=mission,
            items_enriched=len(pending),
            used_llm=used_llm,
            warnings=warnings,
            needs_reapproval=needs_reapproval,
        )

    def revise_mission_from_written_research(self, mission_id: UUID) -> MissionResearchEnrichmentResult:
        """Lightweight LLM revision of task_statement / open questions after research write-back."""
        if self._llm is None or not self._settings.llm_configured:
            raise WorkflowError("配置 LLM 后可使用 AI 修订任务理解")

        mission = self._require_mission(mission_id)
        written_back = self.list_written_back_items(mission_id)
        if not written_back:
            raise WorkflowError("尚无已写回 Mission 的公开研究，请先写回任务理解")

        was_approved = is_mission_approval_current(mission)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=MISSION_RESEARCH_REVISION_SYSTEM_PROMPT,
                user_prompt=build_mission_research_revision_prompt(
                    current_mission_json=to_json(mission),
                    written_research_block=format_confirmed_research_block(written_back),
                ),
                temperature=0.25,
                json_mode=True,
            ),
            MissionResearchRevisionDraft,
        )
        patch = MissionPatch(
            task_statement=draft.task_statement.strip()
            if draft.task_statement and draft.task_statement.strip()
            else None,
            key_unknowns=draft.key_unknowns or None,
            research_questions=draft.research_questions or None,
        )
        if not patch.model_dump(exclude_none=True):
            raise WorkflowError("AI 未建议任何任务理解修订")

        mission = self._mission_service.update_mission(mission.id, patch)
        self._history.record_snapshot(
            mission,
            RevisionSource.CLARIFICATION,
            note="公开研究写回后的轻量任务修订",
        )
        return MissionResearchEnrichmentResult(
            mission=mission,
            used_llm=True,
            mission_revised=True,
            needs_reapproval=was_approved,
        )

    def _enrich_with_llm(
        self,
        mission: ProjectMission,
        items: list[ProjectKnowledgeItem],
    ) -> ProjectMission:
        if self._llm is None:
            raise WorkflowError("LLM 未配置")
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=MISSION_RESEARCH_ENRICHMENT_SYSTEM_PROMPT,
                user_prompt=build_mission_research_enrichment_prompt(
                    current_mission_json=to_json(mission),
                    confirmed_research_block=format_confirmed_research_block(items),
                ),
                temperature=0.25,
                json_mode=True,
            ),
            MissionResearchEnrichmentDraft,
        )
        patch = MissionPatch(
            project_context=draft.project_context.strip(),
            current_situation=draft.current_situation.strip()
            if draft.current_situation and draft.current_situation.strip()
            else None,
            key_unknowns=draft.key_unknowns or None,
        )
        return self._mission_service.update_mission(mission.id, patch)

    def _append_research_block(
        self,
        mission: ProjectMission,
        items: list[ProjectKnowledgeItem],
    ) -> ProjectMission:
        block = self._format_append_block(items)
        existing = mission.project_context.strip()
        if _RESEARCH_SECTION_HEADER in existing:
            merged = f"{existing.rstrip()}\n\n{block}"
        elif existing:
            merged = f"{existing}\n\n{block}"
        else:
            merged = block
        return self._mission_service.update_mission(
            mission.id,
            MissionPatch(project_context=merged),
        )

    @staticmethod
    def _format_append_block(items: list[ProjectKnowledgeItem]) -> str:
        lines = [_RESEARCH_SECTION_HEADER]
        for item in items:
            summary = item.statement.strip().split("\n\n")[0]
            lines.append(f"- {summary}")
            if item.source_citations:
                citation = item.source_citations[0]
                if citation.url:
                    title = citation.source_title or citation.url
                    lines.append(f"  来源：{title}")
        return "\n".join(lines)

    def _select_items(
        self,
        mission: ProjectMission,
        item_ids: list[UUID] | None,
    ) -> list[ProjectKnowledgeItem]:
        pending = self.list_pending_items(mission.id)
        if item_ids is None:
            return pending
        allowed = {str(item_id) for item_id in item_ids}
        selected = [item for item in pending if str(item.id) in allowed]
        if not selected:
            raise WorkflowError("所选研究条目不可写回（可能尚未确认或已写回）")
        return selected

    def _confirmed_research_items(self, project_id: UUID) -> list[ProjectKnowledgeItem]:
        return self._knowledge.list_confirmed_research_items(project_id)

    def _enriched_item_ids(self, mission_id: UUID) -> set[str]:
        pref = self._preferences.get_global(_MISSION_ENRICHMENT_KEY)
        if pref is None or not isinstance(pref.value, dict):
            return set()
        raw = pref.value.get(str(mission_id), [])
        if not isinstance(raw, list):
            return set()
        return {str(item_id) for item_id in raw}

    def _mark_enriched(self, mission_id: UUID, item_ids: list[UUID]) -> None:
        pref = self._preferences.get_global(_MISSION_ENRICHMENT_KEY)
        payload: dict[str, list[str]] = {}
        if pref is not None and isinstance(pref.value, dict):
            payload = {
                str(key): [str(item) for item in value]
                for key, value in pref.value.items()
                if isinstance(value, list)
            }
        existing = set(payload.get(str(mission_id), []))
        existing.update(str(item_id) for item_id in item_ids)
        payload[str(mission_id)] = sorted(existing)
        self._preferences.upsert_global(
            _MISSION_ENRICHMENT_KEY,
            payload,
            description="Mission IDs enriched with confirmed public research knowledge items",
        )

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        return mission
