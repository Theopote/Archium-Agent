"""Phase 9: generate pptx_render.png for architectural benchmark cases."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from archium.domain.visual.benchmark import BenchmarkRenderManifest
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)

from tests.benchmark.architectural_slides.render_manifest import (
    FINAL_RENDER_NAME,
    PPTX_RENDER_NAME,
    ensure_pptx_render_alias,
    load_render_manifest,
    pptx_render_path,
    write_render_manifest,
)

PPTX_NAME = "output.pptx"
_TMP_DIR = "_pptx_render_tmp"


@dataclass(frozen=True)
class PptxRenderMaterializeResult:
    case_id: str
    succeeded: bool
    pptx_render: Path | None
    notes: str


def materialize_case_pptx_render(
    case_dir: Path,
    *,
    force: bool = False,
) -> PptxRenderMaterializeResult:
    """Rasterize ``output.pptx`` → ``final_render.png`` / ``pptx_render.png`` and refresh manifest."""
    case_id = case_dir.name
    pptx_path = case_dir / PPTX_NAME
    if not pptx_path.is_file():
        return PptxRenderMaterializeResult(
            case_id=case_id,
            succeeded=False,
            pptx_render=None,
            notes="missing output.pptx",
        )

    existing = pptx_render_path(case_dir)
    if existing.is_file() and not force and existing.stat().st_size > 0:
        _refresh_manifest_after_render(case_dir, reused=True)
        return PptxRenderMaterializeResult(
            case_id=case_id,
            succeeded=True,
            pptx_render=existing,
            notes="pptx_render.png already present",
        )

    if not screenshot_tools_available():
        return PptxRenderMaterializeResult(
            case_id=case_id,
            succeeded=False,
            pptx_render=None,
            notes="screenshot tools unavailable (LibreOffice+pdftoppm or PowerPoint)",
        )

    tmp_dir = case_dir / _TMP_DIR
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        shots = export_pptx_slide_pngs(pptx_path, tmp_dir)
        if not shots:
            return PptxRenderMaterializeResult(
                case_id=case_id,
                succeeded=False,
                pptx_render=None,
                notes="screenshot export returned no PNGs",
            )
        final_path = case_dir / FINAL_RENDER_NAME
        final_path.write_bytes(shots[0].read_bytes())
        aliased = ensure_pptx_render_alias(case_dir)
        if aliased is None or not aliased.is_file():
            # ensure_pptx_render_alias copies final→pptx_render; write directly if needed
            target = case_dir / PPTX_RENDER_NAME
            target.write_bytes(shots[0].read_bytes())
            aliased = target
        _refresh_manifest_after_render(case_dir, reused=False)
        return PptxRenderMaterializeResult(
            case_id=case_id,
            succeeded=True,
            pptx_render=aliased,
            notes=f"wrote {aliased.name} ({aliased.stat().st_size} bytes)",
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _refresh_manifest_after_render(case_dir: Path, *, reused: bool) -> None:
    manifest = load_render_manifest(case_dir)
    if manifest is None:
        manifest = BenchmarkRenderManifest()
    notes = manifest.notes or ""
    stamp = "pptx_render.png rasterized from output.pptx via screenshot tools."
    if stamp not in notes:
        notes = (notes + " " + stamp).strip()
    if reused and "already present" not in notes:
        notes = (notes + " pptx_render.png reused.").strip()
    updated = manifest.model_copy(
        update={
            "render_source": "pptx_screenshot",
            "image_path": PPTX_RENDER_NAME,
            "pptx_path": PPTX_NAME,
            "rendered_at": datetime.now(UTC),
            "notes": notes,
        }
    )
    # Keep render_valid from prior scene compile; do not flip false→true here.
    write_render_manifest(case_dir, updated)


def write_phase9_eligibility_report(
    root: Path,
    *,
    results: list[PptxRenderMaterializeResult],
    report_path: Path | None = None,
) -> Path:
    from tests.benchmark.architectural_slides.render_manifest import visual_review_eligibility

    rows = []
    for result in results:
        case_dir = root / result.case_id
        eligible, manifest, blockers = visual_review_eligibility(case_dir)
        rows.append(
            {
                "case_id": result.case_id,
                "materialize_ok": result.succeeded,
                "materialize_notes": result.notes,
                "eligible": eligible,
                "blockers": blockers,
                "render_valid": bool(manifest.render_valid) if manifest else False,
                "pptx_render_exists": pptx_render_path(case_dir).is_file(),
            }
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "eligible_count": sum(1 for row in rows if row["eligible"]),
        "total": len(rows),
        "cases": rows,
    }
    path = report_path or (root / "reports" / "phase9-eligibility.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
