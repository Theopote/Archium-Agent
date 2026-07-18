"""Clarification panel — known/unknown columns and clarifying questions."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from archium.application.mission_clarification_service import ClarificationReadiness
from archium.domain.enums import (
    AssumptionStatus,
    KnowledgeGapStatus,
    QuestionStatus,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import MissionConstraint
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import (
    answer_clarifying_question,
    answer_knowledge_gap,
    assume_clarifying_question,
    assume_knowledge_gap,
    confirm_project_fact,
    defer_clarifying_question,
    defer_knowledge_gap,
    mark_question_not_applicable,
    reject_project_fact,
)


def render_known_unknown_panel(
    *,
    gaps: list[KnowledgeGap],
    assumptions: list[Assumption],
    facts: list[ProjectFact] | None = None,
    constraints: list[MissionConstraint] | None = None,
    key_prefix: str = "known",
) -> None:
    """Five-column known/unknown view: 已确认 / 推断 / 假设 / 冲突 / 待确认."""
    st.markdown("#### 已知与未知")
    facts = facts or []
    constraints = constraints or []

    confirmed_facts = [f for f in facts if f.is_confirmed]
    inferred_facts = [f for f in facts if f.is_inferred]
    conflicted_facts = [
        f
        for f in facts
        if f.verification_status == VerificationStatus.CONFLICTED or f.conflict_group
    ]
    pending_facts = [
        f
        for f in facts
        if f.verification_status == VerificationStatus.EXTRACTED
        and f not in conflicted_facts
    ]

    confirmed_gaps = [g for g in gaps if g.status == KnowledgeGapStatus.ANSWERED]
    inferred_constraints = [
        c for c in constraints if c.verification_status == VerificationStatus.INFERRED
    ]
    confirmed_constraints = [
        c for c in constraints if c.verification_status == VerificationStatus.USER_CONFIRMED
    ]
    accepted = [a for a in assumptions if a.status == AssumptionStatus.ACCEPTED]
    proposed = [a for a in assumptions if a.status == AssumptionStatus.PROPOSED]
    pending_gaps = [g for g in gaps if g.status == KnowledgeGapStatus.OPEN]
    deferred_gaps = [g for g in gaps if g.status == KnowledgeGapStatus.DEFERRED]
    assumed_gaps = [g for g in gaps if g.status == KnowledgeGapStatus.ASSUMED]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown("**已确认**")
        _render_fact_lines(confirmed_facts)
        for constraint in confirmed_constraints:
            st.write(f"- {constraint.name}: {constraint.value}")
        for gap in confirmed_gaps:
            st.write(f"- {gap.question}")
            if gap.resolution:
                st.caption(gap.resolution)
        if not (confirmed_facts or confirmed_constraints or confirmed_gaps):
            st.caption("暂无")

    with c2:
        st.markdown("**推断**")
        _render_fact_lines(inferred_facts)
        for constraint in inferred_constraints:
            st.write(f"- {constraint.name}: {constraint.value}")
            st.caption("推断约束")
        if not (inferred_facts or inferred_constraints):
            st.caption("暂无")

    with c3:
        st.markdown("**假设**")
        items = accepted or proposed
        if items:
            for assumption in items:
                st.write(f"- {assumption.statement}")
                st.caption(assumption.reason)
        for gap in assumed_gaps:
            st.write(f"- {gap.question}")
            if gap.resolution:
                st.caption(f"按假设：{gap.resolution}")
        if not (items or assumed_gaps):
            st.caption("暂无")

    with c4:
        st.markdown("**冲突**")
        if conflicted_facts:
            for fact in conflicted_facts:
                st.write(f"- {fact.label}: {_fact_value(fact)}")
                st.caption(f"组：{fact.conflict_group or '—'}")
                b1, b2 = st.columns(2)
                if b1.button(
                    "确认",
                    key=f"{key_prefix}_conflict_confirm_{fact.id}",
                    use_container_width=True,
                ):
                    fid = fact.id
                    _run(lambda s, fid=fid: confirm_project_fact(s, fid))
                if b2.button(
                    "驳回",
                    key=f"{key_prefix}_conflict_reject_{fact.id}",
                    use_container_width=True,
                ):
                    fid = fact.id
                    _run(lambda s, fid=fid: reject_project_fact(s, fid))
        else:
            st.caption("暂无")

    with c5:
        st.markdown("**待确认**")
        for fact in pending_facts:
            st.write(f"- {fact.label}: {_fact_value(fact)}")
            b1, b2 = st.columns(2)
            if b1.button(
                "确认",
                key=f"{key_prefix}_pending_confirm_{fact.id}",
                use_container_width=True,
            ):
                fid = fact.id
                _run(lambda s, fid=fid: confirm_project_fact(s, fid))
            if b2.button(
                "驳回",
                key=f"{key_prefix}_pending_reject_{fact.id}",
                use_container_width=True,
            ):
                fid = fact.id
                _run(lambda s, fid=fid: reject_project_fact(s, fid))
        for gap in pending_gaps:
            flag = "阻塞 · " if gap.blocking else ""
            st.write(f"- {flag}{gap.question}")
            assume_text = st.text_input(
                "假设内容",
                key=f"{key_prefix}_gap_assume_{gap.id}",
                placeholder="填写后点「按假设推进」",
                label_visibility="collapsed",
            )
            a1, a2, a3 = st.columns(3)
            if a1.button(
                "回答",
                key=f"{key_prefix}_gap_answer_{gap.id}",
                use_container_width=True,
            ):
                # Reuse assume field as short answer when answering inline
                g_id, text = gap.id, assume_text
                if text.strip():
                    _run(lambda s, g_id=g_id, text=text: answer_knowledge_gap(s, g_id, text))
                else:
                    st.warning("请先填写回答内容")
            if a2.button(
                "按假设",
                key=f"{key_prefix}_gap_assume_btn_{gap.id}",
                use_container_width=True,
            ):
                g_id, text = gap.id, assume_text
                if text.strip():
                    _run(lambda s, g_id=g_id, text=text: assume_knowledge_gap(s, g_id, text))
                else:
                    st.warning("请先填写假设内容")
            if a3.button(
                "暂缓",
                key=f"{key_prefix}_gap_defer_{gap.id}",
                use_container_width=True,
                disabled=gap.blocking,
            ):
                g_id = gap.id
                _run(lambda s, g_id=g_id: defer_knowledge_gap(s, g_id))
        for gap in deferred_gaps:
            st.caption(f"暂不确定：{gap.question}")
        if not (pending_facts or pending_gaps or deferred_gaps):
            st.caption("暂无")


def render_clarification_panel(
    questions: list[ClarifyingQuestion],
    *,
    readiness: ClarificationReadiness | None = None,
    key_prefix: str = "clarify",
) -> None:
    st.markdown("#### 关键问题")
    if readiness is not None:
        if readiness.can_continue:
            st.success("阻塞项已处理，可以继续工作路径规划。")
        else:
            names = [q.question for q in readiness.open_blocking_questions[:3]]
            st.warning("仍有阻塞性问题待处理：" + "；".join(names))

    open_questions = [q for q in questions if q.status == QuestionStatus.OPEN][:5]
    resolved = [q for q in questions if q.status != QuestionStatus.OPEN]

    if not open_questions and not resolved:
        st.caption("当前没有关键问题。")
        return

    if not open_questions:
        st.info("开放问题已全部处理。")

    for question in open_questions:
        with st.container(border=True):
            badge = "阻塞" if question.blocking else "可选"
            st.markdown(f"**{question.question}** · `{badge}`")
            st.caption(question.why_asked)
            if question.suggested_assumption:
                st.caption(f"建议假设：{question.suggested_assumption}")

            answer = st.text_input(
                "回答",
                key=f"{key_prefix}_answer_{question.id}",
                placeholder="填写你的回答",
            )
            b1, b2, b3, b4 = st.columns(4)
            if b1.button(
                "回答",
                key=f"{key_prefix}_btn_answer_{question.id}",
                use_container_width=True,
            ):
                qid, ans = question.id, answer
                _run(lambda s, qid=qid, ans=ans: answer_clarifying_question(s, qid, ans))
            if b2.button(
                "采用建议假设",
                key=f"{key_prefix}_btn_assume_{question.id}",
                use_container_width=True,
                disabled=not (question.suggested_assumption or question.can_assume),
            ):
                qid = question.id
                _run(lambda s, qid=qid: assume_clarifying_question(s, qid))
            if b3.button(
                "暂不确定",
                key=f"{key_prefix}_btn_defer_{question.id}",
                use_container_width=True,
                disabled=question.blocking,
            ):
                qid = question.id
                _run(lambda s, qid=qid: defer_clarifying_question(s, qid))
            if b4.button(
                "本项目不适用",
                key=f"{key_prefix}_btn_na_{question.id}",
                use_container_width=True,
            ):
                qid = question.id
                _run(lambda s, qid=qid: mark_question_not_applicable(s, qid))

    if resolved:
        with st.expander(f"已处理问题（{len(resolved)}）", expanded=False):
            for question in resolved:
                st.write(f"- [{question.status.value}] {question.question}")
                if question.answer is not None:
                    st.caption(str(question.answer))


def _render_fact_lines(facts: list[ProjectFact]) -> None:
    for fact in facts:
        st.write(f"- {fact.label}: {_fact_value(fact)}")


def _fact_value(fact: ProjectFact) -> str:
    unit = f" {fact.unit}" if fact.unit else ""
    return f"{fact.value}{unit}"


def _run(action: Callable) -> None:
    try:
        with get_session() as session:
            action(session)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
