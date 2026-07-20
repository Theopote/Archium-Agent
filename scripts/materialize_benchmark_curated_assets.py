#!/usr/bin/env python3
"""Materialize curated benchmark assets from Phase 7 e2e project PNG pools."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.domain.enums import VisualType  # noqa: E402

from tests.benchmark.architectural_slides.case_catalog import CASE_CATALOG  # noqa: E402
from tests.benchmark.architectural_slides.curated_assets import (  # noqa: E402
    CURATED_MANIFEST_PATH,
    CURATED_POOL_DIR,
    CURATED_ROOT,
)

_E2E_FILES = _PROJECT_ROOT / "tests" / "e2e" / "real_projects" / "files"

# Source PNGs grouped by visual type (deterministic Phase 7 curated pool).
_POOL_BY_TYPE: dict[VisualType, list[Path]] = {
    VisualType.SITE_PLAN: [
        _E2E_FILES / "cultural_village_001/assets/04_water_network_plan.png",
        _E2E_FILES / "renovation_001/assets/05_floor_plan_after.png",
        _E2E_FILES / "cultural_village_001/assets/03_ancestral_hall_plan.png",
    ],
    VisualType.FLOOR_PLAN: [
        _E2E_FILES / "renovation_001/assets/04_floor_plan_before.png",
        _E2E_FILES / "renovation_001/assets/05_floor_plan_after.png",
    ],
    VisualType.SECTION: [
        _E2E_FILES / "renovation_001/assets/09_section_renovation.png",
        _E2E_FILES / "cultural_village_001/assets/11_street_section.png",
    ],
    VisualType.ELEVATION: [
        _E2E_FILES / "renovation_001/assets/02_facade_before.png",
    ],
    VisualType.SITE_PHOTO: [
        _E2E_FILES / "cultural_village_001/assets/01_village_aerial.png",
        _E2E_FILES / "cultural_village_001/assets/02_historic_alley.png",
        _E2E_FILES / "cultural_village_001/assets/05_courtyard_life.png",
        _E2E_FILES / "renovation_001/assets/01_factory_aerial.png",
        _E2E_FILES / "renovation_001/assets/06_public_realm.png",
    ],
    VisualType.DIAGRAM: [
        _E2E_FILES / "renovation_001/assets/07_circulation_diagram.png",
        _E2E_FILES / "cultural_village_001/assets/07_tourism_circulation.png",
        _E2E_FILES / "renovation_001/assets/08_phasing_diagram.png",
    ],
    VisualType.CHART: [
        _E2E_FILES / "cultural_village_001/assets/10_phasing_diagram.png",
    ],
    VisualType.RENDERING: [
        _E2E_FILES / "renovation_001/assets/10_ground_activation.png",
        _E2E_FILES / "cultural_village_001/assets/09_activation_strategy_plan.png",
    ],
    VisualType.COMPARISON: [
        _E2E_FILES / "renovation_001/assets/02_facade_before.png",
        _E2E_FILES / "renovation_001/assets/04_floor_plan_before.png",
    ],
    VisualType.REFERENCE_CASE: [
        _E2E_FILES / "cultural_village_001/assets/06_heritage_elements.png",
    ],
}


def _pick_source(visual_type: VisualType, index: int) -> Path | None:
    pool = _POOL_BY_TYPE.get(visual_type) or _POOL_BY_TYPE[VisualType.SITE_PHOTO]
    existing = [path for path in pool if path.is_file()]
    if not existing:
        return None
    return existing[index % len(existing)]


def build_manifest(*, force: bool) -> dict[str, str]:
    CURATED_ROOT.mkdir(parents=True, exist_ok=True)
    CURATED_POOL_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    type_counters: dict[VisualType, int] = dict.fromkeys(VisualType, 0)

    for entry in CASE_CATALOG:
        for asset in entry.assets:
            asset_id = str(asset.asset_id)
            counter = type_counters.get(asset.visual_type, 0)
            source = _pick_source(asset.visual_type, counter)
            type_counters[asset.visual_type] = counter + 1
            if source is None:
                continue
            pool_name = f"{asset_id}.png"
            dest = CURATED_POOL_DIR / pool_name
            if force or not dest.exists():
                shutil.copy(source, dest)
            manifest[asset_id] = f"pool/{pool_name}"

    payload = {
        "version": 1,
        "notes": (
            "Curated PNG pool copied from Phase 7 e2e project files. "
            "Used by ensure_case_assets() before placeholder fallback."
        ),
        "assets": manifest,
    }
    CURATED_MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite pool PNG copies")
    parser.add_argument(
        "--sync-cases",
        action="store_true",
        help="Replace per-case assets/*.png from curated pool",
    )
    args = parser.parse_args(argv)
    manifest = build_manifest(force=args.force)
    print(f"Wrote {CURATED_MANIFEST_PATH} ({len(manifest)} assets)")
    if args.sync_cases:
        from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
            materialized_benchmark_case_ids,
        )
        from tests.benchmark.architectural_slides.curated_assets import (  # noqa: E402
            ensure_case_assets,
        )

        root = CURATED_ROOT.parent
        for case_id in materialized_benchmark_case_ids(root=root):
            assets_dir = root / case_id / "assets"
            if assets_dir.is_dir():
                for png in assets_dir.glob("*.png"):
                    png.unlink()
            ensure_case_assets(case_id, assets_dir)
            print(f"synced assets for {case_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
