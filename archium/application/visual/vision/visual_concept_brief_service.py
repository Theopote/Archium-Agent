"""Vision Engine — synthesize VisualConceptBrief for a ConceptDirection (optional pixels)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.vision.image_generation_service import (
    VisionImageGenerationService,
)
from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler
from archium.application.visual.vision.visual_concept_brief_intent import (
    image_request_from_visual_concept_brief,
)
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationContext,
    VisionStylePreset,
)
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    VisualConceptBriefRepository,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.visual_concept_brief_schemas import VisualConceptBriefDraft
from archium.prompts.visual_concept_brief import (
    VISUAL_CONCEPT_BRIEF_SYSTEM_PROMPT,
    build_visual_concept_brief_user_prompt,
)

_ALLOWED_IMAGE_TYPES = {
    ArchitectureImageType.CONCEPT_SKETCH,
    ArchitectureImageType.ATMOSPHERE_IMAGE,
    ArchitectureImageType.SITE_DIAGRAM,
    ArchitectureImageType.SKETCH_NOTE,
}
_ALLOWED_STYLES = {item.value for item in VisionStylePreset}


@dataclass
class VisualConceptBriefResult:
    brief: VisualConceptBrief
    image_attempted: bool = False
    image_succeeded: bool = False
    warnings: list[str] = field(default_factory=list)


class VisualConceptBriefService:
    """Visual-seat service: text brief from ConceptDirection + optional illustrative image."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        compiler: VisionPromptCompiler | None = None,
        image_service: VisionImageGenerationService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._directions = ConceptDirectionRepository(session)
        self._briefs = VisualConceptBriefRepository(session)
        self._compiler = compiler or VisionPromptCompiler()
        self._images = image_service or VisionImageGenerationService(
            session, settings=self._settings, compiler=self._compiler
        )

    def list_for_direction(self, concept_direction_id: UUID) -> list[VisualConceptBrief]:
        return self._briefs.list_by_direction(concept_direction_id)

    def get_latest_for_direction(
        self, concept_direction_id: UUID
    ) -> VisualConceptBrief | None:
        return self._briefs.get_latest_for_direction(concept_direction_id)

    def synthesize_for_direction(
        self,
        concept_direction_id: UUID,
        *,
        generate_image: bool = False,
    ) -> VisualConceptBriefResult:
        direction = self._directions.get(concept_direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {concept_direction_id} 不存在")
        if direction.mission_id is None:
            raise WorkflowError(
                "该方向尚未绑定 Mission；请先在概念探索页选定方向并生成项目任务"
            )
        mission = self._missions.get_mission(direction.mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {direction.mission_id} not found")

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=VISUAL_CONCEPT_BRIEF_SYSTEM_PROMPT,
                user_prompt=build_visual_concept_brief_user_prompt(
                    mission_title=mission.title,
                    task_statement=mission.task_statement,
                    direction_title=direction.title,
                    direction_summary=direction.summary,
                    theme=direction.theme,
                    spatial_idea=direction.spatial_idea,
                    experience_focus=direction.experience_focus,
                    differentiator=direction.differentiator,
                    spatial_strategy=direction.spatial_strategy,
                    formal_language=direction.formal_language,
                    material_strategy=direction.material_strategy,
                    reference_dna="；".join(direction.reference_dna),
                    visual_prompt_block=(
                        direction.visual_prompt.to_prompt_block()
                        if direction.visual_prompt is not None
                        else ""
                    ),
                ),
                temperature=0.45,
                json_mode=True,
            ),
            VisualConceptBriefDraft,
        )
        brief = self._persist_brief(mission, direction, draft)
        warnings: list[str] = []

        request = self._to_image_request(brief)
        context = self._to_context(mission, direction)
        spec = self._compiler.compile(request, context=context)
        brief.mark_ready(compiled_prompt=spec.prompt)
        brief.extra_json = {
            **brief.extra_json,
            "negative_prompt": spec.negative_prompt,
            "prompt_hash": spec.prompt_hash,
            "style_resolved": spec.style,
        }
        brief = self._briefs.update(brief)

        image_attempted = False
        image_succeeded = False
        if generate_image:
            if not self._settings.vision_image_generation_enabled:
                warnings.append("未开启 vision_image_generation_enabled；仅保存文字视觉简报。")
            else:
                image_attempted = True
                result = self._images.generate(
                    request,
                    context=context,
                    project_id=mission.project_id,
                    persist_asset=True,
                )
                if result.success:
                    image_succeeded = True
                    brief.mark_imaged(
                        asset_id=result.asset_id,
                        image_path=result.storage_path,
                    )
                    brief.compiled_prompt = result.spec.prompt or brief.compiled_prompt
                    brief = self._briefs.update(brief)
                else:
                    brief.mark_failed(result.error or "image generation failed")
                    brief = self._briefs.update(brief)
                    warnings.append(result.error or "示意出图失败，已保留文字简报。")

        self._session.commit()
        return VisualConceptBriefResult(
            brief=brief,
            image_attempted=image_attempted,
            image_succeeded=image_succeeded,
            warnings=warnings,
        )

    def _persist_brief(
        self,
        mission: ProjectMission,
        direction: ConceptDirection,
        draft: VisualConceptBriefDraft,
    ) -> VisualConceptBrief:
        image_type = self._coerce_image_type(draft.image_type)
        style = self._coerce_style(draft.style_preset)
        brief = VisualConceptBrief(
            project_id=mission.project_id,
            mission_id=mission.id,
            concept_direction_id=direction.id,
            title=(draft.title or direction.title).strip()[:200],
            composition_intent=(draft.composition_intent or "").strip(),
            atmosphere=(draft.atmosphere or "").strip(),
            diagram_intent=(draft.diagram_intent or "").strip(),
            image_type=image_type,
            style_preset=style,
            subject=(draft.subject or direction.title).strip()[:500],
            elements=[item.strip() for item in draft.elements if item.strip()][:12],
            avoid=[item.strip() for item in draft.avoid if item.strip()][:12],
            status="draft",
        )
        return self._briefs.create(brief)

    @staticmethod
    def _to_image_request(brief: VisualConceptBrief) -> ImageRequest:
        return image_request_from_visual_concept_brief(brief)

    def _to_context(
        self,
        mission: ProjectMission,
        direction: ConceptDirection,
    ) -> VisionGenerationContext:
        summary = direction.summary or mission.task_statement
        return VisionGenerationContext(
            project_type="",
            project_phase="concept",
            audience="",
            page_title=direction.title,
            page_message=summary[:240],
            page_archetype="concept",
            design_brief_summary=summary[:240],
            locale="zh-CN",
        )

    @staticmethod
    def _coerce_image_type(raw: str) -> ArchitectureImageType:
        try:
            value = ArchitectureImageType((raw or "").strip().lower())
        except ValueError:
            return ArchitectureImageType.CONCEPT_SKETCH
        if value not in _ALLOWED_IMAGE_TYPES:
            return ArchitectureImageType.CONCEPT_SKETCH
        return value

    @staticmethod
    def _coerce_style(raw: str) -> VisionStylePreset | str:
        key = (raw or "").strip().lower()
        if key in _ALLOWED_STYLES:
            return VisionStylePreset(key)
        return VisionStylePreset.SOFT_ATMOSPHERE
