"""ComfyUI workflow helpers — placeholders, custom JSON mount, optional LoRA."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def substitute_placeholders(node: Any, values: dict[str, Any]) -> Any:
    """Replace ``{{name}}`` tokens in strings; recurse into lists/dicts."""
    if isinstance(node, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                return match.group(0)
            return str(values[key])

        # Whole-string placeholder → preserve non-string types (int/float/bool).
        stripped = node.strip()
        full = _PLACEHOLDER_RE.fullmatch(stripped)
        if full is not None:
            key = full.group(1)
            if key in values:
                return values[key]
        return _PLACEHOLDER_RE.sub(repl, node)
    if isinstance(node, list):
        return [substitute_placeholders(item, values) for item in node]
    if isinstance(node, dict):
        return {key: substitute_placeholders(value, values) for key, value in node.items()}
    return node


def load_workflow_api_json(path: str | Path) -> dict[str, Any]:
    """Load a ComfyUI **API** prompt graph (node-id → {class_type, inputs})."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"ComfyUI workflow not found: {target}")
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"ComfyUI workflow root must be an object: {target}")
    # Allow wrappers: {"prompt": {...}} from some exporters.
    nested = raw.get("prompt")
    if isinstance(nested, dict) and any(
        isinstance(value, dict) and "class_type" in value for value in nested.values()
    ):
        raw = nested
    cleaned = {
        key: value
        for key, value in raw.items()
        if isinstance(value, dict) and "class_type" in value
    }
    if not cleaned:
        raise ValueError(
            f"ComfyUI workflow has no API nodes (export API format, not UI): {target}"
        )
    return cleaned


def render_custom_workflow(
    path: str | Path,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Load custom API workflow and substitute Archium placeholders."""
    graph = load_workflow_api_json(path)
    return cast(dict[str, Any], substitute_placeholders(deepcopy(graph), values))


def apply_lora_to_checkpoint_graph(
    workflow: dict[str, Any],
    *,
    lora_name: str,
    strength_model: float = 0.8,
    strength_clip: float = 0.8,
    checkpoint_node_id: str = "4",
    lora_node_id: str = "20",
) -> dict[str, Any]:
    """Insert ``LoraLoader`` after CheckpointLoaderSimple and rewire model/clip.

    Expects builtin-style graphs where CLIPTextEncode clip and KSampler model
    originally point at the checkpoint node.
    """
    if not lora_name.strip():
        return workflow
    graph = deepcopy(workflow)
    if checkpoint_node_id not in graph:
        return graph
    graph[lora_node_id] = {
        "class_type": "LoraLoader",
        "inputs": {
            "lora_name": lora_name.strip(),
            "strength_model": float(strength_model),
            "strength_clip": float(strength_clip),
            "model": [checkpoint_node_id, 0],
            "clip": [checkpoint_node_id, 1],
        },
    }
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in list(inputs.items()):
            if value == [checkpoint_node_id, 0] and key == "model":
                inputs[key] = [lora_node_id, 0]
            elif value == [checkpoint_node_id, 1] and key == "clip":
                inputs[key] = [lora_node_id, 1]
    return graph


def placeholder_values(
    *,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    seed: int,
    checkpoint: str,
    denoise: float,
    image: str = "",
    sampler: str = "euler",
    scheduler: str = "normal",
    lora_name: str = "",
    lora_strength_model: float = 0.8,
    lora_strength_clip: float = 0.8,
) -> dict[str, Any]:
    """Canonical placeholder map for Archium-mounted Comfy workflows."""
    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg": cfg,
        "seed": seed,
        "checkpoint": checkpoint,
        "ckpt_name": checkpoint,
        "denoise": denoise,
        "denoising_strength": denoise,
        "image": image,
        "image_name": image,
        "sampler": sampler,
        "sampler_name": sampler,
        "scheduler": scheduler,
        "lora_name": lora_name,
        "lora_strength": lora_strength_model,
        "lora_strength_model": lora_strength_model,
        "lora_strength_clip": lora_strength_clip,
    }
