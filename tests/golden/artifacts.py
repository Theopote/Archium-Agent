"""Persist golden-case export artifacts for validation sprint review."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archium.application.workflow_models import WorkflowRunResult

_ARTIFACT_ROOT = Path(__file__).resolve().parent / "artifacts"


def artifact_dir(case_id: str) -> Path:
    return _ARTIFACT_ROOT / case_id


def save_case_artifacts(case_id: str, result: WorkflowRunResult) -> Path:
    """Copy export files and write a manifest under tests/golden/artifacts/<case_id>/."""
    out_dir = artifact_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    render = result.render
    copied: dict[str, str | None] = {}

    def _copy_if_exists(source: Path | None, dest_name: str) -> None:
        if source is None or not source.exists():
            copied[dest_name] = None
            return
        dest = out_dir / dest_name
        shutil.copy2(source, dest)
        copied[dest_name] = dest.name

    _copy_if_exists(render.json_path, "presentation.json")
    _copy_if_exists(render.spec_path, "presentation.spec.json")
    _copy_if_exists(render.editable_pptx_path, "presentation.editable.pptx")
    _copy_if_exists(render.pptx_path, "presentation.marp.pptx")
    _copy_if_exists(render.pdf_path, "presentation.pdf")
    _copy_if_exists(render.markdown_path, "presentation.marp.md")

    preview_names: list[str] = []
    for index, image_path in enumerate(render.preview_images):
        if not image_path.exists():
            continue
        dest_name = f"preview_{index + 1:02d}{image_path.suffix or '.png'}"
        shutil.copy2(image_path, out_dir / dest_name)
        preview_names.append(dest_name)

    manifest: dict[str, Any] = {
        "case_id": case_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "presentation_id": str(result.presentation.id),
        "workflow_run_id": str(result.workflow_run.id),
        "workflow_status": result.workflow_run.status.value,
        "slide_count": len(result.slides),
        "review_issue_count": result.workflow_run.state.get("review_issue_count"),
        "errors": list(result.errors),
        "artifacts": copied,
        "preview_images": preview_names,
        "warnings": list(render.warnings),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_dir
