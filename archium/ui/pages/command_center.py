"""Retired Streamlit page — v0.1 command center is no longer part of the product UI.

Legacy CLI remains available from the repo checkout only (not the installed package):

    python -m legacy.main
    python main.py
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    st.markdown("### 指令中心（已退役）")
    st.info(
        "v0.1 自然语言指令中心已从主产品 UI 移除，不再加载 `legacy` 包。\n\n"
        "如需实验 CLI，请在仓库根目录运行：`python -m legacy.main` 或 `python main.py`。\n\n"
        "结构化建筑汇报请使用 **项目** → **制作** 主路径。"
    )
