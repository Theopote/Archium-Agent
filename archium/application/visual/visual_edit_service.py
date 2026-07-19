"""Apply Studio natural-language visual edit intents with revision support."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.application.visual.visual_intent_presets import (
    apply_hero_asset,
    apply_layout_family_preference,
    apply_visual_intent_preset,
    remove_primary_asset,
)
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.visual.edit_intent import (
    VisualEditIntent,
    intent_from_preset,
    parse_natural_language,
)
from archium.domain.visual.enums import LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.factory import create_llm_provider


@dataclass(frozen=True)
class VisualEditResult:
    slide_id: UUID
    intent: VisualEditIntent | None
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None
    validation: object | None
    restored: bool = False
    message: str = ""


class VisualEditService:
    """Parse and apply the eight supported slide visual edit intents."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._use_llm = use_llm and self._settings.llm_configured
        self._presentations = PresentationRepository(session)
        self._intents = VisualIntentRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._design_repo = DesignSystemRepository(session)
        self._history = VisualHistoryService(session)

    def apply_text(
        self,
        slide_id: UUID,
        text: str,
        *,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        intent, params = parse_natural_language(text)
        if intent is None:
            raise WorkflowError("无法识别修改意图。请使用预设按钮或更明确的描述。")
        return self.apply_intent(
            slide_id,
            intent,
            params=params,
            candidate_count=candidate_count,
        )

    def apply_intent(
        self,
        slide_id: UUID,
        intent: VisualEditIntent | str,
        *,
        params: dict[str, object] | None = None,
        candidate_count: int = 3,
    ) -> VisualEditResult:
        resolved = intent_from_preset(str(intent)) if not isinstance(intent, VisualEditIntent) else intent
        if resolved is None:
            raise WorkflowError(f"Unsupported visual edit intent: {intent}")
        if resolved == VisualEditIntent.RESTORE_PREVIOUS:
            return self.restore_previous(slide_id)

        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        self._history.record_state(
            slide=slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
            change_source=RevisionSource.MANUAL_EDIT,
            note=resolved.value,
        )

        if resolved in {VisualEditIntent.LOCK_ELEMENT, VisualEditIntent.UNLOCK_ELEMENT}:
            locked = resolved == VisualEditIntent.LOCK_ELEMENT
            return self._apply_element_lock_state(
                slide,
                current_intent,
                current_plan,
                params or {},
                locked=locked,
                edit_intent=resolved,
            )

        if resolved in {
            VisualEditIntent.UPDATE_ELEMENT_TEXT,
            VisualEditIntent.SET_ELEMENT_ASSET,
        }:
            return self._apply_element_direct_edit(
                slide,
                current_intent,
                current_plan,
                resolved,
                params or {},
            )

        updated_intent = self._mutate_intent(current_intent, slide, resolved, params or {})
        replanned = self._replan(
            slide,
            updated_intent,
            candidate_count=candidate_count,
            edit_intent=resolved,
        )
        self._invalidate_preview_cache(slide.presentation_id, replanned.layout_plan)
        return replanned

    def restore_previous(self, slide_id: UUID) -> VisualEditResult:
        slide = self._require_slide(slide_id)
        current_intent = self._load_intent(slide)
        current_plan = self._load_plan(slide)
        revision = self._history.latest_restorable_revision(
            slide,
            visual_intent=current_intent,
            layout_plan=current_plan,
        )
        if revision is None:
            raise WorkflowError("没有可恢复的视觉修订。")

        intent, plan = self._history.restore_revision(
            revision,
            intents=self._intents,
            plans=self._plans,
            presentations=self._presentations,
        )
        validation = None
        design = self._resolve_design_system(slide, intent)
        if plan is not None and design is not None:
            validation = LayoutValidationService().validate(
                plan,
                design,
                require_source=True,
                drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        if plan is not None:
            self._invalidate_preview_cache(slide.presentation_id, plan)
        return VisualEditResult(
            slide_id=slide.id,
            intent=VisualEditIntent.RESTORE_PREVIOUS,
            visual_intent=intent,
            layout_plan=plan,
            validation=validation,
            restored=True,
            message="已恢复到上一版视觉状态。",
        )

    def _apply_element_direct_edit(
        self,
        slide: object,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        edit_intent: VisualEditIntent,
        params: dict[str, object],
    ) -> VisualEditResult:
        if plan is None:
            raise WorkflowError("当前页面尚无版式，无法直接编辑元素。")
        element_id = str(params.get("element_id") or "")
        if not element_id:
            raise WorkflowError("请指定要编辑的元素。")

        updated_elements = []
        changed = False
        for element in plan.elements:
            if element.id != element_id:
                updated_elements.append(element)
                continue
            if edit_intent == VisualEditIntent.UPDATE_ELEMENT_TEXT:
                text = str(params.get("text") or "")
                if not text.strip():
                    raise WorkflowError("文字内容不能为空。")
                updated_elements.append(element.model_copy(update={"text_content": text}))
            elif edit_intent == VisualEditIntent.SET_ELEMENT_ASSET:
                content_ref = str(params.get("content_ref") or params.get("asset_id") or "")
                if not content_ref.strip():
                    raise WorkflowError("请指定素材引用。")
                updated_elements.append(element.model_copy(update={"content_ref": content_ref}))
            changed = True
        if not changed:
            raise WorkflowError(f"未找到元素：{element_id}")

        updated_plan = plan.model_copy(
            update={
                "elements": updated_elements,
                "version": plan.version + 1,
            }
        )
        updated_plan.touch()
        saved_plan = self._plans.save(updated_plan)
        slide.layout_plan_id = saved_plan.id  # type: ignore[attr-defined]
        self._presentations.save_slide(slide)  # type: ignore[arg-type]
        self._invalidate_preview_cache(slide.presentation_id, saved_plan)  # type: ignore[attr-defined]

        design = self._resolve_design_system(slide, visual_intent)  # type: ignore[arg-type]
        validation = None
        if design is not None:
            validation = LayoutValidationService().validate(
                saved_plan,
                design,
                require_source=True,
                drawing_hero=saved_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        message = (
            "已更新元素文字。"
            if edit_intent == VisualEditIntent.UPDATE_ELEMENT_TEXT
            else "已更新元素素材。"
        )
        return VisualEditResult(
            slide_id=slide.id,  # type: ignore[attr-defined]
            intent=edit_intent,
            visual_intent=visual_intent,
            layout_plan=saved_plan,
            validation=validation,
            message=message,
        )

    def _apply_element_lock_state(
        self,
        slide: object,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        params: dict[str, object],
        *,
        locked: bool,
        edit_intent: VisualEditIntent,
    ) -> VisualEditResult:
        if plan is None:
            action = "锁定" if locked else "解锁"
            raise WorkflowError(f"当前页面尚无版式，无法{action}元素。")
        element_id = str(params.get("element_id") or plan.hero_element_id or "")
        if not element_id:
            hero = next(
                (
                    element
                    for element in plan.elements
                    if element.role == LayoutElementRole.HERO_VISUAL
                ),
                None,
            )
            element_id = hero.id if hero is not None else plan.elements[0].id

        updated_elements = []
        changed = False
        for element in plan.elements:
            if element.id == element_id:
                updated_elements.append(element.model_copy(update={"locked": locked}))
                changed = True
            else:
                updated_elements.append(element)
        if not changed:
            action = "锁定" if locked else "解锁"
            raise WorkflowError(f"未找到可{action}的元素：{element_id}")

        updated_plan = plan.model_copy(
            update={
                "elements": updated_elements,
                "version": plan.version + 1,
            }
        )
        updated_plan.touch()
        saved_plan = self._plans.save(updated_plan)
        slide.layout_plan_id = saved_plan.id  # type: ignore[attr-defined]
        self._presentations.save_slide(slide)  # type: ignore[arg-type]
        self._invalidate_preview_cache(slide.presentation_id, saved_plan)  # type: ignore[attr-defined]

        design = self._resolve_design_system(slide, visual_intent)  # type: ignore[arg-type]
        validation = None
        if design is not None:
            validation = LayoutValidationService().validate(
                saved_plan,
                design,
                require_source=True,
                drawing_hero=saved_plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        verb = "锁定" if locked else "解锁"
        return VisualEditResult(
            slide_id=slide.id,  # type: ignore[attr-defined]
            intent=edit_intent,
            visual_intent=visual_intent,
            layout_plan=saved_plan,
            validation=validation,
            message=f"已{verb}元素 `{element_id}`。",
        )

    def _apply_lock_element(
        self,
        slide: object,
        visual_intent: VisualIntent | None,
        plan: LayoutPlan | None,
        params: dict[str, object],
    ) -> VisualEditResult:
        return self._apply_element_lock_state(
            slide,
            visual_intent,
            plan,
            params,
            locked=True,
            edit_intent=VisualEditIntent.LOCK_ELEMENT,
        )

    def _mutate_intent(
        self,
        intent: VisualIntent,
        slide: object,
        edit_intent: VisualEditIntent,
        params: dict[str, object],
    ) -> VisualIntent:
        if edit_intent == VisualEditIntent.ENLARGE_HERO:
            return apply_visual_intent_preset(intent, "enlarge_hero")
        if edit_intent == VisualEditIntent.REDUCE_TEXT:
            return apply_visual_intent_preset(intent, "reduce_text")
        if edit_intent == VisualEditIntent.INCREASE_WHITESPACE:
            return apply_visual_intent_preset(intent, "more_whitespace")
        if edit_intent == VisualEditIntent.CHANGE_LAYOUT:
            family = params.get("layout_family")
            if isinstance(family, LayoutFamily):
                if not get_layout_family_registry().get(family).implemented:
                    raise WorkflowError(f"版式族「{family.value}」尚未实现，无法切换。")
                return apply_layout_family_preference(intent, family)
            return apply_visual_intent_preset(intent, "drawing_focus")
        if edit_intent == VisualEditIntent.SET_HERO_ASSET:
            asset_id = params.get("asset_id")
            if asset_id is None:
                asset_id = self._default_hero_asset_id(slide)  # type: ignore[arg-type]
            if asset_id is None:
                raise WorkflowError("请指定主图素材，或先在页面内容中绑定素材。")
            return apply_hero_asset(intent, UUID(str(asset_id)))
        if edit_intent == VisualEditIntent.REMOVE_ASSET:
            return remove_primary_asset(intent)
        return intent

    def _replan(
        self,
        slide: object,
        intent: VisualIntent,
        *,
        candidate_count: int,
        edit_intent: VisualEditIntent,
    ) -> VisualEditResult:
        intent = self._intents.save(intent)
        slide.visual_intent_id = intent.id  # type: ignore[attr-defined]
        self._presentations.save_slide(slide)  # type: ignore[arg-type]

        art, design = self._resolve_art_and_design(slide, intent)  # type: ignore[arg-type]
        llm = create_llm_provider(self._settings) if self._use_llm else None
        planner = LayoutPlanningService(self._session, llm=llm)
        current_plan = self._load_plan(slide)
        candidates = planner.generate_candidates(
            slide=slide,  # type: ignore[arg-type]
            visual_intent_id=intent.id,
            art_direction_id=art.id if art else None,
            design_system_id=design.id,
            candidate_count=candidate_count,
            previous_layout_plan=current_plan,
        )
        saved_candidates: list[LayoutPlan] = []
        for plan, _report in candidates:
            saved_candidates.append(self._plans.save(plan))
        best = planner.select_best(candidates, previous_layout_plan=current_plan)
        best = self._plans.save(best)
        slide.layout_plan_id = best.id  # type: ignore[attr-defined]
        self._presentations.save_slide(slide)  # type: ignore[arg-type]

        validation = LayoutValidationService().validate(
            best,
            design,
            require_source=True,
            drawing_hero=best.layout_family == LayoutFamily.DRAWING_FOCUS,
        )
        return VisualEditResult(
            slide_id=slide.id,  # type: ignore[attr-defined]
            intent=edit_intent,
            visual_intent=intent,
            layout_plan=best,
            validation=validation,
            message="已应用修改并重新生成版式。",
        )

    def _require_slide(self, slide_id: UUID):
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"页面 {slide_id} 不存在")
        return slide

    def _load_intent(self, slide) -> VisualIntent:
        intent = None
        if slide.visual_intent_id is not None:
            intent = self._intents.get(slide.visual_intent_id)
        if intent is None:
            intent = self._intents.get_by_slide(slide.id)
        if intent is None:
            llm = create_llm_provider(self._settings) if self._use_llm else None
            intent = VisualIntentService(self._session, llm=llm).generate_for_slide(
                slide,
                use_llm=self._use_llm,
            )
            slide.visual_intent_id = intent.id
            self._presentations.save_slide(slide)
        return intent

    def _load_plan(self, slide) -> LayoutPlan | None:
        if slide.layout_plan_id is None:
            listed = self._plans.list_by_slide(slide.id)
            return listed[0] if listed else None
        return self._plans.get(slide.layout_plan_id)

    def _resolve_art_and_design(self, slide, intent: VisualIntent):
        presentation = self._presentations.get_presentation(slide.presentation_id)
        art = None
        design = None
        if intent.art_direction_id is not None:
            art = ArtDirectionRepository(self._session).get(intent.art_direction_id)
            if art is not None and art.design_system_id is not None:
                design = self._design_repo.get(art.design_system_id)
        if design is None and presentation is not None:
            arts = ArtDirectionRepository(self._session).list_by_project(presentation.project_id)
            for item in arts:
                if item.presentation_id == slide.presentation_id and item.design_system_id:
                    design = self._design_repo.get(item.design_system_id)
                    art = item
                    break
            if design is None and arts and arts[0].design_system_id:
                design = self._design_repo.get(arts[0].design_system_id)
                art = arts[0]
        if design is None:
            from archium.domain.visual.defaults import default_presentation_design_system

            design = self._design_repo.save(default_presentation_design_system())
        return art, design

    def _resolve_design_system(self, slide, intent: VisualIntent | None):
        _, design = self._resolve_art_and_design(slide, intent or self._load_intent(slide))
        return design

    @staticmethod
    def _default_hero_asset_id(slide) -> UUID | None:
        for requirement in slide.visual_requirements:
            asset_id = requirement.primary_asset_id
            if asset_id is not None:
                return asset_id
        return None

    def _invalidate_preview_cache(self, presentation_id: UUID, plan: LayoutPlan | None) -> None:
        if plan is None:
            return
        cache_path = (
            self._settings.output_path / "studio-previews" / str(presentation_id) / f"{plan.id}.png"
        )
        if cache_path.is_file():
            cache_path.unlink()
