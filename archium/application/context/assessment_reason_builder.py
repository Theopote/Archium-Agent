"""Build ContextAssessmentReason traces from vector + gaps (deterministic + LLM merge)."""

from __future__ import annotations

from archium.application.context_evidence import ProjectEvidencePack
from archium.domain.intent.context_assessment_reason import (
    AssessmentReasonAxis,
    AssessmentReasonPolarity,
    ContextAssessmentReason,
)
from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def synthesize_assessment_reasons(
    *,
    dimensions: KnowledgeDimensions,
    known: dict[str, str] | None = None,
    unknown: list[str] | None = None,
    actions: list[NextBestAction] | None = None,
    evidence: ProjectEvidencePack | None = None,
    llm_reasons: list[ContextAssessmentReason] | None = None,
    limit: int = 6,
) -> list[ContextAssessmentReason]:
    """Prefer LLM reasons when present; always ensure a deterministic baseline."""
    synthetic = _synthesize_from_signals(
        dimensions=dimensions,
        known=known or {},
        unknown=list(unknown or []),
        actions=list(actions or []),
        evidence=evidence or ProjectEvidencePack(),
    )
    merged: list[ContextAssessmentReason] = []
    seen: set[str] = set()
    for reason in list(llm_reasons or []) + synthetic:
        key = reason.factor.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(reason)
        if len(merged) >= limit:
            break
    return merged


def _synthesize_from_signals(
    *,
    dimensions: KnowledgeDimensions,
    known: dict[str, str],
    unknown: list[str],
    actions: list[NextBestAction],
    evidence: ProjectEvidencePack,
) -> list[ContextAssessmentReason]:
    reasons: list[ContextAssessmentReason] = []
    v = dimensions.as_vector()
    top = actions[0] if actions else None

    # Known positives
    if known.get("type") or known.get("location"):
        parts = []
        if known.get("type"):
            parts.append(f"类型={known['type']}")
        if known.get("location"):
            parts.append(f"地点={known['location']}")
        reasons.append(
            ContextAssessmentReason(
                factor="已有基础项目信息",
                evidence="；".join(parts),
                impact="足以开始概念层讨论，不必空等完备图纸",
                confidence=0.85,
                polarity=AssessmentReasonPolarity.SUPPORT,
                related_axis=AssessmentReasonAxis.FACTS,
            )
        )
    if v["intent"] >= 0.55:
        reasons.append(
            ContextAssessmentReason(
                factor="用户表达偏概念 / 意图较清晰",
                evidence=f"意图轴约 {int(round(v['intent'] * 100))}%",
                impact="适合进入概念探索或任务理解，而非先逼上传资料",
                confidence=0.88,
                polarity=AssessmentReasonPolarity.SUPPORT,
                related_axis=AssessmentReasonAxis.INTENT,
            )
        )

    # Gaps / blocks
    if v["facts"] < 0.4:
        evid = "用户描述中可核验资料较少"
        if evidence.document_count == 0:
            evid = "尚未上传图纸/文档，且事实账本几乎为空"
        reasons.append(
            ContextAssessmentReason(
                factor="缺少基地或项目资料",
                evidence=evid,
                impact="暂不宜直接进入详细分析或正式汇报",
                confidence=0.9,
                polarity=AssessmentReasonPolarity.BLOCK,
                related_axis=AssessmentReasonAxis.FACTS,
            )
        )
    if v["constraints"] < 0.4 and v["facts"] >= 0.35:
        reasons.append(
            ContextAssessmentReason(
                factor="约束条件理解不足",
                evidence=f"约束轴约 {int(round(v['constraints'] * 100))}%",
                impact="需先澄清场地/规范/红线后再加深设计",
                confidence=0.82,
                polarity=AssessmentReasonPolarity.BLOCK,
                related_axis=AssessmentReasonAxis.CONSTRAINTS,
            )
        )
    if v["evidence"] < 0.35 and v["facts"] >= 0.35:
        reasons.append(
            ContextAssessmentReason(
                factor="证据信心偏低",
                evidence=f"证据轴约 {int(round(v['evidence'] * 100))}%，待确认事实 {evidence.pending_fact_count}",
                impact="关键参数应先核实，避免当作已证实条件",
                confidence=0.84,
                polarity=AssessmentReasonPolarity.BLOCK,
                related_axis=AssessmentReasonAxis.EVIDENCE,
            )
        )

    if v["research_need"] >= 0.65:
        reasons.append(
            ContextAssessmentReason(
                factor="背景研究需求较高",
                evidence=f"研究需求轴约 {int(round(v['research_need'] * 100))}%",
                impact="可并行公开研究，但不阻塞概念探索",
                confidence=0.78,
                polarity=AssessmentReasonPolarity.NUANCE,
                related_axis=AssessmentReasonAxis.RESEARCH_NEED,
            )
        )

    # Reserve NBA conclusion before expanding unknown list
    if top is not None:
        reasons.append(
            ContextAssessmentReason(
                factor=f"因此建议：{_action_zh(top.action)}",
                evidence=(top.reason or "由 Knowledge Vector 策略表推导").strip(),
                impact="作为当前 Next Best Action",
                confidence=0.86,
                polarity=AssessmentReasonPolarity.SUPPORT,
                related_axis=AssessmentReasonAxis.WORKFLOW,
            )
        )

    for item in unknown[:3]:
        text = str(item).strip()
        if not text:
            continue
        reasons.append(
            ContextAssessmentReason(
                factor=f"缺少：{text[:80]}",
                evidence="来自知识缺口 / 未知项列表",
                impact="影响详细分析与正式交付完整度",
                confidence=0.8,
                polarity=AssessmentReasonPolarity.BLOCK,
                related_axis=AssessmentReasonAxis.FACTS,
            )
        )

    return reasons


def _action_zh(action: NextBestActionType) -> str:
    return {
        NextBestActionType.EXPLORE_DIRECTIONS: "进入概念探索",
        NextBestActionType.ASK: "先澄清关键问题",
        NextBestActionType.UPLOAD_MATERIALS: "补充项目资料",
        NextBestActionType.RESEARCH: "启动公开研究",
        NextBestActionType.GENERATE_MISSION: "生成任务理解",
        NextBestActionType.OPEN_MISSION: "打开项目任务",
    }.get(action, action.value)
