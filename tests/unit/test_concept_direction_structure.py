"""Unit tests for structured ConceptDirection fields."""

from __future__ import annotations

from uuid import uuid4

from archium.application.concept_direction_mapping import concept_direction_from_draft
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionDraft,
    ConceptVisualPromptDraft,
)


def test_concept_direction_from_draft_maps_structured_fields() -> None:
    draft = ConceptDirectionDraft(
        title="台地聚落",
        summary="沿台地展开",
        theme="台地生活",
        spatial_idea="分散院落",
        spatial_strategy="线性台地轴线 + 共享庭院系统",
        formal_language="低平舒展体量，连续屋面",
        material_strategy="本地夯土与木构混合",
        reference_dna=["黄土高原窑洞类型", "村落聚落尺度"],
        reference_case_ids=["case:terrace_settlement", "ningbo_museum"],
        visual_prompt=ConceptVisualPromptDraft(
            image_prompt="mountain cultural center on terraced plateau",
            camera="architectural axonometric",
            style="concept sketch",
        ),
        experience_focus="日常与访客穿行",
        differentiator="台地地貌组织公共性",
    )
    direction = concept_direction_from_draft(draft, project_id=uuid4())
    assert direction.spatial_strategy.startswith("线性台地")
    assert direction.formal_language
    assert len(direction.reference_dna) == 2
    assert direction.reference_case_ids == ["terrace_settlement", "ningbo_museum"]
    assert direction.visual_prompt is not None
    assert direction.visual_prompt.camera == "architectural axonometric"
    block = direction.to_prompt_block()
    assert "空间策略" in block
    assert "形式语言" in block
    assert "参照案例ID" in block
    assert "视觉生成参数" in block


def test_enrich_direction_case_refs_when_empty() -> None:
    from archium.application.concept_direction_case_refs import enrich_direction_case_refs
    from archium.application.architecture_case_library import ArchitectureCaseLibraryService

    direction = concept_direction_from_draft(
        ConceptDirectionDraft(
            title="山地台地文化中心",
            summary="回应山地公共空间缺失",
            theme="台地公共",
            spatial_strategy="台地聚落",
            formal_language="低平体量",
            material_strategy="夯土",
            reference_dna=["台地", "山地"],
            risks=["造价"],
        ),
        project_id=uuid4(),
    )
    assert direction.reference_case_ids == []
    enriched = enrich_direction_case_refs(direction, library=ArchitectureCaseLibraryService())
    assert enriched.reference_case_ids
    resolved = ArchitectureCaseLibraryService().resolve_ids(enriched.reference_case_ids)
    assert resolved
    assert len(resolved) == len(enriched.reference_case_ids)


def test_concept_visual_prompt_empty_is_ignored() -> None:
    draft = ConceptDirectionDraft(
        title="轻量驿站",
        summary="线性廊道",
        visual_prompt=ConceptVisualPromptDraft(),
    )
    direction = concept_direction_from_draft(draft, project_id=uuid4())
    assert direction.visual_prompt is None


def test_concept_visual_prompt_model() -> None:
    vp = ConceptVisualPrompt(
        image_prompt="temple courtyard in mist",
        camera="eye-level",
        style="watercolor note",
    )
    assert not vp.is_empty()
    assert "temple courtyard" in vp.to_prompt_block()
