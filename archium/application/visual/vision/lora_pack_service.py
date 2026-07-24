"""Discover, verify, and install architectural LoRA packs for ComfyUI."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from archium.config.settings import Settings, get_settings
from archium.domain.visual.vision_lora_pack import (
    LoraAssetSpec,
    VisionLoraPackManifest,
    VisionLoraPackStatus,
)
from archium.exceptions import WorkflowError
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_lora_packs")

_MANIFEST_NAMES = ("pack.json", "manifest.json")


@dataclass(frozen=True)
class ActiveLoraSelection:
    """Resolved LoRA filename + strengths for ComfyUI graphs."""

    filename: str
    strength_model: float
    strength_clip: float
    pack_id: str | None = None
    source: str = "settings"


def bundled_packs_root() -> Path:
    """Shipped pack manifests (weights optional / downloaded)."""
    return (
        Path(__file__).resolve().parents[3]
        / "infrastructure"
        / "vision_gen"
        / "lora_packs"
    )


class VisionLoraPackService:
    """Product distribution surface for architectural LoRA packs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def list_packs(self) -> list[VisionLoraPackStatus]:
        roots = self._search_roots()
        found: dict[str, VisionLoraPackStatus] = {}
        for root in roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                status = self._load_pack_dir(child)
                if status is None:
                    continue
                # Later roots (user dir) override bundled same id.
                found[status.manifest.id] = status
        return sorted(found.values(), key=lambda item: item.manifest.id)

    def get_pack(self, pack_id: str) -> VisionLoraPackStatus | None:
        needle = pack_id.strip()
        for status in self.list_packs():
            if status.manifest.id == needle:
                return status
        return None

    def resolve_active_lora(self) -> ActiveLoraSelection | None:
        """Prefer active pack primary LoRA; else fall back to VISION_COMFYUI_LORA."""
        pack_id = (self._settings.vision_lora_pack_id or "").strip()
        if pack_id:
            status = self.get_pack(pack_id)
            if status is None:
                logger.warning("Configured LoRA pack not found: %s", pack_id)
            else:
                primary = status.manifest.primary_lora()
                if primary is None:
                    raise WorkflowError(f"LoRA pack `{pack_id}` has no lora assets.")
                if primary.filename in status.weights_missing and not status.installed_to_comfy:
                    logger.warning(
                        "LoRA pack `%s` missing weight `%s` (set download_url or install).",
                        pack_id,
                        primary.filename,
                    )
                return ActiveLoraSelection(
                    filename=primary.filename,
                    strength_model=primary.default_strength_model,
                    strength_clip=primary.default_strength_clip,
                    pack_id=pack_id,
                    source="pack",
                )

        filename = (self._settings.vision_comfyui_lora or "").strip()
        if not filename:
            return None
        return ActiveLoraSelection(
            filename=filename,
            strength_model=self._settings.vision_comfyui_lora_strength_model,
            strength_clip=self._settings.vision_comfyui_lora_strength_clip,
            pack_id=None,
            source="settings",
        )

    def suggest_pack_for_style(self, style: str) -> VisionLoraPackStatus | None:
        style_key = style.strip().lower()
        if not style_key:
            return None
        for status in self.list_packs():
            styles = {item.strip().lower() for item in status.manifest.styles}
            if style_key in styles:
                return status
        return None

    def download_missing_weights(self, pack_id: str, *, force: bool = False) -> list[Path]:
        """Download pack weights that declare ``download_url`` into ``weights/``."""
        status = self.get_pack(pack_id)
        if status is None:
            raise WorkflowError(f"LoRA pack not found: {pack_id}")
        pack_dir = Path(status.pack_dir)
        weights_dir = pack_dir / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for asset in status.manifest.loras:
            target = weights_dir / asset.filename
            if target.is_file() and not force:
                continue
            if not asset.download_url:
                continue
            logger.info("Downloading LoRA %s → %s", asset.download_url, target)
            self._download(asset.download_url, target)
            self._verify_sha256(asset, target)
            written.append(target)
        return written

    def install_to_comfy(
        self,
        pack_id: str,
        *,
        comfy_loras_dir: str | Path | None = None,
        download_missing: bool = True,
        link: bool = False,
    ) -> list[Path]:
        """Copy/symlink pack weights into ComfyUI ``models/loras``."""
        status = self.get_pack(pack_id)
        if status is None:
            raise WorkflowError(f"LoRA pack not found: {pack_id}")
        if download_missing:
            self.download_missing_weights(pack_id)

        status = self.get_pack(pack_id)
        assert status is not None
        if status.weights_missing:
            raise WorkflowError(
                "LoRA pack weights missing: "
                + ", ".join(status.weights_missing)
                + "（请提供 weights/ 文件或 pack.json 中的 download_url）"
            )

        dest_root = Path(
            comfy_loras_dir
            or self._settings.vision_comfyui_loras_dir
            or ""
        )
        if not str(dest_root).strip():
            raise WorkflowError(
                "未配置 ComfyUI LoRA 目录：设置 VISION_COMFYUI_LORAS_DIR "
                "（例如 .../ComfyUI/models/loras）。"
            )
        dest_root.mkdir(parents=True, exist_ok=True)

        pack_dir = Path(status.pack_dir)
        installed: list[Path] = []
        for asset in status.manifest.loras:
            source = self._resolve_weight_path(pack_dir, asset.filename)
            if source is None:
                raise WorkflowError(f"Weight not found for {asset.filename}")
            self._verify_sha256(asset, source)
            dest = dest_root / asset.filename
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            if link:
                dest.symlink_to(source.resolve())
            else:
                shutil.copy2(source, dest)
            installed.append(dest)
            logger.info("Installed LoRA %s → %s", source.name, dest)
        return installed

    def _search_roots(self) -> list[Path]:
        roots: list[Path] = [bundled_packs_root()]
        configured = (self._settings.vision_lora_packs_dir or "").strip()
        if configured:
            roots.append(Path(configured))
        # Project-local packs under storage (optional convenience).
        storage = Path(self._settings.project_storage_path)
        roots.append(storage / "vision_lora_packs")
        return roots

    def _load_pack_dir(self, pack_dir: Path) -> VisionLoraPackStatus | None:
        manifest_path = None
        for name in _MANIFEST_NAMES:
            candidate = pack_dir / name
            if candidate.is_file():
                manifest_path = candidate
                break
        if manifest_path is None:
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = VisionLoraPackManifest.model_validate(payload)
        except Exception as exc:
            logger.warning("Invalid LoRA pack manifest at %s: %s", manifest_path, exc)
            return None

        present: list[str] = []
        missing: list[str] = []
        for asset in manifest.loras:
            if self._resolve_weight_path(pack_dir, asset.filename) is not None:
                present.append(asset.filename)
            else:
                missing.append(asset.filename)

        comfy_dir = (self._settings.vision_comfyui_loras_dir or "").strip()
        installed = False
        if comfy_dir:
            root = Path(comfy_dir)
            installed = all((root / name).is_file() for name in present) and bool(present)

        return VisionLoraPackStatus(
            manifest=manifest,
            pack_dir=str(pack_dir.resolve()),
            weights_present=present,
            weights_missing=missing,
            installed_to_comfy=installed,
        )

    @staticmethod
    def _resolve_weight_path(pack_dir: Path, filename: str) -> Path | None:
        for candidate in (
            pack_dir / "weights" / filename,
            pack_dir / filename,
        ):
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _verify_sha256(asset: LoraAssetSpec, path: Path) -> None:
        expected = (asset.sha256 or "").strip().lower()
        if not expected:
            return
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise WorkflowError(
                f"LoRA sha256 mismatch for {asset.filename}: expected {expected}, got {digest}"
            )

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        request = Request(url, headers={"User-Agent": "Archium-Vision-LoRA-Pack/1.0"})
        try:
            with urlopen(request, timeout=120) as response:  # noqa: S310
                data = response.read()
        except URLError as exc:
            raise WorkflowError(f"Failed to download LoRA from {url}: {exc}") from exc
        destination.write_bytes(data)
