"""Vision Engine follow-up — intent suggestion + derivative harmonize."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision import (
    VisionImageGenerationService,
    suggest_image_request_for_slide,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationMode,
)
from archium.domain.visual.visual_grammar import PageArchetype


def _slide(**kwargs) -> SlideSpec:
    from archium.domain.enums import SlideType

    defaults = {
        "id": uuid4(),
        "presentation_id": uuid4(),
        "chapter_id": "ch-1",
        "order": 0,
        "slide_type": SlideType.CONTENT,
        "title": "交通优化策略",
        "message": "增加风雨连廊",
    }
    defaults.update(kwargs)
    return SlideSpec(**defaults)


def test_suggest_design_strategy_flow_diagram() -> None:
    request = suggest_image_request_for_slide(
        _slide(),
        page_archetype=PageArchetype.DESIGN_STRATEGY,
    )
    assert request is not None
    assert request.image_type == ArchitectureImageType.FLOW_DIAGRAM
    assert request.asset_policy.value == "illustrative_only"
    assert "连廊" in request.subject or "风雨" in request.subject


def test_suggest_skips_problem_diagnosis() -> None:
    request = suggest_image_request_for_slide(
        _slide(title="现状问题", message="走廊过窄"),
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    )
    assert request is None


def test_suggest_narrative_opening_atmosphere() -> None:
    request = suggest_image_request_for_slide(
        _slide(title="项目缘起", message="城市中的花园医院"),
        page_archetype=PageArchetype.NARRATIVE_OPENING,
    )
    assert request is not None
    assert request.image_type == ArchitectureImageType.ATMOSPHERE_IMAGE


def test_persist_uses_presentation_unify_derivative(tmp_path) -> None:
    from archium.config.settings import Settings

    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    service = VisionImageGenerationService(session=None, settings=settings)
    project_id = uuid4()
    result = service.generate(
        ImageRequest(
            subject="covered walkway concept",
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            mode=VisionGenerationMode.TEXT_TO_IMAGE,
            width=640,
            height=360,
            harmonize_output=True,
        ),
        project_id=project_id,
        persist_asset=True,
    )
    assert result.success is True
    assert result.harmonized is True
    assert result.storage_path is not None
    assert result.storage_path.endswith("_harmonized.jpg") or "vision_generated" in result.storage_path
    # LocalProjectStorage may nest differently — resolve via relative under storage root.
    from archium.infrastructure.storage.local_storage import LocalProjectStorage

    layout = LocalProjectStorage(settings=settings).ensure_project_layout(project_id)
    final = layout["root"] / result.storage_path
    assert final.is_file()
    assert final.stat().st_size > 500
    # Derivative cache should exist under cache/derivatives
    cache_derivatives = layout["cache"] / "derivatives"
    assert cache_derivatives.exists()
    assert any(cache_derivatives.rglob("*.jpg"))


def test_edit_still_harmonizes_via_derivative(tmp_path) -> None:
    from archium.config.settings import Settings
    from PIL import Image

    base = tmp_path / "photo.png"
    Image.new("RGB", (400, 300), color=(110, 120, 130)).save(base)
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "store")
    service = VisionImageGenerationService(session=None, settings=settings)
    result = service.generate(
        ImageRequest(
            subject="add canopy",
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            base_image_path=str(base),
            width=640,
            height=360,
            harmonize_output=True,
        ),
        project_id=uuid4(),
        persist_asset=True,
    )
    assert result.success is True
    assert result.harmonized is True
    assert result.provider == "conditioned_editor"
