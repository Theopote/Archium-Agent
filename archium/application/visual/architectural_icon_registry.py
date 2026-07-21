"""Load and query the bundled Architectural Icon Registry."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from archium.domain.visual.architectural_icon import ArchitecturalIcon
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_PACK_ROOT = Path(__file__).resolve().parents[2] / "resources" / "architectural_icons"


def default_icon_pack_root() -> Path:
    return _PACK_ROOT


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().casefold())


def _embed_text(text: str) -> list[float]:
    return MockEmbeddingProvider().embed_query(text)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


class ArchitecturalIconRegistry:
    """In-memory registry of curated architectural pictograms."""

    def __init__(self, icons: list[ArchitecturalIcon], *, pack_root: Path) -> None:
        self._icons = list(icons)
        self._pack_root = pack_root
        self._by_id = {icon.id: icon for icon in self._icons}
        self._by_name: dict[str, ArchitecturalIcon] = {}
        for icon in self._icons:
            self._by_name[_normalize(icon.canonical_name)] = icon
            for alias in icon.aliases:
                self._by_name[_normalize(alias)] = icon

    @property
    def pack_root(self) -> Path:
        return self._pack_root

    def all(self) -> list[ArchitecturalIcon]:
        return list(self._icons)

    def get(self, icon_id: str) -> ArchitecturalIcon | None:
        return self._by_id.get(icon_id)

    def resolve_svg_path(self, icon: ArchitecturalIcon) -> Path:
        return (self._pack_root / icon.svg_path).resolve()

    def get_by_name(self, name: str) -> ArchitecturalIcon | None:
        return self._by_name.get(_normalize(name))


@lru_cache(maxsize=1)
def load_default_architectural_icon_registry() -> ArchitecturalIconRegistry:
    return load_architectural_icon_registry(default_icon_pack_root())


def load_architectural_icon_registry(pack_root: Path) -> ArchitecturalIconRegistry:
    manifest_path = pack_root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    license_default = str(payload.get("license") or "MIT")
    icons: list[ArchitecturalIcon] = []
    for item in payload.get("icons", []):
        aliases = [str(a) for a in item.get("aliases", [])]
        categories = [str(c) for c in item.get("categories", [])]
        canonical = str(item["canonical_name"])
        embed_source = " ".join([canonical, *aliases, *categories, str(item.get("description", ""))])
        embedding = list(item.get("embedding") or []) or _embed_text(embed_source)
        icons.append(
            ArchitecturalIcon(
                id=str(item["id"]),
                canonical_name=canonical,
                aliases=aliases,
                categories=categories,
                svg_path=str(item["svg_path"]),
                embedding=embedding,
                license=str(item.get("license") or license_default),
                description=str(item.get("description") or ""),
            )
        )
    return ArchitecturalIconRegistry(icons, pack_root=pack_root)


class ArchitecturalIconMatcher:
    """Match semantic icon queries onto the registry.

    Priority: exact alias/name → alias contains → category → embedding cosine.
    """

    def __init__(self, registry: ArchitecturalIconRegistry | None = None) -> None:
        self._registry = registry or load_default_architectural_icon_registry()

    @property
    def registry(self) -> ArchitecturalIconRegistry:
        return self._registry

    def match(self, query: str, *, min_score: float = 0.35):
        from archium.domain.visual.architectural_icon import ArchitecturalIconMatch

        text = (query or "").strip()
        if not text:
            return None

        # Strip optional [[semantic]] markup from prompts.
        if text.startswith("[[") and text.endswith("]]"):
            text = text[2:-2].strip()

        exact = self._registry.get_by_name(text)
        if exact is not None:
            return ArchitecturalIconMatch(icon=exact, score=1.0, matched_by="exact_alias")

        normalized = _normalize(text)
        tokens = {_normalize(tok) for tok in _TOKEN_PATTERN.findall(text) if tok.strip()}
        best: ArchitecturalIconMatch | None = None

        for icon in self._registry.all():
            names = {_normalize(icon.canonical_name), *(_normalize(a) for a in icon.aliases)}
            cats = {_normalize(c) for c in icon.categories}

            # Alias / name containment
            if any(normalized in name or name in normalized for name in names if name):
                candidate = ArchitecturalIconMatch(icon=icon, score=0.92, matched_by="alias")
                if best is None or candidate.score > best.score:
                    best = candidate
                continue

            overlap = tokens & names
            if overlap:
                score = min(0.88, 0.55 + 0.1 * len(overlap))
                candidate = ArchitecturalIconMatch(icon=icon, score=score, matched_by="alias")
                if best is None or candidate.score > best.score:
                    best = candidate
                continue

            cat_overlap = tokens & cats
            if cat_overlap or any(normalized in cat for cat in cats):
                candidate = ArchitecturalIconMatch(icon=icon, score=0.62, matched_by="category")
                if best is None or candidate.score > best.score:
                    best = candidate
                continue

            if icon.embedding:
                score = _cosine(_embed_text(text), icon.embedding)
                if score >= min_score:
                    candidate = ArchitecturalIconMatch(
                        icon=icon,
                        score=score,
                        matched_by="embedding",
                    )
                    if best is None or candidate.score > best.score:
                        best = candidate

        if best is None or best.score < min_score:
            return None
        return best
