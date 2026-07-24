"""ComfyUI custom workflow mount + LoRA helpers."""

from __future__ import annotations

import json
from pathlib import Path

from archium.application.visual.vision import VisionPromptCompiler
from archium.config.settings import Settings
from archium.domain.visual.vision_generation import ImageRequest
from archium.infrastructure.vision_gen.comfyui import (
    ComfyUiVisionImageGenerator,
    build_txt2img_workflow,
)
from archium.infrastructure.vision_gen.comfyui_workflows import (
    apply_lora_to_checkpoint_graph,
    load_workflow_api_json,
    placeholder_values,
    render_custom_workflow,
    substitute_placeholders,
)


def _repo_example(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "archium"
        / "infrastructure"
        / "vision_gen"
        / "workflows"
        / name
    )


def test_substitute_preserves_numeric_types() -> None:
    node = {"steps": "{{steps}}", "label": "w={{width}}"}
    out = substitute_placeholders(node, {"steps": 24, "width": 768})
    assert out["steps"] == 24
    assert out["label"] == "w=768"


def test_render_example_txt2img_workflow() -> None:
    path = _repo_example("txt2img_api.example.json")
    assert path.is_file(), path
    values = placeholder_values(
        prompt="hospital canopy",
        negative_prompt="evidence photo",
        width=768,
        height=512,
        steps=20,
        cfg=6.5,
        seed=42,
        checkpoint="arch.safetensors",
        denoise=1.0,
        sampler="euler",
        scheduler="normal",
    )
    graph = render_custom_workflow(path, values=values)
    assert graph["4"]["inputs"]["ckpt_name"] == "arch.safetensors"
    assert graph["6"]["inputs"]["text"] == "hospital canopy"
    assert graph["5"]["inputs"]["width"] == 768
    assert graph["3"]["inputs"]["steps"] == 20


def test_load_prompt_wrapped_workflow(tmp_path: Path) -> None:
    payload = {
        "prompt": {
            "1": {"class_type": "SaveImage", "inputs": {"images": ["x", 0]}},
        }
    }
    path = tmp_path / "wrapped.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    graph = load_workflow_api_json(path)
    assert "1" in graph


def test_apply_lora_rewires_model_and_clip() -> None:
    base = build_txt2img_workflow(
        checkpoint="base.safetensors",
        prompt="p",
        negative_prompt="n",
        width=512,
        height=512,
        steps=10,
        cfg=5.0,
        sampler_name="euler",
        scheduler="normal",
    )
    with_lora = apply_lora_to_checkpoint_graph(
        base,
        lora_name="arch_marker.safetensors",
        strength_model=0.7,
        strength_clip=0.6,
    )
    assert with_lora["20"]["class_type"] == "LoraLoader"
    assert with_lora["20"]["inputs"]["lora_name"] == "arch_marker.safetensors"
    assert with_lora["3"]["inputs"]["model"] == ["20", 0]
    assert with_lora["6"]["inputs"]["clip"] == ["20", 1]
    assert with_lora["8"]["inputs"]["vae"] == ["4", 2]


def test_builtin_txt2img_includes_lora_when_requested() -> None:
    graph = build_txt2img_workflow(
        checkpoint="base.safetensors",
        prompt="p",
        negative_prompt="n",
        width=512,
        height=512,
        steps=10,
        cfg=5.0,
        sampler_name="euler",
        scheduler="normal",
        lora_name="arch_sketch.safetensors",
        lora_strength_model=0.85,
    )
    assert graph["20"]["inputs"]["strength_model"] == 0.85
    assert graph["3"]["inputs"]["model"] == ["20", 0]


def test_generator_uses_custom_workflow_path(tmp_path: Path) -> None:
    example = _repo_example("txt2img_api.example.json")
    tiny = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    seen: dict[str, object] = {}

    def transport(method, path, **kwargs):
        if method == "POST" and path == "/prompt":
            seen["prefix"] = kwargs["json_body"]["prompt"]["9"]["inputs"]["filename_prefix"]
            seen["ckpt"] = kwargs["json_body"]["prompt"]["4"]["inputs"]["ckpt_name"]
            return {"prompt_id": "c1"}
        if method == "GET" and path == "/history/c1":
            return {
                "c1": {
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
        vision_comfyui_checkpoint="arch.safetensors",
        vision_comfyui_workflow_txt2img_path=str(example),
        vision_comfyui_poll_interval_seconds=0.2,
    )
    gen = ComfyUiVisionImageGenerator(settings, transport=transport, sleeper=lambda _s: None)
    spec = VisionPromptCompiler().compile(ImageRequest(subject="canopy", width=768, height=512))
    payload = gen.generate(spec)
    assert payload.provider == "comfyui"
    assert seen["prefix"] == "archium_custom_txt"
    assert seen["ckpt"] == "arch.safetensors"
