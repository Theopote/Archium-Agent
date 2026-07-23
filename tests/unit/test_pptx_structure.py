"""Tests for native PPTX master/layout/placeholder structure specs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from archium.domain.visual.pptx_structure import (
    PlaceholderKind,
    PlaceholderSpec,
    PptxStructureMode,
    PresentationStructureSpec,
    SlideLayoutSpec,
    SlideMasterSpec,
    default_archium_structure_spec,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.infrastructure.renderers.pptx_ooxml_structure import (
    inspect_pptx_ooxml_structure,
    require_structured_ooxml,
)
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter
from pydantic import ValidationError


def test_default_structure_catalog_is_structured_and_linked() -> None:
    spec = default_archium_structure_spec()
    assert spec.mode == PptxStructureMode.STRUCTURED
    assert len(spec.masters) >= 2
    assert len(spec.layouts) >= 2
    assert all(layout.master_id in {m.id for m in spec.masters} for layout in spec.layouts)
    drawing = spec.layout_for_family("drawing_focus")
    assert drawing.id == "layout.drawing_focus"
    assert any(ph.placeholder_type == PlaceholderKind.IMAGE for ph in drawing.placeholder_specs)


def test_p0_spike_spec_has_one_master_three_layouts_and_required_placeholders() -> None:
    from archium.domain.visual.pptx_structure import p0_structured_spike_spec

    spec = p0_structured_spike_spec()
    assert len(spec.masters) == 1
    assert len(spec.layouts) == 3
    kinds = {ph.placeholder_type for layout in spec.layouts for ph in layout.placeholder_specs}
    assert kinds >= {
        PlaceholderKind.TITLE,
        PlaceholderKind.BODY,
        PlaceholderKind.IMAGE,
        PlaceholderKind.SLIDE_NUMBER,
    }


def test_structure_spec_rejects_orphan_layout() -> None:
    with pytest.raises(ValidationError, match="unknown master_id"):
        PresentationStructureSpec(
            mode=PptxStructureMode.STRUCTURED,
            masters=[SlideMasterSpec(id="m1", name="M1")],
            layouts=[
                SlideLayoutSpec(
                    id="l1",
                    master_id="missing",
                    name="L1",
                    placeholder_specs=[
                        PlaceholderSpec(
                            id="ph1",
                            name="title",
                            placeholder_type=PlaceholderKind.TITLE,
                            x=0.5,
                            y=0.5,
                            width=9,
                            height=0.7,
                        )
                    ],
                )
            ],
        )


def test_flat_mode_allows_empty_graph() -> None:
    spec = PresentationStructureSpec(mode=PptxStructureMode.FLAT)
    assert spec.masters == []
    assert spec.layouts == []


def test_scene_adapter_embeds_structure_payload_when_structured() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        source_layout_family="textual_argument",
        nodes=[
            TextNode(
                id="title",
                x=0.5,
                y=0.4,
                width=9,
                height=0.7,
                text="Hello",
                font_family="Arial",
                font_size=24,
                color="#111111",
                line_height=1.2,
                semantic_role="title",
            )
        ],
    )
    deck = RenderScenePptxAdapter().render_deck(
        title="Structured",
        scenes=[(scene, None)],
        structure_mode=PptxStructureMode.STRUCTURED,
    )
    assert deck["structure_mode"] == "structured"
    structure = deck["structure"]
    assert structure["mode"] == "structured"
    assert len(structure["masters"]) >= 2
    assert len(structure["layouts"]) >= 2
    assert structure["layouts"][0]["placeholder_specs"]


def test_scene_adapter_omits_structure_in_flat_mode() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
    )
    deck = RenderScenePptxAdapter().render_deck(
        title="Flat",
        scenes=[(scene, None)],
        structure_mode=PptxStructureMode.FLAT,
    )
    assert deck["structure_mode"] == "flat"
    assert "structure" not in deck


def _write_minimal_structured_pptx(path: Path) -> None:
    """Synthetic OOXML package with master/layout/slide relationship chain."""
    presentation = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
    <p:sldMasterId id="2147483649" r:id="rId2"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId3"/>
  </p:sldIdLst>
</p:presentation>
"""
    master = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/></p:spTree></p:cSld>
</p:sldMaster>
"""
    layout = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr/><p:grpSpPr/>
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr>
        <p:ph type="title" idx="0"/>
      </p:nvPr></p:nvSpPr>
      <p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
    </p:sp>
  </p:spTree></p:cSld>
</p:sldLayout>
"""
    slide = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/></p:spTree></p:cSld>
</p:sld>
"""
    slide_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
    Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
"""
    layout_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
    Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""
    layout2_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
    Target="../slideMasters/slideMaster2.xml"/>
</Relationships>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/slideMasters/slideMaster1.xml", master)
        archive.writestr("ppt/slideMasters/slideMaster2.xml", master)
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        archive.writestr("ppt/slideLayouts/slideLayout2.xml", layout)
        archive.writestr("ppt/slides/slide1.xml", slide)
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels)
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        archive.writestr("ppt/slideLayouts/_rels/slideLayout2.xml.rels", layout2_rels)


def test_ooxml_inspector_detects_structured_package(tmp_path: Path) -> None:
    pptx = tmp_path / "structured.pptx"
    _write_minimal_structured_pptx(pptx)
    report = inspect_pptx_ooxml_structure(pptx)
    assert report.valid
    assert report.structure_mode == PptxStructureMode.STRUCTURED
    assert len(report.master_parts) == 2
    assert len(report.layout_parts) == 2
    assert report.slide_to_layout
    assert report.layout_to_master
    assert report.placeholder_count >= 1
    require_structured_ooxml(pptx)


def test_ooxml_inspector_rejects_missing_masters(tmp_path: Path) -> None:
    pptx = tmp_path / "broken.pptx"
    with ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )
        archive.writestr("ppt/slides/slide1.xml", "<p:sld/>")
    report = inspect_pptx_ooxml_structure(pptx)
    assert not report.valid
    assert report.structure_mode == PptxStructureMode.FLAT
    with pytest.raises(ValueError, match="STRUCTURED|slideMasters"):
        require_structured_ooxml(pptx)
