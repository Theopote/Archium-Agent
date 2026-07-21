"""Unit tests for Nightly rendered-visual gate helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from scripts.ci_nightly_rendered_visual_gate import _check_case_artifacts, run_gate


def test_check_case_artifacts_reports_missing(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_001_demo"
    case_dir.mkdir()
    errors = _check_case_artifacts("case_001_demo", case_dir)
    assert any("output.pptx" in item for item in errors)
    assert any("scene.json" in item for item in errors)
    assert any("screenshot" in item for item in errors)


def test_run_gate_writes_report_and_fails_on_empty_root(tmp_path: Path) -> None:
    report = tmp_path / "gate.json"
    # Empty root → 0 cases ≠ 30
    code = run_gate(root=tmp_path, report_path=report)
    assert code == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload["case_count"] == 0
    assert any("expected 30" in err for err in payload["errors"])


def test_check_case_artifacts_passes_minimal_files(tmp_path: Path) -> None:
    from archium.domain.visual.benchmark import BenchmarkRenderManifest
    from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, compute_scene_hash
    from pptx import Presentation
    from tests.benchmark.architectural_slides.render_manifest import (
        sha256_file,
        write_pptx_render_sidecar,
        write_pptx_sidecar,
        write_render_manifest,
    )

    case_dir = tmp_path / "case_001_demo"
    case_dir.mkdir()
    pptx = case_dir / "output.pptx"
    Presentation().save(str(pptx))
    pptx_hash = sha256_file(pptx)
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
    )
    scene_hash = compute_scene_hash(scene)
    (case_dir / "scene.json").write_text(
        json.dumps(scene.model_dump(mode="json")),
        encoding="utf-8",
    )
    (case_dir / "pptx_render.png").write_bytes(b"\x89PNG" + b"0" * 64)
    write_pptx_sidecar(case_dir, scene_hash=scene_hash, pptx_content_hash=pptx_hash)
    write_pptx_render_sidecar(
        case_dir,
        scene_hash=scene_hash,
        pptx_content_hash=pptx_hash,
    )
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
            scene_id=str(scene.id),
            scene_hash=scene_hash,
            pptx_screenshot_source_hash=scene_hash,
            pptx_content_hash=pptx_hash,
            post_render_qa_passed=True,
            rendered_at=datetime.now(UTC),
        ),
    )
    errors = _check_case_artifacts("case_001_demo", case_dir)
    assert errors == [], errors
