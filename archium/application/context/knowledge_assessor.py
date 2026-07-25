"""LLM + rule-based knowledge assessment (no content generation)."""

from __future__ import annotations

from datetime import UTC, datetime

from archium.application.context.next_action_selector import default_actions_for_stage
from archium.application.context.project_context_composer import (
    compose_project_context,
    finalize_assessment_context,
)
from archium.application.context.types import ContextAssessment
from archium.application.context_evidence import ProjectEvidencePack
from archium.domain.context.project_context import ProjectContext
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.context_intelligence_schemas import ContextAssessmentDraft
from archium.prompts.context_intelligence import (
    CONTEXT_INTELLIGENCE_SYSTEM_PROMPT,
    build_context_assessment_user_prompt,
)

_VALID_STAGES = {item.value for item in KnowledgeMaturityStage}
_VALID_ACTIONS = {item.value for item in NextBestActionType}
_VALID_ORIGINS = {item.value for item in ProjectOriginMode}


class KnowledgeAssessor:
    """Assess KnowledgeState and NBA suggestions from user text + evidence."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

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
            return self._from_draft(draft, source="initial", evidence=pack)
        except Exception as exc:  # noqa: BLE001
            assessment = self._rule_fallback(
                text,
                project_name=project_name,
                evidence=pack,
            )
            assessment.warnings.append(f"知识状态自动评估降级：{exc}")
            return assessment

    def _from_draft(
        self,
        draft: ContextAssessmentDraft,
        *,
        source: str,
        evidence: ProjectEvidencePack | None = None,
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
            actions = default_actions_for_stage(stage_raw)

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
        assessment = ContextAssessment(
            knowledge_state=state,
            actions=actions,
            suggested_origin_mode=ProjectOriginMode(origin_raw),
            understanding_summary=(draft.understanding_summary or "").strip(),
        )
        assessment.project_context = compose_project_context(
            assessment,
            evidence=evidence,
        )
        finalize_assessment_context(assessment)
        return assessment

    def _rule_fallback(
        self,
        user_text: str,
        *,
        project_name: str,
        evidence: ProjectEvidencePack | None = None,
    ) -> ContextAssessment:
        pack = evidence or ProjectEvidencePack()
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
        actions = default_actions_for_stage(
            stage.value,
            has_materials=pack.has_evidence,
            blocking_gaps=pack.blocking_gap_count > 0,
        )
        assessment = ContextAssessment(
            knowledge_state=state,
            actions=actions,
            suggested_origin_mode=origin,
            understanding_summary=(
                f"基于{'已有资料与事实' if pack.has_evidence else '文字描述'}的规则评估："
                f"完整度约 {int(completeness * 100)}%。"
            ),
        )
        assessment.project_context = compose_project_context(
            assessment,
            evidence=pack,
            user_text=user_text,
        )
        finalize_assessment_context(assessment)
        return assessment
