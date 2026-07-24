# Archium LoRA packs (product distribution)

Each subdirectory is a **pack**:

```text
pack-id/
  pack.json          # required manifest
  weights/           # optional *.safetensors (not committed by default)
  README.md          # optional
```

## Workflow

1. Put weight files into `weights/` (or set `download_url` in `pack.json`).
2. Point ComfyUI LoRA dir: `VISION_COMFYUI_LORAS_DIR=.../ComfyUI/models/loras`
3. Install:

```bash
python -m archium.infrastructure.vision_gen.lora_packs install archium-marker-sketch-v1
```

4. Activate:

```text
VISION_LORA_PACK_ID=archium-marker-sketch-v1
VISION_IMAGE_GENERATION_PROVIDER=comfyui
```

Archium never treats pack outputs as site evidence — Vision Engine provenance remains `ai_generated` / illustrative.
