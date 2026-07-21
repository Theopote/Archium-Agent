"""E2E acceptance for Phase 0–3 reference PPT induction."""

from __future__ import annotations

import json
from pathlib import Path

from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import FunctionalSlideType
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_e2e_reference_ppt_induction_acceptance(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "建筑参考汇报.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "out" / str(induction_id))  # type: ignore[method-assign]

    first = service.induce(pptx, name="建筑参考", capture_screenshots=False)
    second = service.induce(pptx, name="建筑参考", capture_screenshots=False)

    assert first.induction.slide_count == second.induction.slide_count
    assert first.induction.slide_count >= 16

    # Required artifacts
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

    # Stability of content cluster membership signatures
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

    # Portable paths only
    payload = json.loads(
        (first.workspace / "reference_presentation.json").read_text(encoding="utf-8")
    )
    for slide in payload["slides"]:
        assert not is_machine_absolute_path(slide.get("image_path") or "")
