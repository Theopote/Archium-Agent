"""Local Stable Diffusion WebUI / Forge adapter (A1111 ``sdapi``).

Supports txt2img and img2img for Vision Engine without bundling model weights.
Default target: ``http://127.0.0.1:7860`` (AUTOMATIC1111 / Forge / compatible).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from archium.config.settings import Settings, get_settings
from archium.domain.visual.vision_generation import GenerationSpec
from archium.infrastructure.vision_gen.base import GeneratedImageBytes
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_local_sd")

JsonTransport = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


def _clamp_dim(value: int) -> int:
    """A1111 prefers multiples of 8; keep within a practical local GPU range."""
    clamped = max(256, min(int(value), 1536))
    return max(256, (clamped // 8) * 8)


def _default_transport(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    *,
    timeout: float,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method.upper())
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8")
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"Local SD returned non-object JSON from {url}")
    return data


class LocalSdVisionImageGenerator:
    """AUTOMATIC1111 / Forge compatible local image backend."""

    provider = "local_sd"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: JsonTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def model(self) -> str:
        override = (self._settings.vision_local_sd_model or "").strip()
        if override:
            return override
        return self._settings.vision_image_generation_model or "local_sd"

    @property
    def base_url(self) -> str:
        raw = (
            self._settings.vision_local_sd_base_url
            or "http://127.0.0.1:7860"
        ).strip().rstrip("/")
        return raw

    def is_available(self) -> bool:
        """Configured local_sd (or injected transport). Connectivity checked on generate/edit."""
        if self._transport is not None:
            return True
        return self._settings.vision_local_sd_configured

    def probe(self) -> bool:
        """Optional live check against ``/sdapi/v1/sd-models``."""
        try:
            self._request("GET", "/sdapi/v1/sd-models", None)
            return True
        except Exception as exc:
            logger.info("Local SD probe failed at %s: %s", self.base_url, exc)
            return False

    def generate(self, spec: GenerationSpec) -> GeneratedImageBytes:
        if not self._settings.vision_local_sd_configured and self._transport is None:
            raise RuntimeError("Local SD is not configured")

        width = _clamp_dim(spec.width)
        height = _clamp_dim(spec.height)
        payload: dict[str, Any] = {
            "prompt": spec.prompt[:3500],
            "negative_prompt": (spec.negative_prompt or "")[:1500],
            "steps": self._settings.vision_local_sd_steps,
            "cfg_scale": self._settings.vision_local_sd_cfg_scale,
            "width": width,
            "height": height,
            "sampler_name": self._settings.vision_local_sd_sampler,
            "batch_size": 1,
            "n_iter": 1,
        }
        override = (self._settings.vision_local_sd_model or "").strip()
        if override:
            payload["override_settings"] = {"sd_model_checkpoint": override}

        logger.info(
            "Local SD txt2img model=%s size=%sx%s hash=%s",
            self.model,
            width,
            height,
            spec.prompt_hash,
        )
        response = self._request("POST", "/sdapi/v1/txt2img", payload)
        return self._decode_images(response)

    def edit(self, spec: GenerationSpec, *, base_image_path: str) -> GeneratedImageBytes:
        """Stronger conditioned edit via local img2img (not Pillow overlay)."""
        if not self._settings.vision_local_sd_configured and self._transport is None:
            raise RuntimeError("Local SD is not configured")

        path = Path(base_image_path)
        if not path.is_file():
            raise FileNotFoundError(f"base image not found: {path}")

        width = _clamp_dim(spec.width)
        height = _clamp_dim(spec.height)
        init_b64 = _encode_image_as_png_b64(path, width=width, height=height)
        strength = spec.metadata.get("denoising_strength")
        if strength is None:
            strength = self._settings.vision_local_sd_denoising_strength
        try:
            denoising = float(cast(Any, strength))
        except (TypeError, ValueError):
            denoising = self._settings.vision_local_sd_denoising_strength
        denoising = max(0.05, min(denoising, 1.0))

        payload: dict[str, Any] = {
            "init_images": [init_b64],
            "prompt": spec.prompt[:3500],
            "negative_prompt": (spec.negative_prompt or "")[:1500],
            "steps": self._settings.vision_local_sd_steps,
            "cfg_scale": self._settings.vision_local_sd_cfg_scale,
            "width": width,
            "height": height,
            "sampler_name": self._settings.vision_local_sd_sampler,
            "denoising_strength": denoising,
            "batch_size": 1,
            "n_iter": 1,
        }
        override = (self._settings.vision_local_sd_model or "").strip()
        if override:
            payload["override_settings"] = {"sd_model_checkpoint": override}

        logger.info(
            "Local SD img2img model=%s strength=%.2f hash=%s base=%s",
            self.model,
            denoising,
            spec.prompt_hash,
            path.name,
        )
        response = self._request("POST", "/sdapi/v1/img2img", payload)
        return self._decode_images(response)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        timeout = float(self._settings.vision_local_sd_timeout_seconds)
        try:
            if self._transport is not None:
                return self._transport(method, url, payload)
            return _default_transport(method, url, payload, timeout=timeout)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"Local SD HTTP {exc.code} on {path}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Local SD unreachable at {self.base_url}: {exc}") from exc

    def _decode_images(self, response: dict[str, Any]) -> GeneratedImageBytes:
        images = response.get("images")
        if not isinstance(images, list) or not images:
            raise RuntimeError("Local SD returned no images")
        raw_b64 = images[0]
        if not isinstance(raw_b64, str) or not raw_b64.strip():
            raise RuntimeError("Local SD image payload empty")
        # Some forks prefix data-uri.
        if "," in raw_b64 and raw_b64.strip().lower().startswith("data:"):
            raw_b64 = raw_b64.split(",", 1)[1]
        return GeneratedImageBytes(
            data=base64.b64decode(raw_b64),
            mime_type="image/png",
            provider=self.provider,
            model=self.model,
        )


def _encode_image_as_png_b64(path: Path, *, width: int, height: int) -> str:
    from PIL import Image, ImageOps

    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
