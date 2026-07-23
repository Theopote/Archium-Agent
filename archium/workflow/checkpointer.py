"""LangGraph checkpoint persistence for presentation workflows."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from archium.exceptions import WorkflowError

_CHECKPOINT_MODULES: list[tuple[str, str]] = [
    ("archium.application.chunk_models", "ProjectContextBundle"),
    ("archium.application.presentation_models", "PresentationRequest"),
    ("archium.domain.citation", "Citation"),
    ("archium.domain.deliverable", "DeliverablePlan"),
    ("archium.domain.deliverable", "PlannedDeliverable"),
    ("archium.domain.document", "DocumentChunk"),
    # DOM-018: enums live in submodules; allowlist must match __module__.
    ("archium.domain.enums.assets", "AssetType"),
    ("archium.domain.enums.assets", "VisualType"),
    ("archium.domain.enums.document", "DocumentType"),
    ("archium.domain.enums.document", "ProcessingStatus"),
    ("archium.domain.enums.document", "VerificationStatus"),
    ("archium.domain.enums.knowledge", "AssumptionStatus"),
    ("archium.domain.enums.knowledge", "InformationOrigin"),
    ("archium.domain.enums.knowledge", "KnowledgeGapCategory"),
    ("archium.domain.enums.knowledge", "KnowledgeGapStatus"),
    ("archium.domain.enums.knowledge", "QuestionAnswerType"),
    ("archium.domain.enums.knowledge", "QuestionStatus"),
    ("archium.domain.enums.knowledge", "ResolutionMethod"),
    ("archium.domain.enums.mission", "ConstraintSource"),
    ("archium.domain.enums.mission", "DeliverableType"),
    ("archium.domain.enums.mission", "EffortLevel"),
    ("archium.domain.enums.mission", "InterventionScale"),
    ("archium.domain.enums.mission", "Priority"),
    ("archium.domain.enums.mission", "ServiceDepth"),
    ("archium.domain.enums.mission", "TaskNature"),
    ("archium.domain.enums.mission", "UncertaintyLevel"),
    ("archium.domain.enums.mission", "WorkstreamStatus"),
    ("archium.domain.enums.mission", "WorkstreamType"),
    ("archium.domain.enums.presentation", "ApprovalStatus"),
    ("archium.domain.enums.presentation", "DeckDeliveryStatus"),
    ("archium.domain.enums.presentation", "OutlineAudienceMode"),
    ("archium.domain.enums.presentation", "PresentationStatus"),
    ("archium.domain.enums.presentation", "PresentationType"),
    ("archium.domain.enums.presentation", "SlideDeliveryStatus"),
    ("archium.domain.enums.presentation", "SlideStatus"),
    ("archium.domain.enums.presentation", "SlideType"),
    ("archium.domain.enums.project", "ProjectDomain"),
    ("archium.domain.enums.project", "ProjectStatus"),
    ("archium.domain.enums.project", "ProjectType"),
    ("archium.domain.enums.review", "ReviewCategory"),
    ("archium.domain.enums.review", "ReviewLayer"),
    ("archium.domain.enums.review", "ReviewSeverity"),
    ("archium.domain.enums.review", "ReviewStatus"),
    ("archium.domain.enums.workflow", "WorkflowStatus"),
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
    ("archium.domain.renovation_issue", "RenovationIssueMap"),
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
    ("archium.domain.visual.layout", "LayoutPlan"),
    ("archium.domain.visual.layout", "LayoutElement"),
    ("archium.domain.visual.layout", "LayoutConstraint"),
    ("archium.domain.visual.preferences", "VisualPreferences"),
    ("archium.domain.visual.visual_intent", "VisualIntent"),
    ("archium.domain.visual.validation", "LayoutValidationReport"),
    ("archium.domain.visual.validation", "LayoutValidationIssue"),
    ("archium.domain.visual.validation", "LayoutScore"),
    ("archium.domain.workflow_route", "PresentationWorkflowRoute"),
    ("archium.domain.workstream", "Workstream"),
    ("archium.domain.workstream", "WorkstreamPlan"),
]


class WorkflowCheckpointerManager:
    """Owns the SQLite connection backing a LangGraph SqliteSaver.

    WF-002: a single shared Sqlite connection is not safe for concurrent
    writers across background continue threads. All graph invokes must run
    under :meth:`serialized_execution` (global DB lock + per-run mutex).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._saver: SqliteSaver | None = None
        self._db_lock = threading.RLock()
        self._run_locks_guard = threading.Lock()
        self._run_locks: dict[str, threading.Lock] = {}

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def saver(self) -> SqliteSaver:
        if self._saver is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MODULES)
            self._saver = SqliteSaver(self._conn, serde=serde)
        return self._saver

    def is_run_busy(self, thread_id: str) -> bool:
        """Return True if another thread currently holds the run lock."""
        key = str(thread_id)
        with self._run_locks_guard:
            run_lock = self._run_locks.get(key)
        if run_lock is None:
            return False
        acquired = run_lock.acquire(blocking=False)
        if acquired:
            run_lock.release()
            return False
        return True

    @contextmanager
    def serialized_execution(self, thread_id: str) -> Iterator[None]:
        """Serialize checkpoint access for one workflow run (WF-002).

        - Rejects concurrent invoke/continue for the same ``thread_id``.
        - Holds the process DB lock for the full graph invoke so the shared
          SqliteSaver connection is never used by two threads at once.
        """
        key = str(thread_id)
        with self._run_locks_guard:
            run_lock = self._run_locks.setdefault(key, threading.Lock())
        if not run_lock.acquire(blocking=False):
            raise WorkflowError(
                f"工作流 {key} 正在执行中，请等待当前任务完成后再继续"
                f"（WF-002：拒绝并发 continue/invoke）。"
            )
        try:
            with self._db_lock:
                # Ensure saver/connection exist while holding the DB lock.
                _ = self.saver
                yield
        finally:
            run_lock.release()

    def close(self) -> None:
        with self._db_lock:
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
