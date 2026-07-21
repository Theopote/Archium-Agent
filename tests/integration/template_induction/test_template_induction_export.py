"""Integration tests for template induction artifact export."""

from __future__ import annotations

import json
from pathlib import Path

from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.reference_slide import REFERENCE_TEMPLATE_ASSET_ORIGIN
from archium.domain.visual.template_induction import FunctionalSlideType
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_induction_exports_acceptance_artifacts(tmp_path: Path, monkeypatch) -> None:
    from archium.config import settings as settings_mod

    monkeypatch.setattr(
        settings_mod.get_settings(),
        "output_path",
        tmp_path / "output",
    )
    # Settings may be cached — force service workspace under tmp.
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]

    result = service.induce(pptx, name="测试归纳", capture_screenshots=False)
    workspace = result.workspace

    assert (workspace / "reference_presentation.json").is_file()
    assert (workspace / "functional_classification.json").is_file()
    assert (workspace / "content_clusters.json").is_file()
    assert (workspace / "representative_slides.json").is_file()
    slides_dir = workspace / "slides"
    assert slides_dir.is_dir()
    slide_jsons = list(slides_dir.glob("slide_*.json"))
    assert len(slide_jsons) == result.induction.slide_count

    ref = json.loads((workspace / "reference_presentation.json").read_text(encoding="utf-8"))
    assert ref["slide_count"] == result.induction.slide_count

    clusters = json.loads((workspace / "content_clusters.json").read_text(encoding="utf-8"))
    content_clusters = [c for c in clusters if c["functional_type"] == "content"]
    assert len(content_clusters) >= 3

    reps = json.loads((workspace / "representative_slides.json").read_text(encoding="utf-8"))
    assert all(r["representative_slide_id"] for r in reps)

    # No absolute paths; reference assets stay reference_template.
    blob = (workspace / "reference_presentation.json").read_text(encoding="utf-8")
    assert ":\\" not in blob.replace("https://", "").replace("http://", "")
    for slide in ref["slides"]:
        assert not is_machine_absolute_path(slide.get("image_path") or "")
        for asset in slide.get("image_assets") or []:
            assert asset["asset_origin"] == REFERENCE_TEMPLATE_ASSET_ORIGIN


def test_reference_text_not_treated_as_project_facts(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    # Induction artifacts are reference-only — no manuscript facts created.
    assert not hasattr(result.presentation, "verified_facts")
    for slide in result.presentation.slides:
        for asset in slide.image_assets:
            assert asset.asset_origin == REFERENCE_TEMPLATE_ASSET_ORIGIN
    assert any(
        c.functional_type == FunctionalSlideType.COVER for c in result.induction.classifications
    )
