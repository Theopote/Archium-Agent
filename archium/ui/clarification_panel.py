"""Clarification panel — known/unknown overview + tabs, and clarifying questions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

_TAB_CONFIRMED = "已确认"
_TAB_INFERRED = "推断"
_TAB_ASSUMED = "假设"
_TAB_CONFLICT = "冲突"
_TAB_PENDING = "待确认"


@dataclass
class _KnownUnknownBuckets:
    confirmed_facts: list[ProjectFact]
    confirmed_constraints: list[MissionConstraint]
    confirmed_gaps: list[KnowledgeGap]
    inferred_facts: list[ProjectFact]
    inferred_constraints: list[MissionConstraint]
    assumptions: list[Assumption]
    assumed_gaps: list[KnowledgeGap]
    conflicted_facts: list[ProjectFact]
    pending_facts: list[ProjectFact]
    pending_gaps: list[KnowledgeGap]
    deferred_gaps: list[KnowledgeGap]

    @property
    def counts(self) -> dict[str, int]:
        return {
            _TAB_CONFIRMED: (
                len(self.confirmed_facts)
                + len(self.confirmed_constraints)
                + len(self.confirmed_gaps)
            ),
            _TAB_INFERRED: len(self.inferred_facts) + len(self.inferred_constraints),
            _TAB_ASSUMED: len(self.assumptions) + len(self.assumed_gaps),
            _TAB_CONFLICT: len(self.conflicted_facts),
            _TAB_PENDING: (
                len(self.pending_facts) + len(self.pending_gaps) + len(self.deferred_gaps)
            ),
        }


def render_known_unknown_panel(
    *,
    gaps: list[KnowledgeGap],
    assumptions: list[Assumption],
    facts: list[ProjectFact] | None = None,
    constraints: list[MissionConstraint] | None = None,
    key_prefix: str = "known",
) -> None:
    """Known/unknown panel: status overview + tabs (default), optional wide columns."""
    st.markdown("#### 已知与未知")
    buckets = _build_buckets(
        gaps=gaps,
        assumptions=assumptions,
        facts=facts or [],
        constraints=constraints or [],
    )
    counts = buckets.counts

    _render_status_overview(counts)

    layout_key = f"{key_prefix}_layout_mode"
    layout = st.segmented_control(
        "展示方式",
        options=["标签页", "并排（宽屏）"],
        default="标签页",
        key=layout_key,
        label_visibility="collapsed",
        help="普通屏幕推荐标签页；超宽屏可切换并排五列。",
    )
    if layout is None:
        layout = "标签页"

    if layout == "并排（宽屏）":
        cols = st.columns(5)
        with cols[0]:
            st.markdown(f"**{_TAB_CONFIRMED}（{counts[_TAB_CONFIRMED]}）**")
            _render_confirmed_bucket(buckets)
        with cols[1]:
            st.markdown(f"**{_TAB_INFERRED}（{counts[_TAB_INFERRED]}）**")
            _render_inferred_bucket(buckets)
        with cols[2]:
            st.markdown(f"**{_TAB_ASSUMED}（{counts[_TAB_ASSUMED]}）**")
            _render_assumed_bucket(buckets)
        with cols[3]:
            st.markdown(f"**{_TAB_CONFLICT}（{counts[_TAB_CONFLICT]}）**")
            _render_conflict_bucket(buckets, key_prefix=key_prefix)
        with cols[4]:
            st.markdown(f"**{_TAB_PENDING}（{counts[_TAB_PENDING]}）**")
            _render_pending_bucket(buckets, key_prefix=key_prefix)
        return

    labels = [
        f"{_TAB_CONFIRMED}（{counts[_TAB_CONFIRMED]}）",
        f"{_TAB_INFERRED}（{counts[_TAB_INFERRED]}）",
        f"{_TAB_ASSUMED}（{counts[_TAB_ASSUMED]}）",
        f"{_TAB_CONFLICT}（{counts[_TAB_CONFLICT]}）",
        f"{_TAB_PENDING}（{counts[_TAB_PENDING]}）",
    ]
    tabs = st.tabs(labels)
    with tabs[0]:
        _render_confirmed_bucket(buckets)
    with tabs[1]:
        _render_inferred_bucket(buckets)
    with tabs[2]:
        _render_assumed_bucket(buckets)
    with tabs[3]:
        _render_conflict_bucket(buckets, key_prefix=key_prefix)
    with tabs[4]:
        _render_pending_bucket(buckets, key_prefix=key_prefix)

    if counts[_TAB_CONFLICT] or counts[_TAB_PENDING]:
        st.caption(
            "提示：有冲突或待确认项时，请先打开对应标签处理，再继续回答关键问题。"
        )


def _render_status_overview(counts: dict[str, int]) -> None:
    parts = [
        f"已确认 **{counts[_TAB_CONFIRMED]}**",
        f"推断 **{counts[_TAB_INFERRED]}**",
        f"假设 **{counts[_TAB_ASSUMED]}**",
        f"冲突 **{counts[_TAB_CONFLICT]}**",
        f"待确认 **{counts[_TAB_PENDING]}**",
    ]
    st.markdown(" · ".join(parts))


def _build_buckets(
    *,
    gaps: list[KnowledgeGap],
    assumptions: list[Assumption],
    facts: list[ProjectFact],
    constraints: list[MissionConstraint],
) -> _KnownUnknownBuckets:
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
    accepted = [a for a in assumptions if a.status == AssumptionStatus.ACCEPTED]
    proposed = [a for a in assumptions if a.status == AssumptionStatus.PROPOSED]
    return _KnownUnknownBuckets(
        confirmed_facts=[f for f in facts if f.is_confirmed],
        confirmed_constraints=[
            c for c in constraints if c.verification_status == VerificationStatus.USER_CONFIRMED
        ],
        confirmed_gaps=[g for g in gaps if g.status == KnowledgeGapStatus.ANSWERED],
        inferred_facts=[f for f in facts if f.is_inferred],
        inferred_constraints=[
            c for c in constraints if c.verification_status == VerificationStatus.INFERRED
        ],
        assumptions=accepted or proposed,
        assumed_gaps=[g for g in gaps if g.status == KnowledgeGapStatus.ASSUMED],
        conflicted_facts=conflicted_facts,
        pending_facts=pending_facts,
        pending_gaps=[g for g in gaps if g.status == KnowledgeGapStatus.OPEN],
        deferred_gaps=[g for g in gaps if g.status == KnowledgeGapStatus.DEFERRED],
    )


def _render_confirmed_bucket(buckets: _KnownUnknownBuckets) -> None:
    _render_fact_lines(buckets.confirmed_facts)
    for constraint in buckets.confirmed_constraints:
        st.write(f"- {constraint.name}: {constraint.value}")
    for gap in buckets.confirmed_gaps:
        st.write(f"- {gap.question}")
        if gap.resolution:
            st.caption(gap.resolution)
    if not (
        buckets.confirmed_facts or buckets.confirmed_constraints or buckets.confirmed_gaps
    ):
        st.caption("暂无已确认项")


def _render_inferred_bucket(buckets: _KnownUnknownBuckets) -> None:
    _render_fact_lines(buckets.inferred_facts)
    for constraint in buckets.inferred_constraints:
        st.write(f"- {constraint.name}: {constraint.value}")
        st.caption("推断约束")
    if not (buckets.inferred_facts or buckets.inferred_constraints):
        st.caption("暂无推断项")


def _render_assumed_bucket(buckets: _KnownUnknownBuckets) -> None:
    for assumption in buckets.assumptions:
        st.write(f"- {assumption.statement}")
        st.caption(assumption.reason)
    for gap in buckets.assumed_gaps:
        st.write(f"- {gap.question}")
        if gap.resolution:
            st.caption(f"按假设：{gap.resolution}")
    if not (buckets.assumptions or buckets.assumed_gaps):
        st.caption("暂无假设项")


def _render_conflict_bucket(buckets: _KnownUnknownBuckets, *, key_prefix: str) -> None:
    if not buckets.conflicted_facts:
        st.caption("暂无冲突项")
        return
    for fact in buckets.conflicted_facts:
        with st.container(border=True):
            st.write(f"**{fact.label}**: {_fact_value(fact)}")
            st.caption(f"冲突组：{fact.conflict_group or '—'}")
            b1, b2 = st.columns(2)
            if b1.button(
                "确认此项",
                key=f"{key_prefix}_conflict_confirm_{fact.id}",
                use_container_width=True,
            ):
                fid = fact.id
                _run(lambda s, fid=fid: confirm_project_fact(s, fid))
            if b2.button(
                "驳回此项",
                key=f"{key_prefix}_conflict_reject_{fact.id}",
                use_container_width=True,
            ):
                fid = fact.id
                _run(lambda s, fid=fid: reject_project_fact(s, fid))


def _render_pending_bucket(buckets: _KnownUnknownBuckets, *, key_prefix: str) -> None:
    if not (buckets.pending_facts or buckets.pending_gaps or buckets.deferred_gaps):
        st.caption("暂无待确认项")
        return

    for fact in buckets.pending_facts:
        with st.container(border=True):
            st.write(f"**{fact.label}**: {_fact_value(fact)}")
            st.caption("资料提取，待你确认或驳回")
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

    for gap in buckets.pending_gaps:
        with st.container(border=True):
            flag = "阻塞 · " if gap.blocking else ""
            st.write(f"**{flag}{gap.question}**")
            if gap.why_it_matters:
                st.caption(gap.why_it_matters)
            assume_text = st.text_input(
                "回答或假设",
                key=f"{key_prefix}_gap_assume_{gap.id}",
                placeholder="填写后选择下方操作",
            )
            a1, a2, a3 = st.columns(3)
            if a1.button(
                "回答",
                key=f"{key_prefix}_gap_answer_{gap.id}",
                use_container_width=True,
            ):
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

    if buckets.deferred_gaps:
        st.markdown("**已暂缓**")
        for gap in buckets.deferred_gaps:
            st.caption(f"暂不确定：{gap.question}")


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
