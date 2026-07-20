"""Repository layer for database persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import ProjectStatus, RevisionEntityType
from archium.domain.fact import ProjectFact
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.planning_session import PlanningSession
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.visual_qa import VisualQAReport
from archium.domain.workflow import WorkflowRun
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mappers
from archium.infrastructure.database.models import (
    AssetORM,
    DocumentChunkORM,
    OutlinePlanORM,
    PlanningSessionORM,
    PresentationBriefORM,
    PresentationORM,
    ProjectFactORM,
    ProjectKnowledgeItemORM,
    ProjectORM,
    ReviewIssueORM,
    SlideORM,
    SlideRevisionORM,
    SourceDocumentORM,
    StorylineORM,
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
