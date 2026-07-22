"""Load and query the bundled Architectural Icon Registry."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from archium.domain.visual.architectural_icon import ArchitecturalIcon
from archium.infrastructure.embeddings.local_lexical import (
    LocalLexicalEmbeddingProvider,
    lexical_embed,
)

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_PACK_ROOT = Path(__file__).resolve().parents[2] / "resources" / "architectural_icons"
_EMBEDDINGS_NAME = "embeddings.json"
_EMBEDDING_PROVIDER = LocalLexicalEmbeddingProvider()


def default_icon_pack_root() -> Path:
    return _PACK_ROOT


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().casefold())


def _embed_query(text: str) -> list[float]:
    """Embed a query once using the offline lexical provider."""
    return _EMBEDDING_PROVIDER.embed_query(text)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # Align dims if pack was built with a different size (pad/truncate).
    if len(a) != len(b):
        dim = min(len(a), len(b))
        a = a[:dim]
        b = b[:dim]
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _load_offline_embeddings(pack_root: Path) -> dict[str, list[float]]:
    path = pack_root / _EMBEDDINGS_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    vectors = payload.get("vectors") if isinstance(payload, dict) else None
    if not isinstance(vectors, dict):
        return {}
    result: dict[str, list[float]] = {}
    for key, value in vectors.items():
        if isinstance(value, list) and value:
            result[str(key)] = [float(x) for x in value]
    return result


def build_icon_embed_source(
    *,
    canonical: str,
    aliases: list[str],
    categories: list[str],
    description: str = "",
) -> str:
    return " ".join([canonical, *aliases, *categories, description])


def precompute_icon_embeddings(pack_root: Path | None = None) -> dict[str, object]:
    """Rebuild ``embeddings.json`` from manifest using LocalLexicalEmbeddingProvider."""
    root = pack_root or default_icon_pack_root()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    vectors: dict[str, list[float]] = {}
    for item in manifest.get("icons", []):
        icon_id = str(item["id"])
        source = build_icon_embed_source(
            canonical=str(item["canonical_name"]),
            aliases=[str(a) for a in item.get("aliases", [])],
            categories=[str(c) for c in item.get("categories", [])],
            description=str(item.get("description") or ""),
        )
        vectors[icon_id] = _EMBEDDING_PROVIDER.embed_documents([source])[0]
    payload = {
        "provider": "local_lexical",
        "dimension": _EMBEDDING_PROVIDER.dimension,
        "vectors": vectors,
    }
    out = root / _EMBEDDINGS_NAME
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


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
    offline = _load_offline_embeddings(pack_root)
    icons: list[ArchitecturalIcon] = []
    for item in payload.get("icons", []):
        aliases = [str(a) for a in item.get("aliases", [])]
        categories = [str(c) for c in item.get("categories", [])]
        canonical = str(item["canonical_name"])
        icon_id = str(item["id"])
        description = str(item.get("description") or "")
        # Prefer offline pack vectors; fall back to one-shot lexical embed at load.
        embedding = list(item.get("embedding") or []) or list(offline.get(icon_id) or [])
        if not embedding:
            source = build_icon_embed_source(
                canonical=canonical,
                aliases=aliases,
                categories=categories,
                description=description,
            )
            embedding = lexical_embed(source)
        icons.append(
            ArchitecturalIcon(
                id=icon_id,
                canonical_name=canonical,
                aliases=aliases,
                categories=categories,
                svg_path=str(item["svg_path"]),
                embedding=embedding,
                license=str(item.get("license") or license_default),
                description=description,
            )
        )
    return ArchitecturalIconRegistry(icons, pack_root=pack_root)


class ArchitecturalIconMatcher:
    """Match semantic icon queries onto the registry.

    Priority: exact alias/name → alias contains → category → embedding cosine.

    Query embedding is computed **once** outside the icon loop. Icon vectors
    come from offline ``embeddings.json`` (or load-time lexical cache).
    """

    def __init__(
        self,
        registry: ArchitecturalIconRegistry | None = None,
        *,
        embed_query=None,
    ) -> None:
        self._registry = registry or load_default_architectural_icon_registry()
        self._embed_query = embed_query or _embed_query

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
        # Compute query vector once — never inside the per-icon loop.
        query_embedding = self._embed_query(text)
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
                score = _cosine(query_embedding, icon.embedding)
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
