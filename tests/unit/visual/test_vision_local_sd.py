"""Local SD (A1111/Forge) Vision Engine adapter."""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.vision import VisionPromptCompiler
from archium.config.settings import Settings
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationMode,
)
from archium.infrastructure.vision_gen import (
    LocalSdVisionImageGenerator,
    StubVisionImageGenerator,
    build_vision_image_generator,
)
from archium.infrastructure.vision_gen.local_sd import _clamp_dim


_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_clamp_dim_multiple_of_eight() -> None:
    assert _clamp_dim(721) == 720
    assert _clamp_dim(100) == 256
    assert _clamp_dim(2000) == 1536


def test_factory_selects_local_sd_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="local_sd",
        vision_local_sd_base_url="http://127.0.0.1:7860",
    )
    generator = build_vision_image_generator(settings)
    assert isinstance(generator, LocalSdVisionImageGenerator)
    assert generator.is_available()


def test_factory_falls_back_stub_when_local_disabled() -> None:
    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=False,
        vision_image_generation_provider="local_sd",
    )
    generator = build_vision_image_generator(settings)
    assert isinstance(generator, StubVisionImageGenerator)


def test_local_sd_txt2img_via_transport() -> None:
    calls: list[tuple[str, str]] = []

    def transport(method: str, url: str, payload: dict | None) -> dict:
        calls.append((method, url))
        assert method == "POST"
        assert url.endswith("/sdapi/v1/txt2img")
        assert payload is not None
        assert "prompt" in payload
        assert "negative_prompt" in payload
        assert payload["width"] % 8 == 0
        return {"images": [_TINY_PNG_B64]}

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="forge",
        vision_local_sd_base_url="http://127.0.0.1:7860",
        vision_local_sd_model="arch-sketch.safetensors",
    )
    generator = LocalSdVisionImageGenerator(settings, transport=transport)
    spec = VisionPromptCompiler().compile(
        ImageRequest(subject="hospital canopy concept", width=1280, height=720)
    )
    payload = generator.generate(spec)
    assert payload.provider == "local_sd"
    assert payload.model == "arch-sketch.safetensors"
    assert payload.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert calls


def test_local_sd_img2img_uses_denoising(tmp_path: Path) -> None:
    from PIL import Image

    base = tmp_path / "site.png"
    Image.new("RGB", (320, 200), color=(90, 100, 110)).save(base)
    seen: dict[str, object] = {}

    def transport(method: str, url: str, payload: dict | None) -> dict:
        assert url.endswith("/sdapi/v1/img2img")
        assert payload is not None
        seen["denoising_strength"] = payload["denoising_strength"]
        seen["has_init"] = bool(payload.get("init_images"))
        return {"images": [_TINY_PNG_B64]}

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="a1111",
        vision_local_sd_denoising_strength=0.4,
    )
    generator = LocalSdVisionImageGenerator(settings, transport=transport)
    request = ImageRequest(
        subject="add covered walkway",
        mode=VisionGenerationMode.EDIT_FROM_PHOTO,
        base_image_path=str(base),
        denoising_strength=0.62,
        width=640,
        height=360,
    )
    spec = VisionPromptCompiler().compile(request)
    assert spec.metadata.get("denoising_strength") == 0.62
    payload = generator.edit(spec, base_image_path=str(base))
    assert payload.provider == "local_sd"
    assert seen["denoising_strength"] == 0.62
    assert seen["has_init"] is True


def test_service_prefers_local_sd_edit_over_pillow(tmp_path: Path) -> None:
    from archium.application.visual.vision import VisionImageGenerationService
    from PIL import Image

    base = tmp_path / "photo.png"
    Image.new("RGB", (400, 300), color=(120, 130, 140)).save(base)

    def transport(method: str, url: str, payload: dict | None) -> dict:
        assert "img2img" in url
        return {"images": [_TINY_PNG_B64]}

    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path / "storage",
        vision_image_generation_enabled=True,
        vision_image_generation_provider="local_sd",
        vision_local_sd_base_url="http://127.0.0.1:7860",
    )
    generator = LocalSdVisionImageGenerator(settings, transport=transport)
    service = VisionImageGenerationService(
        session=None,
        settings=settings,
        generator=generator,
    )
    result = service.generate(
        ImageRequest(
            subject="renovation canopy",
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            base_image_path=str(base),
            width=512,
            height=512,
            harmonize_output=False,
        ),
        project_id=uuid4(),
        persist_asset=True,
    )
    assert result.success is True
    assert result.provider == "local_sd"
    assert result.illustrative is True
