"""Phase O — ExportVerdict, citation gaps, art-direction product defaults."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from archium.application.evidence_readiness_service import (
    DeliveryReadinessReport,
    ProjectEvidenceStatus,
    assert_formal_export_allowed,
    citation_lines_for_slide,
    resolve_export_verdict_safe,
)
from archium.domain.citation import Citation
from archium.domain.enums import EvidenceAvailability
from archium.domain.export_verdict import ExportVerdictStatus
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole
from archium.exceptions import WorkflowError


def test_export_verdict_blocked_without_evidence() -> None:
    report = DeliveryReadinessReport(
        evidence=ProjectEvidenceStatus(
            availability=EvidenceAvailability.MISSING,
            document_count=0,
        ),
        pptx_ready=True,
        pdf_ready=True,
        blockers=("概念草稿不可正式交付：请先绑定至少一份项目资料",),
        export_blocker_count=0,
    )
    # evidence alone blocks via formal_delivery_ready
    verdict = report.to_export_verdict()
    assert verdict.status == ExportVerdictStatus.BLOCKED
    assert not verdict.allows_formal_export


def test_assert_formal_export_accepts_verdict() -> None:
    verdict = DeliveryReadinessReport(
        evidence=ProjectEvidenceStatus(
            availability=EvidenceAvailability.AVAILABLE,
            document_count=1,
        ),
        pptx_ready=True,
        pdf_ready=True,
        warnings=("建议复核故事强度",),
        critic_lines=("缺少说服策略",),
    ).to_export_verdict()
    assert verdict.status == ExportVerdictStatus.READY_WITH_WARNINGS
    assert_formal_export_allowed(verdict, export_format="PPTX")


def test_citation_lines_for_slide() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="场地问题",
        message="现状冲突",
        source_citations=[
            Citation(document_id=uuid4(), document_name="任务书", page_number=3),
        ],
    )
    lines = citation_lines_for_slide(slide)
    assert lines == ["任务书 p.3"]


def test_citation_gap_counts_as_blocker() -> None:
    session = MagicMock()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="问题分析",
        message="冲突",
        slide_role=SlideRole.PROBLEM_ANALYSIS,
        source_citations=[],
    )
    with (
        patch(
            "archium.application.visual.layout_readiness.presentation_has_visual_layout",
            return_value=True,
        ),
        patch(
            "archium.application.review_service.PresentationReviewService"
        ) as review_cls,
        patch(
            "archium.infrastructure.database.repositories.DocumentRepository"
        ) as doc_cls,
        patch(
            "archium.infrastructure.database.repositories.PresentationRepository"
        ) as pres_cls,
        patch(
            "archium.application.evidence_readiness_service._scene_export_blocker_messages",
            return_value=[],
        ),
    ):
        review_cls.return_value.list_review_issues.return_value = []
        doc_cls.return_value.list_by_project.return_value = [object()]
        pres_cls.return_value.list_slides.return_value = [slide]
        from archium.application.evidence_readiness_service import resolve_delivery_readiness

        report = resolve_delivery_readiness(
            session,
            project_id=uuid4(),
            presentation_id=uuid4(),
        )
    assert report.citation_gap_count >= 1
    assert report.export_blocker_count >= 1
    with pytest.raises(WorkflowError, match="阻止"):
        assert_formal_export_allowed(report, export_format="PPTX")


def test_product_paths_require_art_direction_review() -> None:
    root = Path(__file__).resolve().parents[2]
    export = (root / "archium/ui/studio/export_panel.py").read_text(encoding="utf-8")
    visual = (root / "archium/ui/visual_service.py").read_text(encoding="utf-8")
    workspace = (root / "archium/ui/pages/workspace.py").read_text(encoding="utf-8")
    assert "require_art_direction_review=True" in export
    assert "require_art_direction_review=False" not in export.split("def _launch_visual_job")[1].split("def _render_scene")[0]
    assert "require_art_direction_review=True" in visual
    assert "require_art_direction_review=True" in workspace


def test_citation_mjs_wired_in_from_plan() -> None:
    root = Path(__file__).resolve().parents[2]
    from_plan = (
        root / "archium/infrastructure/renderers/pptxgen/layouts/from-plan.mjs"
    ).read_text(encoding="utf-8")
    shared = (
        root / "archium/infrastructure/renderers/pptxgen/layouts/shared.mjs"
    ).read_text(encoding="utf-8")
    assert "addCitationBlock" in from_plan
    assert "addSlideCitations" in shared
    assert "citation.mjs" in from_plan


def test_block_export_default_true() -> None:
    from archium.config.settings import Settings

    assert Settings().block_export_on_critical_review is True


def test_resolve_export_verdict_safe_unknown() -> None:
    with patch(
        "archium.infrastructure.database.session.get_session",
        side_effect=RuntimeError("db"),
    ):
        verdict = resolve_export_verdict_safe(
            project_id=uuid4(),
            presentation_id=uuid4(),
        )
    assert verdict.status == ExportVerdictStatus.BLOCKED
