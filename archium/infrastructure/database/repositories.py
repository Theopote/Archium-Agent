"""Repository layer for database persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import ProjectStatus
from archium.domain.fact import ProjectFact
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mappers
from archium.infrastructure.database.models import (
    AssetORM,
    DocumentChunkORM,
    PresentationBriefORM,
    PresentationORM,
    ProjectFactORM,
    ProjectORM,
    ReviewIssueORM,
    SlideORM,
    SourceDocumentORM,
    StorylineORM,
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

    def list_all(self, *, status: ProjectStatus | None = None) -> list[Project]:
        stmt = select(ProjectORM).order_by(ProjectORM.updated_at.desc())
        if status is not None:
            stmt = stmt.where(ProjectORM.status == status.value)
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

    def list_by_presentation(self, presentation_id: UUID) -> list[ReviewIssue]:
        stmt = (
            select(ReviewIssueORM)
            .where(ReviewIssueORM.presentation_id == presentation_id)
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
