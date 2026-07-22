"""Unit tests for materials summary and generate queue helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.page_pipeline_status import (
    PagePipelinePhase,
    PagePipelineStatus,
    PageStatusBoard,
)
from archium.ui.generate_queue import metrics_from_board, queue_row_status


def test_metrics_from_board_counts() -> None:
    board = PageStatusBoard(
        presentation_id=uuid4(),
        rows=[
            PagePipelineStatus(
                order=0, title="封面", phase=PagePipelinePhase.COMPLETE, severity="success"
            ),
            PagePipelineStatus(
                order=1,
                title="现状",
                phase=PagePipelinePhase.ASSET_MISSING,
                severity="warn",
                detail="缺少照片",
            ),
            PagePipelineStatus(
                order=2,
                title="总平面",
                phase=PagePipelinePhase.DRAWING_QA_FAILED,
                severity="error",
            ),
            PagePipelineStatus(
                order=3, title="策略", phase=PagePipelinePhase.QUEUED, severity="info"
            ),
        ],
    )
    metrics = metrics_from_board(board)
    assert metrics.total == 4
    assert metrics.complete == 1
    assert metrics.failed == 1
    assert metrics.pending == 2
    assert queue_row_status(board.rows[0]) == "完成"
    assert "缺少" in queue_row_status(board.rows[1]) or queue_row_status(board.rows[1]) == "缺少素材"
