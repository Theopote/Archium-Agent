"""Project membership / role panel (minimal RBAC chrome)."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from archium.domain.access import LOCAL_ACTOR_ID, ProjectRole
from archium.infrastructure.database.session import get_session

_ROLE_LABELS = {
    ProjectRole.OWNER: "负责人",
    ProjectRole.ARCHITECT: "建筑师",
    ProjectRole.REVIEWER: "审阅者",
    ProjectRole.CLIENT: "甲方 / 客户",
}


def render_project_members_panel(
    project_id: UUID,
    *,
    key_prefix: str = "members",
    expanded: bool = False,
) -> None:
    """List members and allow Owner to add a role (single-user ready)."""
    from archium.application.project_access_service import ProjectAccessService
    from archium.exceptions import AccessDeniedError

    with get_session() as session:
        access = ProjectAccessService(session)
        access.ensure_default_owner(project_id)
        members = access.list_members(project_id)

    with st.expander("项目成员与角色", expanded=expanded):
        st.caption("Owner / Architect / Reviewer / Client — 本地单用户默认已是负责人。")
        if not members:
            st.info("暂无成员记录。")
        else:
            for member in members:
                role_label = _ROLE_LABELS.get(member.role, member.role.value)
                name = member.display_name or member.actor_id
                st.markdown(f"- **{name}** · `{member.actor_id}` · {role_label}")

        with st.form(f"{key_prefix}_add_{project_id}"):
            actor_id = st.text_input("成员 ID", placeholder="例如 reviewer-1")
            display_name = st.text_input("显示名", placeholder="可选")
            role = st.selectbox(
                "角色",
                options=list(ProjectRole),
                format_func=lambda r: _ROLE_LABELS.get(r, r.value),
                index=2,
            )
            submitted = st.form_submit_button("添加 / 更新成员", use_container_width=True)

        if submitted:
            actor = (actor_id or "").strip()
            if not actor:
                st.warning("请填写成员 ID。")
                return
            try:
                with get_session() as session:
                    ProjectAccessService(session).add_member(
                        project_id,
                        actor,
                        role,
                        display_name=(display_name or "").strip(),
                        actor=LOCAL_ACTOR_ID,
                    )
                st.success(f"已更新成员 {actor}")
                st.rerun()
            except AccessDeniedError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"无法更新成员：{exc}")
