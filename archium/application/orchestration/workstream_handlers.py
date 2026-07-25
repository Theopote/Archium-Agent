"""Runtime handlers for workstream execution nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.orchestration.workstream_node_registry import (
    HANDLER_PRESENTATION_SIGNAL,
    HANDLER_RESEARCH,
    HANDLER_SKIP,
    HANDLER_STRATEGY_NOTE,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.orchestration.models import WorkstreamNodeSpec
from archium.infrastructure.llm.base import LLMProvider, LLMRequest


@dataclass
class WorkstreamNodeResult:
    workstream_id: UUID
    handler_key: str
    status: str  # completed | skipped | failed
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    knowledge_item_ids: list[str] = field(default_factory=list)


class WorkstreamHandlerRuntime(Protocol):
    session: Session
    llm: LLMProvider
    settings: Settings
    project_id: UUID
    mission_id: UUID | None


def run_workstream_handler(
    runtime: WorkstreamHandlerRuntime,
    spec: WorkstreamNodeSpec,
    *,
    workstream_objective: str = "",
    workstream_questions: list[str] | None = None,
) -> WorkstreamNodeResult:
    key = spec.handler_key or HANDLER_SKIP
    if key == HANDLER_SKIP:
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=key,
            status="skipped",
            summary=f"暂无执行器：{spec.workstream_type or spec.title}",
            warnings=[f"工作路径「{spec.title}」已跳过（无对应 handler）"],
        )
    if key == HANDLER_PRESENTATION_SIGNAL:
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=key,
            status="completed",
            summary="汇报准备信号已确认，可进入 presentation 阶段",
        )
    if key == HANDLER_RESEARCH:
        return _run_research_handler(
            runtime,
            spec,
            questions=workstream_questions or [],
            objective=workstream_objective,
        )
    if key == HANDLER_STRATEGY_NOTE:
        return _run_strategy_note_handler(
            runtime,
            spec,
            objective=workstream_objective,
            questions=workstream_questions or [],
        )
    return WorkstreamNodeResult(
        workstream_id=spec.workstream_id,
        handler_key=key,
        status="skipped",
        summary=f"未知 handler：{key}",
        warnings=[f"未知 handler_key={key}"],
    )


def _run_research_handler(
    runtime: WorkstreamHandlerRuntime,
    spec: WorkstreamNodeSpec,
    *,
    questions: list[str],
    objective: str,
) -> WorkstreamNodeResult:
    from archium.application.autonomous_research_service import AutonomousResearchService

    topics = [q.strip() for q in questions if q.strip()]
    if objective.strip():
        topics.insert(0, objective.strip())
    if not topics:
        topics = [spec.title or spec.workstream_type or "背景研究"]
    warnings: list[str] = []
    try:
        result = AutonomousResearchService(
            runtime.session,
            runtime.llm,
            settings=runtime.settings,
        ).research_topics(runtime.project_id, topics[:5])
        warnings.extend(result.warnings)
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=HANDLER_RESEARCH,
            status="completed",
            summary=f"研究完成：{len(result.items)} 条公开研究摘要",
            warnings=warnings,
            knowledge_item_ids=[str(item.id) for item in result.items],
        )
    except Exception as exc:  # noqa: BLE001 — node must not crash the whole graph
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=HANDLER_RESEARCH,
            status="failed",
            summary=f"研究失败：{exc}",
            warnings=[str(exc)],
        )


def _run_strategy_note_handler(
    runtime: WorkstreamHandlerRuntime,
    spec: WorkstreamNodeSpec,
    *,
    objective: str,
    questions: list[str],
) -> WorkstreamNodeResult:
    from archium.application.project_knowledge_service import ProjectKnowledgeService

    prompt_bits = [
        f"工作路径：{spec.title}",
        f"类型：{spec.workstream_type}",
    ]
    if objective.strip():
        prompt_bits.append(f"目标：{objective.strip()}")
    if questions:
        prompt_bits.append("问题：\n" + "\n".join(f"- {q}" for q in questions[:6]))
    note = ""
    warnings: list[str] = []
    try:
        note = runtime.llm.generate_text(
            LLMRequest(
                system_prompt=(
                    "你是建筑策划助手。根据工作路径写出 3–6 条可验证的分析要点，"
                    "不要编造精确指标。输出纯文本要点列表。"
                ),
                user_prompt="\n".join(prompt_bits),
                temperature=0.3,
            )
        ).strip()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"策略笔记 LLM 失败，已写入占位：{exc}")
        note = f"（占位）{spec.title}：{objective or '待深化分析'}"

    try:
        saved = ProjectKnowledgeService(runtime.session).create_item(
            runtime.project_id,
            statement=note[:2000] or f"{spec.title} 分析笔记",
            origin=InformationOrigin.SYSTEM_INFERENCE,
            reliability=InformationReliability.INFERENCE,
            requires_user_confirmation=True,
            category=f"workstream:{spec.workstream_type or 'strategy'}",
        )
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=HANDLER_STRATEGY_NOTE,
            status="completed",
            summary="已写入策略分析笔记",
            warnings=warnings,
            knowledge_item_ids=[str(saved.id)],
        )
    except Exception as exc:  # noqa: BLE001
        return WorkstreamNodeResult(
            workstream_id=spec.workstream_id,
            handler_key=HANDLER_STRATEGY_NOTE,
            status="failed",
            summary=f"写入知识失败：{exc}",
            warnings=[*warnings, str(exc)],
        )


@dataclass
class SimpleHandlerRuntime:
    session: Session
    llm: LLMProvider
    project_id: UUID
    mission_id: UUID | None = None
    settings: Settings = field(default_factory=get_settings)
    extras: dict[str, Any] = field(default_factory=dict)
