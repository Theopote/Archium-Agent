"""Formal editable PPTX export authority and legacy Spec fallback gates."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.formal_pptx_export_service import FormalPptxExportService
from archium.config.settings import Settings
from archium.domain.citation import Citation
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.export_authority import DerivedExportKind, FormalExportAuthority
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def presentation_without_visual_layout(
    db_session: Session,
) -> tuple[Project, Presentation]:
    projects = ProjectRepository(db_session)
    presentations = PresentationRepository(db_session)
    project = projects.create(Project(name="导出门禁测试"))
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="测试汇报",
            audience="甲方",
            purpose="测试",
            core_message="核心信息一句。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="测试论点。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="内容页",
            message="要点说明。",
            slide_type=SlideType.CONTENT,
            key_points=["指标 A"],
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.TEXT_ONLY,
                    description="文字",
                )
            ],
            source_citations=[
                Citation(document_id=uuid4(), document_name="任务书.pdf", page_number=1)
            ],
        )
    )
    db_session.commit()
    return project, presentation


def test_default_settings_disallow_legacy_spec_pptx_fallback() -> None:
    settings = Settings()
    assert settings.allow_legacy_presentation_spec_pptx_fallback is False


def test_export_without_visual_layout_rejects_spec_fallback_by_default(
    db_session: Session,
    test_settings: Settings,
    presentation_without_visual_layout: tuple[Project, Presentation],
) -> None:
    _, presentation = presentation_without_visual_layout
    service = FormalPptxExportService(db_session, settings=test_settings)
    with pytest.raises(WorkflowError, match="RenderScene"):
        service.export_editable_pptx(presentation.id)


def test_export_without_visual_layout_allows_explicit_legacy_fallback(
    db_session: Session,
    test_settings: Settings,
    presentation_without_visual_layout: tuple[Project, Presentation],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    _, presentation = presentation_without_visual_layout
    editable = Path(str(tmp_path)) / "presentation.editable.pptx"  # type: ignore[arg-type]
    editable.write_bytes(b"pptx")

    class _FakeRenderer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def output_dir(self, presentation_id: object, *, version: int) -> Path:
            return editable.parent

        def render(self, **kwargs: object) -> Path:
            spec = editable.parent / "presentation.spec.json"
            spec.write_text("{}", encoding="utf-8")
            return spec

    monkeypatch.setattr(
        "archium.infrastructure.renderers.pptxgen_renderer.PptxGenPresentationRenderer",
        _FakeRenderer,
    )

    def _fake_extras(renderer: object, spec_path: Path, *, export_editable_pptx: bool) -> object:
        from archium.application.render_export import PptxGenExportExtras

        assert export_editable_pptx
        return PptxGenExportExtras(editable_pptx_path=editable, warnings=[])

    monkeypatch.setattr(
        "archium.application.render_export.export_pptxgen_extras",
        _fake_extras,
    )

    service = FormalPptxExportService(db_session, settings=test_settings)
    result = service.export_editable_pptx(
        presentation.id,
        allow_legacy_spec_fallback=True,
    )
    assert result.authority == DerivedExportKind.PRESENTATION_SPEC
    assert result.path == editable
    assert any("遗留 PresentationSpec" in warning for warning in result.warnings)


def test_presentation_spec_builder_docstring_marks_compat_only() -> None:
    import archium.infrastructure.renderers.presentation_spec_builder as builder

    doc = builder.__doc__ or ""
    assert "compat" in doc.lower()
    assert "render_scene" in doc.lower() or "RenderScene" in doc
