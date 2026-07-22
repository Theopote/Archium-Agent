# Architectural Icon Pack (v1)

Bundled line pictograms for Archium — **not** an npm Lucide dependency.

| Item | Value |
|------|--------|
| Count | 10 SVGs (`manifest.json`) |
| Style | 24×24 viewBox, stroke `#1a1a1a`, `fill=none`, stroke-width 1.75 |
| License | MIT (see manifest) |
| Embeddings | Offline `embeddings.json` via `LocalLexicalEmbeddingProvider` |

## Rendering

- **PPTX**: `pptxgenjs` `addImage({ path: "*.svg" })` — SVG file path kept; **no CairoSVG** on this path.
- **PNG preview**: `png_renderer` may rasterize SVG with CairoSVG for screenshots only.
- **Theme stroke**: not yet remapped at render time (hardcoded stroke in SVG); tracked for IconNode sprint.

## Regenerate embeddings

```bash
py -3 -c "from archium.application.visual.architectural_icon_registry import precompute_icon_embeddings; precompute_icon_embeddings()"
```
