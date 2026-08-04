"""Streamlit panel to preview hybrid RAG retrieval for a project."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.application.fact_retrieval import match_fact_keys_from_query
from archium.application.knowledge_fusion import KnowledgeFusionService
from archium.application.unit_of_work import unit_of_work
from archium.domain.knowledge_reference import KnowledgeSourceKind
from archium.ui.llm_settings import get_ui_effective_settings
from archium.ui.workspace_service import preview_project_retrieval

_KIND_LABELS = {
    KnowledgeSourceKind.FACT: "事实",
    KnowledgeSourceKind.DOCUMENT_CHUNK: "文档",
    KnowledgeSourceKind.KNOWLEDGE_ITEM: "设计知识",
    KnowledgeSourceKind.ARCHITECTURE_CASE: "案例",
    KnowledgeSourceKind.GRAPH_NODE: "图谱",
    KnowledgeSourceKind.MULTIMODAL_ASSET: "多模态",
}


def render_rag_preview_panel(project_id: UUID) -> None:
    """Let users test vector + fact + keyword + knowledge-space retrieval."""
    st.markdown("#### 检索预览")
    st.caption(
        "测试项目知识空间：事实 / 文档 / 设计知识 / 图谱扩展 / 多模态图档，"
        "再看组装进 Prompt 的 Context。"
    )

    query = st.text_input(
        "检索问题 / 汇报意图",
        placeholder="例如：容积率控制指标、总平面图主入口、院落空间策略",
        key=f"rag_preview_query_{project_id}",
    )
    top_k = st.slider("返回片段数", min_value=3, max_value=24, value=12, key=f"rag_topk_{project_id}")

    if not st.button("预览 Context", key=f"rag_preview_run_{project_id}", use_container_width=True):
        return
    if not query.strip():
        st.warning("请输入检索问题。")
        return

    settings = get_ui_effective_settings()
    with unit_of_work() as uow:
        bundle = preview_project_retrieval(
            uow,
            project_id,
            query.strip(),
            settings=settings,
            max_chunks=top_k,
        )
        fusion_refs = []
        if getattr(settings, "knowledge_fusion_enabled", True):
            try:
                fusion_refs = KnowledgeFusionService(uow, settings=settings).retrieve(
                    project_id,
                    query.strip(),
                    top_k=min(16, top_k + 4),
                )
            except Exception:
                fusion_refs = []

    matched_keys = match_fact_keys_from_query(query)
    if matched_keys:
        st.caption("匹配到的标准事实键：" + "、".join(sorted(matched_keys)))

    if fusion_refs:
        st.markdown("**项目知识空间 · KnowledgeReference**")
        rows = []
        for ref in fusion_refs:
            rows.append(
                {
                    "来源": _KIND_LABELS.get(ref.source_kind, ref.source_kind.value),
                    "用途": ref.usage.value,
                    "标题": (ref.title or "")[:40],
                    "sim": round(ref.similarity, 2),
                    "auth": round(ref.authority, 2),
                    "xfer": round(ref.transferability, 2),
                    "rel": round(ref.relevance, 2),
                    "预览": ref.content[:80] + ("…" if len(ref.content) > 80 else ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        kind_counts: dict[str, int] = {}
        for ref in fusion_refs:
            label = _KIND_LABELS.get(ref.source_kind, ref.source_kind.value)
            kind_counts[label] = kind_counts.get(label, 0) + 1
        st.caption(
            "通道分布："
            + " · ".join(f"{name} {count}" for name, count in sorted(kind_counts.items()))
        )

    if bundle.chunks:
        rows = []
        for chunk in bundle.chunks:
            arch = chunk.metadata.get("architectural_type")
            if not arch:
                arch_attr = getattr(chunk, "architectural_type", None)
                if arch_attr is not None and hasattr(arch_attr, "value"):
                    arch = arch_attr.value
                else:
                    arch = arch_attr
            arch_cell: float | str = arch if isinstance(arch, (float, str)) else (str(arch) if arch is not None else "")
            rows.append(
                {
                    "类型": "图档语义" if chunk.content_type == "asset_caption" else "文本",
                    "建筑块": arch_cell or "—",
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
