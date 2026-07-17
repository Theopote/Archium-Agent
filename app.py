"""
Archium（阿基姆）— Streamlit Web 前端
"""

import os
import shutil
import threading
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv, set_key

from archium.config import get_settings
from archium.logging import setup_logging
from main import ExecutionReport, StepResult, run_instruction

load_dotenv()
setup_logging(get_settings())

ENV_PATH = Path(__file__).resolve().parent / ".env"
PROJECT_ROOT = Path(__file__).resolve().parent

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="Archium · 阿基姆",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 建筑极简风格 CSS ──────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1a1a1a;
}

[data-testid="stSidebar"] {
    background-color: #f7f6f3;
    border-right: 1px solid #e8e6e1;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}

.archium-logo {
    font-size: 1.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #1a1a1a;
    margin-bottom: 0.15rem;
}

.archium-sub {
    font-size: 0.78rem;
    font-weight: 300;
    letter-spacing: 0.06em;
    color: #8a8780;
    margin-bottom: 2rem;
}

.status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.55rem 0;
    border-bottom: 1px solid #eceae4;
    font-size: 0.85rem;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.dot-green  { background: #4a9e6e; box-shadow: 0 0 6px #4a9e6e88; }
.dot-yellow { background: #c4a035; box-shadow: 0 0 6px #c4a03588; }
.dot-red    { background: #c45c5c; box-shadow: 0 0 6px #c45c5c88; }

.section-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #aaa8a2;
    margin: 1.5rem 0 0.6rem 0;
}

[data-testid="stChatMessage"] {
    border-bottom: 1px solid #f0eeea;
    padding-bottom: 1rem;
}

div[data-testid="stChatInput"] textarea {
    border: 1px solid #ddd9d0 !important;
    border-radius: 2px !important;
    background: #fafaf8 !important;
}

.stDownloadButton button {
    border: 1px solid #1a1a1a !important;
    background: transparent !important;
    color: #1a1a1a !important;
    border-radius: 2px !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.04em;
}
</style>
""",
    unsafe_allow_html=True,
)


# ── 状态检测 ──────────────────────────────────────────────
def _module_status_ppt() -> tuple[str, str]:
    settings = get_settings()

    if not settings.llm_configured:
        return "red", "缺少 API Key"
    if not shutil.which(settings.marp_command):
        return "yellow", "待安装 Marp CLI"
    return "green", "就绪"


def _module_status_file_manager() -> tuple[str, str]:
    settings = get_settings()

    if not settings.llm_configured:
        return "red", "缺少 API Key"
    return "green", "就绪"


def _module_status_discord() -> tuple[str, str]:
    token = st.session_state.get("discord_token") or os.getenv("DISCORD_BOT_TOKEN", "")
    user_id = os.getenv("DISCORD_USER_ID", "")
    if st.session_state.get("discord_running"):
        return "green", "运行中"
    if token and user_id:
        return "yellow", "已配置 · 未启动"
    if token:
        return "yellow", "缺少 User ID"
    return "red", "未配置 Token"


def _render_status(name: str, color: str, hint: str) -> None:
    st.markdown(
        f'<div class="status-row">'
        f'<span>{name}</span>'
        f'<span><span class="status-dot dot-{color}"></span>{hint}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _save_discord_token(token: str) -> None:
    os.environ["DISCORD_BOT_TOKEN"] = token
    st.session_state.discord_token = token
    if ENV_PATH.exists() and token:
        set_key(str(ENV_PATH), "DISCORD_BOT_TOKEN", token)


def _start_discord_background() -> None:
    if st.session_state.get("discord_running"):
        return
    token = st.session_state.get("discord_token") or os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        raise ValueError("请先在侧边栏填写 Discord Bot Token")
    if not os.getenv("DISCORD_USER_ID"):
        raise ValueError("请在 .env 中设置 DISCORD_USER_ID")

    os.environ["DISCORD_BOT_TOKEN"] = token

    def _run_bot() -> None:
        import discord_watcher

        discord_watcher.run()

    thread = threading.Thread(target=_run_bot, daemon=True)
    thread.start()
    st.session_state.discord_running = True
    st.session_state.discord_thread_started = True


def _format_report_markdown(report: ExecutionReport) -> str:
    parts: list[str] = [f"**理解：** {report.summary}"]

    if not report.plan_labels:
        parts.append("\n未匹配到可执行工具。请描述具体任务，例如整理文件夹或生成 PPT。")
        return "\n\n".join(parts)

    parts.append(f"\n**执行计划（{len(report.plan_labels)} 步）：**")
    for i, label in enumerate(report.plan_labels, 1):
        parts.append(f"{i}. {label}")

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
    shown: set[str] = set()
    for result in results:
        for fp in result.file_paths:
            path = Path(fp)
            if not path.is_file() or str(path) in shown:
                continue
            shown.add(str(path))
            suffix = path.suffix.lower()
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"📎 `{path}`")
            with col2:
                with path.open("rb") as f:
                    mime = (
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        if suffix == ".pptx"
                        else "application/pdf"
                        if suffix == ".pdf"
                        else "application/octet-stream"
                    )
                    st.download_button(
                        label="下载",
                        data=f.read(),
                        file_name=path.name,
                        mime=mime,
                        key=f"dl_{path.name}_{path.stat().st_mtime_ns}",
                    )


def _process_instruction(instruction: str) -> ExecutionReport:
    return run_instruction(instruction, discord_runner=_start_discord_background)


# ── Session 初始化 ────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "你好，我是 **Archium（阿基姆）**——你的架构与知识管理智能体。\n\n"
                "你可以用自然语言告诉我需要做什么，例如：\n"
                "- 整理 `~/Downloads` 文件夹\n"
                "- 做一份本周项目进度 PPT\n"
                "- 启动 Discord 消息守卫"
            ),
            "artifacts": [],
        }
    ]

if "discord_token" not in st.session_state:
    st.session_state.discord_token = os.getenv("DISCORD_BOT_TOKEN", "")

if "discord_running" not in st.session_state:
    st.session_state.discord_running = False


# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="archium-logo">Archium</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="archium-sub">Architecture × Museum · 阿基姆</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">Module Status</div>', unsafe_allow_html=True)

    ppt_c, ppt_h = _module_status_ppt()
    fm_c, fm_h = _module_status_file_manager()
    dc_c, dc_h = _module_status_discord()

    _render_status("📊 PPT 生成器", ppt_c, ppt_h)
    _render_status("📂 文件管家", fm_c, fm_h)
    _render_status("🤖 Discord 守卫", dc_c, dc_h)

    st.markdown('<div class="section-label">Settings</div>', unsafe_allow_html=True)

    token_input = st.text_input(
        "Discord Bot Token",
        value=st.session_state.discord_token,
        type="password",
        placeholder="MTxxxxxx.xxxxxx.xxxxx",
        help="保存后写入 .env，供 Discord 守卫模块使用",
    )
    if token_input != st.session_state.discord_token:
        _save_discord_token(token_input)
        st.toast("Discord Token 已保存", icon="✅")

    if st.button("启动 Discord 守卫", use_container_width=True):
        if not (st.session_state.discord_token or os.getenv("DISCORD_BOT_TOKEN")):
            st.error("请先填写 Discord Bot Token")
        elif not os.getenv("DISCORD_USER_ID"):
            st.error("请在 .env 中设置 DISCORD_USER_ID")
        else:
            _start_discord_background()
            st.toast("Discord 守卫已在后台启动", icon="🤖")
            st.rerun()

    st.markdown(
        '<div style="margin-top:2rem;font-size:0.72rem;color:#bbb9b2;line-height:1.6;">'
        "Archium v0.2<br>建筑 · 归档 · 智能"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Main Chat ─────────────────────────────────────────────
st.markdown("### 指令中心")
st.caption("用自然语言驱动 PPT 生成、文件整理与 Discord 守卫")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🏛️" if msg["role"] == "assistant" else None):
        st.markdown(msg["content"])
        if msg.get("artifacts"):
            _render_file_artifacts(msg["artifacts"])

if prompt := st.chat_input("请输入您的指令…"):
    st.session_state.messages.append({"role": "user", "content": prompt, "artifacts": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🏛️"):
        with st.spinner("Archium 正在思考…"):
            try:
                report = _process_instruction(prompt)
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
