"""ComfyUI Vision Engine adapter tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.vision import VisionImageGenerationService, VisionPromptCompiler
from archium.config.settings import Settings
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationMode,
)
from archium.infrastructure.vision_gen import (
    ComfyUiVisionImageGenerator,
    StubVisionImageGenerator,
    build_vision_image_generator,
)
from archium.infrastructure.vision_gen.comfyui import (
    build_img2img_workflow,
    build_txt2img_workflow,
)

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_builtin_workflows_have_required_nodes() -> None:
    txt = build_txt2img_workflow(
        checkpoint="demo.safetensors",
        prompt="hospital canopy",
        negative_prompt="photo evidence",
        width=768,
        height=512,
        steps=20,
        cfg=6.5,
        sampler_name="euler",
        scheduler="normal",
    )
    assert txt["4"]["class_type"] == "CheckpointLoaderSimple"
    assert txt["9"]["class_type"] == "SaveImage"
    img = build_img2img_workflow(
        checkpoint="demo.safetensors",
        image_name="in.png",
        prompt="add walkway",
        negative_prompt="survey",
        width=768,
        height=512,
        steps=20,
        cfg=6.5,
        sampler_name="euler",
        scheduler="normal",
        denoise=0.55,
    )
    assert img["10"]["class_type"] == "LoadImage"
    assert img["11"]["class_type"] == "VAEEncode"
    assert img["3"]["inputs"]["denoise"] == 0.55


def test_factory_selects_comfyui() -> None:
    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="comfyui",
        vision_comfyui_base_url="http://127.0.0.1:8188",
        vision_comfyui_checkpoint="arch.safetensors",
    )
    generator = build_vision_image_generator(settings)
    assert isinstance(generator, ComfyUiVisionImageGenerator)
    assert generator.model == "arch.safetensors"


def test_factory_stub_when_comfy_disabled() -> None:
    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=False,
        vision_image_generation_provider="comfyui",
    )
    assert isinstance(build_vision_image_generator(settings), StubVisionImageGenerator)


def test_comfyui_txt2img_via_transport() -> None:
    prompt_id = "prompt-1"
    history_hits = {"n": 0}

    def transport(method, path, **kwargs):
        raw = kwargs.get("raw", False)
        if method == "POST" and path == "/prompt":
            body = kwargs["json_body"]
            assert "prompt" in body
            assert body["prompt"]["4"]["inputs"]["ckpt_name"] == "arch.safetensors"
            return {"prompt_id": prompt_id}
        if method == "GET" and path == f"/history/{prompt_id}":
            history_hits["n"] += 1
            if history_hits["n"] < 2:
                return {}
            return {
                prompt_id: {
                    "outputs": {
                        "9": {
                            "images": [
                                {
                                    "filename": "archium_vision_00001_.png",
                                    "subfolder": "",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            }
        if method == "GET" and path.startswith("/view?"):
            assert raw is True
            return _TINY_PNG
        raise AssertionError(f"unexpected call {method} {path}")

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="comfyui",
        vision_comfyui_checkpoint="arch.safetensors",
        vision_comfyui_poll_interval_seconds=0.2,
        vision_comfyui_timeout_seconds=10.0,
    )
    sleeps: list[float] = []
    generator = ComfyUiVisionImageGenerator(
        settings,
        transport=transport,
        sleeper=lambda seconds: sleeps.append(seconds),
    )
    spec = VisionPromptCompiler().compile(
        ImageRequest(subject="campus atmosphere", width=768, height=512)
    )
    payload = generator.generate(spec)
    assert payload.provider == "comfyui"
    assert payload.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert sleeps  # polled at least once


def test_comfyui_img2img_upload_and_denoise(tmp_path: Path) -> None:
    from PIL import Image

    base = tmp_path / "photo.png"
    Image.new("RGB", (300, 200), color=(100, 110, 120)).save(base)
    seen: dict[str, object] = {}

    def transport(method, path, **kwargs):
        if method == "POST" and path == "/upload/image":
            files = kwargs.get("files") or {}
            assert "image" in files
            return {"name": "uploaded_base.png"}
        if method == "POST" and path == "/prompt":
            workflow = kwargs["json_body"]["prompt"]
            seen["denoise"] = workflow["3"]["inputs"]["denoise"]
            seen["image"] = workflow["10"]["inputs"]["image"]
            return {"prompt_id": "p2"}
        if method == "GET" and path == "/history/p2":
            return {
                "p2": {
                    "outputs": {
                        "9": {
                            "images": [
                                {"filename": "out.png", "subfolder": "", "type": "output"}
                            ]
                        }
                    }
                }
            }
        if method == "GET" and path.startswith("/view?"):
            return _TINY_PNG
        raise AssertionError(f"unexpected {method} {path}")

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="comfyui",
        vision_comfyui_checkpoint="arch.safetensors",
        vision_comfyui_poll_interval_seconds=0.2,
    )
    generator = ComfyUiVisionImageGenerator(settings, transport=transport, sleeper=lambda _s: None)
    request = ImageRequest(
        subject="add canopy",
        mode=VisionGenerationMode.EDIT_FROM_PHOTO,
        base_image_path=str(base),
        denoising_strength=0.48,
        width=512,
        height=512,
    )
    spec = VisionPromptCompiler().compile(request)
    payload = generator.edit(spec, base_image_path=str(base))
    assert payload.provider == "comfyui"
    assert seen["denoise"] == 0.48
    assert seen["image"] == "uploaded_base.png"


def test_service_uses_comfyui_for_edit(tmp_path: Path) -> None:
    from PIL import Image

    base = tmp_path / "in.png"
    Image.new("RGB", (256, 256), color=(80, 90, 100)).save(base)

    def transport(method, path, **kwargs):
        if method == "POST" and path == "/upload/image":
            return {"name": "u.png"}
        if method == "POST" and path == "/prompt":
            return {"prompt_id": "px"}
        if method == "GET" and path == "/history/px":
            return {
                "px": {
                    "outputs": {
                        "9": {"images": [{"filename": "o.png", "subfolder": "", "type": "output"}]}
                    }
                }
            }
        if method == "GET" and path.startswith("/view?"):
            return _TINY_PNG
        raise AssertionError(path)

    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path / "store",
        vision_image_generation_enabled=True,
        vision_image_generation_provider="comfyui",
        vision_comfyui_checkpoint="arch.safetensors",
        vision_comfyui_poll_interval_seconds=0.2,
    )
    service = VisionImageGenerationService(
        session=None,
        settings=settings,
        generator=ComfyUiVisionImageGenerator(settings, transport=transport, sleeper=lambda _s: None),
    )
    result = service.generate(
        ImageRequest(
            subject="renovation sketch",
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            base_image_path=str(base),
            harmonize_output=False,
        ),
        project_id=uuid4(),
        persist_asset=True,
    )
    assert result.success is True
    assert result.provider == "comfyui"
