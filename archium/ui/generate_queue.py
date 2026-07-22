"""Page-status queue metrics for the Generate stage."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.page_pipeline_status import (
    PagePipelinePhase,
    PagePipelineStatus,
    PageStatusBoard,
)


@dataclass(frozen=True)
class GenerateQueueMetrics:
    total: int
    complete: int
    pending: int
    failed: int

    @property
    def progress_label(self) -> str:
        return f"总体 {self.complete}/{self.total}"


def metrics_from_board(board: PageStatusBoard) -> GenerateQueueMetrics:
    complete = 0
    failed = 0
    pending = 0
    for row in board.rows:
        if row.phase in {
            PagePipelinePhase.COMPLETE,
            PagePipelinePhase.TEMPLATE_MATCHED,
            PagePipelinePhase.SCENE_READY,
        } or row.severity == "success":
            complete += 1
        elif row.phase in {
            PagePipelinePhase.DRAWING_QA_FAILED,
            PagePipelinePhase.RENDER_FAILED,
            PagePipelinePhase.SCHEMA_BLOCKED,
        } or row.severity == "error":
            failed += 1
        elif row.phase != PagePipelinePhase.SKIPPED:
            pending += 1
    return GenerateQueueMetrics(
        total=len(board.rows),
        complete=complete,
        pending=pending,
        failed=failed,
    )


def queue_row_status(row: PagePipelineStatus) -> str:
    """Short Chinese status for the generate queue list."""
    from archium.ui.page_status_board_panel import status_label, status_short_detail

    label = status_label(row)
    if row.severity in {"warn", "error"}:
        detail = status_short_detail(row)
        if detail and detail != label:
            return detail
    phase_map = {
        PagePipelinePhase.QUEUED: "等待",
        PagePipelinePhase.GENERATING: "正在生成",
        PagePipelinePhase.COMPILING_SCENE: "正在编译",
        PagePipelinePhase.BINDING_ASSETS: "绑定素材",
        PagePipelinePhase.ASSET_MISSING: "缺少素材",
        PagePipelinePhase.COMPLETE: "完成",
    }
    return phase_map.get(row.phase, label)
