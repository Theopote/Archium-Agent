#!/usr/bin/env python3
"""Refresh curated pool + case assets for the architectural benchmark pilot trio.

Prefer ``scripts/materialize_benchmark_curated_assets.py --presentation-ready --sync-cases``
for the full 30-case pool.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.artifacts import case_dir  # noqa: E402
from tests.benchmark.architectural_slides.curated_assets import (  # noqa: E402
    CURATED_POOL_DIR,
    ensure_case_assets,
)
from tests.benchmark.architectural_slides.pilot_fixture_assets import (  # noqa: E402
    PILOT_ASSET_IDS,
    write_pilot_fixture_asset,
)

PILOT_CASES = (
    "case_001_site_plan",
    "case_002_site_photos",
    "case_006_project_hero",
)


def refresh_pilot_assets(*, sync_cases: bool = True) -> list[Path]:
    CURATED_POOL_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for asset_id in PILOT_ASSET_IDS:
        pool_path = CURATED_POOL_DIR / f"{asset_id}.png"
        write_pilot_fixture_asset(pool_path, asset_id=asset_id)
        written.append(pool_path)

    if not sync_cases:
        return written

    for case_id in PILOT_CASES:
        assets_dir = case_dir(case_id) / "assets"
        if assets_dir.is_dir():
            for png in assets_dir.glob("*.png"):
                png.unlink()
        ensure_case_assets(case_id, assets_dir)
        print(f"synced {case_id}")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pool-only",
        action="store_true",
        help="Update curated pool PNGs without touching per-case assets/",
    )
    args = parser.parse_args(argv)
    paths = refresh_pilot_assets(sync_cases=not args.pool_only)
    print(f"Wrote {len(paths)} pilot fixture assets under {CURATED_POOL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
