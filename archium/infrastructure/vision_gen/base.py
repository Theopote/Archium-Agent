"""Vision generation provider protocol and stub (Pillow) adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from archium.domain.visual.vision_generation import GenerationSpec


@dataclass(frozen=True)
class GeneratedImageBytes:
    data: bytes
    mime_type: str = "image/png"
    provider: str = ""
    model: str = ""


class VisionImageGenerator(Protocol):
    """Pluggable image backend (OpenAI / Flux / SD / stub)."""

    def is_available(self) -> bool:
        ...

    def generate(self, spec: GenerationSpec) -> GeneratedImageBytes:
        ...


class StubVisionImageGenerator:
    """Deterministic placeholder illustration — enables offline tests and demos."""

    provider = "stub"
    model = "pillow_diagram_v0"

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa: F401

            return True
        except ImportError:
            return False

    def generate(self, spec: GenerationSpec) -> GeneratedImageBytes:
        from io import BytesIO

        from PIL import Image, ImageDraw, ImageFont

        if not self.is_available():
            raise RuntimeError("Pillow unavailable for StubVisionImageGenerator")

        image = Image.new("RGB", (spec.width, spec.height), color=(236, 232, 224))
        draw = ImageDraw.Draw(image)
        margin = max(24, min(spec.width, spec.height) // 24)
        draw.rectangle(
            (margin, margin, spec.width - margin, spec.height - margin),
            outline=(60, 70, 80),
            width=3,
        )
        # Simple “diagram” cue: path + canopy bar for covered walkway demos.
        y = spec.height // 2
        draw.line((margin * 2, y, spec.width - margin * 2, y), fill=(180, 90, 70), width=6)
        draw.rectangle(
            (margin * 3, y - margin * 2, spec.width - margin * 3, y - margin),
            outline=(90, 110, 130),
            width=3,
        )
        label = f"{spec.image_type.value} · {spec.prompt_hash}"
        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover
            font = None
        draw.text((margin * 2, margin * 2), "Archium Vision Engine (stub)", fill=(40, 40, 40), font=font)
        draw.text((margin * 2, margin * 2 + 18), label[:80], fill=(70, 70, 70), font=font)
        subject_snip = spec.prompt[spec.prompt.find("Subject:") :][:90] if "Subject:" in spec.prompt else ""
        if subject_snip:
            draw.text((margin * 2, spec.height - margin * 3), subject_snip, fill=(80, 80, 80), font=font)

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedImageBytes(
            data=buffer.getvalue(),
            mime_type="image/png",
            provider=self.provider,
            model=self.model,
        )
