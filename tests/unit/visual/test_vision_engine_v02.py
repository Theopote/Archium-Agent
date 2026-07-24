"""Vision Engine v0.2 — style templates + diagram base overlay."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.vision import (
    DEFAULT_STYLE_REGISTRY,
    VisionDiagramComposer,
    VisionImageGenerationService,
    VisionPromptCompiler,
)
from archium.application.visual.vision.diagram_composer import DiagramComposeRequest
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationContext,
    VisionStylePreset,
)


def test_style_registry_defaults_per_type() -> None:
    registry = DEFAULT_STYLE_REGISTRY
    assert registry.default_style_for(ArchitectureImageType.FLOW_DIAGRAM) == (
        VisionStylePreset.AXONOMETRIC_DIAGRAM
    )
    assert registry.default_style_for(ArchitectureImageType.ATMOSPHERE_IMAGE) == (
        VisionStylePreset.SOFT_ATMOSPHERE
    )
    assert registry.supports_base_overlay(ArchitectureImageType.SITE_DIAGRAM)
    assert not registry.supports_base_overlay(ArchitectureImageType.ATMOSPHERE_IMAGE)
    assert len(registry.list_styles()) >= 7
    assert len(registry.list_type_templates()) == len(ArchitectureImageType)


def test_compiler_resolves_default_style_and_compose_mode(tmp_path: Path) -> None:
    base = tmp_path / "site.png"
    # Minimal valid PNG via Pillow if available; otherwise skip compose assert path later.
    try:
        from PIL import Image

        Image.new("RGB", (200, 150), color=(200, 200, 200)).save(base)
    except ImportError:
        pytest.skip("Pillow unavailable")

    request = ImageRequest(
        image_type=ArchitectureImageType.FLOW_DIAGRAM,
        subject="covered walkway on hospital campus",
        style=None,
        base_image_path=str(base),
        overlay_cues=["入口", "风雨连廊", "门诊"],
    )
    spec = VisionPromptCompiler().compile(
        request,
        context=VisionGenerationContext(project_type="hospital", page_archetype="design_strategy"),
    )
    assert spec.style == VisionStylePreset.AXONOMETRIC_DIAGRAM.value
    assert spec.metadata.get("compose_mode") is True
    assert "compose_mode=base_overlay" in spec.rationale
    assert "analytical overlay" in spec.prompt.lower()
    assert "primary path" in spec.prompt  # type default element


def test_diagram_composer_overlays_base(tmp_path: Path) -> None:
    composer = VisionDiagramComposer()
    if not composer.is_available():
        pytest.skip("Pillow unavailable")

    from PIL import Image

    base = tmp_path / "plan.png"
    Image.new("RGB", (640, 400), color=(180, 185, 190)).save(base)
    data = composer.compose(
        DiagramComposeRequest(
            base_image_path=str(base),
            width=960,
            height=540,
            image_type=ArchitectureImageType.FLOW_DIAGRAM,
            subject="covered walkway",
            overlay_cues=("入口", "连廊"),
            prompt_hash="abcd1234",
        )
    )
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 2000


def test_generation_service_uses_composer_when_base_present(tmp_path: Path) -> None:
    from archium.config.settings import Settings
    from PIL import Image

    base = tmp_path / "site_plan.png"
    Image.new("RGB", (400, 300), color=(170, 175, 180)).save(base)

    settings = Settings(_env_file=None, project_storage_path=tmp_path / "storage")
    service = VisionImageGenerationService(session=None, settings=settings)
    project_id = uuid4()
    result = service.generate(
        ImageRequest(
            subject="rain-protected circulation",
            image_type=ArchitectureImageType.FLOW_DIAGRAM,
            base_image_path=str(base),
            overlay_cues=["入口", "风雨连廊"],
            width=800,
            height=450,
        ),
        project_id=project_id,
        persist_asset=True,
    )
    assert result.success is True
    assert result.provider == "diagram_composer"
    assert result.spec.metadata.get("compose_mode") is True
    assert result.storage_path is not None
    assert "vision_generated" in result.storage_path
