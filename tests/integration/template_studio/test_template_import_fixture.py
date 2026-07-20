"""Integration: import a real fixture PPTX into Template Studio."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.template_studio_service import TemplateStudioService
from archium.config.settings import Settings
from sqlalchemy.orm import Session

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "e2e"
    / "real_projects"
    / "files"
    / "cultural_village_001"
    / "documents"
    / "参考汇报版式.pptx"
)


def test_import_real_reference_pptx(db_session: Session, tmp_path: Path) -> None:
    if not _FIXTURE.is_file():
        return
    settings = Settings(_env_file=None, output_path=tmp_path)
    service = TemplateStudioService(db_session, settings=settings)
    result = service.import_pptx(_FIXTURE, name="文化名村参考版式")
    assert result.template.layouts
    assert result.template.source_master_metadata.slide_count == len(result.template.layouts)
    # At least structure extraction produced slots or explicit empty pages.
    assert all(layout.page_width > 0 for layout in result.template.layouts)
    preview = service.fill_test_content_preview(
        result.template.id,
        result.template.layouts[0].id,
    )
    assert preview.preview_path.is_file()
