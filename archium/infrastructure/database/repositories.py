"""Repository layer for database persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.asset import Asset
from archium.domain.artifact_job import ArtifactJob
from archium.domain.concept_direction import ConceptDirection
from archium.domain.cultural_narrative import CulturalNarrativePlan
from archium.domain.delivery_record import DeliveryRecord
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import ProjectStatus, ReviewStatus, RevisionEntityType
from archium.domain.fact import ProjectFact
from archium.domain.outline import OutlinePlan
from archium.domain.outline_approval_record import OutlineApprovalRecord
from archium.domain.planning_session import PlanningSession
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual_qa import VisualQAReport
from archium.domain.workflow import WorkflowRun
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mappers
from archium.infrastructure.database.models import (
    ArtifactJobORM,
    AssetORM,
    ConceptDirectionORM,
    CulturalNarrativePlanORM,
    DeliveryRecordORM,
    DocumentChunkORM,
    OutlineApprovalRecordORM,
    OutlinePlanORM,
    PlanningSessionORM,
    PresentationBriefORM,
    PresentationManuscriptORM,
    PresentationORM,
    ProjectFactORM,
    ProjectKnowledgeItemORM,
    ProjectORM,
    ReferenceStyleProfileORM,
    RenovationIssueMapORM,
    ReviewIssueORM,
    SlideORM,
    SlideRevisionORM,
    SourceDocumentORM,
    StorylineORM,
    VisualConceptBriefORM,
    VisualQAReportORM,
    WorkflowRunORM,
)


def _handle_error(action: str, exc: Exception) -> None:
    raise RepositoryError(f"Database {action} failed: {exc}") from exc


class ProjectRepository:
    """CRUD operations for projects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, project: Project) -> Project:
        try:
            orm = mappers.project_to_orm(project)
            self._session.add(orm)
            self._session.flush()
            return mappers.project_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create project", exc)
            raise

    def get_by_id(self, project_id: UUID) -> Project | None:
        orm = self._session.get(ProjectORM, project_id)
        return mappers.project_to_domain(orm) if orm else None

    def list_all(
        self,
        *,
        status: ProjectStatus | None = None,
        include_hidden: bool = False,
    ) -> list[Project]:
        stmt = select(ProjectORM).order_by(ProjectORM.updated_at.desc())
        if status is not None:
            stmt = stmt.where(ProjectORM.status == status.value)
        elif not include_hidden:
            stmt = stmt.where(
                ProjectORM.status.not_in(
                    (ProjectStatus.DELETING.value, ProjectStatus.DELETED.value)
                )
            )
        return [mappers.project_to_domain(row) for row in self._session.scalars(stmt)]

    def update(self, project: Project) -> Project:
        try:
            orm = self._session.get(ProjectORM, project.id)
            if orm is None:
                raise RepositoryError(f"Project {project.id} not found")
            mappers.project_to_orm(project, orm)
            self._session.flush()
            return mappers.project_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update project", exc)
            raise

    def delete(self, project_id: UUID) -> bool:
        try:
            orm = self._session.get(ProjectORM, project_id)
            if orm is None:
                return False
            self._session.delete(orm)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            _handle_error("delete project", exc)
            raise

    def save_cultural_narrative(self, plan: CulturalNarrativePlan) -> CulturalNarrativePlan:

        try:
            orm = self._session.get(CulturalNarrativePlanORM, plan.id)
            if orm is None:
                orm = mappers.cultural_narrative_plan_to_orm(plan)
                self._session.add(orm)
            else:
                mappers.cultural_narrative_plan_to_orm(plan, orm)
            self._session.flush()
            return mappers.cultural_narrative_plan_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save cultural narrative", exc)
            raise

    def get_cultural_narrative(self, plan_id: UUID) -> CulturalNarrativePlan | None:
        orm = self._session.get(CulturalNarrativePlanORM, plan_id)
        return mappers.cultural_narrative_plan_to_domain(orm) if orm else None

    def list_cultural_narratives(self, project_id: UUID) -> list[CulturalNarrativePlan]:

        stmt = (
            select(CulturalNarrativePlanORM)
            .where(CulturalNarrativePlanORM.project_id == project_id)
            .order_by(CulturalNarrativePlanORM.version.desc())
        )
        return [mappers.cultural_narrative_plan_to_domain(row) for row in self._session.scalars(stmt)]

    def set_current_cultural_narrative(self, project_id: UUID, plan_id: UUID) -> None:
        try:
            orm = self._session.get(ProjectORM, project_id)
            if orm is None:
                raise RepositoryError(f"Project {project_id} not found")
            orm.current_cultural_narrative_id = plan_id
            self._session.flush()
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("set current cultural narrative", exc)
            raise

    def save_renovation_issue_map(self, plan: RenovationIssueMap) -> RenovationIssueMap:

        try:
            orm = self._session.get(RenovationIssueMapORM, plan.id)
            if orm is None:
                orm = mappers.renovation_issue_map_to_orm(plan)
                self._session.add(orm)
            else:
                mappers.renovation_issue_map_to_orm(plan, orm)
            self._session.flush()
            return mappers.renovation_issue_map_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save renovation issue map", exc)
            raise

    def get_renovation_issue_map(self, plan_id: UUID) -> RenovationIssueMap | None:
        orm = self._session.get(RenovationIssueMapORM, plan_id)
        return mappers.renovation_issue_map_to_domain(orm) if orm else None

    def list_renovation_issue_maps(self, project_id: UUID) -> list[RenovationIssueMap]:
        stmt = (
            select(RenovationIssueMapORM)
            .where(RenovationIssueMapORM.project_id == project_id)
            .order_by(RenovationIssueMapORM.version.desc())
        )
        return [mappers.renovation_issue_map_to_domain(row) for row in self._session.scalars(stmt)]

    def set_current_renovation_issue_map(self, project_id: UUID, plan_id: UUID) -> None:
        try:
            orm = self._session.get(ProjectORM, project_id)
            if orm is None:
                raise RepositoryError(f"Project {project_id} not found")
            orm.current_renovation_issue_map_id = plan_id
            self._session.flush()
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("set current renovation issue map", exc)
            raise

    def save_reference_style_profile(
        self, profile: ReferenceStyleProfile
    ) -> ReferenceStyleProfile:

        try:
            orm = self._session.get(ReferenceStyleProfileORM, profile.id)
            if orm is None:
                orm = mappers.reference_style_profile_to_orm(profile)
                self._session.add(orm)
            else:
                mappers.reference_style_profile_to_orm(profile, orm)
            self._session.flush()
            return mappers.reference_style_profile_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save reference style profile", exc)
            raise

    def get_reference_style_profile(self, profile_id: UUID) -> ReferenceStyleProfile | None:
        orm = self._session.get(ReferenceStyleProfileORM, profile_id)
        return mappers.reference_style_profile_to_domain(orm) if orm else None

    def list_reference_style_profiles(self, project_id: UUID) -> list[ReferenceStyleProfile]:
        stmt = (
            select(ReferenceStyleProfileORM)
            .where(ReferenceStyleProfileORM.project_id == project_id)
            .order_by(ReferenceStyleProfileORM.version.desc())
        )
        return [
            mappers.reference_style_profile_to_domain(row) for row in self._session.scalars(stmt)
        ]

    def set_current_reference_style_profile(self, project_id: UUID, profile_id: UUID) -> None:
        try:
            orm = self._session.get(ProjectORM, project_id)
            if orm is None:
                raise RepositoryError(f"Project {project_id} not found")
            orm.current_reference_style_profile_id = profile_id
            self._session.flush()
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("set current reference style profile", exc)
            raise

    def get_current_cultural_narrative(self, project_id: UUID) -> CulturalNarrativePlan | None:
        orm = self._session.get(ProjectORM, project_id)
        if orm is None or orm.current_cultural_narrative_id is None:
            return None
        return self.get_cultural_narrative(orm.current_cultural_narrative_id)

    def get_current_renovation_issue_map(self, project_id: UUID) -> RenovationIssueMap | None:
        orm = self._session.get(ProjectORM, project_id)
        if orm is None or orm.current_renovation_issue_map_id is None:
            return None
        return self.get_renovation_issue_map(orm.current_renovation_issue_map_id)

    def get_current_reference_style_profile(self, project_id: UUID) -> ReferenceStyleProfile | None:
        orm = self._session.get(ProjectORM, project_id)
        if orm is None or orm.current_reference_style_profile_id is None:
            return None
        return self.get_reference_style_profile(orm.current_reference_style_profile_id)

    def get_current_reference_style_profile_id(self, project_id: UUID) -> UUID | None:
        orm = self._session.get(ProjectORM, project_id)
        if orm is None:
            return None
        return orm.current_reference_style_profile_id


class DocumentRepository:
    """CRUD operations for source documents and chunks."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_document(self, document: SourceDocument) -> SourceDocument:
        try:
            orm = mappers.source_document_to_orm(document)
            self._session.add(orm)
            self._session.flush()
            return mappers.source_document_to_domain(orm)
        except IntegrityError as exc:
            raise RepositoryError("Duplicate document hash for this project") from exc
        except SQLAlchemyError as exc:
            _handle_error("create document", exc)
            raise

    def get_document(self, document_id: UUID) -> SourceDocument | None:
        orm = self._session.get(SourceDocumentORM, document_id)
        return mappers.source_document_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[SourceDocument]:
        stmt = (
            select(SourceDocumentORM)
            .where(SourceDocumentORM.project_id == project_id)
            .order_by(SourceDocumentORM.created_at.desc())
        )
        return [mappers.source_document_to_domain(row) for row in self._session.scalars(stmt)]

    def count_by_project(self, project_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(SourceDocumentORM)
            .where(SourceDocumentORM.project_id == project_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def get_by_hash(self, project_id: UUID, file_hash: str) -> SourceDocument | None:
        stmt = select(SourceDocumentORM).where(
            SourceDocumentORM.project_id == project_id,
            SourceDocumentORM.file_hash == file_hash.lower(),
        )
        orm = self._session.scalars(stmt).first()
        return mappers.source_document_to_domain(orm) if orm else None

    def update_document(self, document: SourceDocument) -> SourceDocument:
        try:
            orm = self._session.get(SourceDocumentORM, document.id)
            if orm is None:
                raise RepositoryError(f"Document {document.id} not found")
            mappers.source_document_to_orm(document, orm)
            self._session.flush()
            return mappers.source_document_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update document", exc)
            raise

    def delete_document(self, document_id: UUID) -> bool:
        try:
            orm = self._session.get(SourceDocumentORM, document_id)
            if orm is None:
                return False
            self._session.delete(orm)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            _handle_error("delete document", exc)
            raise

    def create_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        try:
            orm = mappers.document_chunk_to_orm(chunk)
            self._session.add(orm)
            self._session.flush()
            return mappers.document_chunk_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create chunk", exc)
            raise

    def list_chunks(self, document_id: UUID) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunkORM)
            .where(DocumentChunkORM.document_id == document_id)
            .order_by(DocumentChunkORM.chunk_index)
        )
        return [mappers.document_chunk_to_domain(row) for row in self._session.scalars(stmt)]

    def list_chunks_by_project(self, project_id: UUID) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunkORM)
            .where(DocumentChunkORM.project_id == project_id)
            .order_by(DocumentChunkORM.chunk_index)
        )
        return [mappers.document_chunk_to_domain(row) for row in self._session.scalars(stmt)]

    def count_chunks_by_project(self, project_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunkORM)
            .where(DocumentChunkORM.project_id == project_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def get_chunks_by_ids(self, chunk_ids: list[UUID]) -> list[DocumentChunk]:
        if not chunk_ids:
            return []
        stmt = select(DocumentChunkORM).where(DocumentChunkORM.id.in_(chunk_ids))
        by_id = {
            row.id: mappers.document_chunk_to_domain(row) for row in self._session.scalars(stmt)
        }
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    def get_chunk(self, chunk_id: UUID) -> DocumentChunk | None:
        orm = self._session.get(DocumentChunkORM, chunk_id)
        return mappers.document_chunk_to_domain(orm) if orm else None

    def update_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        try:
            orm = self._session.get(DocumentChunkORM, chunk.id)
            if orm is None:
                raise RepositoryError(f"Chunk {chunk.id} not found")
            mappers.document_chunk_to_orm(chunk, orm)
            self._session.flush()
            return mappers.document_chunk_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update chunk", exc)
            raise

    def delete_chunks_for_document(self, document_id: UUID) -> int:
        try:
            stmt = select(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
            rows = list(self._session.scalars(stmt))
            for row in rows:
                self._session.delete(row)
            self._session.flush()
            return len(rows)
        except SQLAlchemyError as exc:
            _handle_error("delete chunks", exc)
            raise


class PresentationRepository:
    """CRUD operations for presentations and related artifacts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_presentation(self, presentation: Presentation) -> Presentation:
        try:
            orm = mappers.presentation_to_orm(presentation)
            self._session.add(orm)
            self._session.flush()
            return mappers.presentation_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create presentation", exc)
            raise

    def get_presentation(self, presentation_id: UUID) -> Presentation | None:
        orm = self._session.get(PresentationORM, presentation_id)
        return mappers.presentation_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[Presentation]:
        stmt = (
            select(PresentationORM)
            .where(PresentationORM.project_id == project_id)
            .order_by(PresentationORM.updated_at.desc())
        )
        return [mappers.presentation_to_domain(row) for row in self._session.scalars(stmt)]

    def count_by_project(self, project_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(PresentationORM)
            .where(PresentationORM.project_id == project_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def update_presentation(self, presentation: Presentation) -> Presentation:
        try:
            orm = self._session.get(PresentationORM, presentation.id)
            if orm is None:
                raise RepositoryError(f"Presentation {presentation.id} not found")
            mappers.presentation_to_orm(presentation, orm)
            self._session.flush()
            return mappers.presentation_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update presentation", exc)
            raise

    def save_brief(self, brief: PresentationBrief) -> PresentationBrief:
        try:
            orm = self._session.get(PresentationBriefORM, brief.id)
            if orm is None:
                orm = mappers.presentation_brief_to_orm(brief)
                self._session.add(orm)
            else:
                mappers.presentation_brief_to_orm(brief, orm)
            self._session.flush()
            return mappers.presentation_brief_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save brief", exc)
            raise

    def get_brief(self, brief_id: UUID) -> PresentationBrief | None:
        orm = self._session.get(PresentationBriefORM, brief_id)
        return mappers.presentation_brief_to_domain(orm) if orm else None

    def list_briefs(self, presentation_id: UUID) -> list[PresentationBrief]:
        stmt = (
            select(PresentationBriefORM)
            .where(PresentationBriefORM.presentation_id == presentation_id)
            .order_by(PresentationBriefORM.version.desc())
        )
        return [mappers.presentation_brief_to_domain(row) for row in self._session.scalars(stmt)]

    def save_storyline(self, storyline: Storyline) -> Storyline:
        try:
            orm = self._session.get(StorylineORM, storyline.id)
            if orm is None:
                orm = mappers.storyline_to_orm(storyline)
                self._session.add(orm)
            else:
                for chapter in list(orm.chapters):
                    self._session.delete(chapter)
                mappers.storyline_to_orm(storyline, orm)
            self._session.flush()
            self._session.refresh(orm)
            return mappers.storyline_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save storyline", exc)
            raise

    def get_storyline(self, storyline_id: UUID) -> Storyline | None:
        orm = self._session.get(StorylineORM, storyline_id)
        return mappers.storyline_to_domain(orm) if orm else None

    def get_slide(self, slide_id: UUID) -> SlideSpec | None:
        orm = self._session.get(SlideORM, slide_id)
        return mappers.slide_to_domain(orm) if orm else None

    def save_slide(self, slide: SlideSpec) -> SlideSpec:
        try:
            orm = self._session.get(SlideORM, slide.id)
            if orm is None:
                orm = mappers.slide_to_orm(slide)
                self._session.add(orm)
            else:
                mappers.slide_to_orm(slide, orm)
            self._session.flush()
            return mappers.slide_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save slide", exc)
            raise

    def list_slides(self, presentation_id: UUID) -> list[SlideSpec]:
        stmt = (
            select(SlideORM)
            .where(SlideORM.presentation_id == presentation_id)
            .order_by(SlideORM.order)
        )
        return [mappers.slide_to_domain(row) for row in self._session.scalars(stmt)]

    def list_storylines(self, presentation_id: UUID) -> list[Storyline]:
        stmt = (
            select(StorylineORM)
            .where(StorylineORM.presentation_id == presentation_id)
            .order_by(StorylineORM.version.desc())
        )
        return [mappers.storyline_to_domain(row) for row in self._session.scalars(stmt)]

    def save_outline(self, outline: OutlinePlan) -> OutlinePlan:
        try:
            orm = self._session.get(OutlinePlanORM, outline.id)
            if orm is None:
                orm = mappers.outline_plan_to_orm(outline)
                self._session.add(orm)
            else:
                mappers.outline_plan_to_orm(outline, orm)
            self._session.flush()
            return mappers.outline_plan_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save outline", exc)
            raise

    def get_outline(self, outline_id: UUID) -> OutlinePlan | None:
        orm = self._session.get(OutlinePlanORM, outline_id)
        return mappers.outline_plan_to_domain(orm) if orm else None

    def list_outlines(self, presentation_id: UUID) -> list[OutlinePlan]:
        stmt = (
            select(OutlinePlanORM)
            .where(OutlinePlanORM.presentation_id == presentation_id)
            .order_by(OutlinePlanORM.version.desc())
        )
        return [mappers.outline_plan_to_domain(row) for row in self._session.scalars(stmt)]

    def delete_slide(self, slide_id: UUID) -> None:
        """Delete one slide and renumber remaining slides in the presentation."""
        try:
            orm = self._session.get(SlideORM, slide_id)
            if orm is None:
                return
            presentation_id = orm.presentation_id
            deleted_order = orm.order
            self._session.delete(orm)
            self._session.flush()
            remaining = self.list_slides(presentation_id)
            for slide in remaining:
                if slide.order > deleted_order:
                    updated = slide.model_copy(
                        update={
                            "order": slide.order - 1,
                            "logical_key": build_slide_logical_key(
                                slide.chapter_id,
                                slide.order - 1,
                            ),
                        }
                    )
                    self.save_slide(updated)
        except SQLAlchemyError as exc:
            _handle_error("delete slide", exc)
            raise

    def delete_slides_for_presentation(self, presentation_id: UUID) -> int:
        try:
            stmt = select(SlideORM).where(SlideORM.presentation_id == presentation_id)
            rows = list(self._session.scalars(stmt))
            for row in rows:
                self._session.delete(row)
            self._session.flush()
            return len(rows)
        except SQLAlchemyError as exc:
            _handle_error("delete slides", exc)
            raise


class FactRepository:
    """CRUD operations for project facts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, fact: ProjectFact) -> ProjectFact:
        try:
            orm = mappers.project_fact_to_orm(fact)
            self._session.add(orm)
            self._session.flush()
            return mappers.project_fact_to_domain(orm)
        except IntegrityError as exc:
            raise RepositoryError(f"Duplicate fact key '{fact.key}' for this project") from exc
        except SQLAlchemyError as exc:
            _handle_error("create fact", exc)
            raise

    def get_by_id(self, fact_id: UUID) -> ProjectFact | None:
        orm = self._session.get(ProjectFactORM, fact_id)
        return mappers.project_fact_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[ProjectFact]:
        stmt = (
            select(ProjectFactORM)
            .where(ProjectFactORM.project_id == project_id)
            .order_by(ProjectFactORM.key)
        )
        return [mappers.project_fact_to_domain(row) for row in self._session.scalars(stmt)]

    def get_by_project_key(self, project_id: UUID, key: str) -> ProjectFact | None:
        normalized = key.strip().lower().replace(" ", "_")
        stmt = select(ProjectFactORM).where(
            ProjectFactORM.project_id == project_id,
            ProjectFactORM.key == normalized,
        )
        orm = self._session.scalar(stmt)
        return mappers.project_fact_to_domain(orm) if orm else None

    def update(self, fact: ProjectFact) -> ProjectFact:
        try:
            orm = self._session.get(ProjectFactORM, fact.id)
            if orm is None:
                raise RepositoryError(f"Fact {fact.id} not found")
            mappers.project_fact_to_orm(fact, orm)
            self._session.flush()
            return mappers.project_fact_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update fact", exc)
            raise

    def delete(self, fact_id: UUID) -> bool:
        try:
            orm = self._session.get(ProjectFactORM, fact_id)
            if orm is None:
                return False
            self._session.delete(orm)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            _handle_error("delete fact", exc)
            raise


class ProjectKnowledgeRepository:
    """CRUD operations for project knowledge items."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: ProjectKnowledgeItem) -> ProjectKnowledgeItem:
        try:
            orm = mappers.project_knowledge_item_to_orm(item)
            self._session.add(orm)
            self._session.flush()
            return mappers.project_knowledge_item_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create knowledge item", exc)
            raise

    def get_by_id(self, item_id: UUID) -> ProjectKnowledgeItem | None:
        orm = self._session.get(ProjectKnowledgeItemORM, item_id)
        return mappers.project_knowledge_item_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[ProjectKnowledgeItem]:
        stmt = (
            select(ProjectKnowledgeItemORM)
            .where(ProjectKnowledgeItemORM.project_id == project_id)
            .order_by(ProjectKnowledgeItemORM.created_at.desc())
        )
        return [mappers.project_knowledge_item_to_domain(row) for row in self._session.scalars(stmt)]

    def update(self, item: ProjectKnowledgeItem) -> ProjectKnowledgeItem:
        try:
            orm = self._session.get(ProjectKnowledgeItemORM, item.id)
            if orm is None:
                raise RepositoryError(f"Knowledge item {item.id} not found")
            mappers.project_knowledge_item_to_orm(item, orm)
            self._session.flush()
            return mappers.project_knowledge_item_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update knowledge item", exc)
            raise

    def delete(self, item_id: UUID) -> bool:
        try:
            orm = self._session.get(ProjectKnowledgeItemORM, item_id)
            if orm is None:
                return False
            self._session.delete(orm)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            _handle_error("delete knowledge item", exc)
            raise


class AssetRepository:
    """CRUD operations for project assets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, asset: Asset) -> Asset:
        try:
            orm = mappers.asset_to_orm(asset)
            self._session.add(orm)
            self._session.flush()
            return mappers.asset_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create asset", exc)
            raise

    def get_by_id(self, asset_id: UUID) -> Asset | None:
        orm = self._session.get(AssetORM, asset_id)
        return mappers.asset_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[Asset]:
        stmt = select(AssetORM).where(AssetORM.project_id == project_id)
        return [mappers.asset_to_domain(row) for row in self._session.scalars(stmt)]

    def update(self, asset: Asset) -> Asset:
        try:
            orm = self._session.get(AssetORM, asset.id)
            if orm is None:
                raise RepositoryError(f"Asset {asset.id} not found")
            mappers.asset_to_orm(asset, orm)
            self._session.flush()
            return mappers.asset_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update asset", exc)
            raise

    def delete(self, asset_id: UUID) -> bool:
        try:
            orm = self._session.get(AssetORM, asset_id)
            if orm is None:
                return False
            self._session.delete(orm)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            _handle_error("delete asset", exc)
            raise


class ReviewRepository:
    """CRUD operations for presentation review issues."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, issue: ReviewIssue) -> ReviewIssue:
        try:
            orm = mappers.review_issue_to_orm(issue)
            self._session.add(orm)
            self._session.flush()
            return mappers.review_issue_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create review issue", exc)
            raise

    def get_by_id(self, issue_id: UUID) -> ReviewIssue | None:
        orm = self._session.get(ReviewIssueORM, issue_id)
        return mappers.review_issue_to_domain(orm) if orm else None

    def list_by_presentation(self, presentation_id: UUID) -> list[ReviewIssue]:
        stmt = (
            select(ReviewIssueORM)
            .where(ReviewIssueORM.presentation_id == presentation_id)
            .order_by(ReviewIssueORM.created_at.desc())
        )
        return [mappers.review_issue_to_domain(row) for row in self._session.scalars(stmt)]

    def list_by_project(self, project_id: UUID) -> list[ReviewIssue]:
        stmt = (
            select(ReviewIssueORM)
            .join(PresentationORM, ReviewIssueORM.presentation_id == PresentationORM.id)
            .where(PresentationORM.project_id == project_id)
            .order_by(ReviewIssueORM.created_at.desc())
        )
        return [mappers.review_issue_to_domain(row) for row in self._session.scalars(stmt)]

    def update(self, issue: ReviewIssue) -> ReviewIssue:
        try:
            orm = self._session.get(ReviewIssueORM, issue.id)
            if orm is None:
                raise RepositoryError(f"Review issue {issue.id} not found")
            mappers.review_issue_to_orm(issue, orm)
            self._session.flush()
            return mappers.review_issue_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update review issue", exc)
            raise

    def resolve_open_for_presentation(
        self,
        presentation_id: UUID,
        *,
        exclude_ids: set[UUID] | frozenset[UUID] | None = None,
    ) -> int:
        """Mark OPEN issues RESOLVED so a repair → re-review cycle starts clean (B8)."""
        skip = exclude_ids or set()
        resolved = 0
        for issue in self.list_by_presentation(presentation_id):
            if issue.status != ReviewStatus.OPEN:
                continue
            if issue.id in skip:
                continue
            issue.resolve()
            self.update(issue)
            resolved += 1
        return resolved


class VisualQAReportRepository:
    """Persist and retrieve cached visual QA reports per asset fingerprint."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_cached(
        self,
        asset_id: UUID,
        *,
        file_hash: str,
        analyzer_version: str,
    ) -> VisualQAReport | None:
        stmt = select(VisualQAReportORM).where(
            VisualQAReportORM.asset_id == asset_id,
            VisualQAReportORM.file_hash == file_hash,
            VisualQAReportORM.analyzer_version == analyzer_version,
        )
        orm = self._session.scalars(stmt).first()
        return mappers.visual_qa_report_to_domain(orm) if orm else None

    def save(
        self,
        report: VisualQAReport,
        *,
        file_hash: str,
        analyzer_version: str,
    ) -> VisualQAReport:
        try:
            stmt = select(VisualQAReportORM).where(
                VisualQAReportORM.asset_id == report.asset_id,
                VisualQAReportORM.file_hash == file_hash,
                VisualQAReportORM.analyzer_version == analyzer_version,
            )
            existing = self._session.scalars(stmt).first()
            orm = mappers.visual_qa_report_to_orm(
                report,
                file_hash=file_hash,
                analyzer_version=analyzer_version,
                orm=existing,
            )
            if existing is None:
                self._session.add(orm)
            self._session.flush()
            return mappers.visual_qa_report_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save visual QA report", exc)
            raise

    def get_latest_by_asset_ids(self, asset_ids: set[UUID]) -> dict[UUID, VisualQAReport]:
        if not asset_ids:
            return {}
        stmt = select(VisualQAReportORM).where(VisualQAReportORM.asset_id.in_(asset_ids))
        latest_orms: dict[UUID, VisualQAReportORM] = {}
        for orm in self._session.scalars(stmt):
            existing = latest_orms.get(orm.asset_id)
            if existing is None or orm.updated_at > existing.updated_at:
                latest_orms[orm.asset_id] = orm
        return {
            asset_id: mappers.visual_qa_report_to_domain(orm)
            for asset_id, orm in latest_orms.items()
        }


class WorkflowRunRepository:
    """CRUD operations for workflow runs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, run: WorkflowRun) -> WorkflowRun:
        try:
            orm = mappers.workflow_run_to_orm(run)
            self._session.add(orm)
            self._session.flush()
            return mappers.workflow_run_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create workflow run", exc)
            raise

    def get_by_id(self, run_id: UUID) -> WorkflowRun | None:
        orm = self._session.get(WorkflowRunORM, run_id)
        return mappers.workflow_run_to_domain(orm) if orm else None

    def list_by_presentation(self, presentation_id: UUID) -> list[WorkflowRun]:
        stmt = (
            select(WorkflowRunORM)
            .where(WorkflowRunORM.presentation_id == presentation_id)
            .order_by(WorkflowRunORM.created_at.desc())
        )
        return [mappers.workflow_run_to_domain(row) for row in self._session.scalars(stmt)]

    def list_by_project(self, project_id: UUID) -> list[WorkflowRun]:
        stmt = (
            select(WorkflowRunORM)
            .where(WorkflowRunORM.project_id == project_id)
            .order_by(WorkflowRunORM.created_at.desc())
        )
        return [mappers.workflow_run_to_domain(row) for row in self._session.scalars(stmt)]

    def list_planning_by_project(self, project_id: UUID) -> list[WorkflowRun]:
        """Return planning workflow runs (newest first)."""
        return [
            run
            for run in self.list_by_project(project_id)
            if run.state.get("workflow_kind") == "planning"
        ]

    def update(self, run: WorkflowRun) -> WorkflowRun:
        try:
            orm = self._session.get(WorkflowRunORM, run.id)
            if orm is None:
                raise RepositoryError(f"Workflow run {run.id} not found")
            mappers.workflow_run_to_orm(run, orm)
            self._session.flush()
            return mappers.workflow_run_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update workflow run", exc)
            raise


class PlanningSessionRepository:
    """CRUD for mission-first planning sessions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, planning_session: PlanningSession) -> PlanningSession:
        try:
            orm = mappers.planning_session_to_orm(planning_session)
            self._session.add(orm)
            self._session.flush()
            return mappers.planning_session_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create planning session", exc)
            raise

    def get_by_id(self, session_id: UUID) -> PlanningSession | None:
        orm = self._session.get(PlanningSessionORM, session_id)
        return mappers.planning_session_to_domain(orm) if orm else None

    def get_by_workflow_run_id(self, workflow_run_id: UUID) -> PlanningSession | None:
        stmt = (
            select(PlanningSessionORM)
            .where(PlanningSessionORM.workflow_run_id == workflow_run_id)
            .order_by(PlanningSessionORM.created_at.desc())
            .limit(1)
        )
        orm = self._session.scalar(stmt)
        return mappers.planning_session_to_domain(orm) if orm else None

    def get_by_presentation_id(self, presentation_id: UUID) -> PlanningSession | None:
        stmt = (
            select(PlanningSessionORM)
            .where(PlanningSessionORM.presentation_id == presentation_id)
            .order_by(PlanningSessionORM.updated_at.desc())
            .limit(1)
        )
        orm = self._session.scalar(stmt)
        return mappers.planning_session_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[PlanningSession]:
        stmt = (
            select(PlanningSessionORM)
            .where(PlanningSessionORM.project_id == project_id)
            .order_by(PlanningSessionORM.created_at.desc())
        )
        return [
            mappers.planning_session_to_domain(row) for row in self._session.scalars(stmt)
        ]

    def update(self, planning_session: PlanningSession) -> PlanningSession:
        try:
            orm = self._session.get(PlanningSessionORM, planning_session.id)
            if orm is None:
                raise RepositoryError(f"Planning session {planning_session.id} not found")
            mappers.planning_session_to_orm(planning_session, orm)
            self._session.flush()
            return mappers.planning_session_to_domain(orm)
        except RepositoryError:
            raise
        except SQLAlchemyError as exc:
            _handle_error("update planning session", exc)
            raise


class EntityRevisionRepository:
    """CRUD operations for unified entity revision history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, revision: EntityRevision) -> EntityRevision:
        try:
            orm = mappers.entity_revision_to_orm(revision)
            self._session.add(orm)
            self._session.flush()
            return mappers.entity_revision_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create entity revision", exc)
            raise

    def get_by_id(self, revision_id: UUID) -> EntityRevision | None:
        orm = self._session.get(SlideRevisionORM, revision_id)
        return mappers.entity_revision_to_domain(orm) if orm else None

    def list_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        stmt = (
            select(SlideRevisionORM)
            .where(SlideRevisionORM.lineage_id == lineage_id)
            .order_by(SlideRevisionORM.revision_number.desc())
        )
        return [mappers.entity_revision_to_domain(row) for row in self._session.scalars(stmt)]

    def list_by_presentation(
        self,
        presentation_id: UUID,
        *,
        entity_type: RevisionEntityType | None = None,
    ) -> list[EntityRevision]:
        stmt = select(SlideRevisionORM).where(SlideRevisionORM.presentation_id == presentation_id)
        if entity_type is not None:
            stmt = stmt.where(SlideRevisionORM.entity_type == entity_type.value)
        stmt = stmt.order_by(SlideRevisionORM.created_at.desc())
        return [mappers.entity_revision_to_domain(row) for row in self._session.scalars(stmt)]

    def next_revision_number(self, lineage_id: UUID) -> int:
        stmt = (
            select(SlideRevisionORM.revision_number)
            .where(SlideRevisionORM.lineage_id == lineage_id)
            .order_by(SlideRevisionORM.revision_number.desc())
            .limit(1)
        )
        current = self._session.scalar(stmt)
        return 1 if current is None else int(current) + 1

    def get_previous_revision(
        self,
        lineage_id: UUID,
        revision_number: int,
    ) -> EntityRevision | None:
        stmt = (
            select(SlideRevisionORM)
            .where(
                SlideRevisionORM.lineage_id == lineage_id,
                SlideRevisionORM.revision_number < revision_number,
            )
            .order_by(SlideRevisionORM.revision_number.desc())
            .limit(1)
        )
        orm = self._session.scalar(stmt)
        return mappers.entity_revision_to_domain(orm) if orm else None


SlideRevisionRepository = EntityRevisionRepository


class PresentationManuscriptRepository:
    """CRUD for PresentationManuscript (research middle layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, manuscript: PresentationManuscript) -> PresentationManuscript:
        try:
            orm = self._session.get(PresentationManuscriptORM, manuscript.id)
            if orm is None:
                orm = mappers.presentation_manuscript_to_orm(manuscript)
                self._session.add(orm)
            else:
                mappers.presentation_manuscript_to_orm(manuscript, orm)
            self._session.flush()
            return mappers.presentation_manuscript_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save presentation manuscript", exc)
            raise

    def get(self, manuscript_id: UUID) -> PresentationManuscript | None:
        orm = self._session.get(PresentationManuscriptORM, manuscript_id)
        return mappers.presentation_manuscript_to_domain(orm) if orm else None

    def list_by_project(self, project_id: UUID) -> list[PresentationManuscript]:
        stmt = (
            select(PresentationManuscriptORM)
            .where(PresentationManuscriptORM.project_id == project_id)
            .order_by(PresentationManuscriptORM.version.desc())
        )
        return [
            mappers.presentation_manuscript_to_domain(row)
            for row in self._session.scalars(stmt)
        ]


class DeliveryRecordRepository:
    """CRUD for persisted delivery export records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: DeliveryRecord) -> DeliveryRecord:
        try:
            orm = mappers.delivery_record_to_orm(record)
            self._session.add(orm)
            self._session.flush()
            return mappers.delivery_record_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create delivery record", exc)
            raise

    def list_by_project(self, project_id: UUID, *, limit: int = 20) -> list[DeliveryRecord]:
        stmt = (
            select(DeliveryRecordORM)
            .where(DeliveryRecordORM.project_id == project_id)
            .order_by(DeliveryRecordORM.exported_at.desc())
            .limit(limit)
        )
        return [mappers.delivery_record_to_domain(row) for row in self._session.scalars(stmt)]

    def list_by_presentation(
        self,
        presentation_id: UUID,
        *,
        limit: int = 20,
    ) -> list[DeliveryRecord]:
        stmt = (
            select(DeliveryRecordORM)
            .where(DeliveryRecordORM.presentation_id == presentation_id)
            .order_by(DeliveryRecordORM.exported_at.desc())
            .limit(limit)
        )
        return [mappers.delivery_record_to_domain(row) for row in self._session.scalars(stmt)]


class ArtifactJobRepository:
    """CRUD for non-presentation artifact generation jobs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, job: ArtifactJob) -> ArtifactJob:
        try:
            orm = mappers.artifact_job_to_orm(job)
            self._session.add(orm)
            self._session.flush()
            return mappers.artifact_job_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create artifact job", exc)
            raise

    def update(self, job: ArtifactJob) -> ArtifactJob:
        try:
            orm = self._session.get(ArtifactJobORM, job.id)
            if orm is None:
                raise RepositoryError(f"Artifact job {job.id} not found")
            mappers.artifact_job_to_orm(job, orm)
            self._session.flush()
            return mappers.artifact_job_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("update artifact job", exc)
            raise

    def get(self, job_id: UUID) -> ArtifactJob | None:
        orm = self._session.get(ArtifactJobORM, job_id)
        if orm is None:
            return None
        return mappers.artifact_job_to_domain(orm)

    def list_by_mission(self, mission_id: UUID, *, limit: int = 50) -> list[ArtifactJob]:
        stmt = (
            select(ArtifactJobORM)
            .where(ArtifactJobORM.mission_id == mission_id)
            .order_by(ArtifactJobORM.created_at.desc())
            .limit(limit)
        )
        return [mappers.artifact_job_to_domain(row) for row in self._session.scalars(stmt)]

    def list_by_project(self, project_id: UUID, *, limit: int = 50) -> list[ArtifactJob]:
        stmt = (
            select(ArtifactJobORM)
            .where(ArtifactJobORM.project_id == project_id)
            .order_by(ArtifactJobORM.created_at.desc())
            .limit(limit)
        )
        return [mappers.artifact_job_to_domain(row) for row in self._session.scalars(stmt)]


class ConceptDirectionRepository:
    """CRUD for concept design-iteration direction drafts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, direction: ConceptDirection) -> ConceptDirection:
        try:
            orm = mappers.concept_direction_to_orm(direction)
            self._session.add(orm)
            self._session.flush()
            return mappers.concept_direction_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create concept direction", exc)
            raise

    def update(self, direction: ConceptDirection) -> ConceptDirection:
        try:
            orm = self._session.get(ConceptDirectionORM, direction.id)
            if orm is None:
                raise RepositoryError(f"Concept direction {direction.id} not found")
            mappers.concept_direction_to_orm(direction, orm)
            self._session.flush()
            return mappers.concept_direction_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("update concept direction", exc)
            raise

    def get(self, direction_id: UUID) -> ConceptDirection | None:
        orm = self._session.get(ConceptDirectionORM, direction_id)
        if orm is None:
            return None
        return mappers.concept_direction_to_domain(orm)

    def list_by_mission(
        self,
        mission_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[ConceptDirection]:
        stmt = select(ConceptDirectionORM).where(
            ConceptDirectionORM.mission_id == mission_id
        )
        if not include_archived:
            stmt = stmt.where(ConceptDirectionORM.status != "archived")
        stmt = stmt.order_by(
            ConceptDirectionORM.sort_order.asc(),
            ConceptDirectionORM.created_at.asc(),
        )
        return [mappers.concept_direction_to_domain(row) for row in self._session.scalars(stmt)]


class VisualConceptBriefRepository:
    """CRUD for Vision Engine visual concept briefs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, brief: VisualConceptBrief) -> VisualConceptBrief:
        try:
            orm = mappers.visual_concept_brief_to_orm(brief)
            self._session.add(orm)
            self._session.flush()
            return mappers.visual_concept_brief_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create visual concept brief", exc)
            raise

    def update(self, brief: VisualConceptBrief) -> VisualConceptBrief:
        try:
            orm = self._session.get(VisualConceptBriefORM, brief.id)
            if orm is None:
                raise RepositoryError(f"Visual concept brief {brief.id} not found")
            mappers.visual_concept_brief_to_orm(brief, orm)
            self._session.flush()
            return mappers.visual_concept_brief_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("update visual concept brief", exc)
            raise

    def get(self, brief_id: UUID) -> VisualConceptBrief | None:
        orm = self._session.get(VisualConceptBriefORM, brief_id)
        if orm is None:
            return None
        return mappers.visual_concept_brief_to_domain(orm)

    def get_latest_for_direction(self, concept_direction_id: UUID) -> VisualConceptBrief | None:
        stmt = (
            select(VisualConceptBriefORM)
            .where(VisualConceptBriefORM.concept_direction_id == concept_direction_id)
            .order_by(VisualConceptBriefORM.created_at.desc())
            .limit(1)
        )
        orm = self._session.scalars(stmt).first()
        if orm is None:
            return None
        return mappers.visual_concept_brief_to_domain(orm)

    def list_by_mission(self, mission_id: UUID) -> list[VisualConceptBrief]:
        stmt = (
            select(VisualConceptBriefORM)
            .where(VisualConceptBriefORM.mission_id == mission_id)
            .order_by(VisualConceptBriefORM.created_at.desc())
        )
        return [
            mappers.visual_concept_brief_to_domain(row)
            for row in self._session.scalars(stmt)
        ]

    def list_by_direction(self, concept_direction_id: UUID) -> list[VisualConceptBrief]:
        stmt = (
            select(VisualConceptBriefORM)
            .where(VisualConceptBriefORM.concept_direction_id == concept_direction_id)
            .order_by(VisualConceptBriefORM.created_at.desc())
        )
        return [
            mappers.visual_concept_brief_to_domain(row)
            for row in self._session.scalars(stmt)
        ]


class OutlineApprovalRecordRepository:
    """CRUD for durable outline approval audit rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: OutlineApprovalRecord) -> OutlineApprovalRecord:
        try:
            orm = mappers.outline_approval_record_to_orm(record)
            self._session.add(orm)
            self._session.flush()
            return mappers.outline_approval_record_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("create outline approval record", exc)
            raise

    def list_by_outline(
        self,
        outline_id: UUID,
        *,
        limit: int = 20,
        active_only: bool = False,
    ) -> list[OutlineApprovalRecord]:
        stmt = select(OutlineApprovalRecordORM).where(
            OutlineApprovalRecordORM.outline_id == outline_id
        )
        if active_only:
            stmt = stmt.where(OutlineApprovalRecordORM.superseded_at.is_(None))
        stmt = stmt.order_by(OutlineApprovalRecordORM.approved_at.desc()).limit(limit)
        return [
            mappers.outline_approval_record_to_domain(row)
            for row in self._session.scalars(stmt)
        ]

    def supersede_active(
        self, outline_id: UUID, *, superseded_at: datetime | None = None
    ) -> int:
        from datetime import UTC, datetime

        moment = superseded_at or datetime.now(UTC)
        rows = self.list_by_outline(outline_id, active_only=True, limit=100)
        for record in rows:
            orm = self._session.get(OutlineApprovalRecordORM, record.id)
            if orm is None or orm.superseded_at is not None:
                continue
            orm.superseded_at = moment
        self._session.flush()
        return len(rows)
