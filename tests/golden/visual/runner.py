"""Run deterministic golden cases with fixed Marp preview export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.regression.loader import load_regression_case, seed_regression_case
from tests.golden.visual.baseline import MARP_THEME, VISUAL_CASE_IDS

_CASES_DIR = Path(__file__).resolve().parents[1] / "regression" / "cases"


@dataclass(frozen=True)
class VisualRunResult:
    case_id: str
    workflow: WorkflowRunResult
    preview_paths: tuple[Path, ...]


def case_path(case_id: str) -> Path:
    if case_id not in VISUAL_CASE_IDS:
        msg = f"Unsupported visual baseline case: {case_id}"
        raise ValueError(msg)
    path = _CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def run_visual_baseline_case(
    session: Session,
    settings: Settings,
    case_id: str,
) -> VisualRunResult:
    path = case_path(case_id)
    _, project = seed_regression_case(session, path)
    case = load_regression_case(path)
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(session, mock_llm, settings=settings)
    try:
        result = service.run(
            project.id,
            case.request,
            export_json=True,
            export_marp=True,
            export_presentation_spec=case.export_presentation_spec,
            export_preview_images=True,
            require_brief_review=False,
            require_storyline_review=False,
            require_outline_review=False,
            require_slides_review=False,
        )
    finally:
        service.close()

    preview_paths = tuple(path for path in result.render.preview_images if path.exists())
    if not preview_paths:
        msg = (
            f"{case_id}: Marp preview export produced no PNG files. "
            "Ensure Marp CLI is installed and marp_preview_images_enabled=true."
        )
        raise RuntimeError(msg)
    if result.render.markdown_path is None:
        raise RuntimeError(f"{case_id}: expected Marp markdown export")
    return VisualRunResult(case_id=case_id, workflow=result, preview_paths=preview_paths)


def marp_theme_for_run() -> str:
    return MARP_THEME
