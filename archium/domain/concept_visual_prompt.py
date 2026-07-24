"""Structured visual generation parameters for a concept direction."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class ConceptVisualPrompt(DomainModel):
    """Seed parameters for Vision Engine / image generation (not a rendered asset)."""

    image_prompt: str = ""
    camera: str = Field(default="", description="e.g. architectural axonometric, eye-level")
    style: str = Field(default="", description="e.g. concept sketch, soft atmosphere")

    def is_empty(self) -> bool:
        return not any(
            part.strip()
            for part in (self.image_prompt, self.camera, self.style)
        )

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        lines = ["视觉生成参数："]
        if self.image_prompt.strip():
            lines.append(f"- 画面：{self.image_prompt.strip()}")
        if self.camera.strip():
            lines.append(f"- 视角：{self.camera.strip()}")
        if self.style.strip():
            lines.append(f"- 风格：{self.style.strip()}")
        return "\n".join(lines)
