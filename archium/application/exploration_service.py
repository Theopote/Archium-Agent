"""Pre-mission concept exploration — IdeaSeed → directions → commit Mission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context_evidence import build_verified_constraints_block
from archium.application.design_intent_from_direction import design_intent_from_direction
from archium.application.design_knowledge_context import (
    design_knowledge_summary_lines,
    format_design_knowledge_block,
)
from archium.application.design_rationale_fallback import ensure_direction_design_rationale
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import (
    ConceptDirectionStatus,
    ExplorationSessionStatus,
    ProjectOriginMode,
)
from archium.domain.exploration_session import ExplorationSession
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
from archium.infrastructure.llm.call import generate_structured as llm_generate_structured
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)
from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
from archium.prompts.concept_direction import (
    CONCEPT_DIRECTION_SYSTEM_PROMPT,
    build_exploration_direction_user_prompt,
)
from archium.prompts.concept_direction import (
    PROMPT_VERSION as CONCEPT_PROMPT_VERSION,
)
from archium.prompts.idea_seed import (
    IDEA_SEED_SYSTEM_PROMPT,
    build_idea_seed_user_prompt,
)
from archium.prompts.idea_seed import (
    PROMPT_VERSION as IDEA_SEED_PROMPT_VERSION,
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
    critique_warnings: list[str] = field(default_factory=list)
    critique_report: object | None = None

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
        verified_constraints = build_verified_constraints_block(
            self._session, exploration.project_id
        )
        design_knowledge_block = format_design_knowledge_block(
            self._session,
            exploration.project_id,
            query_hint=seed.raw_input,
            design_intent=None,
        )
        draft = llm_generate_structured(
            self._llm,
            LLMRequest(
                system_prompt=CONCEPT_DIRECTION_SYSTEM_PROMPT,
                user_prompt=build_exploration_direction_user_prompt(
                    project_name=project.name,
                    idea_text=seed.raw_input,
                    idea_seed_block=seed.to_prompt_block(),
                    count=target_count,
                    verified_constraints_block=verified_constraints,
                    design_knowledge_block=design_knowledge_block,
                ),
                temperature=0.5,
                json_mode=True,
                metadata={"prompt_version": CONCEPT_PROMPT_VERSION},
            ),
            ConceptDirectionBatchDraft,
            capability=LLMCapability.CONCEPT_GENERATION,
            project_id=exploration.project_id,
            session=self._session,
            settings=self._settings,
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

        critique_gate = self._run_design_critique(direction, design_intent=None)
        direction, critique_warnings, critique_gate, loop_revised = (
            self._maybe_revise_from_critique(
                direction,
                critique_gate,
                design_intent=None,
            )
        )

        siblings = self._directions.list_by_exploration(exploration.id)
        previous_selected = next(
            (
                sibling
                for sibling in siblings
                if sibling.status == ConceptDirectionStatus.SELECTED
                and sibling.id != direction.id
            ),
            None,
        )
        previous_label = None
        if previous_selected is not None:
            previous_label = (
                previous_selected.title or previous_selected.theme or ""
            ).strip() or None
        elif exploration.idea_seed is not None:
            seed = exploration.idea_seed
            previous_label = (seed.theme or seed.raw_input or "").strip()[:80] or None

        for sibling in siblings:
            if sibling.id == direction.id:
                sibling = direction
                sibling.select()
                from archium.application.spatial_design_layer import (
                    design_decision_from_direction_selection,
                    ensure_direction_spatial_layer,
                )

                sibling = ensure_direction_spatial_layer(sibling)
            elif sibling.status == ConceptDirectionStatus.SELECTED:
                sibling.mark_draft()
            self._directions.update(sibling)

        exploration.mark_direction_selected(direction.id)
        exploration = self._explorations.update(exploration)
        refreshed = self._directions.get(direction_id)
        assert refreshed is not None
        new_label = (refreshed.title or refreshed.theme or "").strip() or refreshed.title
        from archium.application.spatial_design_layer import (
            design_decision_from_direction_selection,
        )

        decision = design_decision_from_direction_selection(
            refreshed,
            previous_theme=previous_label or "",
        )
        self._append_intent_evolution(
            exploration.project_id,
            IntentEvolutionKind.DIRECTION_SELECTED,
            f"选定概念方向：{new_label}",
            trigger="选定概念方向",
            previous_summary=previous_label,
            new_summary=new_label,
            reason="建筑师在概念探索中选定当前方向",
            evidence_refs=[
                bit
                for bit in (
                    refreshed.spatial_strategy,
                    refreshed.formal_language,
                    refreshed.experience_focus,
                )
                if bit and str(bit).strip()
            ][:4],
            design_intent_snapshot={
                "direction_id": str(refreshed.id),
                "title": refreshed.title,
                "theme": refreshed.theme,
                "spatial_intent": (
                    refreshed.spatial_intent.model_dump(mode="json")
                    if refreshed.spatial_intent is not None
                    else None
                ),
                "design_rules": [
                    rule.model_dump(mode="json") for rule in refreshed.design_rules[:6]
                ],
            },
            design_decision=decision.as_dict(),
        )
        self._append_intent_evolution(
            exploration.project_id,
            IntentEvolutionKind.DESIGN_DECISION,
            decision.decision or f"设计决策：{new_label}",
            trigger="概念方向选定",
            previous_summary=previous_label,
            new_summary=decision.chosen or new_label,
            reason=decision.reason or None,
            evidence_refs=list(decision.evidence)[:6],
            design_decision=decision.as_dict(),
        )
        if (
            critique_gate is not None
            and critique_gate.report.verdict.value != "proceed"
            and not loop_revised
        ):
            self._append_intent_evolution(
                exploration.project_id,
                IntentEvolutionKind.DESIGN_CRITIQUE,
                f"设计批判：{critique_gate.report.summary or critique_gate.report.verdict.value}",
                trigger="选定前设计批判",
                previous_summary=new_label,
                new_summary=critique_gate.report.verdict.value,
                reason=(critique_gate.report.summary or "独立批判报告")[:500],
                evidence_refs=[
                    item.text
                    for item in (
                        critique_gate.report.weaknesses
                        + critique_gate.report.missing_evidence
                    )[:6]
                ],
                design_intent_snapshot=critique_gate.report.as_dict(),
            )
            from archium.application.design_reflection import reflection_from_critique

            reflection = reflection_from_critique(critique_gate.report)
            if not reflection.is_empty():
                self._append_intent_evolution(
                    exploration.project_id,
                    IntentEvolutionKind.REFLECTION,
                    reflection.why[:200] or "选定后设计反思",
                    trigger="direction_critique_reflection",
                    previous_summary=new_label,
                    new_summary=critique_gate.report.verdict.value,
                    reason=reflection.why[:400] or None,
                    evidence_refs=list(reflection.top_risks)[:4],
                    design_intent_snapshot={"reflection": reflection.as_dict()},
                )
        self._session.commit()
        from archium.application.context import best_effort_reassess_knowledge

        best_effort_reassess_knowledge(
            self._session,
            exploration.project_id,
            llm=self._llm,
            settings=self._settings,
            reason="direction_selected",
        )

        return ExplorationSelectionResult(
            exploration=exploration,
            direction=refreshed,
            directions=self._directions.list_by_exploration(exploration.id),
            critique_warnings=critique_warnings,
            critique_report=critique_gate.report if critique_gate else None,
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
        intent = design_intent_from_direction(direction, base=generated.mission.design_intent)
        mission = self._mission_service.update_mission(
            generated.mission.id,
            MissionPatch(design_intent=intent),
        )

        for sibling in self._directions.list_by_exploration(exploration.id):
            sibling.mission_id = mission.id
            self._directions.update(sibling)

        from archium.application.visual.vision import VisualConceptBriefService

        brief_service = VisualConceptBriefService(
            self._session, self._llm, settings=self._settings
        )
        for sibling in self._directions.list_by_exploration(exploration.id):
            brief_service.backfill_mission_id_for_direction(sibling.id, mission.id)

        exploration.mark_committed(mission.id)
        exploration = self._explorations.update(exploration)
        previous_label = (direction.title or direction.theme or "").strip() or None
        new_label = None
        if mission.design_intent is not None and mission.design_intent.theme.strip():
            new_label = mission.design_intent.theme.strip()
        else:
            new_label = mission.title
        self._append_intent_evolution(
            exploration.project_id,
            IntentEvolutionKind.MISSION_COMMIT,
            f"提交为 Mission：{mission.title}",
            trigger="提交为项目任务",
            previous_summary=previous_label,
            new_summary=new_label,
            reason="将选定概念方向固化为任务理解",
            evidence_refs=[
                bit
                for bit in (
                    direction.spatial_strategy,
                    direction.formal_language,
                    mission.task_statement,
                )
                if bit and str(bit).strip()
            ][:4],
            design_intent_snapshot=(
                mission.design_intent.model_dump(mode="json")
                if mission.design_intent is not None
                else None
            ),
        )
        self._session.commit()
        from archium.application.context import best_effort_reassess_knowledge

        best_effort_reassess_knowledge(
            self._session,
            exploration.project_id,
            llm=self._llm,
            settings=self._settings,
            reason="mission_committed",
        )

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
            draft = llm_generate_structured(
                self._llm,
                LLMRequest(
                    system_prompt=IDEA_SEED_SYSTEM_PROMPT,
                    user_prompt=build_idea_seed_user_prompt(
                        raw_input=raw_input,
                        project_name=project_name,
                    ),
                    temperature=0.4,
                    json_mode=True,
                    metadata={"prompt_version": IDEA_SEED_PROMPT_VERSION},
                ),
                IdeaSeedDraft,
                capability=LLMCapability.IDEA_SEED,
                session=self._session,
                settings=self._settings,
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
        trigger: str | None = None,
        previous_summary: str | None = None,
        new_summary: str | None = None,
        reason: str | None = None,
        evidence_refs: list[str] | None = None,
        design_decision: dict[str, object] | None = None,
    ) -> None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            return
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
            design_decision=design_decision,
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
        from archium.application.concept_direction_mapping import concept_direction_from_draft
        from archium.application.spatial_design_layer import ensure_direction_spatial_layer

        direction = concept_direction_from_draft(
            draft,
            project_id=exploration.project_id,
            exploration_session_id=exploration.id,
            sort_order=sort_order,
        )
        from archium.application.concept_direction_case_refs import (
            enrich_direction_case_refs,
        )

        direction = enrich_direction_case_refs(direction, session=self._session)
        seed = exploration.idea_seed
        direction = ensure_direction_design_rationale(
            direction,
            known_facts=self._known_facts_for_project(exploration.project_id),
            idea_text=seed.raw_input if seed is not None else exploration.idea_text,
        )
        from archium.application.reasoning_artifact import ensure_direction_reasoning

        direction = ensure_direction_reasoning(direction)
        direction = ensure_direction_spatial_layer(direction)
        return self._directions.create(direction)

    def _known_facts_for_project(self, project_id: UUID) -> dict[str, str]:
        from archium.application.context.project_context_builder import (
            build_project_context,
        )

        ctx = build_project_context(self._session, project_id)
        if ctx is None or ctx.knowledge_state is None:
            return {}
        return dict(ctx.knowledge_state.known)

    def _run_design_critique(self, direction: ConceptDirection, *, design_intent: Any=None) -> Any:
        """Independent Architectural Critic before direction hardens (warn/block)."""
        from archium.application.review.design_critique_service import DesignCritiqueService

        project = self._projects.get_by_id(direction.project_id)
        knowledge_state = project.knowledge_state if project is not None else None
        return DesignCritiqueService(
            self._session, self._llm, settings=self._settings
        ).enforce_on_select(
            direction,
            design_intent=design_intent,
            knowledge_state=knowledge_state,
            research_summaries=self._research_summaries_for_critique(direction.project_id),
        )

    def _research_summaries_for_critique(self, project_id: UUID) -> list[str]:
        research_summaries: list[str] = []
        try:
            research_summaries = design_knowledge_summary_lines(
                self._session, project_id
            )
            if not research_summaries:
                from archium.infrastructure.database.repositories import (
                    ProjectKnowledgeRepository,
                )

                for item in ProjectKnowledgeRepository(self._session).list_by_project(
                    project_id
                )[:8]:
                    statement = (getattr(item, "statement", None) or "").strip()
                    if statement:
                        research_summaries.append(statement[:300])
        except Exception:  # noqa: BLE001
            pass
        return research_summaries

    def _maybe_revise_from_critique(
        self,
        direction: ConceptDirection,
        critique_gate: Any,
        *,
        design_intent: Any = None,
    ) -> tuple[ConceptDirection, list[str], Any, bool]:
        """Revise if needed, re-critique (L1), verify only on proceed."""
        from archium.application.design_loop import run_design_loop_on_select
        from archium.application.review.design_critique_service import DesignCritiqueService

        if critique_gate is None or getattr(critique_gate, "report", None) is None:
            return direction, [], critique_gate, False

        project = self._projects.get_by_id(direction.project_id)
        knowledge_state = project.knowledge_state if project is not None else None
        idea_text = ""
        if direction.exploration_session_id is not None:
            exploration = self._explorations.get(direction.exploration_session_id)
            if exploration is not None:
                seed = exploration.idea_seed
                idea_text = (
                    seed.raw_input if seed is not None else exploration.idea_text or ""
                )

        critic = DesignCritiqueService(
            self._session, self._llm, settings=self._settings
        )
        loop = run_design_loop_on_select(
            direction,
            critique_gate,
            critic=critic,
            design_intent=design_intent,
            knowledge_state=knowledge_state,
            research_summaries=self._research_summaries_for_critique(direction.project_id),
            idea_text=idea_text,
            known_facts=self._known_facts_for_project(direction.project_id),
        )
        direction = loop.direction
        notes = list(critique_gate.warnings) + list(loop.notes)
        seen: set[str] = set()
        deduped: list[str] = []
        for item in notes:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)

        if loop.revised or (
            direction.reasoning is not None and direction.reasoning.verified
        ):
            direction = self._directions.update(direction)

        if loop.revised and loop.revise is not None:
            self._append_intent_evolution(
                direction.project_id,
                IntentEvolutionKind.DIRECTION_REVISED,
                "批判后修订概念方向",
                trigger="revise_direction_from_critique",
                previous_summary=(direction.title or "")[:80] or None,
                new_summary=(
                    (
                        direction.design_rationale.strategy
                        if direction.design_rationale
                        else ""
                    )
                    or direction.spatial_strategy
                    or direction.title
                )[:80]
                or None,
                reason=(critique_gate.report.summary or "回应批判弱点与推理链缺口")[:500],
                evidence_refs=list(loop.revise.applied)[:8],
                design_intent_snapshot={
                    "revise": loop.revise.as_dict(),
                    "critique_verdict": critique_gate.report.verdict.value,
                    "recritique_verdict": loop.gate.report.verdict.value,
                },
            )
            if loop.revise.reflection is not None and not loop.revise.reflection.is_empty():
                self._append_intent_evolution(
                    direction.project_id,
                    IntentEvolutionKind.REFLECTION,
                    loop.revise.reflection.why[:200] or "修订后设计反思",
                    trigger="revise_reflection",
                    previous_summary=(direction.title or "")[:80] or None,
                    new_summary=loop.gate.report.verdict.value,
                    reason=loop.revise.reflection.why[:400] or None,
                    evidence_refs=list(loop.revise.reflection.next_adjustments)[:4],
                    design_intent_snapshot={
                        "reflection": loop.revise.reflection.as_dict()
                    },
                )
            self._append_intent_evolution(
                direction.project_id,
                IntentEvolutionKind.DESIGN_CRITIQUE,
                f"修订后再批判：{loop.gate.report.verdict.value}",
                trigger="recritique_after_revise",
                previous_summary=critique_gate.report.verdict.value,
                new_summary=loop.gate.report.verdict.value,
                reason=(loop.gate.report.summary or "L1 再批判")[:500],
                evidence_refs=[
                    item.text
                    for item in (
                        loop.gate.report.weaknesses
                        + loop.gate.report.missing_evidence
                    )[:6]
                ],
                design_intent_snapshot=loop.gate.report.as_dict(),
            )

        return direction, deduped, loop.gate, loop.revised

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
        if direction.spatial_strategy.strip():
            parts.append(f"空间策略：{direction.spatial_strategy.strip()}")
        if direction.formal_language.strip():
            parts.append(f"形式语言：{direction.formal_language.strip()}")
        if direction.material_strategy.strip():
            parts.append(f"材料策略：{direction.material_strategy.strip()}")
        if direction.experience_focus.strip():
            parts.append(f"体验焦点：{direction.experience_focus.strip()}")
        if direction.design_rationale is not None:
            block = direction.design_rationale.to_prompt_block()
            if block.strip():
                parts.append(block)
        return "\n".join(parts)

    def _require_session(self, exploration_id: UUID) -> ExplorationSession:
        exploration = self._explorations.get(exploration_id)
        if exploration is None:
            raise WorkflowError(f"Exploration session {exploration_id} not found")
        return exploration
