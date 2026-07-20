"""Streamlit UI for project knowledge and fact provenance."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.domain.enums import DocumentPurpose, InformationOrigin, InformationReliability
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.infrastructure.database.repositories import DocumentRepository
from archium.infrastructure.database.session import get_session

ORIGIN_LABELS = {
    InformationOrigin.USER_UPLOAD: "用户上传",
    InformationOrigin.USER_CONFIRMED: "用户确认",
    InformationOrigin.PUBLIC_RESEARCH: "公开研究",
    InformationOrigin.SYSTEM_INFERENCE: "系统推测",
    InformationOrigin.REFERENCE_CASE: "参考案例",
}

RELIABILITY_LABELS = {
    InformationReliability.CONFIRMED: "已确认",
    InformationReliability.HIGH_CONFIDENCE: "高置信",
    InformationReliability.UNVERIFIED: "待核实",
    InformationReliability.INFERENCE: "推测",
    InformationReliability.CONFLICTING: "冲突",
}

PURPOSE_LABELS = {
    DocumentPurpose.PROJECT_MATERIAL: "项目资料",
    DocumentPurpose.REFERENCE_CASE: "参考案例",
    DocumentPurpose.REFERENCE_STYLE: "参考风格",
    DocumentPurpose.POLICY: "政策规范",
    DocumentPurpose.PUBLIC_RESEARCH: "公开研究",
}


def render_knowledge_panel(project_id: UUID) -> None:
    st.markdown("#### 资料与事实")
    st.caption("区分项目事实、公开资料、参考案例与系统推测；确认后才优先进入正式汇报生成。")

    with get_session() as session:
        service = ProjectKnowledgeService(session)
        view = service.get_view(project_id)
        documents = DocumentRepository(session).list_by_project(project_id)

    if view.gap_report is not None:
        gap_count = view.gap_report.gap_count
        blocking = len(view.gap_report.blocking_gaps)
        cols = st.columns(3)
        cols[0].metric("资料缺口", gap_count)
        cols[1].metric("阻塞项", blocking)
        cols[2].metric("可生成事实", len(view.generation_eligible_items))

        if view.gap_report.gaps:
            with st.expander("资料缺口清单", expanded=blocking > 0):
                for gap in view.gap_report.gaps[:20]:
                    prefix = "🔴" if gap.blocking else "🟡"
                    st.markdown(f"{prefix} **{gap.description}** — {gap.why_it_matters}")

    for section in view.sections:
        if section.key == "gaps":
            continue
        if not section.items:
            continue
        with st.expander(f"{section.title}（{len(section.items)}）", expanded=section.key == "pending"):
            for item in section.items[:30]:
                _render_item_row(item, service_available=True)

    if documents:
        st.markdown("##### 资料角色标记")
        st.caption("将参考案例/风格文件标记为非项目事实，避免进入正式页面。")
        doc_options = {doc.filename: doc.id for doc in documents}
        selected_name = st.selectbox("选择资料", list(doc_options.keys()), key="knowledge_doc_role")
        selected_id = doc_options[selected_name]
        current = documents[[d.filename for d in documents].index(selected_name)]
        current_purpose = current.metadata.get("purpose", DocumentPurpose.PROJECT_MATERIAL.value)
        purpose = st.selectbox(
            "资料角色",
            options=list(PURPOSE_LABELS.keys()),
            format_func=lambda p: PURPOSE_LABELS[p],
            index=list(PURPOSE_LABELS.keys()).index(DocumentPurpose(str(current_purpose)))
            if str(current_purpose) in PURPOSE_LABELS
            else 0,
            key="knowledge_doc_purpose",
        )
        if st.button("保存资料角色", key="save_doc_purpose"):
            with get_session() as session:
                ProjectKnowledgeService(session).set_document_purpose(selected_id, purpose)
            st.success("资料角色已更新")
            st.rerun()

    with st.expander("手动添加知识条目"):
        statement = st.text_area("陈述", key="knowledge_manual_statement")
        origin = st.selectbox(
            "来源",
            options=list(ORIGIN_LABELS.keys()),
            format_func=lambda o: ORIGIN_LABELS[o],
            key="knowledge_manual_origin",
        )
        reliability = st.selectbox(
            "可靠性",
            options=list(RELIABILITY_LABELS.keys()),
            format_func=lambda r: RELIABILITY_LABELS[r],
            key="knowledge_manual_reliability",
        )
        url = st.text_input("外部来源链接（可选）", key="knowledge_manual_url")
        if st.button("添加", key="add_knowledge_item"):
            citations: list[SourceCitation] = []
            if url.strip():
                citations.append(
                    SourceCitation(
                        url=url.strip(),
                        source_title=url.strip(),
                    )
                )
            with get_session() as session:
                ProjectKnowledgeService(session).create_item(
                    project_id,
                    statement=statement,
                    origin=origin,
                    reliability=reliability,
                    source_citations=citations,
                )
            st.success("已添加")
            st.rerun()


def _render_item_row(item: ProjectKnowledgeItem, *, service_available: bool) -> None:
    origin = ORIGIN_LABELS.get(item.origin, item.origin.value)
    reliability = RELIABILITY_LABELS.get(item.reliability, item.reliability.value)
    st.markdown(f"**{item.statement}**")
    st.caption(f"{origin} · {reliability}")
    if item.source_citations:
        for citation in item.source_citations[:2]:
            if citation.url:
                st.caption(f"来源：{citation.source_title or citation.url}")
            elif citation.document_name:
                st.caption(f"来源：{citation.document_name}")
    if item.linked_fact_id and service_available:
        cols = st.columns(2)
        if cols[0].button("确认", key=f"confirm_ki_{item.id}"):
            with get_session() as session:
                from archium.application.fact_ledger_service import FactLedgerService

                FactLedgerService(session).confirm_fact(item.linked_fact_id)
            st.rerun()
        if cols[1].button("驳回", key=f"reject_ki_{item.id}"):
            with get_session() as session:
                from archium.application.fact_ledger_service import FactLedgerService

                FactLedgerService(session).reject_fact(item.linked_fact_id)
            st.rerun()
    elif not item.linked_fact_id and not item.is_rejected and service_available:
        cols = st.columns(2)
        if cols[0].button("确认", key=f"confirm_ki_{item.id}"):
            with get_session() as session:
                ProjectKnowledgeService(session).confirm_item(item.id)
            st.rerun()
        if cols[1].button("驳回", key=f"reject_ki_{item.id}"):
            with get_session() as session:
                ProjectKnowledgeService(session).reject_item(item.id)
            st.rerun()
