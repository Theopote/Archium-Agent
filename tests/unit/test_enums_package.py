"""DOM-018 / DOM-007: enums package split guards."""

from __future__ import annotations

from pathlib import Path

import archium.domain.enums as enums_pkg
from archium.domain.enums import (
    ApprovalStatus,
    PlanningWorkflowStep,
    PresentationWorkflowStep,
    RevisionSource,
    SlideChangeSource,
    SlideRecoveryWorkflowStep,
    VisualWorkflowStep,
    WorkflowStep,
)
from archium.domain.enums.workflow_steps import WORKFLOW_STEP_STAGES

_ENUMS_DIR = Path(enums_pkg.__file__).resolve().parent
_MAX_MODULE_LINES = 250
_WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / "archium" / "workflow"


def test_enums_is_package_not_monolith() -> None:
    assert _ENUMS_DIR.is_dir()
    assert not (_ENUMS_DIR.parent / "enums.py").exists()
    assert (_ENUMS_DIR / "__init__.py").is_file()


def test_enum_submodules_under_line_budget() -> None:
    oversized: list[str] = []
    for path in sorted(_ENUMS_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > _MAX_MODULE_LINES:
            oversized.append(f"{path.relative_to(_ENUMS_DIR)}:{lines}")
    assert oversized == [], f"enum modules exceed {_MAX_MODULE_LINES} lines: {oversized}"


def test_compat_reexports_and_aliases() -> None:
    assert SlideChangeSource is RevisionSource
    assert WorkflowStep.EXPORT.value == "export"
    assert ApprovalStatus.CHANGES_PENDING.value == "changes_pending"
    assert "WorkflowStep" in enums_pkg.__all__
    assert "PresentationWorkflowStep" in enums_pkg.__all__


def test_workflow_step_stages_cover_mega_enum() -> None:
    stage_values = {member.value for stage in WORKFLOW_STEP_STAGES for member in stage}
    mega_values = {member.value for member in WorkflowStep}
    assert stage_values == mega_values
    assert PresentationWorkflowStep.BRIEF.value == WorkflowStep.BRIEF.value
    assert PlanningWorkflowStep.PLANNING_FINALIZE.value == "planning_finalize"
    assert VisualWorkflowStep.VISUAL_SCENE_REPAIR.value == "visual_scene_repair"
    assert SlideRecoveryWorkflowStep.SLIDE_RECOVERY_QUEUED.value == "slide_recovery_queued"


def test_langgraph_definitions_do_not_import_workflow_step_enums() -> None:
    forbidden = (
        "WorkflowStep",
        "PresentationWorkflowStep",
        "PlanningWorkflowStep",
        "VisualWorkflowStep",
        "SlideRecoveryWorkflowStep",
    )
    for name in ("presentation_graph.py", "planning_graph.py", "visual_graph.py"):
        text = (_WORKFLOW_ROOT / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{name} must not reference {token}"
