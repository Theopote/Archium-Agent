"""Context intelligence — assess KnowledgeState and suggest next actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context_evidence import (
    ProjectEvidencePack,
    gather_project_evidence,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.context_intelligence_schemas import ContextAssessmentDraft
from archium.prompts.context_intelligence import (
    CONTEXT_INTELLIGENCE_SYSTEM_PROMPT,
    build_context_assessment_user_prompt,
)

_VALID_STAGES = {item.value for item in KnowledgeMaturityStage}
_VALID_ACTIONS = {item.value for item in NextBestActionType}
_VALID_ORIGINS = {item.value for item in ProjectOriginMode}


@dataclass
class ContextAssessment:
    knowledge_state: KnowledgeState
    actions: list[NextBestAction] = field(default_factory=list)
    suggested_origin_mode: ProjectOriginMode = ProjectOriginMode.CONCEPT_EXPLORATION
    understanding_summary: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActionDispatch:
    """Where the UI should send the user for a NextBestAction."""

    page_key: str
    mission_step: int | None = None
    label: str = ""
    focus: str | None = None


class ContextIntelligenceService:
    """Judge what the project knows and what to do next (not content generation)."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)

    def assess_text(
        self,
        user_text: str,
        *,
        project_name: str = "",
        document_count: int = 0,
        document_summaries: str = "",
        evidence: ProjectEvidencePack | None = None,
    ) -> ContextAssessment:
        text = user_text.strip()
        if not text:
            raise WorkflowError("请先描述你的建筑项目、问题或灵感")
        pack = evidence or ProjectEvidencePack(
            document_count=document_count,
            document_summaries=document_summaries,
        )
        try:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=CONTEXT_INTELLIGENCE_SYSTEM_PROMPT,
                    user_prompt=build_context_assessment_user_prompt(
                        user_text=text,
                        project_name=project_name,
                        document_count=pack.document_count,
                        document_summaries=pack.document_summaries,
                        fact_lines=pack.fact_lines,
                        chunk_excerpts=pack.chunk_excerpts,
                        gap_lines=pack.gap_lines,
                        confirmed_fact_count=pack.confirmed_fact_count,
                        pending_fact_count=pack.pending_fact_count,
                        blocking_gap_count=pack.blocking_gap_count,
                    ),
                    temperature=0.3,
                    json_mode=True,
                ),
                ContextAssessmentDraft,
            )
            return self._from_draft(draft, source="initial")
        except Exception as exc:  # noqa: BLE001
            assessment = self._rule_fallback(
                text,
                document_count=pack.document_count,
                project_name=project_name,
                evidence=pack,
            )
            assessment.warnings.append(f"知识状态自动评估降级：{exc}")
            return assessment

    def assess_and_persist(
        self,
        project_id: UUID,
        user_text: str,
        *,
        write_evolution: bool = True,
    ) -> ContextAssessment:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")
        evidence = gather_project_evidence(self._session, project_id)
        assessment = self.assess_text(
            user_text,
            project_name=project.name,
            evidence=evidence,
        )
        # Richer materials shift source stamp for UI/debug
        if evidence.has_evidence and assessment.knowledge_state.source == "initial":
            assessment.knowledge_state = assessment.knowledge_state.model_copy(
                update={"source": "materials_aware"}
            )
        project.knowledge_state = assessment.knowledge_state
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
    ) -> ContextAssessment:
        """Refresh KnowledgeState after new evidence; append understanding event only."""
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
        )
        if assessment.understanding_summary.strip():
            self.append_evolution(
                project_id,
                IntentEvolutionKind.AI_UNDERSTANDING,
                f"[刷新] {assessment.understanding_summary.strip()[:480]}",
            )
            # append_evolution commits; refresh assessment from DB is optional
        assessment.knowledge_state = assessment.knowledge_state.model_copy(
            update={"source": "refresh"}
        )
        # Persist refreshed source stamp
        project = self._projects.get_by_id(project_id)
        if project is not None:
            project.knowledge_state = assessment.knowledge_state
            project.touch()
            self._projects.update(project)
            self._session.commit()
        return assessment

    @staticmethod
    def resolve_action_target(
        action: NextBestActionType,
        *,
        pending_fact_count: int = 0,
        conflict_fact_count: int = 0,
    ) -> ActionDispatch:
        """Map NBA to an existing product page (no new pipeline)."""
        if action == NextBestActionType.EXPLORE_DIRECTIONS:
            return ActionDispatch(
                page_key="concept-exploration",
                label="推演概念方向",
            )
        if action == NextBestActionType.UPLOAD_MATERIALS:
            return ActionDispatch(page_key="materials", label="上传 / 整理资料")
        if action == NextBestActionType.RESEARCH:
            return ActionDispatch(
                page_key="project-mission",
                mission_step=2,
                label="启动研究补充背景",
            )
        if action == NextBestActionType.ASK:
            if pending_fact_count > 0 or conflict_fact_count > 0:
                count = pending_fact_count + conflict_fact_count
                return ActionDispatch(
                    page_key="materials",
                    label=f"确认待核实事实（{count}）",
                    focus="pending_facts",
                )
            return ActionDispatch(
                page_key="project-mission",
                mission_step=3,
                label="先澄清关键问题",
            )
        if action in {
            NextBestActionType.GENERATE_MISSION,
            NextBestActionType.OPEN_MISSION,
        }:
            return ActionDispatch(
                page_key="project-mission",
                mission_step=1,
                label="打开项目任务",
            )
        return ActionDispatch(page_key="project-mission", mission_step=1, label=action.value)

    def try_execute_research(
        self,
        project_id: UUID,
    ) -> tuple[bool, str]:
        """Run autonomous research when a Mission exists; otherwise advise navigation.

        Returns (executed, message).
        """
        from archium.application.autonomous_research_service import AutonomousResearchService
        from archium.infrastructure.database.mission_repositories import MissionRepository

        missions = MissionRepository(self._session).list_missions_by_project(project_id)
        if not missions:
            return (
                False,
                "尚无项目任务（Mission）。请先生成任务理解，或进入项目任务页后再启动研究。",
            )
        mission = missions[0]
        try:
            result = AutonomousResearchService(
                self._session,
                self._llm,
                settings=self._settings,
            ).research_for_mission(mission.id)
            self._session.commit()
        except WorkflowError as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001
            return False, f"自主研究未能完成：{exc}"

        self.append_evolution(
            project_id,
            IntentEvolutionKind.RESEARCH,
            f"自主研究生成 {len(result.items)} 条公开摘要",
        )
        try:
            self.reassess(project_id)
        except Exception:
            pass
        provider = (
            f"（来源：{result.search_provider}）" if result.search_provider else ""
        )
        return (
            True,
            f"已生成 {len(result.items)} 条公开研究摘要{provider}。"
            + (" 知识状态已刷新。" if True else ""),
        )

    def append_evolution(
        self,
        project_id: UUID,
        kind: IntentEvolutionKind,
        summary: str,
        *,
        design_intent_snapshot: dict[str, object] | None = None,
    ) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"Project {project_id} not found")
        evo = project.intent_evolution or IntentEvolution()
        project.intent_evolution = evo.append(
            kind,
            summary,
            design_intent_snapshot=design_intent_snapshot,
        )
        project.touch()
        updated = self._projects.update(project)
        self._session.commit()
        return updated

    def _from_draft(
        self, draft: ContextAssessmentDraft, *, source: str
    ) -> ContextAssessment:
        stage_raw = (draft.maturity_stage or "").strip().lower()
        if stage_raw not in _VALID_STAGES:
            stage_raw = KnowledgeMaturityStage.CONCEPT_FORMATION.value
        origin_raw = (draft.suggested_origin_mode or "").strip().lower()
        if origin_raw not in _VALID_ORIGINS:
            origin_raw = ProjectOriginMode.CONCEPT_EXPLORATION.value

        actions: list[NextBestAction] = []
        for item in draft.actions:
            action_raw = (item.action or "").strip().lower()
            if action_raw not in _VALID_ACTIONS:
                continue
            actions.append(
                NextBestAction(
                    action=NextBestActionType(action_raw),
                    reason=(item.reason or "").strip(),
                    question=(item.question or None),
                    priority=int(item.priority or 0),
                )
            )
        actions.sort(key=lambda a: a.priority)
        if not actions:
            actions = self._default_actions_for_stage(stage_raw)

        state = KnowledgeState(
            completeness_score=max(0.0, min(1.0, float(draft.completeness_score))),
            maturity_stage=KnowledgeMaturityStage(stage_raw),
            evidence_ratio=max(0.0, min(1.0, float(draft.evidence_ratio))),
            assumption_ratio=max(0.0, min(1.0, float(draft.assumption_ratio))),
            known={k: str(v) for k, v in (draft.known or {}).items() if str(v).strip()},
            unknown=[u.strip() for u in draft.unknown if u and u.strip()],
            missing_information=[
                m.strip() for m in draft.missing_information if m and m.strip()
            ],
            assessed_at=datetime.now(UTC),
            source=source,
        )
        return ContextAssessment(
            knowledge_state=state,
            actions=actions,
            suggested_origin_mode=ProjectOriginMode(origin_raw),
            understanding_summary=(draft.understanding_summary or "").strip(),
        )

    def _rule_fallback(
        self,
        user_text: str,
        *,
        document_count: int,
        project_name: str,
        evidence: ProjectEvidencePack | None = None,
    ) -> ContextAssessment:
        pack = evidence or ProjectEvidencePack(document_count=document_count)
        has_doc_words = any(
            token in user_text
            for token in ("图纸", "PDF", "pdf", "CAD", "总平", "BIM", "施工图")
        )
        programming = any(
            token in user_text for token in ("投资", "可研", "立项", "策划", "投资人")
        )
        materials_signal = (
            pack.document_count
            + pack.confirmed_fact_count * 2
            + min(pack.extracted_fact_count, 4)
        )
        if (
            materials_signal >= 3
            or pack.confirmed_fact_count >= 2
            or (has_doc_words and pack.document_count >= 1)
        ):
            stage = KnowledgeMaturityStage.DESIGN_ANALYSIS
            completeness = 0.55 if materials_signal < 6 else 0.72
            origin = ProjectOriginMode.EXISTING_PROJECT
            evidence_ratio = min(
                0.9,
                0.2
                + pack.document_count * 0.08
                + pack.confirmed_fact_count * 0.12
                + pack.extracted_fact_count * 0.05,
            )
        elif programming:
            stage = KnowledgeMaturityStage.CONCEPT_FORMATION
            completeness = 0.35
            origin = ProjectOriginMode.RESEARCH_PROGRAMMING
            evidence_ratio = 0.15
        else:
            stage = KnowledgeMaturityStage.CONCEPT_FORMATION
            completeness = 0.28
            origin = ProjectOriginMode.CONCEPT_EXPLORATION
            evidence_ratio = 0.05 if pack.document_count == 0 else 0.2
            if pack.confirmed_fact_count:
                completeness = min(0.5, completeness + pack.confirmed_fact_count * 0.06)
                evidence_ratio = min(0.55, evidence_ratio + pack.confirmed_fact_count * 0.1)

        known: dict[str, str] = {}
        if project_name.strip():
            known["name"] = project_name.strip()
        for label, keys in (
            ("location", ("西安", "陕西", "北京", "上海", "乡村", "山地", "秦岭")),
            ("type", ("博物馆", "文化中心", "医院", "学校", "住宅", "商业")),
        ):
            for key in keys:
                if key in user_text:
                    known[label] = key
                    break
        # Surface first confirmed/extracted facts into known when LLM is down
        for line in pack.fact_lines.splitlines()[:4]:
            cleaned = line.strip().lstrip("- ").strip()
            if not cleaned:
                continue
            if cleaned.startswith("[已确认]"):
                known.setdefault("fact", cleaned.replace("[已确认]", "").strip()[:80])
            elif "fact" not in known and cleaned.startswith("["):
                known.setdefault("extracted", cleaned.split("]", 1)[-1].strip()[:80])

        unknown = ["规模", "目标用户", "场地条件", "投资约束"]
        if pack.gap_lines.strip():
            gap_unknown = [
                line.lstrip("- ").split("]", 1)[-1].strip()
                for line in pack.gap_lines.splitlines()
                if line.strip()
            ][:6]
            if gap_unknown:
                unknown = gap_unknown

        state = KnowledgeState(
            completeness_score=completeness,
            maturity_stage=stage,
            evidence_ratio=evidence_ratio,
            assumption_ratio=max(0.0, 1.0 - evidence_ratio),
            known=known,
            unknown=unknown,
            missing_information=list(unknown),
            assessed_at=datetime.now(UTC),
            source="rule_fallback",
        )
        actions = self._default_actions_for_stage(
            stage.value,
            has_materials=pack.has_evidence,
            blocking_gaps=pack.blocking_gap_count > 0,
        )
        return ContextAssessment(
            knowledge_state=state,
            actions=actions,
            suggested_origin_mode=origin,
            understanding_summary=(
                f"基于{'已有资料与事实' if pack.has_evidence else '文字描述'}的规则评估："
                f"完整度约 {int(completeness * 100)}%。"
            ),
        )

    @staticmethod
    def _default_actions_for_stage(
        stage: str,
        *,
        has_materials: bool = False,
        blocking_gaps: bool = False,
    ) -> list[NextBestAction]:
        if blocking_gaps:
            return [
                NextBestAction(
                    action=NextBestActionType.ASK,
                    reason="存在待确认或冲突的关键事实，先澄清再推进",
                    priority=0,
                ),
                NextBestAction(
                    action=NextBestActionType.UPLOAD_MATERIALS,
                    reason="补充可核验资料以消解缺口",
                    priority=1,
                ),
                NextBestAction(
                    action=NextBestActionType.EXPLORE_DIRECTIONS,
                    reason="在约束内仍可并行推演概念方向",
                    priority=2,
                ),
            ]
        if stage == KnowledgeMaturityStage.TECHNICAL_PRESENTATION.value:
            return [
                NextBestAction(
                    action=NextBestActionType.UPLOAD_MATERIALS,
                    reason="资料较充分时可继续补全证据并进入汇报结构",
                    priority=0,
                ),
                NextBestAction(
                    action=NextBestActionType.OPEN_MISSION,
                    reason="整理任务理解与汇报目标",
                    priority=1,
                ),
            ]
        if stage == KnowledgeMaturityStage.DESIGN_ANALYSIS.value or has_materials:
            return [
                NextBestAction(
                    action=NextBestActionType.ASK,
                    reason="基于已有资料澄清仍缺的关键条件",
                    priority=0,
                ),
                NextBestAction(
                    action=NextBestActionType.GENERATE_MISSION,
                    reason="资料已有部分证据，可形成任务理解",
                    priority=1,
                ),
                NextBestAction(
                    action=NextBestActionType.EXPLORE_DIRECTIONS,
                    reason="在已证实约束内推演概念方向",
                    priority=2,
                ),
                NextBestAction(
                    action=NextBestActionType.RESEARCH,
                    reason="补公开背景与案例参照",
                    priority=3,
                ),
            ]
        return [
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="信息较少时可先推演概念方向",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="补充公开背景与类型参照",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="澄清目标用户与核心问题",
                priority=2,
            ),
        ]
