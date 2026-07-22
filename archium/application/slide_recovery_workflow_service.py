"""Slide Recovery workflow — persisted async steps for external page reconstruction."""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.slide_recovery_region_analyzer import SlideRecoveryRegionAnalyzer
from archium.application.slide_recovery_service import (
    SlideRecoveryRequest,
    SlideRecoveryService,
)
from archium.application.slide_recovery_source_parser import parse_source_page
from archium.config.settings import Settings, get_settings
from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.export_fidelity import ExportFidelityLevel
from archium.domain.slide_recovery import (
    HybridRenderScene,
    SlideRecoveryPageKind,
    SlideRecoveryResult,
)
from archium.domain.visual.render_scene import RenderScene
from archium.domain.workflow import WorkflowRun
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="slide_recovery_workflow")

_RECOVERY_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep.SLIDE_RECOVERY_QUEUED,
    WorkflowStep.SLIDE_RECOVERY_OCR,
    WorkflowStep.SLIDE_RECOVERY_VLM_ANALYSIS,
    WorkflowStep.SLIDE_RECOVERY_REGION_RECOVERY,
    WorkflowStep.SLIDE_RECOVERY_HYBRID_SCENE,
    WorkflowStep.SLIDE_RECOVERY_QA,
    WorkflowStep.SLIDE_RECOVERY_AWAIT_REVIEW,
    WorkflowStep.SLIDE_RECOVERY_FINALIZE,
)


@dataclass
class SlideRecoveryWorkflowRequest:
    """Input payload for a slide recovery workflow run."""

    source_path: Path
    slide_index: int = 0
    page_kind: SlideRecoveryPageKind | None = None
    force_table_bitmap: bool = False
    workspace_dir: Path | None = None
    presentation_id: UUID | None = None


@dataclass
class SlideRecoveryWorkflowResult:
    """Outcome of a slide recovery workflow execution."""

    workflow_run: WorkflowRun
    source_page_id: str = ""
    source_scene: RenderScene | None = None
    recovery_result: SlideRecoveryResult | None = None
    hybrid_scene: HybridRenderScene | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors and self.workflow_run.status == WorkflowStatus.COMPLETED

    @property
    def awaiting_review(self) -> bool:
        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW


class SlideRecoveryWorkflowService:
    """Run slide recovery as a persisted multi-step workflow."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._workflow_runs = WorkflowRunRepository(session)
        self._recovery = SlideRecoveryService(session)
        self._region_analyzer = SlideRecoveryRegionAnalyzer(session, settings=self._settings)

    def run(
        self,
        project_id: UUID,
        request: SlideRecoveryWorkflowRequest,
    ) -> SlideRecoveryWorkflowResult:
        source_path = Path(request.source_path)
        if not source_path.is_file():
            raise WorkflowError(f"源文件不存在：{source_path}")

        workflow_run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                presentation_id=request.presentation_id,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": "slide_recovery",
                    "current_step": WorkflowStep.SLIDE_RECOVERY_QUEUED.value,
                    "step_log": [],
                    "source_path": str(source_path),
                    "slide_index": request.slide_index,
                    "force_table_bitmap": request.force_table_bitmap,
                },
            )
        )

        try:
            return self._execute(workflow_run, request)
        except Exception as exc:
            logger.exception("Slide recovery workflow failed: %s", exc)
            workflow_run.errors = [str(exc)]
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.touch()
            self._workflow_runs.update(workflow_run)
            raise WorkflowError(str(exc)) from exc

    def continue_after_review(
        self,
        workflow_run_id: UUID,
        *,
        accepted: bool,
        notes: str | None = None,
    ) -> SlideRecoveryWorkflowResult:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError("当前工作流不在等待复核状态。")

        state = dict(run.state or {})
        if not accepted:
            run.status = WorkflowStatus.CANCELLED
            run.errors = [notes or "用户拒绝恢复结果"]
            state["review_decision"] = "rejected"
            run.state = state
            run.touch()
            self._workflow_runs.update(run)
            return self.result_from_run(run.id)

        run.status = WorkflowStatus.RUNNING
        state["review_decision"] = "accepted"
        if notes:
            state["review_notes"] = notes
        run.state = state
        run.touch()
        self._workflow_runs.update(run)

        self._checkpoint(
            run,
            WorkflowStep.SLIDE_RECOVERY_FINALIZE,
            extra={"review_accepted": True},
        )
        run.status = WorkflowStatus.COMPLETED
        run.touch()
        self._workflow_runs.update(run)
        return self.result_from_run(run.id)

    def result_from_run(self, workflow_run_id: UUID) -> SlideRecoveryWorkflowResult:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        return self._to_result(run)

    def _execute(
        self,
        workflow_run: WorkflowRun,
        request: SlideRecoveryWorkflowRequest,
    ) -> SlideRecoveryWorkflowResult:
        self._checkpoint(workflow_run, WorkflowStep.SLIDE_RECOVERY_QUEUED)
        time.sleep(0.05)

        parsed = parse_source_page(
            request.source_path,
            slide_index=request.slide_index,
            workspace_dir=request.workspace_dir,
        )
        source_scene = parsed.scene
        source_page_id = parsed.page_id
        preview_path = parsed.preview_image_path or Path(request.source_path)

        region_analysis = self._region_analyzer.analyze(
            source_scene,
            source_page_id=source_page_id,
            source_image_path=preview_path,
            page_kind=request.page_kind,
            source_kind=parsed.source_kind,
        )
        self._checkpoint(
            workflow_run,
            WorkflowStep.SLIDE_RECOVERY_OCR,
            extra={
                "ocr_engine": region_analysis.ocr_engine,
                "ocr_char_count": region_analysis.ocr_char_count,
                "analysis_mode": region_analysis.mode,
            },
        )

        page_kind = region_analysis.page_kind
        self._checkpoint(
            workflow_run,
            WorkflowStep.SLIDE_RECOVERY_VLM_ANALYSIS,
            extra={
                "page_kind": page_kind.value,
                "source_page_id": source_page_id,
                "vlm_source": region_analysis.vlm_source,
            },
        )

        self._checkpoint(workflow_run, WorkflowStep.SLIDE_RECOVERY_REGION_RECOVERY)
        recovery_request = SlideRecoveryRequest(
            source_page_id=source_page_id,
            source_scene=source_scene,
            page_kind=page_kind,
            force_table_bitmap=request.force_table_bitmap,
            regions=region_analysis.regions,
            resolved_page_kind=page_kind,
            source_image_path=preview_path,
            source_kind=parsed.source_kind,
            analysis_meta={
                "analysis_mode": region_analysis.mode,
                "ocr_engine": region_analysis.ocr_engine,
                "vlm_source": region_analysis.vlm_source,
                "ocr_char_count": region_analysis.ocr_char_count,
            },
        )

        self._checkpoint(workflow_run, WorkflowStep.SLIDE_RECOVERY_HYBRID_SCENE)
        recovery_result = self._recovery.recover_page(recovery_request)

        self._checkpoint(
            workflow_run,
            WorkflowStep.SLIDE_RECOVERY_QA,
            extra={
                "recovery_result": recovery_result.model_dump(mode="json"),
                "reconstruction_fidelity": recovery_result.reconstruction_fidelity.value,
            },
        )

        needs_review = (
            recovery_result.reconstruction_fidelity != ExportFidelityLevel.FULLY_EDITABLE
            or bool(recovery_result.warnings)
            or bool(recovery_result.blockers)
        )

        if needs_review:
            self._checkpoint(
                workflow_run,
                WorkflowStep.SLIDE_RECOVERY_AWAIT_REVIEW,
                extra={"review_gate": "recovery_review"},
            )
            workflow_run.status = WorkflowStatus.AWAITING_REVIEW
        else:
            self._checkpoint(workflow_run, WorkflowStep.SLIDE_RECOVERY_FINALIZE)
            workflow_run.status = WorkflowStatus.COMPLETED

        workflow_run.state = {
            **dict(workflow_run.state or {}),
            "source_page_id": source_page_id,
            "source_scene": source_scene.model_dump(mode="json"),
            "recovery_result": recovery_result.model_dump(mode="json"),
            "hybrid_scene": (
                recovery_result.hybrid_scene.model_dump(mode="json")
                if recovery_result.hybrid_scene is not None
                else None
            ),
            "warnings": recovery_result.warnings,
            "blockers": recovery_result.blockers,
        }
        workflow_run.errors = list(recovery_result.blockers)
        workflow_run.touch()
        self._workflow_runs.update(workflow_run)
        return self._to_result(workflow_run)

    def _checkpoint(
        self,
        workflow_run: WorkflowRun,
        step: WorkflowStep,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        state = dict(workflow_run.state or {})
        step_value = step.value
        state["current_step"] = step_value
        log = list(state.get("step_log") or [])
        if not log or log[-1] != step_value:
            log.append(step_value)
        state["step_log"] = log
        if extra:
            state.update(extra)
        workflow_run.state = state
        workflow_run.touch()
        self._workflow_runs.update(workflow_run)

    def _to_result(self, run: WorkflowRun) -> SlideRecoveryWorkflowResult:
        state = dict(run.state or {})
        source_scene = None
        recovery_result = None
        hybrid_scene = None

        raw_scene = state.get("source_scene")
        if isinstance(raw_scene, dict):
            with suppress(Exception):
                source_scene = RenderScene.model_validate(raw_scene)

        raw_recovery = state.get("recovery_result")
        if isinstance(raw_recovery, dict):
            with suppress(Exception):
                recovery_result = SlideRecoveryResult.model_validate(raw_recovery)

        raw_hybrid = state.get("hybrid_scene")
        if isinstance(raw_hybrid, dict):
            with suppress(Exception):
                hybrid_scene = HybridRenderScene.model_validate(raw_hybrid)
        elif recovery_result is not None:
            hybrid_scene = recovery_result.hybrid_scene

        return SlideRecoveryWorkflowResult(
            workflow_run=run,
            source_page_id=str(state.get("source_page_id") or ""),
            source_scene=source_scene,
            recovery_result=recovery_result,
            hybrid_scene=hybrid_scene,
            errors=list(run.errors or []),
            warnings=list(state.get("warnings") or []),
        )
