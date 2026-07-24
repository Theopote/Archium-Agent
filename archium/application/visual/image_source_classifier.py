"""Classify user photo origins for Image Intelligence policy (not an Agent)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from archium.domain.asset import Asset
from archium.domain.visual.image_derivative import ImageSourceKind

_WECHAT_NAME = re.compile(
    r"mmexport|wx_camera|micro.?msg|weixin|微信|wx_?img|msg_\d{10,}",
    re.I,
)
_PHONE_NAME = re.compile(
    r"^img[_\-]?\d|dsc[_\-]?\d|photo[_\-]?\d|camera|iphone|pixel|截屏|screenshot",
    re.I,
)
_SCAN_NAME = re.compile(r"scan|扫描|扫描仪|camscanner|genius.?scan|pdf.?page", re.I)
_HISTORIC_NAME = re.compile(r"historic|history|vintage|老照片|历史|沿革|archive|film", re.I)
_SITE_NAME = re.compile(r"site|现场|踏勘|工地|entrance|corridor|院区|现状", re.I)

_WECHAT_TAGS = frozenset({"wechat", "微信", "wx", "mmexport"})
_PHONE_TAGS = frozenset({"phone", "mobile", "手机", "iphone", "android"})
_SCAN_TAGS = frozenset({"scan", "扫描", "document_scan", "scanned"})
_HISTORIC_TAGS = frozenset({"historic", "historical", "历史", "老照片", "vintage", "archive"})
_SITE_TAGS = frozenset({"site", "site_photo", "现场", "evidence", "踏勘", "工地"})


@dataclass(frozen=True)
class ImageSourceClassification:
    kind: ImageSourceKind
    confidence: float
    evidence: tuple[str, ...] = ()


class ImageSourceClassifier:
    """Rule + light pixel cues → ImageSourceKind for treatment planning."""

    def classify(
        self,
        *,
        path: Path | None = None,
        asset: Asset | None = None,
        filename: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> ImageSourceClassification:
        name = (filename or (asset.filename if asset else "") or (path.name if path else "")).strip()
        tag_set = {t.strip().lower() for t in (tags or (asset.tags if asset else []) or []) if t.strip()}
        meta = dict(asset.metadata) if asset is not None else {}
        blob = " ".join(
            [
                name,
                description or (asset.description if asset else "") or "",
                " ".join(sorted(tag_set)),
                str(meta.get("source_app", "")),
                str(meta.get("origin", "")),
                str(meta.get("purpose", "")),
            ]
        ).casefold()

        scored: list[tuple[ImageSourceKind, float, str]] = []

        if any(token in tag_set for token in _WECHAT_TAGS) or _WECHAT_NAME.search(name):
            scored.append((ImageSourceKind.WECHAT_EXPORT, 0.92, "wechat_name_or_tag"))
        if any(token in tag_set for token in _SCAN_TAGS) or _SCAN_NAME.search(name):
            scored.append((ImageSourceKind.DOCUMENT_SCAN, 0.9, "scan_name_or_tag"))
        if any(token in tag_set for token in _HISTORIC_TAGS) or _HISTORIC_NAME.search(blob):
            scored.append((ImageSourceKind.HISTORICAL, 0.88, "historic_cue"))
        if any(token in tag_set for token in _SITE_TAGS) or _SITE_NAME.search(blob):
            scored.append((ImageSourceKind.SITE_PHOTO, 0.8, "site_cue"))
        if any(token in tag_set for token in _PHONE_TAGS) or _PHONE_NAME.search(name):
            scored.append((ImageSourceKind.PHONE_PHOTO, 0.75, "phone_name_or_tag"))

        source_app = str(meta.get("source_app", "")).casefold()
        if "wechat" in source_app or "微信" in source_app:
            scored.append((ImageSourceKind.WECHAT_EXPORT, 0.95, "metadata_source_app"))
        if "scan" in source_app:
            scored.append((ImageSourceKind.DOCUMENT_SCAN, 0.93, "metadata_source_app"))

        pixel = self._pixel_cues(path)
        scored.extend(pixel)

        if not scored:
            return ImageSourceClassification(
                kind=ImageSourceKind.UNKNOWN,
                confidence=0.0,
                evidence=(),
            )

        scored.sort(key=lambda item: item[1], reverse=True)
        kind, confidence, label = scored[0]
        evidence = tuple(item[2] for item in scored if item[0] == kind)
        return ImageSourceClassification(kind=kind, confidence=confidence, evidence=evidence or (label,))

    def _pixel_cues(self, path: Path | None) -> list[tuple[ImageSourceKind, float, str]]:
        if path is None or not path.is_file():
            return []
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return []
        try:
            with Image.open(path) as opened:
                rgb = opened.convert("RGB")
                rgb.thumbnail((64, 64))
                gray = rgb.convert("L")
                sat = ImageStat.Stat(rgb).mean
                gstat = ImageStat.Stat(gray)
        except OSError:
            return []

        r, g, b = sat[0], sat[1], sat[2]
        mean_chroma = (abs(r - g) + abs(g - b) + abs(b - r)) / 3.0
        brightness = float(gstat.mean[0])
        contrast = float(gstat.stddev[0]) if gstat.stddev else 0.0
        hits: list[tuple[ImageSourceKind, float, str]] = []
        # Near-monochrome + high contrast → likely scan / blueprint photo.
        if mean_chroma < 8.0 and contrast > 45.0:
            hits.append((ImageSourceKind.DOCUMENT_SCAN, 0.62, "pixel_low_chroma_high_contrast"))
        # Low saturation + warm midtones → historical print vibe.
        if mean_chroma < 18.0 and 70.0 <= brightness <= 180.0 and (r - b) > 8.0:
            hits.append((ImageSourceKind.HISTORICAL, 0.55, "pixel_warm_desat"))
        # Typical phone JPEG: colorful mid brightness.
        if mean_chroma > 20.0 and 60.0 <= brightness <= 200.0:
            hits.append((ImageSourceKind.PHONE_PHOTO, 0.45, "pixel_colorful_phoneish"))
        return hits
