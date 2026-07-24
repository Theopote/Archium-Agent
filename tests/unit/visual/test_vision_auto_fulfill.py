"""Tests for VisualIntent image_request auto-fulfill."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.visual.vision import VisionImageGenerationService
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.enums import ContinuityRole, DensityLevel, VisualContentType
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    GenerationSpec,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationResult,
)
from archium.domain.visual.visual_intent import VisualIntent


def _intent(**kwargs) -> VisualIntent:
    defaults = {
        "slide_id": uuid4(),
        "presentation_id": uuid4(),
        "communication_goal": "传达概念",
        "audience_takeaway": "可讨论方向",
        "visual_priority": "主图",
        "dominant_content_type": VisualContentType.HERO_IMAGE,
        "density_level": DensityLevel.BALANCED,
        "continuity_role": ContinuityRole.OPENING,
        "approval_status": ApprovalStatus.PENDING,
        "image_request": ImageRequest(
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            subject="窑洞拱廊示意",
        ),
    }
    defaults.update(kwargs)
    return VisualIntent(**defaults)


def test_fulfill_skips_when_generation_disabled(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        vision_image_generation_enabled=False,
        vision_auto_fulfill_image_requests=True,
    )
    service = VisionImageGenerationService(session=None, settings=settings)
    intent, warnings = service.fulfill_intent_image_request(
        _intent(),
        project_id=uuid4(),
        slide_title="概念缘起",
    )
    assert intent.hero_asset_id is None
    assert warnings == []


def test_fulfill_skips_when_hero_already_set(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        vision_image_generation_enabled=True,
        vision_auto_fulfill_image_requests=True,
    )
    service = VisionImageGenerationService(session=None, settings=settings)
    hero = uuid4()
    intent, warnings = service.fulfill_intent_image_request(
        _intent(hero_asset_id=hero),
        project_id=uuid4(),
    )
    assert intent.hero_asset_id == hero
    assert warnings == []


def test_fulfill_writes_hero_asset_when_enabled(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        vision_image_generation_enabled=True,
        vision_auto_fulfill_image_requests=True,
        vision_image_generation_provider="stub",
    )
    asset_id = uuid4()
    service = VisionImageGenerationService(session=None, settings=settings)
    service.generate_for_intent = MagicMock(  # type: ignore[method-assign]
        return_value=VisionGenerationResult(
            success=True,
            spec=GenerationSpec(
                image_type=ArchitectureImageType.CONCEPT_SKETCH,
                style="marker_sketch",
                prompt="compiled",
                asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
                width=1280,
                height=720,
            ),
            asset_id=asset_id,
            storage_path="assets/vision_generated/demo.png",
        )
    )

    intent, warnings = service.fulfill_intent_image_request(
        _intent(),
        project_id=uuid4(),
        slide_title="概念缘起",
        slide_message="窑洞再生",
        persist=False,
    )

    assert intent.hero_asset_id == asset_id
    assert warnings == []
    service.generate_for_intent.assert_called_once()


def test_fulfill_passes_direction_seed_to_compiler(tmp_path) -> None:
    from archium.domain.concept_direction import ConceptDirection
    from archium.domain.concept_visual_prompt import ConceptVisualPrompt

    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        vision_image_generation_enabled=True,
        vision_auto_fulfill_image_requests=True,
    )
    direction = ConceptDirection(
        project_id=uuid4(),
        mission_id=uuid4(),
        title="台地聚落",
        visual_prompt=ConceptVisualPrompt(
            image_prompt="terraced cultural center",
            camera="architectural axonometric",
            style="concept sketch",
        ),
    )
    service = VisionImageGenerationService(session=None, settings=settings)
    captured: dict[str, object] = {}

    def _fake_generate_for_intent(**kwargs):
        captured.update(kwargs)
        return VisionGenerationResult(
            success=True,
            spec=GenerationSpec(
                image_type=ArchitectureImageType.CONCEPT_SKETCH,
                style="marker_sketch",
                prompt="compiled with seed",
                asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
                width=1280,
                height=720,
                metadata={"direction_seed": True},
            ),
            asset_id=uuid4(),
        )

    service.generate_for_intent = _fake_generate_for_intent  # type: ignore[method-assign]

    intent, warnings = service.fulfill_intent_image_request(
        _intent(),
        project_id=uuid4(),
        direction=direction,
        persist=False,
    )

    assert intent.hero_asset_id is not None
    assert warnings == []
    assert captured.get("direction") is direction


def test_fulfill_records_warning_on_failure(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        vision_image_generation_enabled=True,
        vision_auto_fulfill_image_requests=True,
    )
    service = VisionImageGenerationService(session=None, settings=settings)
    service.generate_for_intent = MagicMock(  # type: ignore[method-assign]
        return_value=VisionGenerationResult(
            success=False,
            spec=GenerationSpec(
                image_type=ArchitectureImageType.CONCEPT_SKETCH,
                style="soft_atmosphere",
                prompt="compiled",
                asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
                width=1280,
                height=720,
            ),
            error="backend unavailable",
        )
    )

    intent, warnings = service.fulfill_intent_image_request(
        _intent(),
        project_id=uuid4(),
        persist=False,
    )

    assert intent.hero_asset_id is None
    assert any("backend unavailable" in item for item in warnings)
