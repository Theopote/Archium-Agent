"""Pre-mission concept exploration — IdeaSeed → directions → commit Mission."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import (
    ConceptDirectionStatus,
    ExplorationSessionStatus,
    ProjectOriginMode,
)
from archium.domain.exploration_session import ExplorationSession
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.idea_seed import IdeaSeed
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ExplorationSessionRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)
from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
from archium.prompts.concept_direction import (
    CONCEPT_DIRECTION_SYSTEM_PROMPT,
    build_exploration_direction_user_prompt,
)
from archium.prompts.idea_seed import (
    IDEA_SEED_SYSTEM_PROMPT,
    build_idea_seed_user_prompt,
)

MAX_DIRECTIONS = 3
MIN_DIRECTIONS = 2


@dataclass
class ExplorationStartResult:
    exploration: ExplorationSession
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExplorationGenerationResult:
    exploration_id: UUID
    directions: list[ConceptDirection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExplorationSelectionResult:
    exploration: ExplorationSession
    direction: ConceptDirection
    directions: list[ConceptDirection] = field(default_factory=list)


@dataclass
class ExplorationCommitResult:
    exploration: ExplorationSession
    mission: ProjectMission
    direction: ConceptDirection


class ExplorationService:
    """Concept exploration before ProjectMission exists."""

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
        self._explorations = ExplorationSessionRepository(session)
        self._directions = ConceptDirectionRepository(session)
        self._projects = ProjectRepository(session)
        self._missions = MissionRepository(session)
        self._mission_service = mission_service or ProjectMissionService(
            session, llm, settings=self._settings
        )

    def start_session(
        self,
        project_id: UUID,
        idea_text: str,
        *,
        source: str = "genesis",
        enrich: bool = True,
    ) -> ExplorationStartResult:
        idea = idea_text.strip()
        if not idea:
            raise WorkflowError("想法不能为空")
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")

        warnings: list[str] = []
        if enrich:
            seed, enrich_warnings = self._enrich_from_raw(
                idea, project_name=project.name
            )
            warnings.extend(enrich_warnings)
        else:
            seed = IdeaSeed.from_raw(idea, source="user")

        exploration = ExplorationSession(
            project_id=project_id,
            idea_text=seed.raw_input,
            idea_seed=seed,
            status=ExplorationSessionStatus.EXPLORING,
            source=source,
        )
        created = self._explorations.create(exploration)
        self._session.commit()
        return ExplorationStartResult(exploration=created, warnings=warnings)

    def enrich_idea_seed(self, exploration_id: UUID) -> ExplorationStartResult:
        exploration = self._require_session(exploration_id)
        if exploration.status == ExplorationSessionStatus.COMMITTED:
            raise WorkflowError("已提交为 Mission 的探索不能再解读想法")
        project = self._projects.get_by_id(exploration.project_id)
        project_name = project.name if project is not None else ""
        seed, warnings = self._enrich_from_raw(
            exploration.idea_text, project_name=project_name
        )
        exploration.idea_seed = seed
        exploration.idea_text = seed.raw_input
        exploration.touch()
        updated = self._explorations.update(exploration)
        self._session.commit()
        return ExplorationStartResult(exploration=updated, warnings=warnings)

    def get_session(self, exploration_id: UUID) -> ExplorationSession | None:
        return self._explorations.get(exploration_id)

    def get_latest_for_project(self, project_id: UUID) -> ExplorationSession | None:
        return self._explorations.get_latest_for_project(project_id)

    def list_directions(
        self,
        exploration_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[ConceptDirection]:
        self._require_session(exploration_id)
        return self._directions.list_by_exploration(
            exploration_id, include_archived=include_archived
        )

    def generate_directions(
        self,
        exploration_id: UUID,
        *,
        count: int = 3,
        replace_drafts: bool = True,
    ) -> ExplorationGenerationResult:
        exploration = self._require_session(exploration_id)
        if exploration.status == ExplorationSessionStatus.COMMITTED:
            raise WorkflowError("已提交为 Mission 的探索不能再推演方向")
        project = self._projects.get_by_id(exploration.project_id)
        if project is None:
            raise WorkflowError(f"Project {exploration.project_id} not found")

        target_count = max(MIN_DIRECTIONS, min(int(count), MAX_DIRECTIONS))
        warnings: list[str] = []
        if replace_drafts:
            for existing in self._directions.list_by_exploration(exploration_id):
                if existing.status == ConceptDirectionStatus.DRAFT:
                    existing.archive()
                    self._directions.update(existing)

        seed = exploration.idea_seed or IdeaSeed.from_raw(exploration.idea_text)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=CONCEPT_DIRECTION_SYSTEM_PROMPT,
                user_prompt=build_exploration_direction_user_prompt(
                    project_name=project.name,
                    idea_text=seed.raw_input,
                    idea_seed_block=seed.to_prompt_block(),
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
            created.append(
                self._persist_draft(exploration, item, sort_order=index)
            )
        if exploration.status != ExplorationSessionStatus.EXPLORING:
            exploration.status = ExplorationSessionStatus.EXPLORING
            exploration.selected_direction_id = None
            self._explorations.update(exploration)
        self._session.commit()
        return ExplorationGenerationResult(
            exploration_id=exploration.id,
            directions=created,
            warnings=warnings,
        )

    def select_direction(self, direction_id: UUID) -> ExplorationSelectionResult:
        direction = self._directions.get(direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {direction_id} 不存在")
        if direction.exploration_session_id is None:
            raise WorkflowError("该方向不属于探索会话，请使用 Mission 下的方向选择")
        if direction.status == ConceptDirectionStatus.ARCHIVED:
            raise WorkflowError("已归档的概念方向不能选为当前方向")

        exploration = self._require_session(direction.exploration_session_id)
        if exploration.status == ExplorationSessionStatus.COMMITTED:
            raise WorkflowError("已提交的探索不能更换方向")

        siblings = self._directions.list_by_exploration(exploration.id)
        for sibling in siblings:
            if sibling.id == direction.id:
                sibling.select()
            elif sibling.status == ConceptDirectionStatus.SELECTED:
                sibling.mark_draft()
            self._directions.update(sibling)

        exploration.mark_direction_selected(direction.id)
        exploration = self._explorations.update(exploration)
        refreshed = self._directions.get(direction_id)
        assert refreshed is not None
        self._append_intent_evolution(
            exploration.project_id,
            IntentEvolutionKind.DIRECTION_SELECTED,
            f"选定概念方向：{refreshed.title}",
        )
        self._session.commit()

        return ExplorationSelectionResult(
            exploration=exploration,
            direction=refreshed,
            directions=self._directions.list_by_exploration(exploration.id),
        )

    def commit_to_mission(self, exploration_id: UUID) -> ExplorationCommitResult:
        exploration = self._require_session(exploration_id)
        if exploration.selected_direction_id is None:
            raise WorkflowError("请先选择一个概念方向，再生成 Mission")
        if exploration.status == ExplorationSessionStatus.COMMITTED:
            if exploration.mission_id is None:
                raise WorkflowError("探索已标记提交但缺少 mission_id")
            mission = self._missions.get_mission(exploration.mission_id)
            if mission is None:
                raise WorkflowError(f"Mission {exploration.mission_id} not found")
            direction = self._directions.get(exploration.selected_direction_id)
            if direction is None:
                raise WorkflowError("已选方向不存在")
            return ExplorationCommitResult(
                exploration=exploration,
                mission=mission,
                direction=direction,
            )

        direction = self._directions.get(exploration.selected_direction_id)
        if direction is None:
            raise WorkflowError("已选方向不存在")

        task_text = self._task_description_from_seed(exploration, direction)
        generated = self._mission_service.generate_mission(
            exploration.project_id,
            task_text,
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
        intent = self._intent_from_direction(direction, base=generated.mission.design_intent)
        mission = self._mission_service.update_mission(
            generated.mission.id,
            MissionPatch(design_intent=intent),
        )

        for sibling in self._directions.list_by_exploration(exploration.id):
            sibling.mission_id = mission.id
            self._directions.update(sibling)

        exploration.mark_committed(mission.id)
        exploration = self._explorations.update(exploration)
        self._append_intent_evolution(
            exploration.project_id,
            IntentEvolutionKind.MISSION_COMMIT,
            f"提交为 Mission：{mission.title}",
            design_intent_snapshot=(
                mission.design_intent.model_dump(mode="json")
                if mission.design_intent is not None
                else None
            ),
        )
        self._session.commit()

        refreshed = self._directions.get(direction.id)
        assert refreshed is not None
        return ExplorationCommitResult(
            exploration=exploration,
            mission=mission,
            direction=refreshed,
        )

    def _enrich_from_raw(
        self,
        raw_input: str,
        *,
        project_name: str = "",
    ) -> tuple[IdeaSeed, list[str]]:
        warnings: list[str] = []
        try:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=IDEA_SEED_SYSTEM_PROMPT,
                    user_prompt=build_idea_seed_user_prompt(
                        raw_input=raw_input,
                        project_name=project_name,
                    ),
                    temperature=0.4,
                    json_mode=True,
                ),
                IdeaSeedDraft,
            )
            level = (draft.imagination_level or "open").strip().lower()
            if level not in {"open", "grounded", "speculative"}:
                level = "open"
            seed = IdeaSeed(
                raw_input=raw_input.strip(),
                theme=(draft.theme or "").strip(),
                inspiration=(draft.inspiration or "").strip(),
                keywords=[item.strip() for item in draft.keywords if item.strip()][:8],
                imagination_level=level,
                source="user",
            )
            if not seed.is_enriched:
                warnings.append("想法解读结果较空，可稍后重新解读。")
            return seed, warnings
        except Exception as exc:  # noqa: BLE001 — degrade without blocking session
            warnings.append(f"想法解读未完成，已仅保存原文：{exc}")
            return IdeaSeed.from_raw(raw_input, source="user"), warnings

    def _append_intent_evolution(
        self,
        project_id: UUID,
        kind: IntentEvolutionKind,
        summary: str,
        *,
        design_intent_snapshot: dict[str, object] | None = None,
    ) -> None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            return
        evo = project.intent_evolution or IntentEvolution()
        project.intent_evolution = evo.append(
            kind,
            summary,
            design_intent_snapshot=design_intent_snapshot,
        )
        project.touch()
        self._projects.update(project)

    def _persist_draft(
        self,
        exploration: ExplorationSession,
        draft: ConceptDirectionDraft,
        *,
        sort_order: int,
    ) -> ConceptDirection:
        direction = ConceptDirection(
            project_id=exploration.project_id,
            exploration_session_id=exploration.id,
            mission_id=None,
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

    @staticmethod
    def _task_description_from_seed(
        exploration: ExplorationSession,
        direction: ConceptDirection,
    ) -> str:
        seed = exploration.idea_seed
        parts = [
            f"初始想法：{seed.raw_input if seed else exploration.idea_text}",
            f"选定概念方向：{direction.title}",
        ]
        if seed is not None and seed.to_prompt_block().strip():
            parts.append("想法种子：\n" + seed.to_prompt_block())
        if direction.summary.strip():
            parts.append(f"方向摘要：{direction.summary.strip()}")
        if direction.theme.strip():
            parts.append(f"主题：{direction.theme.strip()}")
        if direction.spatial_idea.strip():
            parts.append(f"空间想法：{direction.spatial_idea.strip()}")
        if direction.experience_focus.strip():
            parts.append(f"体验焦点：{direction.experience_focus.strip()}")
        return "\n".join(parts)

    @staticmethod
    def _intent_from_direction(
        direction: ConceptDirection,
        *,
        base: DesignIntent | None = None,
    ) -> DesignIntent:
        seed = base or DesignIntent()
        return DesignIntent(
            theme=direction.theme or direction.title or seed.theme,
            problem_statement=direction.summary or seed.problem_statement,
            social_background=seed.social_background,
            cultural_context=seed.cultural_context,
            target_users=list(seed.target_users),
            desired_experience=direction.experience_focus or seed.desired_experience,
            core_questions=list(direction.open_questions) or list(seed.core_questions),
            research_needed=list(seed.research_needed),
            working_assumptions=list(seed.working_assumptions),
        )

    def _require_session(self, exploration_id: UUID) -> ExplorationSession:
        exploration = self._explorations.get(exploration_id)
        if exploration is None:
            raise WorkflowError(f"Exploration session {exploration_id} not found")
        return exploration
