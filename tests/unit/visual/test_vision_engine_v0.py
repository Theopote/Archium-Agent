"""Vision Engine v0.1 — Prompt Compiler + stub generation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.vision import VisionImageGenerationService, VisionPromptCompiler
from archium.domain.visual.enums import ContinuityRole, DensityLevel, VisualContentType
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationContext,
    VisionStylePreset,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.vision_gen import StubVisionImageGenerator


def test_prompt_compiler_injects_architecture_semantics() -> None:
    request = ImageRequest(
        image_type=ArchitectureImageType.FLOW_DIAGRAM,
        subject="hospital campus covered walkway between entrance and outpatient hall",
        purpose="explain weather-protected circulation improvement",
        style=VisionStylePreset.AXONOMETRIC_DIAGRAM,
        elements=["patients walking", "transparent canopy", "rain weather cue"],
        avoid=["luxury lobby"],
    )
    context = VisionGenerationContext(
        project_type="healthcare renovation",
        project_phase="concept",
        audience="government review",
        page_title="交通优化策略",
        page_message="增加风雨连廊",
        page_archetype="design_strategy",
    )
    spec = VisionPromptCompiler().compile(request, context=context)
    assert "Architectural visualization" in spec.prompt
    assert "covered walkway" in spec.prompt
    assert "government review" in spec.prompt
    assert "healthcare renovation" in spec.prompt
    assert "luxury commercial" in spec.negative_prompt
    assert "site photograph" in spec.negative_prompt.lower() or "evidence" in spec.negative_prompt
    assert spec.prompt_hash
    assert spec.asset_policy.value == "illustrative_only"


def test_stub_generator_writes_png_bytes() -> None:
    generator = StubVisionImageGenerator()
    if not generator.is_available():
        pytest.skip("Pillow unavailable")
    request = ImageRequest(
        subject="courtyard healing garden concept",
        image_type=ArchitectureImageType.CONCEPT_SKETCH,
        width=640,
        height=360,
    )
    spec = VisionPromptCompiler().compile(request)
    payload = generator.generate(spec)
    assert payload.mime_type == "image/png"
    assert payload.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload.data) > 500


def test_generation_service_persists_illustrative_file(tmp_path) -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.storage.local_storage import LocalProjectStorage

    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    service = VisionImageGenerationService(session=None, settings=settings)
    project_id = uuid4()
    result = service.generate_for_intent(
        request=ImageRequest(
            subject="covered walkway linking entrance to outpatient",
            image_type=ArchitectureImageType.FLOW_DIAGRAM,
            style=VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
        ),
        project_id=project_id,
        slide_title="交通优化策略",
        slide_message="增加风雨连廊",
        project_type="hospital",
        persist_asset=True,
    )
    assert result.success is True
    assert result.illustrative is True
    assert result.storage_path is not None
    assert "vision_generated" in result.storage_path
    assert result.asset_id is None  # no DB session
    files = list(
        (LocalProjectStorage(settings=settings).ensure_project_layout(project_id)["assets"] / "vision_generated").glob(
            "*.png"
        )
    )
    assert files
    assert files[0].stat().st_size > 500


def test_openai_compatible_adapter_decodes_b64() -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.vision_gen.openai_compatible import (
        OpenAICompatibleVisionImageGenerator,
        _map_size,
    )

    assert _map_size(1280, 720) == "1792x1024"
    assert _map_size(720, 1280) == "1024x1792"
    assert _map_size(1024, 1024) == "1024x1024"

    class _Data:
        b64_json = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )

    class _Response:
        data = [_Data()]

    class _Images:
        def generate(self, **kwargs):
            assert kwargs["response_format"] == "b64_json"
            return _Response()

    class _Client:
        images = _Images()

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="openai_compatible",
        vision_image_generation_api_key="test-key",
    )
    generator = OpenAICompatibleVisionImageGenerator(settings, client=_Client())
    assert generator.is_available()
    request = ImageRequest(subject="test canopy", width=1280, height=720)
    spec = VisionPromptCompiler().compile(request)
    payload = generator.generate(spec)
    assert payload.provider == "openai_compatible"
    assert payload.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_factory_falls_back_to_stub_when_api_disabled() -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.vision_gen import (
        StubVisionImageGenerator,
        build_vision_image_generator,
    )

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=False,
        vision_image_generation_provider="openai_compatible",
    )
    generator = build_vision_image_generator(settings)
    assert isinstance(generator, StubVisionImageGenerator)


def test_visual_intent_accepts_image_request() -> None:
    intent = VisualIntent(
        slide_id=uuid4(),
        communication_goal="说明连廊策略",
        audience_takeaway="风雨连廊改善体验",
        visual_priority="diagram",
        dominant_content_type=VisualContentType.ANALYTICAL_DIAGRAM,
        density_level=DensityLevel.BALANCED,
        continuity_role=ContinuityRole.EXPLANATION,
        image_request=ImageRequest(
            subject="covered walkway diagram",
            image_type=ArchitectureImageType.FLOW_DIAGRAM,
        ),
    )
    assert intent.image_request is not None
    assert intent.image_request.image_type == ArchitectureImageType.FLOW_DIAGRAM
