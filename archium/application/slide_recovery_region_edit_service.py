"""Apply manual region corrections and recompute slide recovery output."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.slide_recovery_service import SlideRecoveryRequest, SlideRecoveryService
from archium.application.slide_recovery_workflow_service import (
    SlideRecoveryWorkflowResult,
    SlideRecoveryWorkflowService,
)
from archium.domain.enums import WorkflowStatus
from archium.domain.slide_recovery import (
    NormalizedBox,
    RecoveredPageRegion,
    RegionType,
    SlideRecoveryResult,
)
from archium.domain.visual.render_scene import RenderScene
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository


def extract_regions(result: SlideRecoveryWorkflowResult) -> list[RecoveredPageRegion]:
    """Return editable regions from a workflow result."""
    hybrid = result.hybrid_scene or (
        result.recovery_result.hybrid_scene if result.recovery_result else None
    )
    if hybrid is not None and hybrid.regions:
        return [region.model_copy(deep=True) for region in hybrid.regions]

    recovery = result.recovery_result
    if recovery is None:
        return []
    return [
        region.model_copy(deep=True)
        for region in (
            recovery.text_regions
            + recovery.visual_regions
            + recovery.native_shape_regions
        )
    ]


def normalize_bbox(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> NormalizedBox:
    """Clamp bbox values into valid normalized page coordinates."""
    width = max(0.01, min(float(width), 1.0))
    height = max(0.01, min(float(height), 1.0))
    x = min(max(float(x), 0.0), 1.0 - width)
    y = min(max(float(y), 0.0), 1.0 - height)
    return NormalizedBox(x=x, y=y, width=width, height=height)


def sanitize_region(region: RecoveredPageRegion) -> RecoveredPageRegion:
    """Validate and clamp one region before recompute."""
    bbox = normalize_bbox(
        x=region.bbox.x,
        y=region.bbox.y,
        width=region.bbox.width,
        height=region.bbox.height,
    )
    return region.model_copy(update={"bbox": bbox})


def sanitize_regions(regions: list[RecoveredPageRegion]) -> list[RecoveredPageRegion]:
    return [sanitize_region(region) for region in regions]


def new_region(*, region_type: RegionType = "unknown") -> RecoveredPageRegion:
    """Create a default region centered on the page."""
    return RecoveredPageRegion(
        id=uuid4(),
        bbox=NormalizedBox(x=0.35, y=0.35, width=0.3, height=0.2),
        region_type=region_type,
        semantic_role=None,
        confidence=0.5,
        recovered_text="" if region_type == "text" else None,
    )


class SlideRecoveryRegionEditService:
    """Re-run recovery after manual region edits."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._workflow_runs = WorkflowRunRepository(session)
        self._recovery = SlideRecoveryService(session)
        self._workflow = SlideRecoveryWorkflowService(session)

    def apply_region_edits(
        self,
        workflow_run_id: UUID,
        regions: list[RecoveredPageRegion],
    ) -> SlideRecoveryWorkflowResult:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status not in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.AWAITING_REVIEW,
        }:
            raise WorkflowError("当前工作流状态不支持区域编辑。")

        state = dict(run.state or {})
        raw_scene = state.get("source_scene")
        if not isinstance(raw_scene, dict):
            raise WorkflowError("缺少源场景，无法重新计算恢复结果。")

        source_scene = RenderScene.model_validate(raw_scene)
        source_page_id = str(state.get("source_page_id") or "")
        if not source_page_id:
            raise WorkflowError("缺少 source_page_id，无法重新计算恢复结果。")

        previous = None
        raw_recovery = state.get("recovery_result")
        if isinstance(raw_recovery, dict):
            previous = SlideRecoveryResult.model_validate(raw_recovery)

        cleaned = sanitize_regions(regions)
        page_kind = None
        analysis_meta: dict[str, object] = {"region_edit": True}
        if previous is not None:
            analysis_meta.update(previous.analysis_meta or {})
            if previous.hybrid_scene is not None:
                page_kind = previous.hybrid_scene.page_kind

        recovery_result = self._recovery.recover_page(
            SlideRecoveryRequest(
                source_page_id=source_page_id,
                source_scene=source_scene,
                regions=cleaned,
                resolved_page_kind=page_kind,
                source_image_path=state.get("preview_image_path"),
                force_table_bitmap=bool(state.get("force_table_bitmap")),
                analysis_meta=analysis_meta,
            )
        )

        run.status = WorkflowStatus.AWAITING_REVIEW
        run.state = {
            **state,
            "recovery_result": recovery_result.model_dump(mode="json"),
            "hybrid_scene": (
                recovery_result.hybrid_scene.model_dump(mode="json")
                if recovery_result.hybrid_scene is not None
                else None
            ),
            "edited_regions": [region.model_dump(mode="json") for region in cleaned],
            "warnings": recovery_result.warnings,
            "blockers": recovery_result.blockers,
            "region_edit_applied": True,
        }
        run.errors = list(recovery_result.blockers)
        run.touch()
        self._workflow_runs.update(run)
        return self._workflow.result_from_run(run.id)
