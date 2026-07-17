"""Streamlit UI for document chunk preview and editing."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.chunk_service import ChunkService
from archium.infrastructure.database.session import get_session
from archium.ui.workspace_service import list_project_documents


def render_chunk_panel(project_id: UUID) -> None:
    """Render chunk preview and manual edit controls."""
    st.markdown("#### 资料片段")
    st.caption("预览并编辑语义分块结果；保存后会同步更新向量索引。")

    with get_session() as session:
        documents = list_project_documents(session, project_id)

    if not documents:
        st.caption("导入资料后可在此查看与编辑文本片段。")
        return

    labels = {str(document.id): document.filename for document in documents}
    selected_id = st.selectbox(
        "选择资料文件",
        options=list(labels.keys()),
        format_func=lambda value: labels[value],
        key=f"chunk_doc_{project_id}",
    )
    document_id = UUID(selected_id)

    with get_session() as session:
        chunks = ChunkService(session).list_document_chunks(document_id)

    if not chunks:
        st.info("该文件尚无文本片段。")
        return

    preview_rows = [
        {
            "序号": chunk.chunk_index,
            "页码": chunk.page_number or "-",
            "章节": chunk.section_title or "",
            "策略": chunk.metadata.get("chunk_strategy", "semantic"),
            "字数": len(chunk.content),
            "内容预览": chunk.content[:120] + ("…" if len(chunk.content) > 120 else ""),
        }
        for chunk in chunks
    ]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    with st.expander("编辑片段内容", expanded=False):
        chunk_labels = {
            str(chunk.id): f"#{chunk.chunk_index} · p.{chunk.page_number or '?'} · {chunk.content[:40]}…"
            for chunk in chunks
        }
        chunk_id = st.selectbox(
            "选择片段",
            options=list(chunk_labels.keys()),
            format_func=lambda value: chunk_labels[value],
            key=f"chunk_edit_select_{project_id}",
        )
        selected = next(item for item in chunks if str(item.id) == chunk_id)
        section_title = st.text_input("章节标题", value=selected.section_title or "")
        content = st.text_area("片段内容", value=selected.content, height=220)
        if st.button("保存片段修改", key=f"save_chunk_{chunk_id}"):
            if not content.strip():
                st.error("片段内容不能为空。")
                return
            with get_session() as session:
                ChunkService(session).update_chunk(
                    UUID(chunk_id),
                    content=content,
                    section_title=section_title,
                )
            st.success("片段已保存，向量索引已更新。")
            st.rerun()
