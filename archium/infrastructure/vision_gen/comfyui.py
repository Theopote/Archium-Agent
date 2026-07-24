"""ComfyUI adapter for Vision Engine (builtin txt2img / img2img graphs).

Does not ship model weights. Talks to a running ComfyUI server via HTTP API:
``POST /prompt`` → poll ``/history/{id}`` → ``GET /view``.
"""

from __future__ import annotations

import json
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from archium.config.settings import Settings, get_settings
from archium.domain.visual.vision_generation import GenerationSpec
from archium.infrastructure.vision_gen.base import GeneratedImageBytes
from archium.infrastructure.vision_gen.local_sd import _clamp_dim
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_comfyui")

# method, path, json_body, files(dict name->(filename, bytes, content_type)|None), raw_bytes?
ComfyTransport = Callable[..., Any]


def _default_json_request(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> bytes:
    body = data
    req_headers = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=body, headers=req_headers, method=method.upper())
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _multipart_form(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----ArchiumComfy{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
        )
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def build_txt2img_workflow(
    *,
    checkpoint: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    seed: int = 0,
    lora_name: str = "",
    lora_strength_model: float = 0.8,
    lora_strength_clip: float = 0.8,
) -> dict[str, Any]:
    """Minimal SD1.x/SDXL-compatible txt2img graph (CheckpointLoaderSimple)."""
    from archium.infrastructure.vision_gen.comfyui_workflows import apply_lora_to_checkpoint_graph

    graph = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["4", 1]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "archium_vision", "images": ["8", 0]},
        },
    }
    if lora_name.strip():
        return apply_lora_to_checkpoint_graph(
            graph,
            lora_name=lora_name,
            strength_model=lora_strength_model,
            strength_clip=lora_strength_clip,
        )
    return graph


def build_img2img_workflow(
    *,
    checkpoint: str,
    image_name: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    seed: int = 0,
    lora_name: str = "",
    lora_strength_model: float = 0.8,
    lora_strength_clip: float = 0.8,
) -> dict[str, Any]:
    """Minimal img2img graph: LoadImage → VAEEncode → KSampler → VAEDecode."""
    from archium.infrastructure.vision_gen.comfyui_workflows import apply_lora_to_checkpoint_graph

    graph = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "10": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        },
        "11": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["10", 0], "vae": ["4", 2]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["4", 1]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["11", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "archium_vision_edit", "images": ["8", 0]},
        },
    }
    if lora_name.strip():
        return apply_lora_to_checkpoint_graph(
            graph,
            lora_name=lora_name,
            strength_model=lora_strength_model,
            strength_clip=lora_strength_clip,
        )
    return graph


class ComfyUiVisionImageGenerator:
    """ComfyUI HTTP backend for Vision Engine."""

    provider = "comfyui"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: ComfyTransport | None = None,
        sleeper: Callable[[float], None] | None = None,
        client_id: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport
        self._sleep = sleeper or time.sleep
        self._client_id = client_id or f"archium-{uuid.uuid4().hex[:12]}"

    @property
    def model(self) -> str:
        return (
            (self._settings.vision_comfyui_checkpoint or "").strip()
            or (self._settings.vision_local_sd_model or "").strip()
            or (self._settings.vision_image_generation_model or "").strip()
            or "model.safetensors"
        )

    @property
    def base_url(self) -> str:
        return (self._settings.vision_comfyui_base_url or "http://127.0.0.1:8188").strip().rstrip(
            "/"
        )

    def is_available(self) -> bool:
        if self._transport is not None:
            return True
        return self._settings.vision_comfyui_configured

    def generate(self, spec: GenerationSpec) -> GeneratedImageBytes:
        if not self.is_available():
            raise RuntimeError("ComfyUI is not configured")
        width = _clamp_dim(spec.width)
        height = _clamp_dim(spec.height)
        seed = abs(hash(spec.prompt_hash)) % (2**31)
        values = self._placeholder_values(
            spec,
            width=width,
            height=height,
            seed=seed,
            denoise=1.0,
            image="",
        )
        custom_path = (self._settings.vision_comfyui_workflow_txt2img_path or "").strip()
        if custom_path:
            from archium.infrastructure.vision_gen.comfyui_workflows import render_custom_workflow

            workflow = render_custom_workflow(custom_path, values=values)
            logger.info(
                "ComfyUI txt2img custom_workflow=%s checkpoint=%s hash=%s",
                custom_path,
                self.model,
                spec.prompt_hash,
            )
        else:
            workflow = build_txt2img_workflow(
                checkpoint=self.model,
                prompt=str(values["prompt"]),
                negative_prompt=str(values["negative_prompt"]),
                width=width,
                height=height,
                steps=int(values["steps"]),
                cfg=float(values["cfg"]),
                sampler_name=str(values["sampler"]),
                scheduler=str(values["scheduler"]),
                seed=seed,
                lora_name=str(values["lora_name"]),
                lora_strength_model=float(values["lora_strength_model"]),
                lora_strength_clip=float(values["lora_strength_clip"]),
            )
            logger.info(
                "ComfyUI txt2img checkpoint=%s size=%sx%s hash=%s lora=%s",
                self.model,
                width,
                height,
                spec.prompt_hash,
                values["lora_name"] or "-",
            )
        return self._run_workflow(workflow)

    def edit(self, spec: GenerationSpec, *, base_image_path: str) -> GeneratedImageBytes:
        if not self.is_available():
            raise RuntimeError("ComfyUI is not configured")
        path = Path(base_image_path)
        if not path.is_file():
            raise FileNotFoundError(f"base image not found: {path}")

        width = _clamp_dim(spec.width)
        height = _clamp_dim(spec.height)
        image_name = self._upload_resized_image(path, width=width, height=height)

        strength = spec.metadata.get("denoising_strength")
        if strength is None:
            strength = self._settings.vision_local_sd_denoising_strength
        try:
            denoise = float(strength)
        except (TypeError, ValueError):
            denoise = self._settings.vision_local_sd_denoising_strength
        denoise = max(0.05, min(denoise, 1.0))
        seed = abs(hash(spec.prompt_hash)) % (2**31)
        values = self._placeholder_values(
            spec,
            width=width,
            height=height,
            seed=seed,
            denoise=denoise,
            image=image_name,
        )
        custom_path = (self._settings.vision_comfyui_workflow_img2img_path or "").strip()
        if custom_path:
            from archium.infrastructure.vision_gen.comfyui_workflows import render_custom_workflow

            workflow = render_custom_workflow(custom_path, values=values)
            logger.info(
                "ComfyUI img2img custom_workflow=%s denoise=%.2f hash=%s",
                custom_path,
                denoise,
                spec.prompt_hash,
            )
        else:
            workflow = build_img2img_workflow(
                checkpoint=self.model,
                image_name=image_name,
                prompt=str(values["prompt"]),
                negative_prompt=str(values["negative_prompt"]),
                width=width,
                height=height,
                steps=int(values["steps"]),
                cfg=float(values["cfg"]),
                sampler_name=str(values["sampler"]),
                scheduler=str(values["scheduler"]),
                denoise=denoise,
                seed=seed,
                lora_name=str(values["lora_name"]),
                lora_strength_model=float(values["lora_strength_model"]),
                lora_strength_clip=float(values["lora_strength_clip"]),
            )
            logger.info(
                "ComfyUI img2img checkpoint=%s denoise=%.2f hash=%s base=%s lora=%s",
                self.model,
                denoise,
                spec.prompt_hash,
                path.name,
                values["lora_name"] or "-",
            )
        return self._run_workflow(workflow)

    def _placeholder_values(
        self,
        spec: GenerationSpec,
        *,
        width: int,
        height: int,
        seed: int,
        denoise: float,
        image: str,
    ) -> dict[str, Any]:
        from archium.infrastructure.vision_gen.comfyui_workflows import placeholder_values

        return placeholder_values(
            prompt=spec.prompt[:3500],
            negative_prompt=(spec.negative_prompt or "")[:1500],
            width=width,
            height=height,
            steps=self._settings.vision_local_sd_steps,
            cfg=self._settings.vision_local_sd_cfg_scale,
            seed=seed,
            checkpoint=self.model,
            denoise=denoise,
            image=image,
            sampler=self._settings.vision_comfyui_sampler,
            scheduler=self._settings.vision_comfyui_scheduler,
            lora_name=(self._settings.vision_comfyui_lora or "").strip(),
            lora_strength_model=self._settings.vision_comfyui_lora_strength_model,
            lora_strength_clip=self._settings.vision_comfyui_lora_strength_clip,
        )

    def _run_workflow(self, workflow: dict[str, Any]) -> GeneratedImageBytes:
        queued = self._post_json(
            "/prompt",
            {"prompt": workflow, "client_id": self._client_id},
        )
        prompt_id = queued.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise RuntimeError(f"ComfyUI queue did not return prompt_id: {queued!r}")

        outputs = self._wait_for_outputs(prompt_id)
        image_meta = _first_saved_image(outputs)
        if image_meta is None:
            raise RuntimeError("ComfyUI finished without SaveImage output")
        raw = self._get_bytes(
            "/view?"
            + urlencode(
                {
                    "filename": image_meta["filename"],
                    "subfolder": image_meta.get("subfolder") or "",
                    "type": image_meta.get("type") or "output",
                }
            )
        )
        return GeneratedImageBytes(
            data=raw,
            mime_type="image/png",
            provider=self.provider,
            model=self.model,
        )

    def _wait_for_outputs(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + float(self._settings.vision_comfyui_timeout_seconds)
        interval = float(self._settings.vision_comfyui_poll_interval_seconds)
        while time.monotonic() < deadline:
            history = self._get_json(f"/history/{prompt_id}")
            entry = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(entry, dict) and entry.get("outputs"):
                outputs = entry["outputs"]
                if isinstance(outputs, dict):
                    return outputs
            self._sleep(interval)
        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out")

    def _upload_resized_image(self, path: Path, *, width: int, height: int) -> str:
        from PIL import Image, ImageOps

        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        filename = f"archium_{path.stem[:40]}_{width}x{height}.png"

        if self._transport is not None:
            result = self._transport(
                "POST",
                "/upload/image",
                json_body=None,
                files={"image": (filename, png_bytes, "image/png")},
                fields={"overwrite": "true"},
                raw=False,
            )
        else:
            body, content_type = _multipart_form(
                {"overwrite": "true"},
                {"image": (filename, png_bytes, "image/png")},
            )
            raw = _default_json_request(
                "POST",
                f"{self.base_url}/upload/image",
                data=body,
                headers={"Content-Type": content_type},
                timeout=float(self._settings.vision_comfyui_timeout_seconds),
            )
            result = json.loads(raw.decode("utf-8"))

        if not isinstance(result, dict):
            raise RuntimeError("ComfyUI upload returned invalid payload")
        name = result.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"ComfyUI upload missing name: {result!r}")
        return name

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._call("POST", path, json_body=payload, raw=False)
        if not isinstance(data, dict):
            raise RuntimeError(f"ComfyUI POST {path} returned non-object")
        return data

    def _get_json(self, path: str) -> dict[str, Any]:
        data = self._call("GET", path, json_body=None, raw=False)
        if not isinstance(data, dict):
            raise RuntimeError(f"ComfyUI GET {path} returned non-object")
        return data

    def _get_bytes(self, path: str) -> bytes:
        data = self._call("GET", path, json_body=None, raw=True)
        if not isinstance(data, (bytes, bytearray)):
            raise RuntimeError(f"ComfyUI GET {path} did not return bytes")
        return bytes(data)

    def _call(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None,
        raw: bool,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        fields: dict[str, str] | None = None,
    ) -> Any:
        try:
            if self._transport is not None:
                return self._transport(
                    method,
                    path,
                    json_body=json_body,
                    files=files,
                    fields=fields,
                    raw=raw,
                )
            url = f"{self.base_url}{path}"
            timeout = float(self._settings.vision_comfyui_timeout_seconds)
            if files:
                body, content_type = _multipart_form(fields or {}, files)
                response = _default_json_request(
                    method,
                    url,
                    data=body,
                    headers={"Content-Type": content_type},
                    timeout=timeout,
                )
            else:
                response = _default_json_request(
                    method,
                    url,
                    json_body=json_body,
                    timeout=timeout,
                )
            if raw:
                return response
            if not response.strip():
                return {}
            return json.loads(response.decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"ComfyUI HTTP {exc.code} on {path}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"ComfyUI unreachable at {self.base_url}: {exc}") from exc


def _first_saved_image(outputs: dict[str, Any]) -> dict[str, Any] | None:
    for node_out in outputs.values():
        if not isinstance(node_out, dict):
            continue
        images = node_out.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict) and first.get("filename"):
                return first
    return None
