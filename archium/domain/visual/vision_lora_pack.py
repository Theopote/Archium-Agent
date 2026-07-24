"""Architectural LoRA pack contracts (Vision Engine product distribution).

Packs are **manifests + optional weight files**. Archium does not ship multi-GB
checkpoints in git; packs declare filenames, license, and optional download URLs.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class LoraPackBaseModel(StrEnum):
    """Target diffusion family for the pack."""

    SD15 = "sd15"
    SDXL = "sdxl"
    FLUX = "flux"
    UNKNOWN = "unknown"


class LoraAssetRole(StrEnum):
    PRIMARY = "primary"
    STYLE = "style"
    DETAIL = "detail"


class LoraAssetSpec(DomainModel):
    """One LoRA file inside a pack."""

    id: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=1, max_length=260)
    role: LoraAssetRole = LoraAssetRole.PRIMARY
    default_strength_model: float = Field(default=0.8, ge=0.0, le=2.0)
    default_strength_clip: float = Field(default=0.8, ge=0.0, le=2.0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    download_url: str | None = Field(default=None, max_length=2000)
    notes: str = ""


class VisionLoraPackManifest(DomainModel):
    """Product unit for distributing architectural LoRA presets."""

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0.0", max_length=40)
    description: str = ""
    license: str = Field(default="proprietary", max_length=120)
    base_model: LoraPackBaseModel = LoraPackBaseModel.SD15
    recommended_checkpoint: str = ""
    loras: list[LoraAssetSpec] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    image_types: list[str] = Field(default_factory=list)
    homepage: str = ""
    publisher: str = "Archium"

    def primary_lora(self) -> LoraAssetSpec | None:
        for item in self.loras:
            if item.role == LoraAssetRole.PRIMARY:
                return item
        return self.loras[0] if self.loras else None


class VisionLoraPackStatus(DomainModel):
    """Resolved pack on disk (manifest + weight presence)."""

    manifest: VisionLoraPackManifest
    pack_dir: str
    weights_present: list[str] = Field(default_factory=list)
    weights_missing: list[str] = Field(default_factory=list)
    installed_to_comfy: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.manifest.loras) and not self.weights_missing
