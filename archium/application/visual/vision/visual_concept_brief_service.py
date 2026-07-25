"""Vision Engine — synthesize VisualConceptBrief for a ConceptDirection (optional pixels)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.vision.concept_direction_visual_seed import (
    apply_direction_seed_to_request,
    direction_has_visual_seed,
    visual_concept_brief_from_direction_seed,
)
from archium.application.visual.vision.image_generation_service import (
    VisionImageGenerationService,
)
from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler
from archium.application.visual.vision.visual_concept_brief_intent import (
    image_request_from_visual_concept_brief,
)
from archium.config.settings import Settings, get_settings
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
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
    ProjectRepository,
    VisualConceptBriefRepository,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.visual_concept_brief_schemas import (
    VisualConceptBriefDraft,
    VisualSeedRefineDraft,
)
from archium.prompts.visual_concept_brief import (
    VISUAL_CONCEPT_BRIEF_SYSTEM_PROMPT,
    VISUAL_SEED_REFINE_SYSTEM_PROMPT,
    build_visual_concept_brief_user_prompt,
    build_visual_seed_refine_user_prompt,
)

_ALLOWED_IMAGE_TYPES = {
    ArchitectureImageType.CONCEPT_SKETCH,
    ArchitectureImageType.ATMOSPHERE_IMAGE,
    ArchitectureImageType.SITE_DIAGRAM,
    ArchitectureImageType.SKETCH_NOTE,
    ArchitectureImageType.MATERIAL_STUDY,
    ArchitectureImageType.SECTION_ILLUSTRATION,
}
_ALLOWED_STYLES = {item.value for item in VisionStylePreset}


@dataclass
class VisualConceptBriefResult:
    brief: VisualConceptBrief
    image_attempted: bool = False
    image_succeeded: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ConceptVisualizationLoopResult:
    """P3 边想边画：反馈 → 修订方向种子 → 再合成简报/出图。"""

    direction: ConceptDirection
    brief_result: VisualConceptBriefResult
    change_summary: str = ""


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
        self._projects = ProjectRepository(session)
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
        preferred_image_type: ArchitectureImageType | None = None,
        slot_key: str | None = None,
        focus_hint: str | None = None,
        style_preset: VisionStylePreset | None = None,
    ) -> VisualConceptBriefResult:
        direction = self._directions.get(concept_direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {concept_direction_id} 不存在")

        mission = self._optional_mission(direction)
        project = self._projects.get_by_id(direction.project_id)
        project_name = project.name if project is not None else ""

        warnings: list[str] = []
        if direction_has_visual_seed(direction):
            brief = self._briefs.create(
                visual_concept_brief_from_direction_seed(
                    project_id=direction.project_id,
                    direction=direction,
                    mission_id=direction.mission_id,
                )
            )
            warnings.append(
                "已使用概念方向 visual_prompt 直出视觉简报，跳过 LLM 扩写。"
            )
            if direction.design_rationale is not None and not direction.design_rationale.is_empty():
                brief.extra_json = {
                    **brief.extra_json,
                    "design_rationale": direction.design_rationale.model_dump(mode="json"),
                }
                brief = self._briefs.update(brief)
        else:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=VISUAL_CONCEPT_BRIEF_SYSTEM_PROMPT,
                    user_prompt=build_visual_concept_brief_user_prompt(
                        mission_title=(
                            mission.title
                            if mission is not None
                            else (project_name or "概念探索")
                        ),
                        task_statement=(
                            mission.task_statement
                            if mission is not None
                            else (direction.summary or "概念方向示意探索")
                        ),
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
                        design_rationale_block=(
                            direction.design_rationale.to_prompt_block()
                            if direction.design_rationale is not None
                            else ""
                        ),
                    ),
                    temperature=0.45,
                    json_mode=True,
                ),
                VisualConceptBriefDraft,
            )
            brief = self._persist_brief(
                project_id=direction.project_id,
                mission_id=direction.mission_id,
                direction=direction,
                draft=draft,
            )

        brief = self._apply_slot_overrides(
            brief,
            preferred_image_type=preferred_image_type,
            slot_key=slot_key,
            focus_hint=focus_hint,
            style_preset=style_preset,
        )

        request = apply_direction_seed_to_request(self._to_image_request(brief), direction)
        context = self._to_context(direction, mission=mission)
        spec = self._compiler.compile(request, context=context, direction=direction)
        brief.mark_ready(compiled_prompt=spec.prompt)
        brief.extra_json = {
            **brief.extra_json,
            "negative_prompt": spec.negative_prompt,
            "prompt_hash": spec.prompt_hash,
            "style_resolved": spec.style,
            "direction_seed": spec.metadata.get("direction_seed", False),
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
                    project_id=direction.project_id,
                    persist_asset=True,
                    direction=direction,
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

    def latest_brief_for_slot(
        self,
        concept_direction_id: UUID,
        slot_key: str,
    ) -> VisualConceptBrief | None:
        """Prefer brief tagged with slot_key; else match by slot image_type."""
        from archium.application.visual.vision.visual_thinking_slots import slot_by_key

        slot = slot_by_key(slot_key)
        briefs = self._briefs.list_by_direction(concept_direction_id)
        for brief in briefs:
            if str(brief.extra_json.get("slot_key") or "") == slot_key:
                return brief
        if slot is not None:
            for brief in briefs:
                if brief.image_type == slot.image_type:
                    return brief
        return None

    def _apply_slot_overrides(
        self,
        brief: VisualConceptBrief,
        *,
        preferred_image_type: ArchitectureImageType | None,
        slot_key: str | None,
        focus_hint: str | None,
        style_preset: VisionStylePreset | None,
    ) -> VisualConceptBrief:
        changed = False
        extra = dict(brief.extra_json or {})
        if preferred_image_type is not None:
            coerced = self._coerce_image_type(preferred_image_type.value)
            if brief.image_type != coerced:
                brief.image_type = coerced
                changed = True
        if style_preset is not None:
            brief.style_preset = style_preset
            changed = True
        if slot_key:
            extra["slot_key"] = slot_key
            changed = True
        hint = (focus_hint or "").strip()
        if hint:
            extra["intent_binding"] = hint
            if not brief.subject.strip():
                brief.subject = hint[:500]
            elif hint not in brief.subject:
                brief.subject = f"{brief.subject.strip()}；{hint}"[:500]
            if slot_key == "atmosphere" and not brief.atmosphere.strip():
                brief.atmosphere = hint[:500]
            if slot_key == "space" and not brief.diagram_intent.strip():
                brief.diagram_intent = hint[:500]
            if slot_key == "massing" and not brief.composition_intent.strip():
                brief.composition_intent = hint[:500]
            changed = True
        if changed:
            brief.extra_json = extra
            return self._briefs.update(brief)
        return brief

    def refine_and_resynthesize(
        self,
        concept_direction_id: UUID,
        feedback: str,
        *,
        generate_image: bool = False,
    ) -> ConceptVisualizationLoopResult:
        """Architect review → revise ConceptDirection visual seed → re-synthesize brief."""
        text = (feedback or "").strip()
        if not text:
            raise WorkflowError("请填写对概念示意的反馈后再修订")

        direction = self._directions.get(concept_direction_id)
        if direction is None:
            raise WorkflowError(f"概念方向 {concept_direction_id} 不存在")

        latest = self._briefs.get_latest_for_direction(concept_direction_id)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=VISUAL_SEED_REFINE_SYSTEM_PROMPT,
                user_prompt=build_visual_seed_refine_user_prompt(
                    feedback=text,
                    direction_title=direction.title,
                    direction_summary=direction.summary,
                    spatial_strategy=direction.spatial_strategy,
                    formal_language=direction.formal_language,
                    material_strategy=direction.material_strategy,
                    experience_focus=direction.experience_focus,
                    visual_prompt_block=(
                        direction.visual_prompt.to_prompt_block()
                        if direction.visual_prompt is not None
                        else ""
                    ),
                    brief_title=latest.title if latest is not None else "",
                    composition_intent=(
                        latest.composition_intent if latest is not None else ""
                    ),
                    atmosphere=latest.atmosphere if latest is not None else "",
                ),
                temperature=0.4,
                json_mode=True,
            ),
            VisualSeedRefineDraft,
        )
        direction_before = direction
        previous_label = (
            direction_before.title
            or direction_before.theme
            or (direction_before.spatial_strategy or "")[:60]
            or ""
        ).strip() or None
        previous_prompt = ""
        if direction_before.visual_prompt is not None:
            previous_prompt = (direction_before.visual_prompt.image_prompt or "").strip()[:120]

        direction = self._apply_refine_draft(direction, draft)
        change_summary = (draft.change_summary or text[:120]).strip()
        new_label = (
            direction.title
            or direction.theme
            or (direction.spatial_strategy or "")[:60]
            or change_summary
            or ""
        ).strip() or None
        self._append_visual_feedback_evolution(
            direction.project_id,
            change_summary,
            direction=direction,
            feedback=text,
            previous_summary=previous_label,
            new_summary=new_label,
            reason=text.strip()[:200] or change_summary,
            evidence_refs=[
                bit
                for bit in (previous_prompt, change_summary)
                if bit and str(bit).strip()
            ],
        )
        brief_result = self.synthesize_for_direction(
            direction.id,
            generate_image=generate_image,
        )
        refreshed = self._directions.get(direction.id)
        assert refreshed is not None
        return ConceptVisualizationLoopResult(
            direction=refreshed,
            brief_result=brief_result,
            change_summary=change_summary,
        )

    def backfill_mission_id_for_direction(
        self,
        concept_direction_id: UUID,
        mission_id: UUID,
    ) -> int:
        """Attach mission_id to pre-mission briefs for one direction. Returns updated count."""
        updated = 0
        for brief in self._briefs.list_by_direction(concept_direction_id):
            if brief.mission_id is None:
                brief.mission_id = mission_id
                self._briefs.update(brief)
                updated += 1
        return updated

    def _apply_refine_draft(
        self,
        direction: ConceptDirection,
        draft: VisualSeedRefineDraft,
    ) -> ConceptDirection:
        current = direction.visual_prompt or ConceptVisualPrompt()
        direction.visual_prompt = ConceptVisualPrompt(
            image_prompt=(draft.image_prompt or current.image_prompt).strip(),
            camera=(draft.camera or current.camera).strip(),
            style=(draft.style or current.style).strip(),
        )
        if draft.spatial_strategy.strip():
            direction.spatial_strategy = draft.spatial_strategy.strip()
        if draft.formal_language.strip():
            direction.formal_language = draft.formal_language.strip()
        if draft.material_strategy.strip():
            direction.material_strategy = draft.material_strategy.strip()
        if draft.experience_focus.strip():
            direction.experience_focus = draft.experience_focus.strip()
        direction.touch()
        return self._directions.update(direction)

    def _append_visual_feedback_evolution(
        self,
        project_id: UUID,
        summary: str,
        *,
        direction: ConceptDirection,
        feedback: str,
        previous_summary: str | None = None,
        new_summary: str | None = None,
        reason: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> None:
        project = self._projects.get_by_id(project_id)
        if project is None:
            return
        snapshot: dict[str, object] = {
            "feedback": feedback[:800],
            "direction_id": str(direction.id),
            "direction_title": direction.title,
        }
        if direction.visual_prompt is not None:
            snapshot["visual_prompt"] = direction.visual_prompt.model_dump(mode="json")
        evo = project.intent_evolution or IntentEvolution()
        project.intent_evolution = evo.append(
            IntentEvolutionKind.VISUAL_FEEDBACK,
            summary[:500],
            design_intent_snapshot=snapshot,
            trigger="示意反馈",
            previous_summary=previous_summary,
            new_summary=new_summary,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        self._projects.update(project)

    def _optional_mission(self, direction: ConceptDirection) -> ProjectMission | None:
        if direction.mission_id is None:
            return None
        mission = self._missions.get_mission(direction.mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {direction.mission_id} not found")
        return mission

    def _persist_brief(
        self,
        *,
        project_id: UUID,
        mission_id: UUID | None,
        direction: ConceptDirection,
        draft: VisualConceptBriefDraft,
    ) -> VisualConceptBrief:
        image_type = self._coerce_image_type(draft.image_type)
        style = self._coerce_style(draft.style_preset)
        composition_intent = (draft.composition_intent or "").strip()
        if (
            not composition_intent
            and direction.design_rationale is not None
            and direction.design_rationale.statement.strip()
        ):
            composition_intent = direction.design_rationale.statement.strip()[:500]
        extra_json: dict[str, object] = {}
        if direction.design_rationale is not None and not direction.design_rationale.is_empty():
            extra_json["design_rationale"] = direction.design_rationale.model_dump(mode="json")
        brief = VisualConceptBrief(
            project_id=project_id,
            mission_id=mission_id,
            concept_direction_id=direction.id,
            title=(draft.title or direction.title).strip()[:200],
            composition_intent=composition_intent,
            atmosphere=(draft.atmosphere or "").strip(),
            diagram_intent=(draft.diagram_intent or "").strip(),
            image_type=image_type,
            style_preset=style,
            subject=(draft.subject or direction.title).strip()[:500],
            elements=[item.strip() for item in draft.elements if item.strip()][:12],
            avoid=[item.strip() for item in draft.avoid if item.strip()][:12],
            status="draft",
            extra_json=extra_json,
        )
        return self._briefs.create(brief)

    @staticmethod
    def _to_image_request(brief: VisualConceptBrief) -> ImageRequest:
        return image_request_from_visual_concept_brief(brief)

    def _to_context(
        self,
        direction: ConceptDirection,
        *,
        mission: ProjectMission | None,
    ) -> VisionGenerationContext:
        summary = direction.summary or (
            mission.task_statement if mission is not None else direction.title
        )
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
