"""Thin tenant root persistence (DOM-032) — imported by repositories package path.

Kept as a small module so OrganizationRepository can land without rewriting the
large repositories.py file; re-exported from repositories for existing imports.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.organization import Organization
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mappers
from archium.infrastructure.database.models import OrganizationORM


def _handle_error(action: str, exc: Exception) -> None:
    raise RepositoryError(f"Database {action} failed: {exc}") from exc


class OrganizationRepository:
    """Thin tenant root persistence (DOM-032)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, organization: Organization) -> Organization:
        try:
            orm = mappers.organization_to_orm(organization)
            self._session.add(orm)
            self._session.flush()
            return mappers.organization_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create organization", exc)
            raise

    def update(self, organization: Organization) -> Organization:
        try:
            orm = self._session.get(OrganizationORM, organization.id)
            if orm is None:
                raise RepositoryError(f"Organization {organization.id} not found")
            mappers.organization_to_orm(organization, orm)
            self._session.flush()
            return mappers.organization_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update organization", exc)
            raise

    def get(self, organization_id: UUID) -> Organization | None:
        orm = self._session.get(OrganizationORM, organization_id)
        return mappers.organization_to_domain(orm) if orm else None

    def get_by_slug(self, slug: str) -> Organization | None:
        key = (slug or "").strip()
        if not key:
            return None
        stmt = select(OrganizationORM).where(OrganizationORM.slug == key).limit(1)
        orm = self._session.scalars(stmt).first()
        return mappers.organization_to_domain(orm) if orm else None

    def list_all(self, *, limit: int = 50) -> list[Organization]:
        stmt = (
            select(OrganizationORM)
            .order_by(OrganizationORM.updated_at.desc())
            .limit(max(1, int(limit)))
        )
        return [mappers.organization_to_domain(row) for row in self._session.scalars(stmt)]
