"""Organization service — thin tenant root (DOM-032 / Topic 08)."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.organization import Organization
from archium.domain.project import Project
from archium.exceptions import ValidationError, WorkflowError
from archium.infrastructure.database.organization_repository import (
    OrganizationRepository,
)
from archium.infrastructure.database.repositories import ProjectRepository

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,78}$")


def _normalize_slug(slug: str | None) -> str | None:
    text = (slug or "").strip().lower()
    if not text:
        return None
    if not _SLUG_RE.match(text):
        raise ValidationError(
            "组织 slug 仅允许小写字母、数字、连字符与下划线，且不能以符号开头"
        )
    return text


class OrganizationService:
    """Create / attach projects to an Organization (no Org-level RBAC yet)."""

    def __init__(self, session: SessionLike) -> None:
        session = session_of(session)
        self._session = session
        self._orgs = OrganizationRepository(session)
        self._projects = ProjectRepository(session)

    def create_organization(
        self,
        name: str,
        *,
        slug: str | None = None,
        display_name: str = "",
    ) -> Organization:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValidationError("组织名称不能为空")
        resolved_slug = _normalize_slug(slug)
        if resolved_slug and self._orgs.get_by_slug(resolved_slug) is not None:
            raise ValidationError(f"组织 slug「{resolved_slug}」已存在")
        org = Organization(
            name=cleaned[:300],
            slug=resolved_slug,
            display_name=(display_name or "").strip()[:300],
        )
        created = self._orgs.create(org)
        self._session.commit()
        return created

    def get(self, organization_id: UUID) -> Organization | None:
        return self._orgs.get(organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self._orgs.get_by_slug(slug)

    def list_organizations(self, *, limit: int = 50) -> list[Organization]:
        return self._orgs.list_all(limit=limit)

    def list_projects(self, organization_id: UUID) -> list[Project]:
        if self._orgs.get(organization_id) is None:
            raise WorkflowError(f"组织 {organization_id} 不存在")
        return self._projects.list_by_organization(organization_id)

    def attach_project(
        self,
        project_id: UUID,
        organization_id: UUID | None,
    ) -> Project:
        """Set or clear project.organization_id."""
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"项目 {project_id} 不存在")
        if organization_id is not None and self._orgs.get(organization_id) is None:
            raise WorkflowError(f"组织 {organization_id} 不存在")
        project.organization_id = organization_id
        project.touch()
        updated = self._projects.update(project)
        self._session.commit()
        return updated
