"""Run Phase 8 real-project pipelines and write RenderScene deliverable artifacts."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from archium.application.project_acceptance_service import ProjectAcceptanceService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.domain.project_acceptance import RealProjectAcceptanceRecord
from archium.domain.visual.benchmark import HumanVisualReviewSource
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm import MockLLMProvider
from archium.infrastructure.renderers.pptx_pdf import convert_pptx_to_pdf
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from archium.ui.visual_service import export_presentation_pptx_from_layout_plans
from sqlalchemy.orm import Session

from tests.e2e.real_projects.loader import seed_real_project_case
from tests.e2e.real_projects.phase7_loader import (
    load_phase7_project,
    resolve_input_manifest_path,
)
from tests.e2e.real_projects.phase8_artifacts import (
    PHASE8_PROJECT_IDS,
    ensure_outputs_dir,
    inspect_phase8_artifacts,
    write_json,
)
from tests.fixtures.mock_llm import pipeline_mock_selector


@dataclass(frozen=True)
class Phase8RunSummary:
    project_id: str
    presentation_id: UUID
    succeeded: bool
    slide_count: int
    outputs_dir: Path
    record: RealProjectAcceptanceRecord
    pptx_path: Path | None
    pdf_path: Path | None
    screenshot_count: int
    soft_notes: tuple[str, ...]


def run_phase8_project(
    project_id: str,
    *,
    session: Session,
    settings: object,
    scratch_dir: Path,
) -> Phase8RunSummary:
    """Seed, accept, compile RenderScenes, export PPTX/PDF, and dump Phase 8 outputs."""
    bundle = load_phase7_project(project_id)
    manifest_path = resolve_input_manifest_path(bundle)
    loaded, project, _paths = seed_real_project_case(
        session,
        manifest_path,
        scratch_dir=scratch_dir,
    )
    service = ProjectAcceptanceService(
        session,
        MockLLMProvider(selector=pipeline_mock_selector),
        settings=settings,  # type: ignore[arg-type]
    )
    record = service.run(loaded.manifest, project=project, presentation_request=loaded.request)
    record = record.model_copy(
        update={
            "project_id": bundle.profile.id,
            "scenario": bundle.profile.scenario,
            "title": bundle.profile.name,
        }
    )

    presentations = PresentationRepository(session)
    presentation_list = presentations.list_by_project(project.id)
    if not presentation_list:
        raise RuntimeError(f"{project_id}: no presentation after acceptance run")
    presentation = presentation_list[0]
    presentation_id = presentation.id

    outputs = ensure_outputs_dir(project_id)
    soft_notes: list[str] = []

    _dump_outline(session, presentation_id, outputs / "outline_plan.json")
    slides = presentations.list_slides(presentation_id)
    _dump_slide_specs(slides, outputs / "slide_specs")

    scene_service = StudioSceneService(session, settings=settings)  # type: ignore[arg-type]
    scene_results = scene_service.ensure_scenes_for_presentation(
        presentation_id,
        force_recompile=True,
    )
    if not scene_results:
        raise RuntimeError(f"{project_id}: failed to compile RenderScenes")
    _dump_scenes_and_previews(scene_results, outputs)

    pptx_path: Path | None = None
    pdf_path: Path | None = None
    screenshot_count = 0
    try:
        export = export_presentation_pptx_from_layout_plans(
            session,
            presentation_id,
            settings=settings,  # type: ignore[arg-type]
        )
        if export.editable_pptx_path is not None and Path(export.editable_pptx_path).is_file():
            pptx_path = outputs / "presentation.pptx"
            shutil.copy2(export.editable_pptx_path, pptx_path)
        else:
            soft_notes.append("PPTX export returned no file")
    except Exception as exc:  # noqa: BLE001 — keep soft diagnostics in manifest
        soft_notes.append(f"PPTX export failed: {exc}")

    if pptx_path is not None and pptx_path.is_file():
        try:
            converted = convert_pptx_to_pdf(pptx_path, outputs)
            if converted is not None and converted.is_file():
                target_pdf = outputs / "presentation.pdf"
                if converted.resolve() != target_pdf.resolve():
                    shutil.copy2(converted, target_pdf)
                pdf_path = target_pdf
            else:
                soft_notes.append("PDF skipped (LibreOffice unavailable or conversion failed)")
        except Exception as exc:  # noqa: BLE001
            soft_notes.append(f"PDF conversion failed: {exc}")

        shots_dir = outputs / "pptx_screenshots"
        if screenshot_tools_available():
            shots_dir.mkdir(parents=True, exist_ok=True)
            try:
                shots = export_pptx_slide_pngs(pptx_path, shots_dir)
                screenshot_count = len(shots)
                if not shots:
                    soft_notes.append("pptx_screenshots tools available but produced no PNGs")
            except Exception as exc:  # noqa: BLE001
                soft_notes.append(f"pptx_screenshots failed: {exc}")
        else:
            soft_notes.append("pptx_screenshots skipped (LibreOffice/pdftoppm unavailable)")
            if shots_dir.is_dir() and not any(shots_dir.iterdir()):
                shots_dir.rmdir()

    _write_placeholder_reviews(project_id, outputs, slide_count=len(slides))
    _write_render_manifest(
        outputs,
        project_id=project_id,
        presentation_id=presentation_id,
        slide_count=len(slides),
        scene_count=len(scene_results),
        pptx_path=pptx_path,
        pdf_path=pdf_path,
        screenshot_count=screenshot_count,
        soft_notes=soft_notes,
        scene_results=scene_results,
    )

    write_json(outputs / "acceptance_record.json", record.model_dump(mode="json"))
    return Phase8RunSummary(
        project_id=project_id,
        presentation_id=presentation_id,
        succeeded=bool(record.metrics.generation_succeeded and pptx_path is not None),
        slide_count=len(slides),
        outputs_dir=outputs,
        record=record,
        pptx_path=pptx_path,
        pdf_path=pdf_path,
        screenshot_count=screenshot_count,
        soft_notes=tuple(soft_notes),
    )


def run_all_phase8_projects(
    *,
    session: Session,
    settings: object,
    scratch_dir: Path,
    project_ids: list[str] | None = None,
) -> list[Phase8RunSummary]:
    ids = project_ids or list(PHASE8_PROJECT_IDS)
    return [
        run_phase8_project(
            project_id,
            session=session,
            settings=settings,
            scratch_dir=scratch_dir / project_id,
        )
        for project_id in ids
    ]


def _dump_outline(session: Session, presentation_id: UUID, path: Path) -> None:
    outlines = PresentationRepository(session).list_outlines(presentation_id)
    if not outlines:
        write_json(
            path,
            {
                "status": "missing",
                "sections": [],
                "notes": "No OutlinePlan persisted after acceptance run",
            },
        )
        return
    outline = outlines[0]
    payload = outline.model_dump(mode="json")
    # Normalize section key for checklist.
    if "sections" not in payload and "chapters" in payload:
        payload["sections"] = payload["chapters"]
    write_json(path, payload)


def _dump_slide_specs(slides: list, directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for slide in sorted(slides, key=lambda item: item.order):
        name = f"slide_{slide.order + 1:02d}.json"
        write_json(directory / name, slide.model_dump(mode="json"))


def _dump_scenes_and_previews(scene_results: list, outputs: Path) -> None:
    """Dump scenes in presentation slide order (ensure_scenes_for_presentation order)."""
    scenes_dir = outputs / "render_scenes"
    previews_dir = outputs / "scene_previews"
    if scenes_dir.exists():
        shutil.rmtree(scenes_dir)
    if previews_dir.exists():
        shutil.rmtree(previews_dir)
    scenes_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)
    for index, result in enumerate(scene_results, start=1):
        scene_path = scenes_dir / f"slide_{index:02d}.json"
        write_json(scene_path, result.scene.model_dump(mode="json"))
        preview_target = previews_dir / f"slide_{index:02d}.png"
        if result.preview_path.is_file():
            shutil.copy2(result.preview_path, preview_target)
        else:
            raise RuntimeError(f"missing scene preview: {result.preview_path}")


def _write_placeholder_reviews(project_id: str, outputs: Path, *, slide_count: int) -> None:
    visual = {
        "project_id": project_id,
        "source": HumanVisualReviewSource.PLACEHOLDER.value,
        "review_completed": False,
        "accepted_for_delivery": False,
        "slide_count": slide_count,
        "pages": [],
        "reviewer_notes": (
            "Phase 8 占位：须在 render_valid=true 且 pptx_render/scene_preview 就绪后 "
            "进行真实人工视觉评审（Phase 9）。"
        ),
    }
    editability = {
        "project_id": project_id,
        "source": HumanVisualReviewSource.PLACEHOLDER.value,
        "passed": False,
        "slide_count": slide_count,
        "pages": [],
        "reviewer_notes": (
            "Phase 8 占位：须基于 presentation.pptx 真实打开后填写可编辑性评审。"
        ),
    }
    write_json(outputs / "visual_review.json", visual)
    write_json(outputs / "editability_review.json", editability)


def _write_render_manifest(
    outputs: Path,
    *,
    project_id: str,
    presentation_id: UUID,
    slide_count: int,
    scene_count: int,
    pptx_path: Path | None,
    pdf_path: Path | None,
    screenshot_count: int,
    soft_notes: list[str],
    scene_results: list,
) -> None:
    unresolved = 0
    for result in scene_results:
        unresolved += sum(
            1
            for node in result.scene.nodes
            if getattr(node, "asset_unresolved", False)
        )
    pptx_ok = pptx_path is not None and pptx_path.is_file()
    render_valid = pptx_ok and scene_count == slide_count and unresolved == 0
    payload = {
        "project_id": project_id,
        "presentation_id": str(presentation_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "slide_count": slide_count,
        "scene_count": scene_count,
        "scene_preview_count": scene_count,
        "pptx_path": pptx_path.name if pptx_ok else "",
        "pdf_path": pdf_path.name if pdf_path is not None and pdf_path.is_file() else "",
        "pptx_screenshot_count": screenshot_count,
        "unresolved_asset_node_count": unresolved,
        "render_valid": render_valid,
        "renderer": "studio_scene_service+pptx_renderer",
        "soft_notes": soft_notes,
        "checklist": inspect_phase8_artifacts(project_id).present,
    }
    write_json(outputs / "render_manifest.json", payload)
