"""Persistence for visual composition entities (JSON-validated payloads)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain._base import new_uuid, utc_now
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.element_comment import ElementComment
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.domain.visual.theme_change_proposal import ThemeChangeProposal, ThemeProposalStatus
from archium.domain.visual.template_usage_brief import TemplateUsageBrief
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import RepositoryError
from archium.infrastructure.database import visual_mappers
from archium.infrastructure.database.models import (
    ArchitecturalTemplateORM,
    ArtDirectionORM,
    DesignSystemORM,
    ElementCommentORM,
    LayoutPlanORM,
    RenderSceneORM,
    SceneChangeProposalORM,
    TemplateUsageBriefORM,
    ThemeChangeProposalORM,
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


class ElementCommentRepository:
    """Persist element-bound Studio comments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, comment: ElementComment) -> ElementComment:
        try:
            orm = self._session.get(ElementCommentORM, comment.id)
            updated = comment.model_copy(update={"updated_at": utc_now()})
            if orm is None:
                orm = visual_mappers.element_comment_to_orm(updated)
                self._session.add(orm)
            else:
                visual_mappers.element_comment_to_orm(updated, orm)
            self._session.flush()
            return visual_mappers.element_comment_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save element comment", exc)
            raise

    def get(self, comment_id: UUID) -> ElementComment | None:
        orm = self._session.get(ElementCommentORM, comment_id)
        return visual_mappers.element_comment_to_domain(orm) if orm else None

    def list_by_slide(self, slide_id: UUID) -> list[ElementComment]:
        stmt = (
            select(ElementCommentORM)
            .where(ElementCommentORM.slide_id == slide_id)
            .order_by(ElementCommentORM.created_at.desc())
        )
        return [
            visual_mappers.element_comment_to_domain(row)
            for row in self._session.scalars(stmt)
        ]

    def list_by_proposal(self, proposal_id: UUID) -> list[ElementComment]:
        stmt = (
            select(ElementCommentORM)
            .where(ElementCommentORM.proposal_id == proposal_id)
            .order_by(ElementCommentORM.created_at.desc())
        )
        return [
            visual_mappers.element_comment_to_domain(row)
            for row in self._session.scalars(stmt)
        ]


_ACTIVE_THEME_PROPOSAL_STATUSES = (
    ThemeProposalStatus.DRAFT,
    ThemeProposalStatus.READY,
    ThemeProposalStatus.READY_WITH_WARNINGS,
)


class ThemeProposalRepository:
    """Persist deck-wide theme change proposals with DesignSystem snapshots."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._design_systems = DesignSystemRepository(session)

    def save(
        self,
        proposal: ThemeChangeProposal,
        *,
        supersede_previous: bool = True,
    ) -> ThemeChangeProposal:
        try:
            if supersede_previous:
                self._supersede_active_for_presentation(
                    proposal.presentation_id,
                    exclude_proposal_id=proposal.proposal_id,
                )

            base_ds = self._design_systems.save(proposal.base_design_system)
            proposed = proposal.proposed_design_system.model_copy(deep=True)
            if proposal.proposed_design_system_id is not None:
                proposed = proposed.model_copy(
                    update={"id": proposal.proposed_design_system_id}
                )
            elif proposed.id == base_ds.id:
                proposed = proposed.model_copy(update={"id": new_uuid()})
            saved_proposed = self._design_systems.save(proposed)

            hydrated = proposal.model_copy(
                update={
                    "base_design_system": base_ds,
                    "proposed_design_system": saved_proposed,
                    "base_design_system_id": base_ds.id,
                    "proposed_design_system_id": saved_proposed.id,
                }
            )
            orm = self._session.get(ThemeChangeProposalORM, proposal.proposal_id)
            if orm is None:
                orm = visual_mappers.theme_change_proposal_to_orm(
                    hydrated,
                    base_design_system_id=base_ds.id,
                    proposed_design_system_id=saved_proposed.id,
                )
                self._session.add(orm)
            else:
                visual_mappers.theme_change_proposal_to_orm(
                    hydrated,
                    base_design_system_id=base_ds.id,
                    proposed_design_system_id=saved_proposed.id,
                    target=orm,
                )
            self._session.flush()
            return self._hydrate(orm)
        except SQLAlchemyError as exc:
            _handle_error("save theme change proposal", exc)
            raise

    def get(self, proposal_id: UUID) -> ThemeChangeProposal | None:
        orm = self._session.get(ThemeChangeProposalORM, proposal_id)
        return self._hydrate(orm) if orm else None

    def get_active_for_presentation(
        self, presentation_id: UUID
    ) -> ThemeChangeProposal | None:
        statuses = [status.value for status in _ACTIVE_THEME_PROPOSAL_STATUSES]
        stmt = (
            select(ThemeChangeProposalORM)
            .where(
                ThemeChangeProposalORM.presentation_id == presentation_id,
                ThemeChangeProposalORM.status.in_(statuses),
            )
            .order_by(ThemeChangeProposalORM.created_at.desc())
        )
        orm = self._session.scalars(stmt).first()
        return self._hydrate(orm) if orm else None

    def _supersede_active_for_presentation(
        self,
        presentation_id: UUID,
        *,
        exclude_proposal_id: UUID | None = None,
    ) -> None:
        statuses = [status.value for status in _ACTIVE_THEME_PROPOSAL_STATUSES]
        stmt = select(ThemeChangeProposalORM).where(
            ThemeChangeProposalORM.presentation_id == presentation_id,
            ThemeChangeProposalORM.status.in_(statuses),
        )
        if exclude_proposal_id is not None:
            stmt = stmt.where(ThemeChangeProposalORM.id != exclude_proposal_id)
        for orm in self._session.scalars(stmt):
            orm.status = ThemeProposalStatus.SUPERSEDED.value

    def _hydrate(self, orm: ThemeChangeProposalORM) -> ThemeChangeProposal | None:
        base = self._design_systems.get(orm.base_design_system_id)
        proposed = self._design_systems.get(orm.proposed_design_system_id)
        if base is None or proposed is None:
            return None
        return visual_mappers.theme_change_proposal_to_domain(
            orm,
            base_design_system=base,
            proposed_design_system=proposed,
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


class TemplateUsageBriefRepository:
    """Immutable brief versions — re-induction inserts a new id/version row."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_new_version(self, brief: TemplateUsageBrief) -> TemplateUsageBrief:
        """Always insert; bumps version based on existing rows for template_id."""
        try:
            next_version = self.next_version_for_template(brief.template_id)
            to_save = brief.model_copy(update={"version": next_version})
            to_save.touch()
            orm = visual_mappers.template_usage_brief_to_orm(to_save)
            self._session.add(orm)
            self._session.flush()
            return visual_mappers.template_usage_brief_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save template usage brief", exc)
            raise

    def get(self, brief_id: UUID) -> TemplateUsageBrief | None:
        orm = self._session.get(TemplateUsageBriefORM, brief_id)
        return visual_mappers.template_usage_brief_to_domain(orm) if orm else None

    def get_latest_for_template(self, template_id: str) -> TemplateUsageBrief | None:
        stmt = (
            select(TemplateUsageBriefORM)
            .where(TemplateUsageBriefORM.template_id == template_id)
            .order_by(TemplateUsageBriefORM.version.desc())
            .limit(1)
        )
        orm = self._session.scalars(stmt).first()
        return visual_mappers.template_usage_brief_to_domain(orm) if orm else None

    def next_version_for_template(self, template_id: str) -> int:
        latest = self.get_latest_for_template(template_id)
        if latest is None:
            return 1
        return latest.version + 1

    def list_for_template(self, template_id: str) -> list[TemplateUsageBrief]:
        stmt = (
            select(TemplateUsageBriefORM)
            .where(TemplateUsageBriefORM.template_id == template_id)
            .order_by(TemplateUsageBriefORM.version.asc())
        )
        return [
            visual_mappers.template_usage_brief_to_domain(row)
            for row in self._session.scalars(stmt)
        ]
