"""Tests for ConceptDirection visual_prompt → Vision Engine seed path."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision.concept_direction_visual_seed import (
    apply_direction_seed_to_request,
    direction_has_visual_seed,
    image_request_from_concept_direction,
    resolve_image_type_from_camera,
    resolve_style_from_visual_prompt,
    visual_concept_brief_from_direction_seed,
)
from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionStylePreset,
)


def _seeded_direction() -> ConceptDirection:
    return ConceptDirection(
        project_id=uuid4(),
        mission_id=uuid4(),
        title="台地聚落",
        summary="沿台地展开",
        spatial_strategy="台地层级 + 院落聚落",
        formal_language="低平体量，连续屋面",
        material_strategy="夯土与木构",
        reference_dna=["窑洞类型学"],
        visual_prompt=ConceptVisualPrompt(
            image_prompt="terraced cultural center on loess plateau",
            camera="architectural axonometric",
            style="concept sketch",
        ),
        differentiator="台地组织公共性",
    )


def test_direction_has_visual_seed() -> None:
    assert direction_has_visual_seed(_seeded_direction()) is True
    bare = _seeded_direction()
    bare.visual_prompt = None
    assert direction_has_visual_seed(bare) is False


def test_resolve_style_and_image_type() -> None:
    assert (
        resolve_style_from_visual_prompt("concept sketch")
        == VisionStylePreset.COMPETITION_CONCEPT_SKETCH
    )
    assert (
        resolve_image_type_from_camera("architectural axonometric")
        == ArchitectureImageType.SITE_DIAGRAM
    )


def test_compiler_injects_primary_scene_seed() -> None:
    direction = _seeded_direction()
    request = image_request_from_concept_direction(direction)
    spec = VisionPromptCompiler().compile(request, direction=direction)
    assert "Primary scene seed: terraced cultural center" in spec.prompt
    assert spec.metadata.get("direction_seed") is True
    assert any("direction_seed" in item for item in spec.rationale)


def test_apply_direction_seed_overrides_subject() -> None:
    direction = _seeded_direction()
    base = ImageRequest(subject="fallback title")
    enriched = apply_direction_seed_to_request(base, direction)
    assert "terraced cultural center" in enriched.subject
    assert enriched.image_type == ArchitectureImageType.SITE_DIAGRAM


def test_generate_compile_accepts_direction(tmp_path) -> None:
    from archium.application.visual.vision import VisionImageGenerationService
    from archium.config.settings import Settings

    direction = _seeded_direction()
    request = ImageRequest(subject="fallback")
    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    service = VisionImageGenerationService(session=None, settings=settings)
    spec = service.compile(request, direction=direction)
    assert spec.metadata.get("direction_seed") is True
    assert "Primary scene seed" in spec.prompt


def test_preview_compiled_prompt_for_direction() -> None:
    direction = _seeded_direction()
    from archium.application.visual.vision.concept_direction_visual_seed import (
        preview_compiled_prompt_for_direction,
    )

    prompt = preview_compiled_prompt_for_direction(direction)
    assert "Primary scene seed" in prompt
    assert "terraced cultural center" in prompt


def test_visual_brief_from_direction_seed() -> None:
    direction = _seeded_direction()
    mission = ProjectMission(
        project_id=direction.project_id,
        title="文化中心",
        task_statement="探索概念",
    )
    brief = visual_concept_brief_from_direction_seed(mission, direction)
    assert brief.subject == direction.visual_prompt.image_prompt
    assert brief.extra_json["seed_source"] == "concept_direction.visual_prompt"
