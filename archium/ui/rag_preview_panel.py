"""Streamlit panel to preview hybrid RAG retrieval for a project."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.fact_retrieval import match_fact_keys_from_query
from archium.infrastructure.database.session import get_session
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.workspace_service import preview_project_retrieval


def render_rag_preview_panel(project_id: UUID) -> None:
    """Let users test vector + fact + keyword retrieval before generation."""
    st.markdown("#### 检索预览")
    st.caption(
        "测试项目资料会如何进入生成 Context：结构化事实优先，"
        "其次是向量检索片段（含图档语义索引）。"
    )

    query = st.text_input(
        "检索问题 / 汇报意图",
        placeholder="例如：容积率控制指标、总平面图主入口、老院区交通组织",
        key=f"rag_preview_query_{project_id}",
    )
    top_k = st.slider("返回片段数", min_value=3, max_value=24, value=12, key=f"rag_topk_{project_id}")

    if not st.button("预览 Context", key=f"rag_preview_run_{project_id}", use_container_width=True):
        return
    if not query.strip():
        st.warning("请输入检索问题。")
        return

    settings = get_ui_effective_settings()
    with get_session() as session:
        bundle = preview_project_retrieval(
            session,
            project_id,
            query.strip(),
            settings=settings,
            max_chunks=top_k,
        )

    matched_keys = match_fact_keys_from_query(query)
    if matched_keys:
        st.caption("匹配到的标准事实键：" + "、".join(sorted(matched_keys)))

    if bundle.chunks:
        rows = []
        for chunk in bundle.chunks:
            rows.append(
                {
                    "类型": "图档语义" if chunk.content_type == "asset_caption" else "文本",
                    "页码": chunk.page_number or "—",
                    "章节": chunk.section_title or "—",
                    "字数": len(chunk.content),
                    "预览": chunk.content[:100] + ("…" if len(chunk.content) > 100 else ""),
                }
            )
        st.markdown("**命中文档片段**")
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("未检索到文档片段（可检查是否已导入并完成索引）。")

    st.markdown("**组装后的 Prompt Context**")
    st.text_area(
        "context",
        value=bundle.text,
        height=320,
        disabled=True,
        label_visibility="collapsed",
    )
