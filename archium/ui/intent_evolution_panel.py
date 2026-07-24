"""IntentEvolution timeline — project-level intent shift history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import streamlit as st

from archium.domain.intent.intent_evolution import (
    IntentEvolution,
    IntentEvolutionEvent,
    IntentEvolutionKind,
)
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project import Project
from archium.infrastructure.database.session import get_session

_KIND_LABELS: dict[IntentEvolutionKind, str] = {
    IntentEvolutionKind.SEED: "初始想法",
    IntentEvolutionKind.AI_UNDERSTANDING: "AI 理解",
    IntentEvolutionKind.RESEARCH: "研究补充",
    IntentEvolutionKind.DIRECTION_SELECTED: "选定方向",
    IntentEvolutionKind.MISSION_COMMIT: "确认任务",
    IntentEvolutionKind.EVIDENCE: "出处确认",
}


def intent_evolution_kind_label(kind: IntentEvolutionKind | str) -> str:
    if isinstance(kind, IntentEvolutionKind):
        return _KIND_LABELS.get(kind, kind.value)
    try:
        return _KIND_LABELS.get(IntentEvolutionKind(kind), kind)
    except ValueError:
        return str(kind)


def format_intent_event_time(at: datetime) -> str:
    local = at.astimezone() if at.tzinfo is not None else at
    return local.strftime("%m-%d %H:%M")


def render_intent_evolution_timeline(
    evolution: IntentEvolution | None,
    *,
    key_prefix: str = "intent_evo",
    limit: int = 24,
) -> None:
    """Render chronological intent events (oldest → newest)."""
    events = list(evolution.events) if evolution is not None else []
    if not events:
        st.caption("尚无意图演进记录。理解项目、研究或选定方向后会出现。")
        return

    visible = events[-limit:] if len(events) > limit else events
    if len(events) > limit:
        st.caption(f"共 {len(events)} 次演进，显示最近 {limit} 条")
    else:
        st.caption(f"共 {len(events)} 次演进")

    for index, event in enumerate(visible):
        _render_timeline_event(event, key=f"{key_prefix}_{index}_{event.kind.value}")


def render_project_knowledge_and_evolution(
    project_id: UUID,
    *,
    expanded: bool = False,
    key_prefix: str = "ks_evo",
    show_knowledge: bool = True,
    title: str = "知识状态与意图演进",
) -> None:
    """Load project and show KnowledgeState + IntentEvolution timeline."""
    from archium.infrastructure.database.repositories import ProjectRepository

    with get_session() as session:
        project = ProjectRepository(session).get_by_id(project_id)
    if project is None:
        return
    render_knowledge_and_evolution(
        project,
        expanded=expanded,
        key_prefix=key_prefix,
        show_knowledge=show_knowledge,
        title=title,
    )


def render_knowledge_and_evolution(
    project: Project,
    *,
    expanded: bool = False,
    key_prefix: str = "ks_evo",
    show_knowledge: bool = True,
    title: str = "知识状态与意图演进",
) -> None:
    state = project.knowledge_state if show_knowledge else None
    evolution = project.intent_evolution
    has_events = bool(evolution and evolution.events)
    if state is None and not has_events:
        return

    with st.expander(title, expanded=expanded):
        if state is not None:
            _render_knowledge_snapshot(state)
        if state is not None and has_events:
            st.divider()
        st.markdown("**意图演进**")
        render_intent_evolution_timeline(
            evolution,
            key_prefix=f"{key_prefix}_{project.id}",
        )


def _render_knowledge_snapshot(state: KnowledgeState) -> None:
    st.caption(state.summary_line())
    if state.known:
        st.markdown(
            "**已知**：" + "；".join(f"{key}={value}" for key, value in state.known.items())
        )
    unknowns = state.unknown or state.missing_information
    if unknowns:
        st.markdown("**未知 / 仍缺**：" + "；".join(unknowns[:8]))


def _render_timeline_event(event: IntentEvolutionEvent, *, key: str) -> None:
    kind_label = intent_evolution_kind_label(event.kind)
    when = format_intent_event_time(event.at)
    st.markdown(f"**{kind_label}** · `{when}`")
    st.markdown(event.summary.strip())
    snapshot = event.design_intent_snapshot
    if not snapshot:
        return
    with st.expander("当时意图快照", expanded=False, key=f"{key}_snap"):
        evidence_rows = snapshot.get("evidence")
        if isinstance(evidence_rows, list) and evidence_rows:
            st.markdown("**出处**")
            for row in evidence_rows[:8]:
                if not isinstance(row, dict):
                    continue
                statement = str(row.get("statement") or "").strip()
                if not statement:
                    continue
                source = str(row.get("source_type") or "")
                try:
                    from archium.domain.intent.intent_evidence import (
                        IntentEvidenceSourceType,
                    )

                    source_label = {
                        IntentEvidenceSourceType.USER_INPUT.value: "用户输入",
                        IntentEvidenceSourceType.DOCUMENT.value: "项目资料",
                        IntentEvidenceSourceType.PUBLIC_RESEARCH.value: "公开研究",
                        IntentEvidenceSourceType.AI_INFERENCE.value: "AI 推理",
                        IntentEvidenceSourceType.ARCHITECT_ASSUMPTION.value: "建筑师假设",
                        IntentEvidenceSourceType.DIRECTION_SELECTION.value: "选定方向",
                    }.get(source, source)
                except Exception:
                    source_label = source
                materials = row.get("supporting_materials") or []
                suffix = ""
                if isinstance(materials, list) and materials:
                    suffix = " · " + "；".join(str(item) for item in materials[:2])
                st.caption(f"[{source_label}] {statement}{suffix}")
        for field_name, value in snapshot.items():
            if field_name == "evidence" or value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                text = "；".join(str(item) for item in value[:6] if str(item).strip())
                if not text:
                    continue
                st.caption(f"{field_name}：{text}")
            else:
                st.caption(f"{field_name}：{value}")
