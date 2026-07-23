"""LangGraph checkpoint persistence for presentation workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

_CHECKPOINT_MODULES: list[tuple[str, str]] = [
    ("archium.application.chunk_models", "ProjectContextBundle"),
    ("archium.application.presentation_models", "PresentationRequest"),
    ("archium.domain.citation", "Citation"),
    ("archium.domain.deliverable", "DeliverablePlan"),
    ("archium.domain.deliverable", "PlannedDeliverable"),
    ("archium.domain.document", "DocumentChunk"),
    ("archium.domain.enums", "ApprovalStatus"),
    ("archium.domain.enums", "AssetType"),
    ("archium.domain.enums", "AssumptionStatus"),
    ("archium.domain.enums", "ConstraintSource"),
    ("archium.domain.enums", "DeliverableType"),
    ("archium.domain.enums", "DocumentType"),
    ("archium.domain.enums", "EffortLevel"),
    ("archium.domain.enums", "InterventionScale"),
    ("archium.domain.enums", "KnowledgeGapCategory"),
    ("archium.domain.enums", "KnowledgeGapStatus"),
    ("archium.domain.enums", "PresentationStatus"),
    ("archium.domain.enums", "PresentationType"),
    ("archium.domain.enums", "Priority"),
    ("archium.domain.enums", "ProcessingStatus"),
    ("archium.domain.enums", "ProjectDomain"),
    ("archium.domain.enums", "ProjectStatus"),
    ("archium.domain.enums", "ProjectType"),
    ("archium.domain.enums", "QuestionAnswerType"),
    ("archium.domain.enums", "QuestionStatus"),
    ("archium.domain.enums", "ResolutionMethod"),
    ("archium.domain.enums", "OutlineAudienceMode"),
    ("archium.domain.enums", "ReviewLayer"),
    ("archium.domain.enums", "ReviewSeverity"),
    ("archium.domain.enums", "ReviewStatus"),
    ("archium.domain.enums", "ServiceDepth"),
    ("archium.domain.enums", "SlideStatus"),
    ("archium.domain.enums", "SlideType"),
    ("archium.domain.enums", "TaskNature"),
    ("archium.domain.enums", "UncertaintyLevel"),
    ("archium.domain.enums", "VerificationStatus"),
    ("archium.domain.enums", "VisualType"),
    ("archium.domain.enums", "WorkstreamStatus"),
    ("archium.domain.enums", "WorkstreamType"),
    ("archium.domain.visual.enums", "LayoutFamily"),
    ("archium.domain.visual.enums", "LayoutElementRole"),
    ("archium.domain.visual.enums", "LayoutContentType"),
    ("archium.domain.visual.enums", "LayoutValidationStatus"),
    ("archium.domain.visual.enums", "VisualContentType"),
    ("archium.domain.visual.enums", "DensityLevel"),
    ("archium.domain.visual.enums", "ContinuityRole"),
    ("archium.domain.visual.enums", "ImageFit"),
    ("archium.domain.visual.enums", "CropPolicy"),
    ("archium.domain.visual.enums", "DesignSystemSource"),
    ("archium.domain.visual.enums", "GridType"),
    ("archium.domain.visual.enums", "PhotoTreatment"),
    ("archium.domain.visual.enums", "OverflowPolicy"),
    ("archium.domain.visual.enums", "LayoutConstraintType"),
    ("archium.domain.visual.enums", "ConstraintPriority"),
    ("archium.domain.visual.enums", "LayoutIssueSeverity"),
    ("archium.domain.fact", "ProjectFact"),
    ("archium.domain.knowledge_gap", "Assumption"),
    ("archium.domain.knowledge_gap", "ClarifyingQuestion"),
    ("archium.domain.knowledge_gap", "DesignQuestion"),
    ("archium.domain.knowledge_gap", "KnowledgeGap"),
    ("archium.domain.outline", "OutlinePlan"),
    ("archium.domain.outline", "OutlineSection"),
    ("archium.domain.presentation_manuscript", "CitationReference"),
    ("archium.domain.presentation_manuscript", "EvidenceItem"),
    ("archium.domain.presentation_manuscript", "ManuscriptFact"),
    ("archium.domain.presentation_manuscript", "ManuscriptSection"),
    ("archium.domain.presentation_manuscript", "ManuscriptStatus"),
    ("archium.domain.presentation_manuscript", "PresentationManuscript"),
    ("archium.domain.presentation", "Presentation"),
    ("archium.domain.presentation", "PresentationBrief"),
    ("archium.domain.presentation", "Storyline"),
    ("archium.domain.project_mission", "EvaluationCriterion"),
    ("archium.domain.project_mission", "MissionConstraint"),
    ("archium.domain.project_mission", "ProjectMission"),
    ("archium.domain.project_mission", "Stakeholder"),
    ("archium.domain.review", "ReviewIssue"),
    ("archium.domain.slide", "SlideSpec"),
    ("archium.domain.slide", "SlideVisualRequirement"),
    ("archium.domain.slide", "VisualRequirement"),
    ("archium.domain.visual.art_direction", "ArtDirection"),
    ("archium.domain.visual.design_system", "DesignSystem"),
    ("archium.domain.visual.design_system", "PageSystem"),
    ("archium.domain.visual.design_system", "GridSystem"),
    ("archium.domain.visual.design_system", "SpacingSystem"),
    ("archium.domain.visual.design_system", "TypographySystem"),
    ("archium.domain.visual.design_system", "ColorSystem"),
    ("archium.domain.visual.design_system", "TextStyleToken"),
    ("archium.domain.visual.design_system", "ImageStyleSystem"),
    ("archium.domain.visual.design_system", "AnnotationStyleSystem"),
    ("archium.domain.visual.design_system", "ChartStyleSystem"),
    ("archium.domain.visual.design_system", "TableStyleSystem"),
    ("archium.domain.visual.design_system", "FooterStyleSystem"),
    ("archium.domain.visual.design_system", "LayoutThresholds"),
    ("archium.domain.visual.layout", "LayoutPlan"),
    ("archium.domain.visual.layout", "LayoutElement"),
    ("archium.domain.visual.layout", "LayoutConstraint"),
    ("archium.domain.visual.preferences", "VisualPreferences"),
    ("archium.domain.visual.visual_intent", "VisualIntent"),
    ("archium.domain.visual.validation", "LayoutValidationReport"),
    ("archium.domain.visual.validation", "LayoutValidationIssue"),
    ("archium.domain.visual.validation", "LayoutScore"),
    ("archium.domain.workstream", "Workstream"),
    ("archium.domain.workstream", "WorkstreamPlan"),
]


class WorkflowCheckpointerManager:
    """Owns the SQLite connection backing a LangGraph SqliteSaver."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._saver: SqliteSaver | None = None

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def saver(self) -> SqliteSaver:
        if self._saver is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MODULES)
            self._saver = SqliteSaver(self._conn, serde=serde)
        return self._saver

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        self._saver = None

    def __enter__(self) -> WorkflowCheckpointerManager:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
