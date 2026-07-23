# Architectural Icon Pack (legacy path)

**Canonical pack location:** [`../../../assets/icons/README.md`](../../../assets/icons/README.md)

The registry loads from `assets/icons/` when `manifest.json` exists there; this directory remains as a fallback for older checkouts.

Regenerate embeddings:

```bash
py -3 -c "from archium.application.visual.architectural_icon_registry import precompute_icon_embeddings; precompute_icon_embeddings()"
```
