#!/usr/bin/env python3
"""Nightly gate for 30-case Rendered Visual Benchmark (§15).

Hard-fails when PPTX / screenshot / scene artifacts are missing, screenshots
are empty or all identical, or Scene Semantic QA reports high-severity issues
(font fallback, unresolved images, Scene↔PPTX mismatch).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.application.visual.scene_semantic_qa_service import (  # noqa: E402
    run_scene_semantic_qa,
)
from archium.domain.visual.render_scene import RenderScene  # noqa: E402
from archium.domain.visual.scene_qa import SceneSemanticCheckCode  # noqa: E402
from archium.infrastructure.renderers.renderer_conformance import (  # noqa: E402
    assert_renderer_conformance,
)
from archium.infrastructure.vision.screenshot_qa import (  # noqa: E402
    average_hash,
    hash_distance,
    load_image,
)
from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
    BENCHMARK_ROOT,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.render_manifest import (  # noqa: E402
    SCENE_JSON_NAME,
    final_render_path,
    pptx_render_path,
    validate_scene_manifest_consistency,
    visual_review_image_path,
)

_EXPECTED_CASE_COUNT = 30
_HARD_SCENE_CODES = frozenset(
    {
        SceneSemanticCheckCode.FONT_FALLBACK_CHANGED_LAYOUT,
        SceneSemanticCheckCode.IMAGE_NOT_RENDERED,
        SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH,
    }
)
_DEFAULT_REPORT = _PROJECT_ROOT / "output" / "ci" / "nightly-rendered-visual-gate.json"


def _pptx_path(case_dir: Path) -> Path:
    return case_dir / "output.pptx"


def _check_case_artifacts(case_id: str, case_dir: Path) -> list[str]:
    errors: list[str] = []
    pptx = _pptx_path(case_dir)
    if not pptx.is_file() or pptx.stat().st_size <= 0:
        errors.append(f"{case_id}: missing or empty output.pptx")

    scene = case_dir / SCENE_JSON_NAME
    if not scene.is_file() or scene.stat().st_size <= 0:
        errors.append(f"{case_id}: missing or empty scene.json")

    preferred = visual_review_image_path(case_dir)
    pptx_png = pptx_render_path(case_dir)
    final_png = final_render_path(case_dir)
    screenshot = preferred if preferred is not None else (
        pptx_png if pptx_png.is_file() else final_png if final_png.is_file() else None
    )
    if screenshot is None or not screenshot.is_file() or screenshot.stat().st_size <= 0:
        errors.append(
            f"{case_id}: missing non-empty screenshot "
            f"(need pptx_render.png or final_render.png)"
        )

    for blocker in validate_scene_manifest_consistency(case_dir):
        errors.append(f"{case_id}: {blocker}")
    return errors


def _load_scene(case_dir: Path) -> RenderScene | None:
    path = case_dir / SCENE_JSON_NAME
    if not path.is_file():
        return None
    try:
        return RenderScene.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _scene_qa_errors(
    case_id: str,
    case_dir: Path,
    *,
    presentation_id: UUID,
) -> tuple[list[str], list[dict[str, object]]]:
    scene = _load_scene(case_dir)
    if scene is None:
        return [f"{case_id}: scene.json could not be parsed"], []

    from archium.application.visual.asset_path_resolver import (
        AssetPathResolveContext,
        AssetPathResolver,
    )

    render_scene = AssetPathResolver().resolve_scene(
        scene,
        AssetPathResolveContext(
            case_dir=case_dir,
            case_id=case_id,
            assets_dir=case_dir / "assets",
            benchmark_root=case_dir.parent,
        ),
    )

    pptx = _pptx_path(case_dir)
    pptx_map = {scene.slide_id: pptx} if pptx.is_file() else None
    # Also run conformance explicitly when PPTX exists (feeds SCENE_PPTX_NODE_MISMATCH).
    findings_payload: list[dict[str, object]] = []
    errors: list[str] = []

    if pptx.is_file():
        conformance = assert_renderer_conformance(render_scene, pptx_path=pptx)
        if not conformance.passed:
            errors.append(
                f"{case_id}: Scene/PPTX mismatch — " + "; ".join(conformance.issues[:3])
            )
            findings_payload.append(
                {
                    "case_id": case_id,
                    "check_code": SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH,
                    "severity": "high",
                    "description": "; ".join(conformance.issues[:6]),
                }
            )

    report = run_scene_semantic_qa(
        presentation_id,
        [scene],
        pptx_paths_by_slide=pptx_map,
        slide_orders={scene.slide_id: 0},
    )
    for finding in report.findings:
        findings_payload.append(
            {
                "case_id": case_id,
                "check_code": finding.check_code,
                "severity": finding.severity,
                "title": finding.title,
                "description": finding.description,
            }
        )
        if finding.check_code in _HARD_SCENE_CODES:
            errors.append(
                f"{case_id}: {finding.check_code} — {finding.title}: {finding.description}"
            )
    return errors, findings_payload


def run_gate(*, root: Path, report_path: Path) -> int:
    case_ids = materialized_benchmark_case_ids(root=root)
    errors: list[str] = []
    findings: list[dict[str, object]] = []
    screenshot_hashes: list[tuple[str, int]] = []
    presentation_id = uuid4()

    if len(case_ids) != _EXPECTED_CASE_COUNT:
        errors.append(
            f"expected {_EXPECTED_CASE_COUNT} materialized cases, found {len(case_ids)}"
        )

    for case_id in case_ids:
        case_dir = root / case_id
        errors.extend(_check_case_artifacts(case_id, case_dir))

        image_path = visual_review_image_path(case_dir)
        if image_path is not None and image_path.is_file() and image_path.stat().st_size > 0:
            image = load_image(image_path)
            if image is not None:
                screenshot_hashes.append((case_id, average_hash(image)))

        scene_errors, scene_findings = _scene_qa_errors(
            case_id,
            case_dir,
            presentation_id=presentation_id,
        )
        errors.extend(scene_errors)
        findings.extend(scene_findings)

    if len(screenshot_hashes) >= 2:
        digests = [digest for _case_id, digest in screenshot_hashes]
        if all(hash_distance(digests[0], other) == 0 for other in digests[1:]):
            errors.append(
                f"all {len(screenshot_hashes)} screenshots are identical (aHash match)"
            )

    report = {
        "passed": not errors,
        "expected_case_count": _EXPECTED_CASE_COUNT,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "screenshot_count": len(screenshot_hashes),
        "errors": errors,
        "scene_findings": findings,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if errors:
        print(f"FAIL nightly rendered visual gate ({len(errors)} error(s))", file=sys.stderr)
        for item in errors[:40]:
            print(f"  - {item}", file=sys.stderr)
        if len(errors) > 40:
            print(f"  … and {len(errors) - 40} more", file=sys.stderr)
        print(f"Report: {report_path}", file=sys.stderr)
        return 1

    print(
        f"OK nightly rendered visual gate: {len(case_ids)} cases, "
        f"{len(screenshot_hashes)} screenshots → {report_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=BENCHMARK_ROOT)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    args = parser.parse_args(argv)
    return run_gate(root=args.root, report_path=args.report)


if __name__ == "__main__":
    raise SystemExit(main())
