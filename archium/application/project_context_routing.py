"""Route projects from ProjectContext — origin_mode is legacy compat only."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.context.legacy_origin import apply_legacy_origin, infer_legacy_origin_mode
from archium.domain.context.project_context import ProjectContext
from archium.domain.enums import ProjectOriginMode
from archium.domain.project import Project


def project_context_for(session: Session, project: Project | UUID) -> ProjectContext | None:
    from archium.application.project_context_builder import build_project_context

    ctx = build_project_context(session, project)
    if ctx is None:
        return None
    return apply_legacy_origin(ctx)


def legacy_origin_for_project(session: Session, project: Project | UUID) -> ProjectOriginMode:
    ctx = project_context_for(session, project)
    if ctx is not None:
        return ctx.suggested_origin_mode
    from archium.infrastructure.database.repositories import ProjectRepository

    if isinstance(project, UUID):
        loaded = ProjectRepository(session).get_by_id(project)
        if loaded is None:
            return ProjectOriginMode.CONCEPT_EXPLORATION
        return loaded.origin_mode
    return project.origin_mode


def skips_default_clarification(session: Session, project: Project | UUID) -> bool:
    return legacy_origin_for_project(session, project).skips_default_clarification


def is_research_programming(session: Session, project: Project | UUID) -> bool:
    return (
        legacy_origin_for_project(session, project) == ProjectOriginMode.RESEARCH_PROGRAMMING
    )


def is_concept_leaning(session: Session, project: Project | UUID) -> bool:
    return skips_default_clarification(session, project)
