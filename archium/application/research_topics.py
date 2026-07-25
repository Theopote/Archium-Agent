"""Shared helpers for mission-driven and project-level research topics.

Policy (testable, not prompt): rank topics by **design impact** —
which Knowledge Vector axis they address and how blocking the gap is —
then return the top texts for AutonomousResearch.
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.intent.context_assessment_reason import (
    AssessmentReasonAxis,
    AssessmentReasonPolarity,
    ContextAssessmentReason,
)
from archium.domain.intent.knowledge_claim import KnowledgeUnknownRef
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_mission import ProjectMission

# Keywords that typically change architectural decisions (site / code / program).
_DESIGN_IMPACT_KEYWORDS: tuple[tuple[str, float, AssessmentReasonAxis], ...] = (
    ("红线", 0.35, AssessmentReasonAxis.CONSTRAINTS),
    ("用地", 0.32, AssessmentReasonAxis.CONSTRAINTS),
    ("场地", 0.3, AssessmentReasonAxis.CONSTRAINTS),
    ("消防", 0.32, AssessmentReasonAxis.CONSTRAINTS),
    ("规范", 0.3, AssessmentReasonAxis.CONSTRAINTS),
    ("结构", 0.28, AssessmentReasonAxis.CONSTRAINTS),
    ("交通", 0.26, AssessmentReasonAxis.CONSTRAINTS),
    ("流线", 0.26, AssessmentReasonAxis.CONSTRAINTS),
    ("面积", 0.24, AssessmentReasonAxis.FACTS),
    ("预算", 0.24, AssessmentReasonAxis.CONSTRAINTS),
    ("业主", 0.22, AssessmentReasonAxis.INTENT),
    ("功能", 0.22, AssessmentReasonAxis.INTENT),
    ("程序", 0.2, AssessmentReasonAxis.INTENT),
    ("类型", 0.28, AssessmentReasonAxis.RESEARCH_NEED),
    ("案例", 0.26, AssessmentReasonAxis.RESEARCH_NEED),
    ("文化", 0.28, AssessmentReasonAxis.CONTEXT),
    ("礼仪", 0.26, AssessmentReasonAxis.CONTEXT),
    ("遗产", 0.26, AssessmentReasonAxis.CONTEXT),
    ("气候", 0.22, AssessmentReasonAxis.CONTEXT),
    ("历史", 0.2, AssessmentReasonAxis.CONTEXT),
)

_AXIS_BASE: dict[AssessmentReasonAxis, float] = {
    AssessmentReasonAxis.RESEARCH_NEED: 0.55,
    AssessmentReasonAxis.CONSTRAINTS: 0.52,
    AssessmentReasonAxis.FACTS: 0.48,
    AssessmentReasonAxis.EVIDENCE: 0.45,
    AssessmentReasonAxis.CONTEXT: 0.5,
    AssessmentReasonAxis.INTENT: 0.42,
    AssessmentReasonAxis.DESIGN_READINESS: 0.35,
    AssessmentReasonAxis.WORKFLOW: 0.25,
    AssessmentReasonAxis.OTHER: 0.3,
}


@dataclass(frozen=True)
class ResearchTopicCandidate:
    """One ranked research topic with explainable design-impact scoring."""

    text: str
    score: float
    axis: AssessmentReasonAxis = AssessmentReasonAxis.OTHER
    source: str = "unknown"
    design_impact: str = ""


def collect_mission_research_topics(mission: ProjectMission) -> list[str]:
    """Mission topics ranked: design_intent.research_needed before free questions."""
    return [c.text for c in collect_mission_research_topic_candidates(mission)]


def collect_mission_research_topic_candidates(
    mission: ProjectMission,
    *,
    max_topics: int = 8,
) -> list[ResearchTopicCandidate]:
    candidates: list[ResearchTopicCandidate] = []
    if mission.design_intent is not None:
        for item in mission.design_intent.research_needed:
            text = (item or "").strip()
            if not text:
                continue
            axis, boost = _keyword_axis_boost(text)
            candidates.append(
                ResearchTopicCandidate(
                    text=text,
                    score=min(1.0, 0.88 + boost * 0.3),
                    axis=axis,
                    source="design_intent.research_needed",
                    design_impact="任务设计意图标明的必研项，直接影响方案边界",
                )
            )
    for item in mission.research_questions:
        text = (item or "").strip()
        if not text:
            continue
        axis, boost = _keyword_axis_boost(text)
        candidates.append(
            ResearchTopicCandidate(
                text=text,
                score=min(0.75, 0.45 + boost * 0.5),
                axis=axis,
                source="mission.research_questions",
                design_impact="任务研究问题，用于补证据或语境",
            )
        )
    return _dedupe_rank(candidates, max_topics=max_topics)


def collect_project_research_topics(
    *,
    project_name: str = "",
    project_description: str = "",
    knowledge_state: KnowledgeState | None = None,
    max_topics: int = 5,
) -> list[str]:
    """Derive research topics when Mission is absent (pre-mission research)."""
    return [
        c.text
        for c in collect_project_research_topic_candidates(
            project_name=project_name,
            project_description=project_description,
            knowledge_state=knowledge_state,
            max_topics=max_topics,
        )
    ]


def collect_project_research_topic_candidates(
    *,
    project_name: str = "",
    project_description: str = "",
    knowledge_state: KnowledgeState | None = None,
    max_topics: int = 5,
) -> list[ResearchTopicCandidate]:
    """Ranked candidates: open gaps + assessment reasons + type/location seeds.

    Higher score ⇒ more likely to change design decisions (constraints / type /
    culture / facts), not just fill prose.
    """
    candidates: list[ResearchTopicCandidate] = []
    state = knowledge_state
    research_need = 0.0

    if state is not None:
        dims = state.effective_dimensions()
        research_need = float(dims.research_need)

        for gap in state.open_unknowns:
            candidates.append(_from_open_unknown(gap, research_need=research_need))

        for item in state.unknown or []:
            candidates.append(
                _from_free_gap(
                    item,
                    source="knowledge_state.unknown",
                    research_need=research_need,
                )
            )
        for item in state.missing_information or []:
            candidates.append(
                _from_free_gap(
                    item,
                    source="knowledge_state.missing_information",
                    research_need=research_need,
                )
            )

        for reason in state.assessment_reasons or []:
            candidates.extend(_from_assessment_reason(reason, research_need=research_need))

        known = state.known or {}
        location = (known.get("location") or "").strip()
        ptype = (known.get("type") or "").strip()
        if location and ptype:
            candidates.append(
                ResearchTopicCandidate(
                    text=f"{location}{ptype}地方文化与类型先例",
                    score=0.62 + research_need * 0.15,
                    axis=AssessmentReasonAxis.CONTEXT,
                    source="known.location+type",
                    design_impact="地点+类型决定叙事与参照系，影响概念与排版证据",
                )
            )
        elif location:
            candidates.append(
                ResearchTopicCandidate(
                    text=f"{location}地域文化与场地语境",
                    score=0.55 + research_need * 0.15,
                    axis=AssessmentReasonAxis.CONTEXT,
                    source="known.location",
                    design_impact="地域语境影响场地策略与文化叙事",
                )
            )
        elif ptype:
            candidates.append(
                ResearchTopicCandidate(
                    text=f"{ptype}类型案例与文化语境",
                    score=0.55 + research_need * 0.15,
                    axis=AssessmentReasonAxis.RESEARCH_NEED,
                    source="known.type",
                    design_impact="类型先例影响空间组织与汇报论证结构",
                )
            )

        if dims.research_need >= 0.55 and not candidates:
            candidates.append(
                ResearchTopicCandidate(
                    text="项目类型与场地文化背景",
                    score=0.5 + research_need * 0.2,
                    axis=AssessmentReasonAxis.RESEARCH_NEED,
                    source="dimensions.research_need",
                    design_impact="研究需求轴偏高但尚无具体缺口，先补类型与场地语境",
                )
            )

        # Weak constraints with some facts → prefer constraint-shaped queries
        if dims.constraints < 0.4 and dims.facts >= 0.3:
            candidates.append(
                ResearchTopicCandidate(
                    text="场地约束、规范红线与可核验边界条件",
                    score=0.58 + (0.4 - dims.constraints),
                    axis=AssessmentReasonAxis.CONSTRAINTS,
                    source="dimensions.constraints",
                    design_impact="约束轴偏低会直接影响可建范围与合规方案",
                )
            )

    name = (project_name or "").strip()
    desc = (project_description or "").strip()
    seed = desc or name
    if seed:
        first = seed.splitlines()[0].strip()[:80]
        if first:
            candidates.append(
                ResearchTopicCandidate(
                    text=f"{first}：地方文化与设计语境",
                    score=0.48 + research_need * 0.1,
                    axis=AssessmentReasonAxis.CONTEXT,
                    source="project_description",
                    design_impact="从项目陈述抽取语境研究，支撑叙事而非空泛搜索",
                )
            )
        if any(token in seed for token in ("寺", "庙", "礼", "禅", "文化", "遗产", "民俗")):
            candidates.append(
                ResearchTopicCandidate(
                    text="当地文化、礼仪与空间叙事先例",
                    score=0.6 + research_need * 0.1,
                    axis=AssessmentReasonAxis.CONTEXT,
                    source="project_description.cultural",
                    design_impact="文化类项目的礼仪与叙事先例直接决定概念方向",
                )
            )

    if not candidates and (name or desc):
        candidates.append(
            ResearchTopicCandidate(
                text=f"{name or '项目'}背景与类型研究",
                score=0.4,
                axis=AssessmentReasonAxis.RESEARCH_NEED,
                source="project_name_fallback",
                design_impact="无结构化缺口时的保底类型背景研究",
            )
        )

    return _dedupe_rank(candidates, max_topics=max_topics)


def _from_open_unknown(
    gap: KnowledgeUnknownRef,
    *,
    research_need: float,
) -> ResearchTopicCandidate:
    text = (gap.description or "").strip()
    axis, boost = _keyword_axis_boost(text)
    category = (gap.category or "").strip().casefold()
    if category in {"constraint", "constraints", "code", "site", "规范", "场地"}:
        axis = AssessmentReasonAxis.CONSTRAINTS
        boost += 0.12
    elif category in {"type", "precedent", "research", "类型"}:
        axis = AssessmentReasonAxis.RESEARCH_NEED
        boost += 0.1
    score = 0.58 + boost + research_need * 0.12
    if gap.blocking:
        score += 0.18
        impact = f"阻断性未知项（{axis.value}）— 不补齐则方案易建立在错误假设上"
    else:
        impact = f"开放未知项（{axis.value}）— 补齐后可减少方案假设"
    return ResearchTopicCandidate(
        text=text,
        score=score,
        axis=axis,
        source="open_unknown",
        design_impact=impact,
    )


def _from_free_gap(
    raw: str,
    *,
    source: str,
    research_need: float,
) -> ResearchTopicCandidate:
    text = (raw or "").strip()
    axis, boost = _keyword_axis_boost(text)
    return ResearchTopicCandidate(
        text=text,
        score=0.5 + boost + research_need * 0.1,
        axis=axis,
        source=source,
        design_impact=f"知识缺口（{axis.value}）影响设计输入完备性",
    )


def _from_assessment_reason(
    reason: ContextAssessmentReason,
    *,
    research_need: float,
) -> list[ResearchTopicCandidate]:
    axis = reason.related_axis or AssessmentReasonAxis.OTHER
    # Only promote reasons that imply missing research / facts / context.
    if axis not in {
        AssessmentReasonAxis.RESEARCH_NEED,
        AssessmentReasonAxis.FACTS,
        AssessmentReasonAxis.CONTEXT,
        AssessmentReasonAxis.CONSTRAINTS,
        AssessmentReasonAxis.EVIDENCE,
    } and "研究" not in (reason.factor or ""):
        return []

    base = _AXIS_BASE.get(axis, 0.3)
    if reason.polarity == AssessmentReasonPolarity.BLOCK:
        base += 0.2
    elif reason.polarity == AssessmentReasonPolarity.SUPPORT:
        base += 0.05
    score = base + research_need * 0.1 + float(reason.confidence or 0.0) * 0.05

    out: list[ResearchTopicCandidate] = []
    factor = (reason.factor or "").strip()
    if factor:
        out.append(
            ResearchTopicCandidate(
                text=factor,
                score=score,
                axis=axis,
                source="assessment_reason.factor",
                design_impact=(reason.impact or "评估理由指向的研究缺口").strip(),
            )
        )
    evidence = (reason.evidence or "").strip()
    if evidence and evidence.casefold() != factor.casefold():
        out.append(
            ResearchTopicCandidate(
                text=evidence,
                score=score - 0.05,
                axis=axis,
                source="assessment_reason.evidence",
                design_impact="评估证据线索，可转成可检索研究主题",
            )
        )
    return out


def _keyword_axis_boost(text: str) -> tuple[AssessmentReasonAxis, float]:
    best_axis = AssessmentReasonAxis.OTHER
    best_boost = 0.0
    for keyword, boost, axis in _DESIGN_IMPACT_KEYWORDS:
        if keyword in text:
            if boost > best_boost:
                best_boost = boost
                best_axis = axis
    return best_axis, best_boost


def _dedupe_rank(
    candidates: list[ResearchTopicCandidate],
    *,
    max_topics: int,
) -> list[ResearchTopicCandidate]:
    ranked = sorted(candidates, key=lambda c: (-c.score, c.text))
    seen: set[str] = set()
    out: list[ResearchTopicCandidate] = []
    for item in ranked:
        key = item.text.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max_topics:
            break
    return out
