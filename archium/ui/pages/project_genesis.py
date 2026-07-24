"""Project genesis — orientation router then pipeline entry."""

from __future__ import annotations

import streamlit as st

from archium.application.project_management_service import ProjectManagementService
from archium.domain.enums import ProjectOriginMode
from archium.domain.intent.entry_intent import EntryIntentResult, EntryOrientation
from archium.exceptions import ValidationError, WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.app_navigation import get_app_page
from archium.ui.components.chrome import render_page_header
from archium.ui.error_handlers import report_user_error
from archium.ui.llm_settings import get_ui_effective_settings

_ORIENTATION_KEY = "genesis_orientation"
_CLASSIFIER_RESULT_KEY = "genesis_classifier_result"

_ORIENTATION_LABELS = {
    EntryOrientation.CONCEPT_EXPLORATION: "以想法为主",
    EntryOrientation.EXISTING_PROJECT: "以现有资料为主",
    EntryOrientation.RESEARCH_PROGRAMMING: "策划与可研",
}


def render() -> None:
    """Guide users to pick a primary orientation, then enter the matching pipeline."""
    render_page_header(
        "开始项目",
        "先选主路径取向：多数项目资料不完整，也很少从零开始——至少有地点、名称或基本思路。",
    )
    st.caption(
        "取向只决定先走哪一侧；之后仍可交叉补充（概念侧可后补资料，资料侧可后补想法）。"
    )

    orientation = _resolve_orientation()
    if orientation is None:
        _render_orientation_chooser()
        _render_classifier_panel()
        return

    _render_selected_banner(orientation)
    if orientation == EntryOrientation.CONCEPT_EXPLORATION:
        _render_concept_form()
    elif orientation == EntryOrientation.RESEARCH_PROGRAMMING:
        _render_programming_form()
    else:
        _render_existing_form()


def _resolve_orientation() -> EntryOrientation | None:
    raw = st.session_state.get(_ORIENTATION_KEY)
    if not raw:
        return None
    try:
        return EntryOrientation(str(raw))
    except ValueError:
        st.session_state.pop(_ORIENTATION_KEY, None)
        return None


def _set_orientation(orientation: EntryOrientation) -> None:
    st.session_state[_ORIENTATION_KEY] = orientation.value


def _render_selected_banner(orientation: EntryOrientation) -> None:
    label = _ORIENTATION_LABELS[orientation]
    cols = st.columns([4, 1])
    cols[0].info(f"当前主路径：{label}")
    if cols[1].button("重选", key="genesis_reselect", use_container_width=True):
        st.session_state.pop(_ORIENTATION_KEY, None)
        st.session_state.pop(_CLASSIFIER_RESULT_KEY, None)
        st.rerun()


def _render_orientation_chooser() -> None:
    st.markdown("### 你更想先从哪边开始？")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**以想法为主**")
        st.caption("一句话思路 + 可选地点/名称；稍后可上传部分资料。")
        if st.button(
            "进入想法路径",
            key="orient_concept",
            type="primary",
            use_container_width=True,
        ):
            _set_orientation(EntryOrientation.CONCEPT_EXPLORATION)
            st.rerun()
    with c2:
        st.markdown("**以现有资料为主**")
        st.caption("有图纸/PDF/照片要整理汇报；资料不必一次齐全。")
        if st.button(
            "进入资料路径",
            key="orient_existing",
            type="primary",
            use_container_width=True,
        ):
            _set_orientation(EntryOrientation.EXISTING_PROJECT)
            st.rerun()
    with c3:
        st.markdown("**策划与可研**")
        st.caption("投资人沟通、功能定位、立项未知项；未必先做方案 PPT。")
        if st.button(
            "进入策划路径",
            key="orient_programming",
            type="primary",
            use_container_width=True,
        ):
            _set_orientation(EntryOrientation.RESEARCH_PROGRAMMING)
            st.rerun()


def _render_classifier_panel() -> None:
    st.markdown("---")
    with st.expander("说不清，描述一下", expanded=False):
        st.caption("用几句话说明现状；系统会建议主路径，你仍可改选。")
        text = st.text_area(
            "项目情况",
            placeholder=(
                "例如：西安某医院改扩建，手头有旧总平与部分照片，"
                "甲方还没说清功能分区，我想先理清汇报结构"
            ),
            height=120,
            key="genesis_classifier_text",
        )
        settings = get_ui_effective_settings()
        if st.button(
            "帮我判断主路径",
            key="genesis_classify",
            use_container_width=True,
            disabled=not settings.llm_configured,
        ):
            if not text.strip():
                st.error("请先描述项目情况")
                return
            if not settings.llm_configured:
                st.error("未配置 LLM。请前往设置，或上方手动选择主路径。")
                return
            from archium.ui.planning_service import classify_entry_intent

            with st.spinner("正在判断主路径…"):
                try:
                    result = classify_entry_intent(text.strip(), settings=settings)
                    st.session_state[_CLASSIFIER_RESULT_KEY] = result.model_dump(mode="json")
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(report_user_error(exc))

        raw = st.session_state.get(_CLASSIFIER_RESULT_KEY)
        if not raw:
            return
        result = EntryIntentResult.model_validate(raw)
        st.markdown(
            f"**建议**：{_ORIENTATION_LABELS[result.orientation]}"
            f"（置信度 {result.confidence:.0%}）"
        )
        if result.rationale:
            st.write(result.rationale)
        if result.suggested_next:
            st.caption(result.suggested_next)
        if result.needs_confirmation:
            st.warning("置信度偏低或无法自动判断，请确认或改选手选。")

        action_cols = st.columns(2)
        if action_cols[0].button(
            "按建议进入",
            key="genesis_accept_classifier",
            type="primary",
            use_container_width=True,
        ):
            _set_orientation(result.orientation)
            st.rerun()
        if action_cols[1].button(
            "清除建议",
            key="genesis_clear_classifier",
            use_container_width=True,
        ):
            st.session_state.pop(_CLASSIFIER_RESULT_KEY, None)
            st.rerun()


def _compose_concept_idea(*, idea: str, location: str, site_name: str) -> str:
    parts = [idea.strip()]
    if location.strip():
        parts.append(f"地点：{location.strip()}")
    if site_name.strip():
        parts.append(f"建筑/场地名称：{site_name.strip()}")
    return "\n".join(parts)


def _render_concept_form() -> None:
    st.markdown(
        "**概念探索** — 以想法为主；地点与名称可选。"
        "资料不完整也没关系，可稍后补充。"
    )
    with st.form("genesis_concept_form"):
        name = st.text_input("项目名称", placeholder="例如：黄土高原文化中心")
        location = st.text_input("地点（可选）", placeholder="例如：陕西关中某乡村")
        site_name = st.text_input(
            "建筑或场地名称（可选）",
            placeholder="例如：原供销社旧址",
        )
        idea = st.text_area(
            "一句话想法",
            placeholder="例如：做一个面向游客和村民的小型书店",
            height=100,
        )
        submit = st.form_submit_button(
            "创建并进入概念探索", type="primary", use_container_width=True
        )
        if submit:
            if not name.strip():
                st.error("请填写项目名称")
                return
            if not idea.strip():
                st.error("请用一句话描述你的想法")
                return
            try:
                from archium.application.exploration_service import ExplorationService
                from archium.infrastructure.llm.factory import create_llm_provider
                from archium.ui.planning_service import start_exploration_session

                composed = _compose_concept_idea(
                    idea=idea, location=location, site_name=site_name
                )
                description_bits = [idea.strip()]
                if location.strip():
                    description_bits.append(f"地点：{location.strip()}")
                if site_name.strip():
                    description_bits.append(site_name.strip())
                settings = get_ui_effective_settings()
                with get_session() as session:
                    project = ProjectManagementService(session).create_project(
                        name.strip(),
                        " · ".join(description_bits),
                        origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
                    )
                    if settings.llm_configured:
                        result = start_exploration_session(
                            session,
                            project.id,
                            composed,
                            settings=settings,
                            enrich=True,
                        )
                    else:
                        result = ExplorationService(
                            session, create_llm_provider(settings), settings=settings
                        ).start_session(
                            project.id,
                            composed,
                            source="genesis",
                            enrich=False,
                        )
                for warning in result.warnings:
                    st.session_state.setdefault("exploration_seed_warnings", []).append(
                        warning
                    )
                st.session_state.selected_project_id = str(project.id)
                st.session_state.genesis_task_description = composed
                st.session_state.pop(_ORIENTATION_KEY, None)
                st.switch_page(get_app_page("concept-exploration"))
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))


def _render_programming_form() -> None:
    st.markdown(
        "**策划与可研** — 面向投资人沟通、功能策划或立项启动；"
        "重点弄清决策背景与未知项，而非空间定稿。"
    )
    with st.form("genesis_programming_form"):
        name = st.text_input("项目名称", placeholder="例如：某文旅综合体前期策划")
        brief = st.text_area(
            "策划任务描述",
            placeholder=(
                "例如：某城市更新地块拟引入文化商业，需梳理功能定位、"
                "投资逻辑与关键未知项，形成投资人沟通提纲"
            ),
            height=120,
        )
        submit = st.form_submit_button(
            "创建并进入项目任务", type="primary", use_container_width=True
        )
        if submit:
            if not name.strip():
                st.error("请填写项目名称")
                return
            if not brief.strip():
                st.error("请描述策划任务")
                return
            try:
                with get_session() as session:
                    project = ProjectManagementService(session).create_project(
                        name.strip(),
                        brief.strip(),
                        origin_mode=ProjectOriginMode.RESEARCH_PROGRAMMING,
                    )
                st.session_state.selected_project_id = str(project.id)
                st.session_state.genesis_task_description = brief.strip()
                st.session_state.mission_step = 1
                st.session_state.pop(_ORIENTATION_KEY, None)
                st.switch_page(get_app_page("project-mission"))
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))


def _render_existing_form() -> None:
    st.markdown(
        "**以现有资料为主** — 上传 PDF、图纸、照片等。"
        "资料不必一次齐全；也可稍后补充想法与任务理解。"
    )
    with st.form("genesis_existing_form"):
        name = st.text_input("项目名称", placeholder="例如：陕西省人民医院改造汇报")
        description = st.text_area(
            "项目背景（可选）",
            placeholder="地点、业主、已知限制或汇报场合…",
            height=80,
        )
        submit = st.form_submit_button(
            "创建并进入资料", type="primary", use_container_width=True
        )
        if submit:
            if not name.strip():
                st.error("请填写项目名称")
                return
            try:
                with get_session() as session:
                    project = ProjectManagementService(session).create_project(
                        name.strip(),
                        description.strip() or None,
                        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
                    )
                st.session_state.selected_project_id = str(project.id)
                st.session_state.pop(_ORIENTATION_KEY, None)
                st.switch_page(get_app_page("materials"))
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(report_user_error(exc))
