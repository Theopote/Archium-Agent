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


def test_concept_draft_skips_scene_semantic_blockers() -> None:
    session = MagicMock()
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
            return_value=["[scene] 图片节点未渲染"],
        ),
        patch(
            "archium.application.evidence_readiness_service._citation_gap_messages",
            return_value=[],
        ),
    ):
        review_cls.return_value.list_review_issues.return_value = []
        doc_cls.return_value.list_by_project.return_value = []
        pres_cls.return_value.list_slides.return_value = []
        from archium.application.evidence_readiness_service import resolve_delivery_readiness

        report = resolve_delivery_readiness(
            session,
            project_id=uuid4(),
            presentation_id=uuid4(),
        )
    assert "概念草稿不可正式交付：请先绑定至少一份项目资料" in report.blockers
    assert "[scene] 图片节点未渲染" not in report.blockers
    assert "scene_semantic" not in report.evidence_stacks


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


def test_app004_export_gate_facade_and_evidence_stacks() -> None:
    """APP-004: stacks produce evidence; export reads ExportVerdict via facade."""
    from archium.application import export_gate
    from archium.application.evidence_readiness_service import resolve_delivery_readiness

    assert export_gate.resolve_export_verdict_safe is resolve_export_verdict_safe
    assert hasattr(export_gate, "assert_formal_export_allowed")

    report = DeliveryReadinessReport(
        evidence=ProjectEvidenceStatus(
            availability=EvidenceAvailability.AVAILABLE,
            document_count=1,
        ),
        pptx_ready=True,
        pdf_ready=True,
        evidence_stacks=("materials_evidence", "deck_qa", "presentation_critic"),
    )
    verdict = report.to_export_verdict()
    assert verdict.evidence_stacks == (
        "materials_evidence",
        "deck_qa",
        "presentation_critic",
    )
    assert verdict.allows_formal_export

    session = MagicMock()
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
        patch(
            "archium.application.evidence_readiness_service._citation_gap_messages",
            return_value=[],
        ),
    ):
        review_cls.return_value.list_review_issues.return_value = []
        doc_cls.return_value.list_by_project.return_value = [object()]
        pres_cls.return_value.list_slides.return_value = []
        resolved = resolve_delivery_readiness(
            session,
            project_id=uuid4(),
            presentation_id=uuid4(),
            deck_qa_report={"blocker_count": 0},
            presentation_critique={"suggestions": ["tighten story"]},
        )
    assert "materials_evidence" in resolved.evidence_stacks
    assert "deck_qa" in resolved.evidence_stacks
    assert "presentation_critic" in resolved.evidence_stacks
    out = resolved.to_export_verdict()
    assert out.evidence_stacks == resolved.evidence_stacks


def test_app004_product_export_ui_reads_verdict_only() -> None:
    root = Path(__file__).resolve().parents[2]
    export = (root / "archium/ui/studio/export_panel.py").read_text(encoding="utf-8")
    deliver = (root / "archium/ui/pages/flow/deliver.py").read_text(encoding="utf-8")
    assert "from archium.application.export_gate import" in export
    assert "resolve_export_verdict_safe" in export
    assert "assert_formal_export_allowed" in export
    assert "export_gate" in deliver
    # Must not gate export buttons on DeliveryReadinessReport.allows_formal_export directly
    assert "readiness.allows_formal_export" not in export
    assert "_export_verdict" in export
