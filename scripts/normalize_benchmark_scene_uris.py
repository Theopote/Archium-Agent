"""One-shot: rewrite absolute scene asset paths to portable URIs and resync manifests."""

from __future__ import annotations

from tests.benchmark.architectural_slides.artifacts import (
    BENCHMARK_ROOT,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.render_manifest import (
    normalize_case_scene_portability,
    validate_scene_manifest_consistency,
)


def main() -> int:
    ok = 0
    fail = 0
    for case_id in materialized_benchmark_case_ids():
        case_dir = BENCHMARK_ROOT / case_id
        if not (case_dir / "scene.json").is_file():
            print(f"SKIP {case_id}: no scene.json")
            continue
        result = normalize_case_scene_portability(case_dir)
        blockers = validate_scene_manifest_consistency(case_dir)
        status = "OK" if result.get("ok") and not blockers else "FAIL"
        if status == "OK":
            ok += 1
        else:
            fail += 1
        print(
            f"{status} {case_id}: render_valid={result.get('render_valid')} "
            f"blockers={blockers[:3]}"
        )
    print(f"Done ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
