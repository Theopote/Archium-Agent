"""Enforce cognition gate before Narrative / presentation pipeline entry.

Planner classes stay prompt-only; this Service owns Goal/Context/Strategy/Action
wiring: evaluate KnowledgeState → optional RESEARCH → block or proceed with warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context.presentation_readiness import (
    PresentationContextReadiness,
    PresentationGateVerdict,
    presentation_readiness_from_context,
)
from archium.application.context.project_context_builder import build_project_context
from archium.config.settings import Settings, get_settings
from archium.domain.intent.next_best_action import NextBestActionType
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger

logger = get_logger(__name__, operation="presentation_cognition_gate")

PresentationCognitionGateMode = Literal["off", "warn", "block", "auto_research"]


@dataclass
class PresentationCognitionGateResult:
    """Outcome of evaluate (+ optional auto research) at Narrative entry."""

    readiness: PresentationContextReadiness
    mode: str
    blocked: bool = False
    auto_research_ran: bool = False
    auto_research_message: str = ""
    messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "blocked": self.blocked,
            "auto_research_ran": self.auto_research_ran,
            "auto_research_message": self.auto_research_message,
            "messages": list(self.messages),
            "readiness": self.readiness.as_dict(),
        }


def evaluate_presentation_cognition(
    session: Session,
    project_id: UUID,
) -> PresentationContextReadiness:
    """Build ProjectContext and map to presentation readiness / gate verdict."""
    try:
        context = build_project_context(session, project_id)
    except Exception as exc:  # noqa: BLE001 — gate must not crash entry for builder glitches
        logger.warning("build_project_context failed for gate: %s", exc)
        return presentation_readiness_from_context(None)
    return presentation_readiness_from_context(context)


def enforce_presentation_cognition_gate(
    session: Session,
    project_id: UUID,
    *,
    llm: LLMProvider | None = None,
    settings: Settings | None = None,
    force: bool = False,
) -> PresentationCognitionGateResult:
    """Apply configured gate policy before starting the presentation workflow.

    Modes (``settings.presentation_cognition_gate``):
    - ``off``: evaluate only for observability; never block or auto-act
    - ``warn``: never block; return warnings (default)
    - ``block``: raise ``WorkflowError`` when verdict is BLOCK (unless ``force``)
    - ``auto_research``: when suggested action is RESEARCH and verdict is WARN/BLOCK,
      run one RESEARCH via NBA executor, reassess, then proceed with warnings
      (hard-block only if still BLOCK *and* you switch to ``block``; auto mode stays soft)
    """
    cfg = settings or get_settings()
    mode = (cfg.presentation_cognition_gate or "warn").strip().lower()
    if mode not in {"off", "warn", "block", "auto_research"}:
        mode = "warn"

    readiness = evaluate_presentation_cognition(session, project_id)
    messages = list(readiness.warnings)
    result = PresentationCognitionGateResult(
        readiness=readiness,
        mode=mode,
        messages=messages,
    )

    if mode == "off" or force:
        result.blocked = False
        if force and readiness.blocks_generation:
            result.messages.append("已强制跳过认知门禁（force）。")
        return result

    if mode == "auto_research" and llm is not None:
        result = _maybe_auto_research(
            session,
            project_id,
            llm=llm,
            settings=cfg,
            result=result,
        )

    if mode == "block" and result.readiness.blocks_generation and not force:
        result.blocked = True
        detail = result.readiness.summary or "知识完备性不足"
        action = result.readiness.suggested_action
        hint = f"建议先执行：{action.value}" if action else "建议先补充研究或澄清未知项"
        raise WorkflowError(
            f"认知门禁阻断汇报生成：{detail}。{hint}。"
            "（设置 PRESENTATION_COGNITION_GATE=warn 可仅警告，"
            "或 auto_research 可先自动研究。）"
        )

    result.blocked = False
    return result


def _maybe_auto_research(
    session: Session,
    project_id: UUID,
    *,
    llm: LLMProvider,
    settings: Settings,
    result: PresentationCognitionGateResult,
) -> PresentationCognitionGateResult:
    readiness = result.readiness
    if readiness.suggested_action != NextBestActionType.RESEARCH:
        return result
    if readiness.verdict == PresentationGateVerdict.PROCEED:
        return result

    from archium.application.context.nba_action_executor import NbaActionExecutor

    logger.info(
        "presentation gate auto_research project=%s completeness=%s",
        project_id,
        readiness.completeness_pct,
    )
    nba = NbaActionExecutor(session, llm, settings=settings).execute(
        project_id,
        NextBestActionType.RESEARCH,
    )
    result.auto_research_ran = True
    result.auto_research_message = nba.message or ""
    if nba.message:
        result.messages.append(f"已自动执行研究：{nba.message}")
    if not nba.success:
        result.messages.append(
            nba.message or "自动研究未成功；仍按当前知识状态继续（warn）。"
        )
        return result

    refreshed = evaluate_presentation_cognition(session, project_id)
    result.readiness = refreshed
    # Prefer post-research warnings; keep auto-research note at front.
    note = list(result.messages)
    result.messages = note + [w for w in refreshed.warnings if w not in note]
    return result
