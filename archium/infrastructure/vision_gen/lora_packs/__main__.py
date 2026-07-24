"""CLI: list / install architectural Vision LoRA packs.

Examples::

    python -m archium.infrastructure.vision_gen.lora_packs list
    python -m archium.infrastructure.vision_gen.lora_packs install archium-marker-sketch-v1
"""

from __future__ import annotations

import argparse
import json
import sys

from archium.infrastructure.vision_gen.lora_packs.service import VisionLoraPackService
from archium.config.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archium Vision LoRA pack manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List discovered packs")

    install = sub.add_parser("install", help="Install pack weights into ComfyUI loras dir")
    install.add_argument("pack_id")
    install.add_argument(
        "--link",
        action="store_true",
        help="Symlink instead of copy (Windows may require admin / Developer Mode)",
    )
    install.add_argument(
        "--no-download",
        action="store_true",
        help="Do not attempt download_url fetches",
    )

    show = sub.add_parser("show", help="Show one pack as JSON")
    show.add_argument("pack_id")

    args = parser.parse_args(argv)
    service = VisionLoraPackService(get_settings())

    if args.command == "list":
        rows = []
        for status in service.list_packs():
            rows.append(
                {
                    "id": status.manifest.id,
                    "name": status.manifest.name,
                    "version": status.manifest.version,
                    "ready": status.ready,
                    "missing": status.weights_missing,
                    "installed_to_comfy": status.installed_to_comfy,
                    "styles": status.manifest.styles,
                }
            )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.command == "show":
        pack = service.get_pack(args.pack_id)
        if pack is None:
            print(f"pack not found: {args.pack_id}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "manifest": pack.manifest.model_dump(mode="json"),
                    "pack_dir": pack.pack_dir,
                    "weights_present": pack.weights_present,
                    "weights_missing": pack.weights_missing,
                    "ready": pack.ready,
                    "installed_to_comfy": pack.installed_to_comfy,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "install":
        paths = service.install_to_comfy(
            args.pack_id,
            download_missing=not args.no_download,
            link=args.link,
        )
        print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
