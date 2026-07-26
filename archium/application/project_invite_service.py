"""Project invite codes — create / list / redeem."""

from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_access_service import ProjectAccessService
from archium.domain._base import utc_now
from archium.domain.access import (
    LOCAL_ACTOR_ID,
    ProjectInvite,
    ProjectMember,
    ProjectPermission,
    ProjectRole,
)
from archium.exceptions import ValidationError
from archium.infrastructure.database.repositories import ProjectInviteRepository

_INVITABLE_ROLES = frozenset(
    {ProjectRole.ARCHITECT, ProjectRole.REVIEWER, ProjectRole.CLIENT}
)


def _new_code() -> str:
    # Short, human-shareable; collision retried in create.
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10].upper()


class ProjectInviteService:
    """Invite codes for multi-seat without full auth stack."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ProjectInviteRepository(session)
        self._access = ProjectAccessService(session)

    def create_invite(
        self,
        project_id: UUID,
        role: ProjectRole,
        *,
        actor_id: str = LOCAL_ACTOR_ID,
        label: str = "",
        max_uses: int = 5,
        ttl_hours: int | None = 72,
    ) -> ProjectInvite:
        self._access.require(project_id, actor_id, ProjectPermission.MANAGE_MEMBERS)
        if role not in _INVITABLE_ROLES:
            raise ValidationError("邀请角色仅支持 architect / reviewer / client")
        expires_at = None
        if ttl_hours is not None and ttl_hours > 0:
            expires_at = utc_now() + timedelta(hours=int(ttl_hours))
        for _ in range(8):
            code = _new_code()
            if self._repo.get_by_code(code) is None:
                invite = ProjectInvite(
                    project_id=project_id,
                    code=code,
                    role=role,
                    created_by=actor_id,
                    expires_at=expires_at,
                    max_uses=max(1, min(100, int(max_uses))),
                    label=(label or "").strip()[:200],
                )
                return self._repo.create(invite)
        raise ValidationError("无法生成唯一邀请码，请重试")

    def list_for_project(self, project_id: UUID, *, limit: int = 20) -> list[ProjectInvite]:
        return self._repo.list_for_project(project_id, limit=limit)

    def revoke(
        self,
        invite_id: UUID,
        *,
        actor_id: str = LOCAL_ACTOR_ID,
    ) -> ProjectInvite:
        invite = self._repo.get_by_id(invite_id)
        if invite is None:
            raise ValidationError("邀请不存在")
        self._access.require(
            invite.project_id, actor_id, ProjectPermission.MANAGE_MEMBERS
        )
        invite.revoked = True
        invite.touch()
        return self._repo.update(invite)

    def redeem(
        self,
        code: str,
        *,
        actor_id: str,
        display_name: str = "",
    ) -> tuple[ProjectInvite, ProjectMember]:
        cleaned = (code or "").strip().upper()
        if not cleaned:
            raise ValidationError("请输入邀请码")
        invite = self._repo.get_by_code(cleaned)
        if invite is None:
            raise ValidationError("邀请码无效")
        if not invite.is_redeemable():
            raise ValidationError("邀请码已失效、用尽或已撤销")
        member = self._access.add_member(
            invite.project_id,
            actor_id.strip(),
            invite.role,
            display_name=(display_name or "").strip() or actor_id.strip(),
        )
        invite.use_count += 1
        invite.touch()
        invite = self._repo.update(invite)
        try:
            from archium.application.project_event_service import ProjectEventService
            from archium.domain.project_event import (
                ProjectEventActor,
                ProjectEventType,
            )

            ProjectEventService(self._session).emit(
                invite.project_id,
                ProjectEventType.OTHER,
                f"成员加入：{member.display_name or member.actor_id}（{invite.role.value}）",
                actor=ProjectEventActor.USER,
                actor_id=member.actor_id,
                payload={
                    "invite_code": invite.code,
                    "role": invite.role.value,
                    "member_id": str(member.id),
                },
                dedupe_key=f"member_joined:{invite.project_id}:{member.actor_id}:{invite.id}",
                source="invite_redeem",
            )
        except Exception:
            pass
        return invite, member

    def get_by_code(self, code: str) -> ProjectInvite | None:
        return self._repo.get_by_code((code or "").strip().upper())
