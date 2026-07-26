"""Design iteration — generate and select concept direction drafts under a Mission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.concept_direction_mapping import concept_direction_from_draft
from archium.application.design_intent_from_direction import design_intent_from_direction
from archium.application.design_knowledge_context import (
    design_knowledge_summary_lines,
    format_design_knowledge_block,
)
from archium.application.design_rationale_fallback import ensure_direction_design_rationale
from archium.application.project_mission_service import MissionPatch, ProjectMissionService
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.enums import ConceptDirectionStatus
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ConceptDirectionRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.call import generate_structured as llm_generate_structured
from archium.infrastructure.llm.capabilities import LLMCapability
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)
from archium.prompts.concept_direction import (
    CONCEPT_DIRECTION_SYSTEM_PROMPT,
    build_concept_direction_user_prompt,
)
from archium.prompts.concept_direction import (
    PROMPT_VERSION as CONCEPT_PROMPT_VERSION,
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
    critique_warnings: list[str] = field(default_factory=list)
    critique_report: object | None = None
    selection_completed: bool = True
    pending_revise: object | None = None

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

        draft = llm_generate_structured(
            self._llm,
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
                    design_knowledge_block=format_design_knowledge_block(
                        self._session,
                        mission.project_id,
                        design_intent=mission.design_intent,
                        query_hint=mission.task_statement or mission.title,
                    ),
                ),
                temperature=0.5,
                json_mode=True,
                metadata={"prompt_version": CONCEPT_PROMPT_VERSION},
            ),
            ConceptDirectionBatchDraft,
            capability=LLMCapability.CONCEPT_GENERATION,
            project_id=mission.project_id,
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
            created.append(self._persist_draft(mission, item, sort_order=index))
        self._session.commit()
        return ConceptDirectionGenerationResult(
            mission_id=mission.id,
            directions=created,
            warnings=warnings,
        )

    def select_direction(
        self,
        direction_id: UUID,
        *,
        revise_action: str | None = None,
    ) -> ConceptDirectionSelectionResult:
        direction = self._directions.get(direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {direction_id} 不存在")
        if direction.mission_id is None:
            raise WorkflowError(
                "该方向尚未绑定 Mission；请在概念探索页选择方向并提交生成 Mission"
            )
        if direction.status == ConceptDirectionStatus.ARCHIVED:
            raise WorkflowError("已归档的概念方向不能选为当前方向")

        mission = self._require_mission(direction.mission_id)
        critique_gate = self._run_design_critique(
            direction,
            design_intent=mission.design_intent,
        )
        direction, critique_warnings, critique_gate, _loop_revised, pending = (
            self._maybe_revise_from_critique(
                direction,
                critique_gate,
                design_intent=mission.design_intent,
                revise_action=revise_action,
            )
        )
        if pending is not None:
            return ConceptDirectionSelectionResult(
                direction=direction,
                mission=mission,
                directions=self._directions.list_by_mission(direction.mission_id),
                critique_warnings=critique_warnings,
                critique_report=critique_gate.report if critique_gate else None,
                selection_completed=False,
                pending_revise=pending,
            )

        siblings = self._directions.list_by_mission(direction.mission_id)
        previous_theme = (
            (mission.design_intent.theme if mission.design_intent else "") or ""
        ).strip()
        from archium.application.spatial_design_layer import (
            design_decision_from_direction_selection,
            ensure_direction_spatial_layer,
        )
        from archium.infrastructure.database.repositories import ProjectRepository

        selected: ConceptDirection | None = None
        for sibling in siblings:
            if sibling.id == direction.id:
                sibling = direction
                sibling.select()
                sibling = ensure_direction_spatial_layer(sibling)
                selected = sibling
            elif sibling.status == ConceptDirectionStatus.SELECTED:
                sibling.mark_draft()
            self._directions.update(sibling)

        selected = selected or ensure_direction_spatial_layer(direction)
        updated_intent = design_intent_from_direction(
            selected,
            base=mission.design_intent,
        )
        mission = self._mission_service.update_mission(
            mission.id,
            MissionPatch(design_intent=updated_intent),
        )
        try:
            from archium.domain.intent.intent_evolution import (
                IntentEvolution,
                IntentEvolutionKind,
            )

            project = ProjectRepository(self._session).get_by_id(mission.project_id)
            if project is not None:
                decision = design_decision_from_direction_selection(
                    selected,
                    previous_theme=previous_theme,
                )
                evo = project.intent_evolution or IntentEvolution()
                project.intent_evolution = evo.append(
                    IntentEvolutionKind.DESIGN_DECISION,
                    decision.decision or f"选定方向：{selected.title}",
                    trigger="Mission 方向选定",
                    previous_summary=previous_theme or None,
                    new_summary=selected.title,
                    reason=decision.reason or None,
                    evidence_refs=list(decision.evidence)[:6],
                    design_decision=decision.as_dict(),
                    design_intent_snapshot=updated_intent.model_dump(mode="json"),
                )
                if critique_gate.report is not None:
                    from archium.application.design_reflection import (
                        reflection_from_critique,
                    )
                    from archium.domain.intent.intent_evolution import (
                        IntentEvolutionKind as _Kind,
                    )

                    reflection = reflection_from_critique(critique_gate.report)
                    if not reflection.is_empty():
                        project.intent_evolution = project.intent_evolution.append(
                            _Kind.REFLECTION,
                            reflection.why[:200] or "选定后设计反思",
                            trigger="direction_critique_reflection",
                            reason=reflection.why[:400] or None,
                            evidence_refs=list(reflection.top_risks)[:4],
                            design_intent_snapshot={"reflection": reflection.as_dict()},
                        )
                project.touch()
                ProjectRepository(self._session).update(project)
        except Exception:
            pass

        self._session.commit()
        from archium.application.context import best_effort_reassess_knowledge

        best_effort_reassess_knowledge(
            self._session,
            mission.project_id,
            llm=self._llm,
            settings=self._settings,
            reason="mission_direction_selected",
        )

        refreshed = self._directions.get(direction_id)
        assert refreshed is not None
        return ConceptDirectionSelectionResult(
            direction=refreshed,
            mission=mission,
            directions=self._directions.list_by_mission(direction.mission_id),
            critique_warnings=critique_warnings,
            critique_report=critique_gate.report,
            selection_completed=True,
            pending_revise=None,
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

    def update_visual_seed(
        self,
        direction_id: UUID,
        *,
        visual_prompt: ConceptVisualPrompt,
        spatial_strategy: str | None = None,
        formal_language: str | None = None,
        material_strategy: str | None = None,
        experience_focus: str | None = None,
    ) -> ConceptDirection:
        """Write-back visual seed (and optional light spatial fields) after architect review."""
        direction = self._directions.get(direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {direction_id} 不存在")
        if direction.status == ConceptDirectionStatus.ARCHIVED:
            raise WorkflowError("已归档的概念方向不能修订视觉种子")
        if visual_prompt.is_empty():
            raise WorkflowError("视觉种子不能为空")

        direction.visual_prompt = visual_prompt
        if spatial_strategy is not None:
            direction.spatial_strategy = spatial_strategy.strip()
        if formal_language is not None:
            direction.formal_language = formal_language.strip()
        if material_strategy is not None:
            direction.material_strategy = material_strategy.strip()
        if experience_focus is not None:
            direction.experience_focus = experience_focus.strip()
        direction.touch()
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
        direction = concept_direction_from_draft(
            draft,
            project_id=mission.project_id,
            mission_id=mission.id,
            sort_order=sort_order,
        )
        from archium.application.concept_direction_case_refs import (
            enrich_direction_case_refs,
        )

        direction = enrich_direction_case_refs(direction, session=self._session)
        direction = ensure_direction_design_rationale(
            direction,
            known_facts=self._known_facts_for_project(mission.project_id),
        )
        from archium.application.reasoning_artifact import ensure_direction_reasoning
        from archium.application.spatial_design_layer import ensure_direction_spatial_layer

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

    def _maybe_revise_from_critique(
        self,
        direction: ConceptDirection,
        critique_gate: Any,
        *,
        design_intent: Any = None,
        revise_action: str | None = None,
    ) -> tuple[ConceptDirection, list[str], Any, bool, Any]:
        """Revise per DESIGN_REVISE_ON_SELECT (L2); re-critique when applied (L1)."""
        from archium.application.design_loop import (
            resolve_revise_policy,
            run_design_loop_on_select,
        )
        from archium.application.review.design_critique_service import DesignCritiqueService
        from archium.domain.intent.intent_evolution import (
            IntentEvolution,
            IntentEvolutionKind,
        )
        from archium.infrastructure.database.repositories import ProjectRepository

        if critique_gate is None or getattr(critique_gate, "report", None) is None:
            return direction, [], critique_gate, False, None

        project = ProjectRepository(self._session).get_by_id(direction.project_id)
        knowledge_state = project.knowledge_state if project is not None else None
        research_summaries = self._research_summaries_for_critique(direction.project_id)
        critic = DesignCritiqueService(
            self._session, self._llm, settings=self._settings
        )
        policy = resolve_revise_policy(
            getattr(self._settings, "design_revise_on_select", None),
            revise_action,
        )
        loop = run_design_loop_on_select(
            direction,
            critique_gate,
            critic=critic,
            design_intent=design_intent,
            knowledge_state=knowledge_state,
            research_summaries=research_summaries,
            known_facts=self._known_facts_for_project(direction.project_id),
            revise_policy=policy,
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

        if loop.pending_offer is not None:
            return direction, deduped, critique_gate, False, loop.pending_offer

        if loop.revised or (
            direction.reasoning is not None and direction.reasoning.verified
        ):
            direction = self._directions.update(direction)

        if policy == "reject" and project is not None:
            try:
                evo = project.intent_evolution or IntentEvolution()
                project.intent_evolution = evo.append(
                    IntentEvolutionKind.DESIGN_CRITIQUE,
                    "拒绝批判修订补丁",
                    trigger="revise_rejected",
                    previous_summary=(direction.title or "")[:80] or None,
                    new_summary="reject",
                    reason="建筑师拒绝自动修订，按原方向继续",
                    evidence_refs=list(deduped)[:6],
                    design_intent_snapshot={
                        "revise_action": "reject",
                        "critique": critique_gate.report.as_dict(),
                    },
                )
                project.touch()
                ProjectRepository(self._session).update(project)
            except Exception:
                pass

        if loop.revised and loop.revise is not None:
            try:
                if project is not None:
                    evo = project.intent_evolution or IntentEvolution()
                    project.intent_evolution = evo.append(
                        IntentEvolutionKind.DIRECTION_REVISED,
                        "批判后修订概念方向",
                        trigger=(
                            "revise_direction_from_critique_apply"
                            if policy == "apply"
                            else "revise_direction_from_critique"
                        ),
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
                        reason=(critique_gate.report.summary or "回应批判弱点与推理链缺口")[
                            :500
                        ],
                        evidence_refs=list(loop.revise.applied)[:8],
                        design_intent_snapshot={
                            "revise": loop.revise.as_dict(),
                            "critique_verdict": critique_gate.report.verdict.value,
                            "recritique_verdict": loop.gate.report.verdict.value,
                            "revise_policy": policy,
                        },
                    )
                    if loop.revise.reflection is not None and not loop.revise.reflection.is_empty():
                        project.intent_evolution = project.intent_evolution.append(
                            IntentEvolutionKind.REFLECTION,
                            loop.revise.reflection.why[:200] or "修订后设计反思",
                            trigger="revise_reflection",
                            reason=loop.revise.reflection.why[:400] or None,
                            evidence_refs=list(loop.revise.reflection.next_adjustments)[:4],
                            design_intent_snapshot={
                                "reflection": loop.revise.reflection.as_dict()
                            },
                        )
                    project.intent_evolution = project.intent_evolution.append(
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
                    project.touch()
                    ProjectRepository(self._session).update(project)
            except Exception:
                pass

        return direction, deduped, loop.gate, loop.revised, None

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

    def _run_design_critique(self, direction: ConceptDirection, *, design_intent: Any=None) -> Any:
        from archium.application.review.design_critique_service import DesignCritiqueService
        from archium.infrastructure.database.repositories import ProjectRepository

        project = ProjectRepository(self._session).get_by_id(direction.project_id)
        knowledge_state = project.knowledge_state if project is not None else None
        return DesignCritiqueService(
            self._session, self._llm, settings=self._settings
        ).enforce_on_select(
            direction,
            design_intent=design_intent,
            knowledge_state=knowledge_state,
            research_summaries=self._research_summaries_for_critique(direction.project_id),
        )

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        return mission
