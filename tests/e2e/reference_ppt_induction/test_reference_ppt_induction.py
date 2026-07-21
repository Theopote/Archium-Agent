"""E2E acceptance for Phase 0–3 reference PPT induction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import FunctionalSlideType
from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available

from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_e2e_reference_ppt_induction_structure_only(tmp_path: Path) -> None:
    """Structure/classification acceptance without screenshots.

    CI hosts without LibreOffice/PowerPoint keep this gate. It does **not**
    satisfy the Phase 0–3 screenshot artifact requirement — see
    ``test_real_reference_ppt_induction_with_screenshots``.
    """
    pptx = write_architectural_reference_pptx(tmp_path / "建筑参考汇报.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "out" / str(induction_id))  # type: ignore[method-assign]

    first = service.induce(pptx, name="建筑参考", capture_screenshots=False)
    second = service.induce(pptx, name="建筑参考", capture_screenshots=False)

    assert first.induction.slide_count == second.induction.slide_count
    assert first.induction.slide_count >= 16
    assert first.screenshot_count == 0

    for name in (
        "reference_presentation.json",
        "functional_classification.json",
        "content_clusters.json",
        "representative_slides.json",
    ):
        assert (first.workspace / name).is_file()

    slide_jsons = list((first.workspace / "slides").glob("slide_*.json"))
    assert len(slide_jsons) == first.induction.slide_count

    types = {c.functional_type for c in first.induction.classifications}
    assert FunctionalSlideType.COVER in types
    assert FunctionalSlideType.AGENDA in types or FunctionalSlideType.SECTION_DIVIDER in types
    assert FunctionalSlideType.CONTENT in types
    assert FunctionalSlideType.CLOSING in types

    content_clusters = [
        c
        for c in first.induction.clusters
        if c.functional_type == FunctionalSlideType.CONTENT
    ]
    assert len(content_clusters) >= 3
    assert all(c.representative_slide_id for c in first.induction.clusters)

    def fingerprint(run):
        return sorted(
            (
                c.content_type.value,
                tuple(c.slide_ids),
                c.representative_slide_id,
            )
            for c in run.induction.clusters
            if c.functional_type == FunctionalSlideType.CONTENT
        )

    assert fingerprint(first) == fingerprint(second)

    payload = json.loads(
        (first.workspace / "reference_presentation.json").read_text(encoding="utf-8")
    )
    for slide in payload["slides"]:
        assert not is_machine_absolute_path(slide.get("image_path") or "")


@pytest.mark.requires_libreoffice
def test_real_reference_ppt_induction_with_screenshots(tmp_path: Path) -> None:
    """Phase 0–3 screenshot acceptance: every page has slide_XXX.json + slide_XXX.png."""
    if not screenshot_tools_available():
        pytest.skip(
            "LibreOffice+pdftoppm or Windows PowerPoint required for screenshot acceptance"
        )

    pptx = write_architectural_reference_pptx(tmp_path / "建筑参考汇报.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "shot" / str(induction_id))  # type: ignore[method-assign]

    result = service.induce(
        pptx,
        name="建筑参考截图验收",
        capture_screenshots=True,
        require_screenshots=True,
    )
    presentation = result.presentation
    workspace = result.workspace

    assert presentation.slide_count >= 16
    assert result.screenshot_tools_available is True
    assert result.screenshot_count == presentation.slide_count
    assert all(slide.image_path for slide in presentation.slides)
    assert all(
        (workspace / slide.image_path).is_file() for slide in presentation.slides
    )

    for slide in presentation.slides:
        json_path = workspace / "slides" / f"{slide.slide_id}.json"
        png_path = workspace / "slides" / f"{slide.slide_id}.png"
        assert json_path.is_file(), f"missing {json_path.name}"
        assert png_path.is_file(), f"missing {png_path.name}"
        assert slide.image_path == f"slides/{slide.slide_id}.png"
        assert not is_machine_absolute_path(slide.image_path)
        # Non-trivial raster (not an empty placeholder).
        assert png_path.stat().st_size > 1_000
