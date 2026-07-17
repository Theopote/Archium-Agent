"""Streamlit UI for the project fact ledger."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.fact_ledger_service import FactLedgerService
from archium.config import get_settings
from archium.domain.enums import VerificationStatus
from archium.infrastructure.database.session import get_session
from archium.infrastructure.llm.factory import create_llm_provider

STATUS_LABELS = {
    VerificationStatus.EXTRACTED: "待确认",
    VerificationStatus.INFERRED: "推断",
    VerificationStatus.USER_CONFIRMED: "已确认",
    VerificationStatus.REJECTED: "已驳回",
    VerificationStatus.CONFLICTED: "冲突",
}


def render_fact_ledger_panel(project_id: UUID) -> None:
    st.markdown("#### 项目事实账本")
    st.caption("结构化项目参数 · 确认后将优先注入 Brief / Storyline / SlideSpec 生成上下文")

    settings = get_settings()
    with get_session() as session:
        service = FactLedgerService(
            session,
            llm=create_llm_provider(settings) if settings.llm_configured else None,
            settings=settings,
        )
        ledger = service.get_ledger(project_id)

    summary_cols = st.columns(4)
    summary_cols[0].metric("已确认", ledger.confirmed_count)
    summary_cols[1].metric("待确认", ledger.pending_count)
    summary_cols[2].metric("冲突", ledger.conflict_count)
    summary_cols[3].metric("标准项缺失", len(ledger.missing_standard_keys))

    if ledger.missing_standard_keys:
        missing_labels = [
            entry.label
            for entry in ledger.entries
            if entry.key in ledger.missing_standard_keys
        ]
        st.info("尚未提取的标准事实：" + "、".join(missing_labels[:8]) + ("…" if len(missing_labels) > 8 else ""))

    rows = []
    for entry in ledger.entries:
        fact = entry.fact
        if fact is None:
            rows.append(
                {
                    "标准项": entry.label,
                    "值": "—",
                    "单位": "",
                    "状态": "缺失",
                    "置信度": "",
                    "冲突组": "",
                }
            )
            continue
        rows.append(
            {
                "标准项": entry.label,
                "值": str(fact.value),
                "单位": fact.unit or "",
                "状态": STATUS_LABELS.get(fact.verification_status, fact.verification_status.value),
                "置信度": f"{fact.confidence:.2f}",
                "冲突组": fact.conflict_group or "",
            }
        )

    for fact in ledger.extra_facts:
        rows.append(
            {
                "标准项": fact.label,
                "值": str(fact.value),
                "单位": fact.unit or "",
                "状态": STATUS_LABELS.get(fact.verification_status, fact.verification_status.value),
                "置信度": f"{fact.confidence:.2f}",
                "冲突组": fact.conflict_group or "",
            }
        )

    if not rows:
        st.caption("运行汇报管线或导入资料后，系统将从文档片段中提取结构化事实。")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)

    editable_facts = [entry.fact for entry in ledger.entries if entry.fact is not None]
    editable_facts.extend(ledger.extra_facts)
    if not editable_facts:
        return

    st.markdown("**人工确认 / 修正**")
    options = {
        str(fact.id): f"{fact.label} · {fact.value}"
        for fact in editable_facts
        if fact.verification_status != VerificationStatus.REJECTED
    }
    if not options:
        st.caption("所有事实均已驳回。")
        return

    selected_id = st.selectbox(
        "选择事实",
        options=list(options.keys()),
        format_func=lambda value: options[value],
        key=f"fact_select_{project_id}",
    )
    selected = next(fact for fact in editable_facts if str(fact.id) == selected_id)

    col1, col2 = st.columns(2)
    new_value = col1.text_input("值", value=str(selected.value), key=f"fact_value_{selected.id}")
    new_unit = col2.text_input("单位", value=selected.unit or "", key=f"fact_unit_{selected.id}")

    btn1, btn2, btn3 = st.columns(3)
    if btn1.button("保存修正", key=f"save_fact_{selected.id}", use_container_width=True):
        with get_session() as session:
            FactLedgerService(session).update_fact(
                selected.id,
                value=new_value.strip(),
                unit=new_unit.strip() or None,
            )
        st.success("事实已更新。")
        st.rerun()

    if btn2.button("确认事实", key=f"confirm_fact_{selected.id}", use_container_width=True):
        with get_session() as session:
            FactLedgerService(session).confirm_fact(selected.id)
        st.success("事实已确认。")
        st.rerun()

    if btn3.button("驳回事实", key=f"reject_fact_{selected.id}", use_container_width=True):
        with get_session() as session:
            FactLedgerService(session).reject_fact(selected.id)
        st.warning("事实已驳回，后续生成将不再引用。")
        st.rerun()
