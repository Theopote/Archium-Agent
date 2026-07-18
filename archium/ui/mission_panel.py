"""Mission understanding panel — structured editable fields, not a single AI blob."""

from __future__ import annotations

import streamlit as st

from archium.application.project_mission_service import MissionPatch
from archium.domain.enums import InterventionScale, TaskNature, UncertaintyLevel
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.error_handlers import format_user_error
from archium.ui.planning_service import update_mission_fields

TASK_NATURE_LABELS = {
    TaskNature.NEW_BUILD: "新建",
    TaskNature.RECONSTRUCTION: "重建",
    TaskNature.RENOVATION: "改造",
    TaskNature.ADAPTIVE_REUSE: "适应性再利用",
    TaskNature.EXPANSION: "扩建",
    TaskNature.RESTORATION: "修复",
    TaskNature.CONSERVATION: "保护",
    TaskNature.URBAN_RENEWAL: "城市更新",
    TaskNature.RESEARCH: "研究",
    TaskNature.PLANNING: "策划",
    TaskNature.CONSULTING: "咨询",
    TaskNature.ASSESSMENT: "评估",
    TaskNature.STRATEGY: "策略",
    TaskNature.DESIGN_REVIEW: "设计评审",
    TaskNature.PRESENTATION_SYNTHESIS: "汇报综合",
    TaskNature.TECHNICAL_STUDY: "技术专题",
    TaskNature.OTHER: "其他",
}

SCALE_LABELS = {
    InterventionScale.REGION: "区域",
    InterventionScale.CITY: "城市",
    InterventionScale.DISTRICT: "片区",
    InterventionScale.CAMPUS: "园区/校园",
    InterventionScale.VILLAGE: "村庄",
    InterventionScale.SITE: "场地",
    InterventionScale.BUILDING_COMPLEX: "建筑群",
    InterventionScale.BUILDING: "单体建筑",
    InterventionScale.FLOOR: "楼层",
    InterventionScale.SPACE: "空间",
    InterventionScale.COMPONENT: "构件/细部",
    InterventionScale.SYSTEM: "系统",
}

UNCERTAINTY_LABELS = {
    UncertaintyLevel.LOW: "低",
    UncertaintyLevel.MEDIUM: "中",
    UncertaintyLevel.HIGH: "高",
    UncertaintyLevel.CRITICAL: "关键",
}


def _lines_to_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_to_lines(items: list[str]) -> str:
    return "\n".join(items)


def render_mission_panel(mission: ProjectMission, *, key_prefix: str = "mission") -> None:
    """Render structured mission understanding with per-field editing."""
    st.markdown("#### 我对任务的理解")
    st.caption(f"{mission.title} · v{mission.version} · 置信度 {mission.confidence:.0%}")

    natures = "、".join(
        TASK_NATURE_LABELS.get(item, item.value) for item in mission.task_natures
    ) or "未标注"
    scales = "、".join(
        SCALE_LABELS.get(item, item.value) for item in mission.intervention_scales
    ) or "未标注"
    depths = "、".join(item.value for item in mission.requested_service_depths) or "未标注"
    domains = "、".join(item.value for item in mission.domains) or "未标注"

    meta1, meta2, meta3, meta4 = st.columns(4)
    meta1.markdown(f"**任务性质**\n\n{natures}")
    meta2.markdown(f"**项目尺度**\n\n{scales}")
    meta3.markdown(f"**服务深度**\n\n{depths}")
    meta4.markdown(
        f"**不确定性**\n\n"
        f"{UNCERTAINTY_LABELS.get(mission.uncertainty_level, mission.uncertainty_level.value)}"
    )
    st.caption(f"领域：{domains}")

    with st.form(f"{key_prefix}_edit_form"):
        title = st.text_input("标题", value=mission.title)
        task_statement = st.text_area("任务陈述", value=mission.task_statement, height=90)
        current_situation = st.text_area(
            "当前情况", value=mission.current_situation or "", height=70
        )
        col_a, col_b = st.columns(2)
        with col_a:
            primary_problems = st.text_area(
                "主要问题（每行一项）",
                value=_list_to_lines(mission.primary_problems),
                height=100,
            )
            in_scope = st.text_area(
                "工作范围（每行一项）",
                value=_list_to_lines(mission.in_scope),
                height=100,
            )
            decisions_required = st.text_area(
                "关键决策（每行一项）",
                value=_list_to_lines(mission.decisions_required),
                height=80,
            )
        with col_b:
            desired_changes = st.text_area(
                "希望产生的改变（每行一项）",
                value=_list_to_lines(mission.desired_changes),
                height=100,
            )
            out_of_scope = st.text_area(
                "不包含内容（每行一项）",
                value=_list_to_lines(mission.out_of_scope),
                height=100,
            )
            design_questions = st.text_area(
                "设计命题（每行一项）",
                value=_list_to_lines(mission.design_questions),
                height=80,
            )

        if mission.stakeholders:
            st.markdown("**利益相关方**")
            for stakeholder in mission.stakeholders:
                concerns = "、".join(stakeholder.concerns) if stakeholder.concerns else "—"
                st.write(f"- {stakeholder.name}（{stakeholder.role}）：关注 {concerns}")

        if mission.known_constraints:
            st.markdown("**已知约束**")
            for constraint in mission.known_constraints:
                st.write(f"- {constraint.name}：{constraint.value}")

        saved = st.form_submit_button("保存修改", use_container_width=True)

    if saved:
        patch = MissionPatch(
            title=title.strip() or None,
            task_statement=task_statement.strip() or None,
            current_situation=current_situation.strip() or None,
            primary_problems=_lines_to_list(primary_problems),
            desired_changes=_lines_to_list(desired_changes),
            in_scope=_lines_to_list(in_scope),
            out_of_scope=_lines_to_list(out_of_scope),
            decisions_required=_lines_to_list(decisions_required),
            design_questions=_lines_to_list(design_questions),
        )
        try:
            with get_session() as session:
                update_mission_fields(session, mission.id, patch)
            st.success("任务理解已更新。")
            st.rerun()
        except WorkflowError as exc:
            st.error(format_user_error(exc))
        except Exception as exc:
            st.error(format_user_error(exc))
