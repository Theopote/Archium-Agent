"""Design iteration — generate and select concept direction drafts under a Mission."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ConceptDirectionRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)
from archium.prompts.concept_direction import (
    CONCEPT_DIRECTION_SYSTEM_PROMPT,
    build_concept_direction_user_prompt,
)

MAX_DIRECTIONS = 3
MIN_DIRECTIONS = 2


@dataclass
class ConceptDirectionGenerationResult:
    mission_id: UUID
    directions: list[ConceptDirection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConceptDirectionSelectionResult:
    direction: ConceptDirection
    mission: ProjectMission
    directions: list[ConceptDirection] = field(default_factory=list)


class ConceptDirectionService:
    """Planning-side service for concept direction drafts (not vision rendering)."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        mission_service: ProjectMissionService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._directions = ConceptDirectionRepository(session)
        self._mission_service = mission_service or ProjectMissionService(
            session, llm, settings=self._settings
        )

    def list_directions(
        self,
        mission_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[ConceptDirection]:
        self._require_mission(mission_id)
        return self._directions.list_by_mission(
            mission_id, include_archived=include_archived
        )

    def generate_directions(
        self,
        mission_id: UUID,
        *,
        count: int = 3,
        replace_drafts: bool = True,
    ) -> ConceptDirectionGenerationResult:
        mission = self._require_mission(mission_id)
        target_count = max(MIN_DIRECTIONS, min(int(count), MAX_DIRECTIONS))
        warnings: list[str] = []

        if replace_drafts:
            for existing in self._directions.list_by_mission(mission_id):
                if existing.status == ConceptDirectionStatus.DRAFT:
                    existing.archive()
                    self._directions.update(existing)

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=CONCEPT_DIRECTION_SYSTEM_PROMPT,
                user_prompt=build_concept_direction_user_prompt(
                    mission_title=mission.title,
                    task_statement=mission.task_statement,
                    design_intent_block=(
                        mission.design_intent.to_prompt_block()
                        if mission.design_intent is not None
                        else ""
                    ),
                    project_context=mission.project_context,
                    count=target_count,
                ),
                temperature=0.5,
                json_mode=True,
            ),
            ConceptDirectionBatchDraft,
        )
        items = list(draft.directions)[:MAX_DIRECTIONS]
        if len(items) < MIN_DIRECTIONS:
            warnings.append(
                f"模型仅返回 {len(items)} 个方向，已尽量保存；建议再次推演。"
            )
        if not items:
            raise WorkflowError("未能生成概念方向草稿")

        created: list[ConceptDirection] = []
        for index, item in enumerate(items):
            created.append(self._persist_draft(mission, item, sort_order=index))
        self._session.commit()
        return ConceptDirectionGenerationResult(
            mission_id=mission.id,
            directions=created,
            warnings=warnings,
        )

    def select_direction(self, direction_id: UUID) -> ConceptDirectionSelectionResult:
        direction = self._directions.get(direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {direction_id} 不存在")
        if direction.status == ConceptDirectionStatus.ARCHIVED:
            raise WorkflowError("已归档的概念方向不能选为当前方向")

        mission = self._require_mission(direction.mission_id)
        siblings = self._directions.list_by_mission(direction.mission_id)
        for sibling in siblings:
            if sibling.id == direction.id:
                sibling.select()
            elif sibling.status == ConceptDirectionStatus.SELECTED:
                sibling.mark_draft()
            self._directions.update(sibling)

        updated_intent = self._intent_from_direction(mission, direction)
        mission = self._mission_service.update_mission(
            mission.id,
            MissionPatch(design_intent=updated_intent),
        )
        self._session.commit()

        refreshed = self._directions.get(direction_id)
        assert refreshed is not None
        return ConceptDirectionSelectionResult(
            direction=refreshed,
            mission=mission,
            directions=self._directions.list_by_mission(direction.mission_id),
        )

    def archive_direction(self, direction_id: UUID) -> ConceptDirection:
        direction = self._directions.get(direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {direction_id} 不存在")
        if direction.status == ConceptDirectionStatus.SELECTED:
            raise WorkflowError("请先选择其他方向，再归档当前选中方向")
        direction.archive()
        updated = self._directions.update(direction)
        self._session.commit()
        return updated

    def _persist_draft(
        self,
        mission: ProjectMission,
        draft: ConceptDirectionDraft,
        *,
        sort_order: int,
    ) -> ConceptDirection:
        direction = ConceptDirection(
            project_id=mission.project_id,
            mission_id=mission.id,
            title=draft.title.strip(),
            summary=draft.summary.strip(),
            theme=(draft.theme or "").strip(),
            spatial_idea=(draft.spatial_idea or "").strip(),
            experience_focus=(draft.experience_focus or "").strip(),
            differentiator=(draft.differentiator or "").strip(),
            open_questions=[item.strip() for item in draft.open_questions if item.strip()],
            risks=[item.strip() for item in draft.risks if item.strip()],
            status=ConceptDirectionStatus.DRAFT,
            sort_order=sort_order,
            source="generated",
        )
        return self._directions.create(direction)

    def _intent_from_direction(
        self,
        mission: ProjectMission,
        direction: ConceptDirection,
    ) -> DesignIntent:
        base = mission.design_intent or DesignIntent()
        return DesignIntent(
            theme=direction.theme or direction.title or base.theme,
            problem_statement=direction.summary or base.problem_statement,
            social_background=base.social_background,
            cultural_context=base.cultural_context,
            target_users=list(base.target_users),
            desired_experience=direction.experience_focus or base.desired_experience,
            core_questions=list(direction.open_questions) or list(base.core_questions),
            research_needed=list(base.research_needed),
            working_assumptions=list(base.working_assumptions),
        )

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        return mission
