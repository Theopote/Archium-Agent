"""case_a: mixed WeChat / site / historic photos → StyleMatcher + Derivative E2E."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from archium.application.visual.image_derivative_executor import ImageDerivativeExecutor
from archium.application.visual.image_derivative_service import ImageDerivativeService
from archium.application.visual.image_source_classifier import ImageSourceClassifier
from archium.config.settings import Settings
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import ImageSourceKind, default_presentation_unify_params
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene
from archium.infrastructure.storage.local_storage import LocalProjectStorage

pytestmark = pytest.mark.regression


def _write_photo(
    path: Path,
    *,
    color: tuple[int, int, int],
    label: str,
    size: tuple[int, int] = (960, 640),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, size[0] - 30, size[1] - 30), outline=(255, 255, 255), width=3)
    draw.text((50, 50), label, fill=(255, 255, 255))
    image.save(path, format="JPEG", quality=88)
    return path


def test_case_a_mixed_sources_deck_style_and_derivatives(tmp_path: Path) -> None:
    if not ImageDerivativeExecutor().is_available():
        pytest.skip("Pillow unavailable")

    project_id = uuid4()
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        image_derivatives_enabled=True,
    )
    storage = LocalProjectStorage(settings=settings)
    layout = storage.ensure_project_layout(project_id)
    assets_dir = layout["assets"]

    # Warm WeChat export + dark site shot + faded historic — typical hospital deck mix.
    wechat = _write_photo(
        assets_dir / "mmexport1712345678901.jpg",
        color=(210, 140, 90),
        label="wechat courtyard",
    )
    site = _write_photo(
        assets_dir / "site_entry_dusk.jpg",
        color=(38, 40, 48),
        label="site entry",
    )
    historic = _write_photo(
        assets_dir / "historic_ward_1978.jpg",
        color=(155, 135, 105),
        label="historic ward",
    )

    classifier = ImageSourceClassifier()
    assert classifier.classify(filename=wechat.name).kind == ImageSourceKind.WECHAT_EXPORT
    assert classifier.classify(
        filename=site.name,
        description="现场踏勘入口",
        tags=["现场"],
    ).kind == ImageSourceKind.SITE_PHOTO
    assert classifier.classify(
        filename=historic.name,
        description="历史院区老照片",
        tags=["历史"],
    ).kind == ImageSourceKind.HISTORICAL

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="opening_hero",
                x=0.4,
                y=0.4,
                width=4.2,
                height=3.2,
                z_index=1,
                asset_id=uuid4(),
                storage_uri=str(wechat.resolve()),
                asset_origin="project_upload",
                semantic_role="historic_or_context_photo",
            ),
            ImageNode(
                id="site_evidence_1",
                x=5.0,
                y=0.4,
                width=2.2,
                height=1.6,
                z_index=2,
                asset_id=uuid4(),
                storage_uri=str(site.resolve()),
                asset_origin="project_upload",
                semantic_role="site_photo",
            ),
            ImageNode(
                id="site_evidence_2",
                x=7.4,
                y=0.4,
                width=2.2,
                height=1.6,
                z_index=3,
                asset_id=uuid4(),
                storage_uri=str(historic.resolve()),
                asset_origin="project_upload",
                semantic_role="historic_photo",
            ),
        ],
    )

    design = default_presentation_design_system()
    design = design.model_copy(
        update={
            "image_style": design.image_style.model_copy(
                update={"photo_treatment": PhotoTreatment.SUBTLE_UNIFY}
            )
        }
    )
    base = default_presentation_unify_params()
    before = {
        wechat.name: wechat.read_bytes(),
        site.name: site.read_bytes(),
        historic.name: historic.read_bytes(),
    }
    result = ImageDerivativeService(
        session=None,
        settings=settings,
        storage=storage,
    ).apply_to_scene(scene, project_id=project_id, design_system=design)

    assert result.deck_style is not None
    assert result.deck_style.sample_count == 3
    assert result.deck_style.median_warmth is not None
    # Warm WeChat + sepia historic pull median warmth positive → cooler deck temperature.
    assert result.deck_style.unify.temperature <= base.temperature
    assert len(result.derivatives) == 3

    for node in result.scene.nodes:
        assert isinstance(node, ImageNode)
        assert "cache/derivatives/" in (node.storage_uri or "")

    # Originals stay byte-identical; derivatives are separate cache files.
    assert wechat.read_bytes() == before[wechat.name]
    assert site.read_bytes() == before[site.name]
    assert historic.read_bytes() == before[historic.name]
