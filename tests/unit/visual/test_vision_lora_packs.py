"""Architectural LoRA pack product distribution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from archium.application.visual.vision.lora_pack_service import VisionLoraPackService
from archium.config.settings import Settings
from archium.exceptions import WorkflowError
from archium.infrastructure.vision_gen.lora_packs import __main__ as lora_cli


def test_list_bundled_packs() -> None:
    service = VisionLoraPackService(Settings(_env_file=None))
    packs = {item.manifest.id: item for item in service.list_packs()}
    assert "archium-marker-sketch-v1" in packs
    assert "archium-analytical-diagram-v1" in packs
    marker = packs["archium-marker-sketch-v1"]
    assert marker.manifest.primary_lora() is not None
    assert "arch_marker_sketch.safetensors" in marker.weights_missing


def test_suggest_pack_for_style() -> None:
    service = VisionLoraPackService(Settings(_env_file=None))
    status = service.suggest_pack_for_style("marker_sketch")
    assert status is not None
    assert status.manifest.id == "archium-marker-sketch-v1"


def test_resolve_active_lora_from_pack() -> None:
    settings = Settings(
        _env_file=None,
        vision_lora_pack_id="archium-marker-sketch-v1",
        vision_comfyui_lora="ignored.safetensors",
    )
    active = VisionLoraPackService(settings).resolve_active_lora()
    assert active is not None
    assert active.source == "pack"
    assert active.filename == "arch_marker_sketch.safetensors"
    assert active.strength_model == pytest.approx(0.82)


def test_install_to_comfy_copies_weights(tmp_path: Path) -> None:
    packs_root = tmp_path / "packs"
    pack_dir = packs_root / "demo-pack"
    weights = pack_dir / "weights"
    weights.mkdir(parents=True)
    weight_file = weights / "demo.safetensors"
    payload = b"fake-lora-bytes-for-test"
    weight_file.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (pack_dir / "pack.json").write_text(
        json.dumps(
            {
                "id": "demo-pack",
                "name": "Demo",
                "loras": [
                    {
                        "id": "primary",
                        "filename": "demo.safetensors",
                        "role": "primary",
                        "sha256": digest,
                        "default_strength_model": 0.5,
                        "default_strength_clip": 0.4,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    comfy_loras = tmp_path / "ComfyUI" / "models" / "loras"
    settings = Settings(
        _env_file=None,
        vision_lora_packs_dir=str(packs_root),
        vision_comfyui_loras_dir=str(comfy_loras),
    )
    service = VisionLoraPackService(settings)
    installed = service.install_to_comfy("demo-pack", download_missing=False)
    assert len(installed) == 1
    assert installed[0].is_file()
    assert installed[0].read_bytes() == payload
    status = service.get_pack("demo-pack")
    assert status is not None
    assert status.installed_to_comfy is True
    assert status.ready is True


def test_install_fails_when_weights_missing(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        vision_comfyui_loras_dir=str(tmp_path / "loras"),
    )
    service = VisionLoraPackService(settings)
    with pytest.raises(WorkflowError, match="weights missing"):
        service.install_to_comfy("archium-marker-sketch-v1", download_missing=False)


def test_cli_list_runs() -> None:
    code = lora_cli.main(["list"])
    assert code == 0


def test_comfy_generator_uses_pack_lora(tmp_path: Path) -> None:
    from archium.application.visual.vision import VisionPromptCompiler
    from archium.domain.visual.vision_generation import ImageRequest
    from archium.infrastructure.vision_gen.comfyui import ComfyUiVisionImageGenerator

    tiny = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    seen: dict[str, object] = {}

    def transport(method, path, **kwargs):
        if method == "POST" and path == "/prompt":
            workflow = kwargs["json_body"]["prompt"]
            seen["lora"] = workflow["20"]["inputs"]["lora_name"]
            seen["strength"] = workflow["20"]["inputs"]["strength_model"]
            return {"prompt_id": "p"}
        if method == "GET" and path == "/history/p":
            return {
                "p": {
                    "outputs": {
                        "9": {"images": [{"filename": "o.png", "subfolder": "", "type": "output"}]}
                    }
                }
            }
        if method == "GET" and path.startswith("/view?"):
            return tiny
        raise AssertionError(path)

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="comfyui",
        vision_comfyui_checkpoint="base.safetensors",
        vision_lora_pack_id="archium-marker-sketch-v1",
        vision_comfyui_poll_interval_seconds=0.2,
    )
    gen = ComfyUiVisionImageGenerator(settings, transport=transport, sleeper=lambda _s: None)
    spec = VisionPromptCompiler().compile(ImageRequest(subject="marker campus"))
    payload = gen.generate(spec)
    assert payload.provider == "comfyui"
    assert seen["lora"] == "arch_marker_sketch.safetensors"
    assert seen["strength"] == pytest.approx(0.82)
