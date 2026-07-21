"""Persistence for visual composition entities (JSON-validated payloads)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain._base import new_uuid
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import RepositoryError
from archium.infrastructure.database import visual_mappers
from archium.infrastructure.database.models import (
    ArchitecturalTemplateORM,
    ArtDirectionORM,
    DesignSystemORM,
    LayoutPlanORM,
    RenderSceneORM,
    SceneChangeProposalORM,
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


_ACTIVE_PROPOSAL_STATUSES = (
    ProposalStatus.DRAFT,
    ProposalStatus.READY,
    ProposalStatus.READY_WITH_WARNINGS,
)


class SceneProposalRepository:
    """Persist scene change proposals with scene snapshots stored by reference."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._scenes = RenderSceneRepository(session)

    def save(self, proposal: SceneChangeProposal, *, supersede_previous: bool = True) -> SceneChangeProposal:
        try:
            if supersede_previous:
                self._supersede_active_for_slide(
                    proposal.slide_id,
                    exclude_proposal_id=proposal.proposal_id,
                )

            base_scene = self._scenes.save(proposal.base_scene)
            proposed_scene = self._candidate_scene_snapshot(proposal)
            saved_proposed = self._scenes.save(proposed_scene)

            orm = self._session.get(SceneChangeProposalORM, proposal.proposal_id)
            hydrated = proposal.model_copy(
                update={
                    "base_scene": base_scene,
                    "proposed_scene": saved_proposed,
                    "base_scene_id": base_scene.id,
                    "proposed_scene_id": saved_proposed.id,
                }
            )
            if orm is None:
                orm = visual_mappers.scene_change_proposal_to_orm(
                    hydrated,
                    base_scene_id=base_scene.id,
                    proposed_scene_id=saved_proposed.id,
                )
                self._session.add(orm)
            else:
                visual_mappers.scene_change_proposal_to_orm(
                    hydrated,
                    base_scene_id=base_scene.id,
                    proposed_scene_id=saved_proposed.id,
                    target=orm,
                )
            self._session.flush()
            return self._hydrate(orm)
        except SQLAlchemyError as exc:
            _handle_error("save scene change proposal", exc)
            raise

    def get(self, proposal_id: UUID) -> SceneChangeProposal | None:
        orm = self._session.get(SceneChangeProposalORM, proposal_id)
        return self._hydrate(orm) if orm else None

    def get_active_for_slide(self, slide_id: UUID) -> SceneChangeProposal | None:
        statuses = [status.value for status in _ACTIVE_PROPOSAL_STATUSES]
        stmt = (
            select(SceneChangeProposalORM)
            .where(
                SceneChangeProposalORM.slide_id == slide_id,
                SceneChangeProposalORM.status.in_(statuses),
            )
            .order_by(SceneChangeProposalORM.created_at.desc())
        )
        orm = self._session.scalars(stmt).first()
        return self._hydrate(orm) if orm else None

    def list_by_slide(self, slide_id: UUID) -> list[SceneChangeProposal]:
        stmt = (
            select(SceneChangeProposalORM)
            .where(SceneChangeProposalORM.slide_id == slide_id)
            .order_by(SceneChangeProposalORM.created_at.desc())
        )
        return [item for orm in self._session.scalars(stmt) if (item := self._hydrate(orm))]

    def _candidate_scene_snapshot(self, proposal: SceneChangeProposal) -> RenderScene:
        proposed = proposal.proposed_scene.model_copy(deep=True)
        if proposal.proposed_scene_id is not None:
            proposed = proposed.model_copy(update={"id": proposal.proposed_scene_id})
        elif proposed.id == proposal.base_scene.id:
            proposed = proposed.model_copy(update={"id": new_uuid()})
        return proposed

    def _supersede_active_for_slide(
        self,
        slide_id: UUID,
        *,
        exclude_proposal_id: UUID | None = None,
    ) -> None:
        statuses = [status.value for status in _ACTIVE_PROPOSAL_STATUSES]
        stmt = select(SceneChangeProposalORM).where(
            SceneChangeProposalORM.slide_id == slide_id,
            SceneChangeProposalORM.status.in_(statuses),
        )
        if exclude_proposal_id is not None:
            stmt = stmt.where(SceneChangeProposalORM.id != exclude_proposal_id)
        for orm in self._session.scalars(stmt):
            orm.status = ProposalStatus.SUPERSEDED.value

    def _hydrate(self, orm: SceneChangeProposalORM) -> SceneChangeProposal | None:
        base_scene = self._scenes.get(orm.base_scene_id)
        proposed_scene = self._scenes.get(orm.proposed_scene_id)
        if base_scene is None or proposed_scene is None:
            return None
        return visual_mappers.scene_change_proposal_to_domain(
            orm,
            base_scene=base_scene,
            proposed_scene=proposed_scene,
        )


class ArchitecturalTemplateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, template: ArchitecturalTemplate) -> ArchitecturalTemplate:
        try:
            orm = self._session.get(ArchitecturalTemplateORM, template.id)
            if orm is None:
                orm = visual_mappers.architectural_template_to_orm(template)
                self._session.add(orm)
            else:
                visual_mappers.architectural_template_to_orm(template, orm)
            self._session.flush()
            return visual_mappers.architectural_template_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save architectural template", exc)
            raise

    def get(self, template_id: UUID) -> ArchitecturalTemplate | None:
        orm = self._session.get(ArchitecturalTemplateORM, template_id)
        return visual_mappers.architectural_template_to_domain(orm) if orm else None

    def list_all(self) -> list[ArchitecturalTemplate]:
        stmt = select(ArchitecturalTemplateORM).order_by(ArchitecturalTemplateORM.updated_at.desc())
        return [
            visual_mappers.architectural_template_to_domain(row)
            for row in self._session.scalars(stmt)
        ]

    def list_by_project(self, project_id: UUID) -> list[ArchitecturalTemplate]:
        stmt = (
            select(ArchitecturalTemplateORM)
            .where(ArchitecturalTemplateORM.project_id == project_id)
            .order_by(ArchitecturalTemplateORM.updated_at.desc())
        )
        return [
            visual_mappers.architectural_template_to_domain(row)
            for row in self._session.scalars(stmt)
        ]
