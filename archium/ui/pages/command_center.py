"""Streamlit legacy command center page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from main import ExecutionReport, StepResult, run_instruction

from archium.ui.components import render_file_downloads


def _module_status_file_manager() -> tuple[str, str]:
    from archium.ui.llm_settings import get_ui_effective_settings

    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        return "red", "缺少 API Key"
    return "green", "就绪"


def _format_report_markdown(report: ExecutionReport) -> str:
    parts: list[str] = [f"**理解：** {report.summary}"]

    if not report.plan_labels:
        parts.append("\n未匹配到可执行工具。请描述具体任务，例如整理文件夹或生成 PPT。")
        return "\n\n".join(parts)

    parts.append(f"\n**执行计划（{len(report.plan_labels)} 步）：**")
    for index, label in enumerate(report.plan_labels, 1):
        parts.append(f"{index}. {label}")

    for result in report.step_results:
        parts.append(f"\n---\n\n### {result.label}")
        icon = "✅" if result.success else "❌"
        parts.append(f"{icon} {'完成' if result.success else '失败'}")
        for line in result.lines:
            parts.append(line)

    if report.success:
        parts.append("\n🎉 **全部任务已完成。**")
    else:
        parts.append("\n⚠️ **任务链中断，请检查上方错误信息。**")

    return "\n\n".join(parts)


def _render_file_artifacts(results: list[StepResult]) -> None:
    paths = [Path(fp) for result in results for fp in result.file_paths]
    render_file_downloads(paths, key_prefix="command_center")


def _init_chat_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "你好，我是 **Archium（阿基姆）**——你的建筑汇报与知识管理智能体。\n\n"
                    "你可以用自然语言告诉我需要做什么，例如：\n"
                    "- 整理 `~/Downloads` 文件夹\n"
                    "- 做一份本周项目进度 PPT\n\n"
                    "如需结构化建筑项目汇报，请使用 **项目工作台**。"
                ),
                "artifacts": [],
            }
        ]


def render() -> None:
    _init_chat_state()
    st.markdown("### 指令中心")
    st.caption("用自然语言驱动 PPT 生成与文件整理（v0.1 遗留路径）")

    _fm_c, fm_h = _module_status_file_manager()
    st.caption(f"文件管家：{fm_h}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🏛️" if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])
            if msg.get("artifacts"):
                _render_file_artifacts(msg["artifacts"])

    if prompt := st.chat_input("请输入您的指令…"):
        st.session_state.messages.append({"role": "user", "content": prompt, "artifacts": []})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🏛️"), st.spinner("Archium 正在思考…"):
            try:
                report = run_instruction(prompt)
                reply = _format_report_markdown(report)
                st.markdown(reply)
                if report.step_results:
                    _render_file_artifacts(report.step_results)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": reply,
                        "artifacts": report.step_results,
                    }
                )
            except Exception as exc:
                err = f"❌ 执行出错：{exc}"
                st.error(err)
                st.session_state.messages.append(
                    {"role": "assistant", "content": err, "artifacts": []}
                )
