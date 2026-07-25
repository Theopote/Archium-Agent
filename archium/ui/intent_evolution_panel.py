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
    IntentEvolutionKind.VISUAL_FEEDBACK: "示意反馈",
}

_KS_REASON_LABELS = {
    "initial_assess": "首次评估",
    "refresh": "刷新评估",
    "document_uploaded": "上传资料",
    "fact_confirmed": "确认事实",
    "research": "自主研究",
    "clarification_continued": "澄清继续",
    "mission_approved": "批准任务",
    "direction_selected": "选定方向",
    "mission_direction_selected": "更换方向",
    "mission_committed": "提交任务",
    "nba_explore": "一键推演方向",
    "nba_generate_mission": "一键生成任务",
    "manual": "手动刷新",
    "other": "其他",
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
    history = project.knowledge_state_history
    evolution = project.intent_evolution
    has_history = bool(history and history.snapshots)
    has_events = bool(evolution and evolution.events)
    if state is None and not has_history and not has_events:
        return

    with st.expander(title, expanded=expanded):
        if state is not None:
            from archium.ui.project_knowledge_profile import render_project_knowledge_strip

            render_project_knowledge_strip(project.id, compact=True, show_known_unknown=True)
        if has_history:
            if state is not None:
                st.divider()
            st.markdown("**知识演进**")
            render_knowledge_state_history_timeline(
                history,
                key_prefix=f"{key_prefix}_ks_{project.id}",
            )
        if has_events:
            if state is not None or has_history:
                st.divider()
            st.markdown("**意图演进**")
            render_intent_evolution_timeline(
                evolution,
                key_prefix=f"{key_prefix}_{project.id}",
            )


def render_knowledge_state_history_timeline(
    history,
    *,
    key_prefix: str = "ks_hist",
    limit: int = 24,
) -> None:
    """Render KnowledgeStateHistory snapshots oldest → newest."""
    from archium.domain.intent.knowledge_state_history import KnowledgeStateHistory

    if history is None:
        st.caption("尚无知识演进快照。")
        return
    if not isinstance(history, KnowledgeStateHistory):
        try:
            history = KnowledgeStateHistory.model_validate(history)
        except Exception:
            st.caption("知识演进数据不可用。")
            return
    snaps = list(history.snapshots)
    if not snaps:
        st.caption("尚无知识演进快照。评估或补充资料后会出现。")
        return

    visible = snaps[-limit:] if len(snaps) > limit else snaps
    if len(snaps) > limit:
        st.caption(f"共 {len(snaps)} 个版本，显示最近 {limit} 个")
    else:
        st.caption(f"共 {len(snaps)} 个版本")

    for index, snap in enumerate(visible):
        reason_key = (
            snap.reason.value if hasattr(snap.reason, "value") else str(snap.reason)
        )
        reason_label = _KS_REASON_LABELS.get(reason_key, reason_key)
        when = format_intent_event_time(snap.at)
        st.markdown(f"**`{snap.version_label}`** · {reason_label} · `{when}`")
        st.markdown(snap.summary.strip() or snap.milestone or "知识状态更新")
        if snap.added_known_keys or snap.resolved_unknown or snap.known:
            with st.expander("当时已知 / 增量", expanded=False, key=f"{key_prefix}_{index}"):
                if snap.added_known_keys:
                    st.caption("新增：" + "、".join(snap.added_known_keys[:8]))
                if snap.resolved_unknown:
                    st.caption("消解未知：" + "、".join(snap.resolved_unknown[:8]))
                for key, value in list(snap.known.items())[:8]:
                    st.caption(f"{key}：{value}")


def _render_timeline_event(event: IntentEvolutionEvent, *, key: str) -> None:
    kind_label = intent_evolution_kind_label(event.kind)
    when = format_intent_event_time(event.at)
    trigger = (event.trigger or "").strip()
    header = f"**{kind_label}** · `{when}`"
    if trigger:
        header = f"**{kind_label}** · {trigger} · `{when}`"
    st.markdown(header)
    st.markdown(event.display_line())
    if event.has_history_edge():
        bits: list[str] = []
        if (event.previous_summary or "").strip() and (event.new_summary or "").strip():
            bits.append(
                f"旧：「{(event.previous_summary or '').strip()}」 → "
                f"新：「{(event.new_summary or '').strip()}」"
            )
        if (event.reason or "").strip():
            bits.append(f"原因：{(event.reason or '').strip()}")
        if event.evidence_refs:
            bits.append("证据：" + "；".join(event.evidence_refs[:4]))
        if bits:
            st.caption(" · ".join(bits))
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
