"""Tests for perceptual slide recovery OCR/VLM adapters."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from archium.application.slide_recovery_region_analyzer import SlideRecoveryRegionAnalyzer
from archium.application.slide_recovery_service import SlideRecoveryRequest, SlideRecoveryService
from archium.domain.slide_recovery import SlideRecoveryPageKind
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene, TextNode
from archium.infrastructure.llm.slide_recovery_schemas import (
    SlideRecoveryPageAnalysisDraft,
    SlideRecoveryRegionDraft,
)
from archium.infrastructure.slide_recovery.ocr_region_detector import detect_text_regions
from archium.infrastructure.slide_recovery.perceptual_region_adapter import (
    is_raster_proxy_scene,
    regions_from_page_image,
)
from archium.infrastructure.slide_recovery.vlm_region_analyzer import VlmRegionAnalyzer


def _raster_scene(image_path: Path) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="source_page_image",
                x=0,
                y=0,
                width=10.0,
                height=5.625,
                z_index=0,
                storage_uri=f"file://{image_path.resolve().as_posix()}",
                semantic_role="source_page",
                asset_origin="project_upload",
                fit_mode="contain",
            )
        ],
    )


def test_is_raster_proxy_scene_detects_full_page_image() -> None:
    scene = _raster_scene(Path("page.png"))
    assert is_raster_proxy_scene(scene) is True


def test_ocr_detects_drawn_text(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    image_path = tmp_path / "text_page.png"
    image = Image.new("RGB", (1200, 675), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((80, 60), "测试标题", fill=(0, 0, 0))
    image.save(image_path)

    with patch(
        "archium.infrastructure.slide_recovery.ocr_region_detector._pytesseract"
    ) as mock_tesseract:
        mock_tesseract.Output = MagicMock()
        mock_tesseract.Output.DICT = "dict"
        mock_tesseract.image_to_data.return_value = {
            "text": ["", "测试标题"],
            "conf": ["-1", "92"],
            "left": [0, 80],
            "top": [0, 60],
            "width": [0, 220],
            "height": [0, 48],
            "block_num": [0, 1],
            "par_num": [0, 1],
            "line_num": [0, 1],
        }
        result = detect_text_regions(image_path, page_width=10.0, page_height=5.625)

    assert result.engine == "pytesseract"
    assert result.char_count > 0
    assert any(region.region_type == "text" for region in result.regions)


def test_vlm_analyzer_uses_llm_when_configured(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "drawing.png"
    Image.new("RGB", (800, 600), color=(240, 240, 240)).save(image_path)

    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = SlideRecoveryPageAnalysisDraft(
        page_kind="drawing_dominant",
        regions=[
            SlideRecoveryRegionDraft(
                region_type="drawing",
                bbox_x=0.05,
                bbox_y=0.1,
                bbox_width=0.9,
                bbox_height=0.8,
                semantic_role="site_plan",
                keep_whole_drawing=True,
            )
        ],
    )
    settings = MagicMock()
    settings.slide_recovery_vlm_enabled = True
    settings.llm_configured = True
    settings.slide_recovery_vlm_model = None
    settings.llm_model = "vision-model"

    analyzer = VlmRegionAnalyzer(llm=mock_llm, settings=settings, enabled=True)
    result = analyzer.analyze(image_path, page_width=10.0, page_height=5.625)

    assert result.source == "llm_vision"
    assert result.page_kind == SlideRecoveryPageKind.DRAWING_DOMINANT
    assert any(region.region_type == "drawing" for region in result.regions)
    mock_llm.generate_structured.assert_called_once()


def test_perceptual_adapter_combines_ocr_and_vlm(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "page.png"
    Image.new("RGB", (640, 360), color=(255, 255, 255)).save(image_path)
    scene = _raster_scene(image_path)

    mock_vlm = MagicMock()
    mock_vlm.analyze.return_value = MagicMock(
        page_kind=SlideRecoveryPageKind.IMAGE_TEXT,
        regions=[],
        source="heuristic",
    )

    with patch(
        "archium.infrastructure.slide_recovery.perceptual_region_adapter.detect_text_regions"
    ) as mock_ocr:
        from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion
        from archium.infrastructure.slide_recovery.ocr_region_detector import OcrDetectionResult

        mock_ocr.return_value = OcrDetectionResult(
            regions=[
                RecoveredPageRegion(
                    id=uuid4(),
                    bbox=NormalizedBox(x=0.1, y=0.1, width=0.3, height=0.1),
                    region_type="text",
                    recovered_text="标题",
                )
            ],
            engine="pytesseract",
            char_count=2,
        )
        result = regions_from_page_image(scene, image_path, vlm_analyzer=mock_vlm)

    assert result.ocr_engine == "pytesseract"
    assert result.vlm_source == "heuristic"
    assert any(region.region_type == "text" for region in result.regions)


def test_region_analyzer_uses_perceptual_for_raster(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "page.png"
    Image.new("RGB", (800, 450), color=(255, 255, 255)).save(image_path)
    scene = _raster_scene(image_path)

    analysis = SlideRecoveryRegionAnalyzer(session=None).analyze(
        scene,
        source_page_id="page_1",
        source_image_path=image_path,
    )
    assert analysis.mode == "perceptual"
    assert analysis.vlm_source in {"heuristic", "llm_vision"}


def test_service_raster_recovery_records_analysis_meta(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "page.png"
    Image.new("RGB", (800, 450), color=(255, 255, 255)).save(image_path)
    scene = _raster_scene(image_path)

    with patch(
        "archium.application.slide_recovery_region_analyzer.regions_from_page_image"
    ) as mock_perceptual:
        from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion
        from archium.infrastructure.slide_recovery.perceptual_region_adapter import (
            PerceptualAnalysisResult,
        )

        mock_perceptual.return_value = PerceptualAnalysisResult(
            regions=[
                RecoveredPageRegion(
                    id=uuid4(),
                    bbox=NormalizedBox(x=0.0, y=0.0, width=1.0, height=1.0),
                    region_type="background",
                    bitmap_fallback=True,
                    source_asset_uri=f"file://{image_path}",
                )
            ],
            page_kind=SlideRecoveryPageKind.IMAGE_TEXT,
            ocr_engine=None,
            vlm_source="heuristic",
            ocr_char_count=0,
        )
        result = SlideRecoveryService(session=None).recover_page(
            SlideRecoveryRequest(
                source_page_id="page_1",
                source_scene=scene,
                source_image_path=image_path,
            )
        )

    assert result.analysis_meta.get("analysis_mode") == "perceptual"
    assert result.analysis_meta.get("vlm_source") == "heuristic"
    assert result.hybrid_scene is not None


def test_hybrid_merge_supplements_structural_text() -> None:
    from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion
    from archium.infrastructure.slide_recovery.structural_perceptual_merge import (
        merge_structural_and_perceptual,
    )

    structural = [
        RecoveredPageRegion(
            id=uuid4(),
            bbox=NormalizedBox(x=0.1, y=0.1, width=0.3, height=0.08),
            region_type="text",
            recovered_text="测试标题",
            source_node_id="text_0",
        )
    ]
    perceptual = [
        RecoveredPageRegion(
            id=uuid4(),
            bbox=NormalizedBox(x=0.1, y=0.5, width=0.4, height=0.08),
            region_type="text",
            recovered_text="补充正文",
        ),
        RecoveredPageRegion(
            id=uuid4(),
            bbox=NormalizedBox(x=0.0, y=0.0, width=1.0, height=1.0),
            region_type="background",
            bitmap_fallback=True,
        ),
    ]
    merged = merge_structural_and_perceptual(structural, perceptual)
    assert len(merged) == 3
    assert any(region.recovered_text == "补充正文" for region in merged)


def test_region_analyzer_hybrid_for_structural_pptx_with_preview(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "preview.png"
    Image.new("RGB", (800, 450), color=(255, 255, 255)).save(image_path)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="text_0",
                x=1,
                y=1,
                width=4,
                height=1,
                z_index=0,
                text="结构标题",
                semantic_role="title",
                font_family="Microsoft YaHei",
                font_size=18,
                color="#1A1A1A",
                line_height=24,
            )
        ],
    )

    with patch(
        "archium.application.slide_recovery_region_analyzer.regions_from_page_image"
    ) as mock_perceptual:
        from archium.domain.slide_recovery import NormalizedBox, RecoveredPageRegion
        from archium.infrastructure.slide_recovery.perceptual_region_adapter import (
            PerceptualAnalysisResult,
        )

        mock_perceptual.return_value = PerceptualAnalysisResult(
            regions=[
                RecoveredPageRegion(
                    id=uuid4(),
                    bbox=NormalizedBox(x=0.1, y=0.5, width=0.5, height=0.1),
                    region_type="text",
                    recovered_text="OCR 补充",
                )
            ],
            page_kind=SlideRecoveryPageKind.IMAGE_TEXT,
            ocr_engine="pytesseract",
            vlm_source="heuristic",
            ocr_char_count=4,
        )
        analysis = SlideRecoveryRegionAnalyzer(session=None).analyze(
            scene,
            source_page_id="pptx_1",
            source_image_path=image_path,
            source_kind="pptx",
        )

    assert analysis.mode == "hybrid"
    assert any(region.recovered_text == "结构标题" for region in analysis.regions)
    assert any(region.recovered_text == "OCR 补充" for region in analysis.regions)
