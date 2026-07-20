"""Persistence for visual composition entities (JSON-validated payloads)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import RepositoryError
from archium.infrastructure.database import visual_mappers
from archium.infrastructure.database.models import (
    ArtDirectionORM,
    DesignSystemORM,
    LayoutPlanORM,
    RenderSceneORM,
    VisualIntentORM,
)


def _handle_error(action: str, exc: Exception) -> None:
    raise RepositoryError(f"Database {action} failed: {exc}") from exc


class DesignSystemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, design_system: DesignSystem) -> DesignSystem:
        try:
            orm = self._session.get(DesignSystemORM, design_system.id)
            if orm is None:
                orm = visual_mappers.design_system_to_orm(design_system)
                self._session.add(orm)
            else:
                visual_mappers.design_system_to_orm(design_system, orm)
            self._session.flush()
            return visual_mappers.design_system_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save design system", exc)
            raise

    def get(self, design_system_id: UUID) -> DesignSystem | None:
        orm = self._session.get(DesignSystemORM, design_system_id)
        return visual_mappers.design_system_to_domain(orm) if orm else None

    def list_all(self) -> list[DesignSystem]:
        stmt = select(DesignSystemORM).order_by(DesignSystemORM.updated_at.desc())
        return [visual_mappers.design_system_to_domain(row) for row in self._session.scalars(stmt)]


class ArtDirectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, art_direction: ArtDirection) -> ArtDirection:
        try:
            orm = self._session.get(ArtDirectionORM, art_direction.id)
            if orm is None:
                orm = visual_mappers.art_direction_to_orm(art_direction)
                self._session.add(orm)
            else:
                visual_mappers.art_direction_to_orm(art_direction, orm)
            self._session.flush()
            return visual_mappers.art_direction_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save art direction", exc)
            raise

    def get(self, art_direction_id: UUID) -> ArtDirection | None:
        orm = self._session.get(ArtDirectionORM, art_direction_id)
        return visual_mappers.art_direction_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[ArtDirection]:
        stmt = (
            select(ArtDirectionORM)
            .where(ArtDirectionORM.project_id == project_id)
            .order_by(ArtDirectionORM.updated_at.desc())
        )
        return [visual_mappers.art_direction_to_domain(row) for row in self._session.scalars(stmt)]


class VisualIntentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, intent: VisualIntent) -> VisualIntent:
        try:
            orm = self._session.get(VisualIntentORM, intent.id)
            if orm is None:
                orm = visual_mappers.visual_intent_to_orm(intent)
                self._session.add(orm)
            else:
                visual_mappers.visual_intent_to_orm(intent, orm)
            self._session.flush()
            return visual_mappers.visual_intent_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save visual intent", exc)
            raise

    def get(self, intent_id: UUID) -> VisualIntent | None:
        orm = self._session.get(VisualIntentORM, intent_id)
        return visual_mappers.visual_intent_to_domain(orm) if orm else None

    def get_by_slide(self, slide_id: UUID) -> VisualIntent | None:
        stmt = (
            select(VisualIntentORM)
            .where(VisualIntentORM.slide_id == slide_id)
            .order_by(VisualIntentORM.updated_at.desc())
        )
        orm = self._session.scalars(stmt).first()
        return visual_mappers.visual_intent_to_domain(orm) if orm else None


class LayoutPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, plan: LayoutPlan) -> LayoutPlan:
        try:
            orm = self._session.get(LayoutPlanORM, plan.id)
            if orm is None:
                orm = visual_mappers.layout_plan_to_orm(plan)
                self._session.add(orm)
            else:
                visual_mappers.layout_plan_to_orm(plan, orm)
            self._session.flush()
            return visual_mappers.layout_plan_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save layout plan", exc)
            raise

    def get(self, plan_id: UUID) -> LayoutPlan | None:
        orm = self._session.get(LayoutPlanORM, plan_id)
        return visual_mappers.layout_plan_to_domain(orm) if orm else None

    def list_by_slide(self, slide_id: UUID) -> list[LayoutPlan]:
        stmt = (
            select(LayoutPlanORM)
            .where(LayoutPlanORM.slide_id == slide_id)
            .order_by(LayoutPlanORM.updated_at.desc())
        )
        return [visual_mappers.layout_plan_to_domain(row) for row in self._session.scalars(stmt)]


class RenderSceneRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, scene: RenderScene) -> RenderScene:
        try:
            orm = self._session.get(RenderSceneORM, scene.id)
            if orm is None:
                orm = visual_mappers.render_scene_to_orm(scene)
                self._session.add(orm)
            else:
                visual_mappers.render_scene_to_orm(scene, orm)
            self._session.flush()
            return visual_mappers.render_scene_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save render scene", exc)
            raise

    def get(self, scene_id: UUID) -> RenderScene | None:
        orm = self._session.get(RenderSceneORM, scene_id)
        return visual_mappers.render_scene_to_domain(orm) if orm else None

    def get_by_layout_plan(self, layout_plan_id: UUID) -> RenderScene | None:
        stmt = (
            select(RenderSceneORM)
            .where(RenderSceneORM.layout_plan_id == layout_plan_id)
            .order_by(RenderSceneORM.updated_at.desc())
        )
        orm = self._session.scalars(stmt).first()
        return visual_mappers.render_scene_to_domain(orm) if orm else None

    def list_by_slide(self, slide_id: UUID) -> list[RenderScene]:
        stmt = (
            select(RenderSceneORM)
            .where(RenderSceneORM.slide_id == slide_id)
            .order_by(RenderSceneORM.updated_at.desc())
        )
        return [visual_mappers.render_scene_to_domain(row) for row in self._session.scalars(stmt)]
