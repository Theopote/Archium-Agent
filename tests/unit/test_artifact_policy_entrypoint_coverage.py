from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.artifact_policy_service import (
    ARTIFACT_WRITE_ENTRYPOINTS,
    reconcile_pptx_into_scene,
    require_artifact_write_entrypoint,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.exceptions import WorkflowError


def test_all_application_render_scene_writes_use_artifact_policy_gateway() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "application"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "artifact_policy_service.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "_scenes.save(" in source:
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"RenderScene writes bypass ArtifactMutationGuard: {offenders}"


def test_required_write_entrypoints_are_registered() -> None:
    required = {
        "template_studio.import_pptx",
        "slide_recovery.import_external_scene",
        "scene_revision.restore",
        "reference_slide_editing.generate_scene",
        "pptx.reconcile.accept",
        "delivery.record_pptx_export",
    }
    assert required <= ARTIFACT_WRITE_ENTRYPOINTS


def test_unregistered_entrypoint_is_rejected() -> None:
    with pytest.raises(WorkflowError, match="Unregistered artifact write entrypoint"):
        require_artifact_write_entrypoint("not.a.real.entrypoint")


def test_reconcile_pptx_into_scene_is_the_product_write_path() -> None:
    class _Writer:
        def save(self, scene: RenderScene) -> RenderScene:
            return scene

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#fff"),
        nodes=[
            TextNode(
                id="t",
                x=0,
                y=0,
                width=1,
                height=1,
                text="x",
                font_family="Arial",
                font_size=12,
                color="#000",
                line_height=1.2,
            )
        ],
    )
    saved, proposal = reconcile_pptx_into_scene(
        _Writer(),
        scene,
        project_id=uuid4(),
        presentation_id=uuid4(),
        source_artifact_id=uuid4(),
        base_revision_id=uuid4(),
        diff={"nodes": ["t"]},
    )
    assert saved is scene
    assert proposal.status.value == "accepted"
