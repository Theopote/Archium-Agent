"""Project membership / role / invite panel (minimal RBAC chrome)."""

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

_INVITE_ROLES = [ProjectRole.ARCHITECT, ProjectRole.REVIEWER, ProjectRole.CLIENT]


def render_project_members_panel(
    project_id: UUID,
    *,
    key_prefix: str = "members",
    expanded: bool = False,
) -> None:
    """List members, create invite codes, and redeem invites."""
    from archium.application.project_access_service import ProjectAccessService
    from archium.application.project_invite_service import ProjectInviteService
    from archium.exceptions import AccessDeniedError, ValidationError

    with get_session() as session:
        access = ProjectAccessService(session)
        access.ensure_default_owner(project_id)
        members = access.list_members(project_id)
        invites = ProjectInviteService(session).list_for_project(project_id, limit=8)

    with st.expander("项目成员与角色", expanded=expanded):
        from archium.ui.session_actor import get_current_actor_id

        actor = get_current_actor_id()
        if actor == LOCAL_ACTOR_ID:
            st.caption("当前为本地单用户模式，默认拥有负责人权限。")
        else:
            st.caption(f"当前身份：{actor}")
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
            else:
                try:
                    with get_session() as session:
                        assert role is not None
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

        st.markdown("**邀请码**")
        active = [i for i in invites if i.is_redeemable()]
        if active:
            for invite in active:
                role_label = _ROLE_LABELS.get(invite.role, invite.role.value)
                uses = f"{invite.use_count}/{invite.max_uses}"
                st.code(invite.code, language=None)
                from archium.ui.invite_deep_link import invite_share_path

                st.caption(
                    f"{role_label} · 已用 {uses}"
                    + (f" · {invite.label}" if invite.label else "")
                    + f" · 分享链接后缀 `{invite_share_path(invite.code)}`（打开首页兑换）"
                )
        else:
            st.caption("暂无有效邀请码。")

        with st.form(f"{key_prefix}_invite_{project_id}"):
            invite_role = st.selectbox(
                "邀请角色",
                options=_INVITE_ROLES,
                format_func=lambda r: _ROLE_LABELS.get(r, r.value),
                index=1,
            )
            invite_label = st.text_input("备注", placeholder="例如：外部审阅")
            create_invite = st.form_submit_button("生成邀请码", use_container_width=True)
        if create_invite:
            try:
                with get_session() as session:
                    invite = ProjectInviteService(session).create_invite(
                        project_id,
                        invite_role,
                        actor_id=LOCAL_ACTOR_ID,
                        label=(invite_label or "").strip(),
                    )
                st.success(f"邀请码：{invite.code}")
                st.rerun()
            except (AccessDeniedError, ValidationError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"无法生成邀请码：{exc}")

        with st.form(f"{key_prefix}_redeem_{project_id}"):
            from archium.ui.invite_deep_link import peek_pending_invite_code

            pending_code = peek_pending_invite_code() or ""
            redeem_code = st.text_input(
                "兑换邀请码",
                value=pending_code,
                placeholder="粘贴邀请码或通过 ?invite= 打开首页",
            )
            redeem_actor = st.text_input("加入为成员 ID", value="guest-user")
            redeem_name = st.text_input("显示名", placeholder="可选")
            redeem = st.form_submit_button("兑换并加入", use_container_width=True)
        if redeem:
            try:
                from archium.ui.invite_deep_link import clear_pending_invite_code
                from archium.ui.session_actor import set_current_actor_id

                joined_actor = (redeem_actor or "").strip() or "guest-user"
                with get_session() as session:
                    invite, member = ProjectInviteService(session).redeem(
                        redeem_code,
                        actor_id=joined_actor,
                        display_name=(redeem_name or "").strip(),
                    )
                set_current_actor_id(member.actor_id)
                clear_pending_invite_code()
                if invite.project_id != project_id:
                    st.warning(
                        f"已加入其他项目成员（{invite.project_id}）· 角色 {member.role.value}"
                    )
                else:
                    st.success(f"已加入：{member.actor_id} · {member.role.value}")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"兑换失败：{exc}")
