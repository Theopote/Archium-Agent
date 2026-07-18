"""Clarification panel — known/unknown columns and clarifying questions."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from archium.application.mission_clarification_service import ClarificationReadiness
from archium.domain.enums import AssumptionStatus, KnowledgeGapStatus, QuestionStatus
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import (
    answer_clarifying_question,
    assume_clarifying_question,
    defer_clarifying_question,
    mark_question_not_applicable,
)


def render_known_unknown_panel(
    *,
    gaps: list[KnowledgeGap],
    assumptions: list[Assumption],
) -> None:
    st.markdown("#### 已知与未知")
    confirmed = [
        g for g in gaps if g.status in {KnowledgeGapStatus.ANSWERED, KnowledgeGapStatus.ASSUMED}
    ]
    pending = [g for g in gaps if g.status == KnowledgeGapStatus.OPEN]
    deferred = [g for g in gaps if g.status == KnowledgeGapStatus.DEFERRED]
    accepted = [a for a in assumptions if a.status == AssumptionStatus.ACCEPTED]
    proposed = [a for a in assumptions if a.status == AssumptionStatus.PROPOSED]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**已确认 / 已回答**")
        if confirmed:
            for gap in confirmed:
                st.write(f"- {gap.question}")
                if gap.resolution:
                    st.caption(gap.resolution)
        else:
            st.caption("暂无")
    with c2:
        st.markdown("**假设**")
        items = accepted or proposed
        if items:
            for assumption in items:
                st.write(f"- {assumption.statement}")
                st.caption(assumption.reason)
        else:
            st.caption("暂无")
    with c3:
        st.markdown("**待确认**")
        if pending:
            for gap in pending:
                flag = "阻塞 · " if gap.blocking else ""
                st.write(f"- {flag}{gap.question}")
        else:
            st.caption("暂无")
    with c4:
        st.markdown("**暂不确定**")
        if deferred:
            for gap in deferred:
                st.write(f"- {gap.question}")
        else:
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


def _run(action: Callable) -> None:
    try:
        with get_session() as session:
            action(session)
        st.rerun()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
    except Exception as exc:
        st.error(format_user_error(exc))
