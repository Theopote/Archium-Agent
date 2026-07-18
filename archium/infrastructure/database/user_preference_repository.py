"""Repository for global user preferences."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.memory import UserPreference
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mappers
from archium.infrastructure.database.models import UserPreferenceORM


def _handle_error(action: str, exc: Exception) -> None:
    raise RepositoryError(f"Database {action} failed: {exc}") from exc


class UserPreferenceRepository:
    """Key/value preference storage scoped to global or project context."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_global(self, key: str) -> UserPreference | None:
        stmt = select(UserPreferenceORM).where(
            UserPreferenceORM.key == key,
            UserPreferenceORM.project_id.is_(None),
        )
        orm = self._session.scalar(stmt)
        return mappers.user_preference_to_domain(orm) if orm else None

    def upsert_global(self, key: str, value: Any, *, description: str | None = None) -> UserPreference:
        try:
            stmt = select(UserPreferenceORM).where(
                UserPreferenceORM.key == key,
                UserPreferenceORM.project_id.is_(None),
            )
            orm = self._session.scalar(stmt)
            if orm is None:
                pref = UserPreference(key=key, value=value, description=description)
                orm = mappers.user_preference_to_orm(pref)
                self._session.add(orm)
            else:
                domain = mappers.user_preference_to_domain(orm)
                domain.value = value
                if description is not None:
                    domain.description = description
                domain.touch()
                mappers.user_preference_to_orm(domain, orm)
            self._session.flush()
            return mappers.user_preference_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("upsert user preference", exc)
            raise

    def delete_global(self, key: str) -> None:
        try:
            stmt = select(UserPreferenceORM).where(
                UserPreferenceORM.key == key,
                UserPreferenceORM.project_id.is_(None),
            )
            orm = self._session.scalar(stmt)
            if orm is not None:
                self._session.delete(orm)
                self._session.flush()
        except SQLAlchemyError as exc:
            _handle_error("delete user preference", exc)
            raise
