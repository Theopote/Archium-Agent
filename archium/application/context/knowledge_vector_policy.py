"""Knowledge Vector → Next Best Action policy (architect-like routing)."""

from __future__ import annotations

from archium.domain.intent.knowledge_dimensions import KnowledgeDimensions, KnowledgeVector
from archium.domain.intent.knowledge_state import KnowledgeMaturityStage
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def actions_from_knowledge_vector(
    vector: KnowledgeVector | KnowledgeDimensions,
    *,
    stage: str = "",
    has_materials: bool = False,
    blocking_gaps: bool = False,
) -> list[NextBestAction]:
    """Explicit vector policy — lowest critical axis drives the next move.

    Policy (priority order):
      blocking gaps           → ask / upload (verify)
      design_readiness↑       → mission / explore (advance design)
      intent↓                 → ask or explore (clarify concept)
      facts↓ + intent↑        → explore (temple case; before constraint nag)
      constraints↓ + facts↑   → ask
      evidence↓ + facts↑      → ask (verify)
      facts↓                  → upload / explore / research
      research_need↑          → research
    """
    from archium.application.context.next_action_selector import default_actions_for_stage

    if blocking_gaps:
        return default_actions_for_stage(
            stage or KnowledgeMaturityStage.DESIGN_ANALYSIS.value,
            has_materials=has_materials,
            blocking_gaps=True,
        )

    v = vector.as_vector()
    facts = v["facts"]
    intent = v["intent"]
    constraints = v["constraints"]
    evidence = v["evidence"]
    readiness = v["design_readiness"]
    research = v["research_need"]

    # 1) Ready enough to advance design / mission
    if readiness >= 0.65 and intent >= 0.55:
        return [
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="设计就绪度较高，可固化任务理解并推进方案路径",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="并行比较概念方向",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.OPEN_MISSION,
                reason="查看或完善已有任务理解",
                priority=2,
            ),
        ]

    # 2) Intent low — clarify concept before collecting more sheets
    if intent < 0.45:
        if facts >= 0.55:
            return [
                NextBestAction(
                    action=NextBestActionType.ASK,
                    reason="资料较充足但设计意图仍模糊，先澄清目标",
                    priority=0,
                ),
                NextBestAction(
                    action=NextBestActionType.GENERATE_MISSION,
                    reason="用任务理解把目标与成果边界说清",
                    priority=1,
                ),
                NextBestAction(
                    action=NextBestActionType.EXPLORE_DIRECTIONS,
                    reason="意图澄清后可并行比较方向",
                    priority=2,
                ),
            ]
        return [
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="意图尚弱，先通过方向推演把概念说清楚",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="澄清核心问题与目标用户",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="补充类型参照以刺激意图形成",
                priority=2,
            ),
        ]

    # 3) Facts low, intent clear — temple case BEFORE constraint nagging
    if facts < 0.4 and intent >= 0.55:
        actions = [
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="设计意图较清晰、资料仍少，可先推演概念方向",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="意图清楚时可先固化任务理解，不必等齐资料",
                priority=1,
            ),
        ]
        if research >= 0.55:
            actions.append(
                NextBestAction(
                    action=NextBestActionType.RESEARCH,
                    reason="背景/类型研究需求高，并行补充公开参照",
                    priority=2,
                )
            )
        actions.append(
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="澄清仍缺的关键约束与使用者条件",
                priority=3,
            )
        )
        return actions

    # 4) Constraints low — only when project already has substance
    if constraints < 0.4 and facts >= 0.35:
        return [
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="约束理解不足，先澄清场地、规范或红线条件",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="补充可核验的约束类资料",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="在已知意图下仍可轻量推演",
                priority=2,
            ),
        ]

    # 5) Evidence low while materials/facts already present — verify
    if evidence < 0.35 and facts >= 0.35:
        return [
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="已有资料但证据信心不足，先核实关键事实",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="补充可引用证据",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.GENERATE_MISSION,
                reason="核实同时可整理任务理解",
                priority=2,
            ),
        ]

    # 6) Facts low — collect materials (when intent not carrying the project)
    if facts < 0.35:
        return [
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="资料完整度偏低，补充可核验项目资料",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="并行推演方向，避免空等资料",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="公开研究可补类型语境",
                priority=2,
            ),
        ]

    # 7) Research need high with some intent
    if research >= 0.7 and intent >= 0.5:
        return [
            NextBestAction(
                action=NextBestActionType.RESEARCH,
                reason="研究需求高，优先补充类型与背景证据",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="研究同时仍可推演方向",
                priority=1,
            ),
            NextBestAction(
                action=NextBestActionType.ASK,
                reason="对齐关键未知项",
                priority=2,
            ),
        ]

    return default_actions_for_stage(
        stage or KnowledgeMaturityStage.CONCEPT_FORMATION.value,
        has_materials=has_materials or facts >= 0.35,
        blocking_gaps=False,
    )
