"""Art direction generation and approval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import ApprovalStatus
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.preferences import VisualPreferences
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
)
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.visual_schemas import ArtDirectionDraft
from archium.prompts.art_direction import (
    ART_DIRECTION_SYSTEM_PROMPT,
    build_art_direction_user_prompt,
)


class ArtDirectionService:
    """Generate / regenerate / approve ArtDirection (LLM optional, rule fallback)."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._art_directions = ArtDirectionRepository(session)
        self._design_systems = DesignSystemRepository(session)

    def generate(
        self,
        *,
        project_id: UUID,
        mission_id: UUID | None = None,
        deliverable_id: str | None = None,
        presentation_id: UUID | None = None,
        design_system_id: UUID | None = None,
        user_preferences: VisualPreferences | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        use_llm: bool = True,
    ) -> ArtDirection:
        design_system_id = self._ensure_design_system(design_system_id)
        preferences = user_preferences or VisualPreferences()

        draft: ArtDirectionDraft | None = None
        if use_llm and self._llm is not None:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=ART_DIRECTION_SYSTEM_PROMPT,
                    user_prompt=build_art_direction_user_prompt(
                        brief=brief,
                        storyline=storyline,
                        preferences=preferences,
                        deliverable_id=deliverable_id,
                        mission_id=str(mission_id) if mission_id else None,
                    ),
                    temperature=0.4,
                ),
                ArtDirectionDraft,
            )

        if draft is None:
            draft = self._rule_based_draft(brief=brief, preferences=preferences)

        art = ArtDirection(
            project_id=project_id,
            deliverable_id=deliverable_id,
            presentation_id=presentation_id,
            concept_name=draft.concept_name,
            rationale=draft.rationale,
            visual_tone=list(draft.visual_tone),
            emotional_keywords=list(draft.emotional_keywords),
            palette_strategy=draft.palette_strategy,
            typography_strategy=draft.typography_strategy,
            grid_strategy=draft.grid_strategy,
            image_strategy=draft.image_strategy,
            drawing_strategy=draft.drawing_strategy,
            diagram_strategy=draft.diagram_strategy,
            annotation_strategy=draft.annotation_strategy,
            cover_strategy=draft.cover_strategy,
            section_strategy=draft.section_strategy,
            content_strategy=draft.content_strategy,
            closing_strategy=draft.closing_strategy,
            pacing_strategy=draft.pacing_strategy,
            consistency_rules=list(draft.consistency_rules),
            forbidden_styles=list(draft.forbidden_styles),
            design_system_id=design_system_id,
            approval_status=ApprovalStatus.PENDING,
        )
        return self._art_directions.save(art)

    def regenerate(self, art_direction_id: UUID, feedback: str) -> ArtDirection:
        existing = self._art_directions.get(art_direction_id)
        if existing is None:
            raise ValueError(f"ArtDirection {art_direction_id} not found")

        draft: ArtDirectionDraft | None = None
        if self._llm is not None:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=ART_DIRECTION_SYSTEM_PROMPT,
                    user_prompt=(
                        f"请根据用户反馈重新生成 ArtDirection。\n"
                        f"【现有方向】\n{existing.model_dump_json()}\n\n"
                        f"【用户反馈】\n{feedback}"
                    ),
                    temperature=0.4,
                ),
                ArtDirectionDraft,
            )
        if draft is None:
            existing.rationale = f"{existing.rationale}\n反馈调整：{feedback.strip()}"
            existing.version += 1
            existing.approval_status = ApprovalStatus.PENDING
            existing.touch()
            return self._art_directions.save(existing)

        updated = existing.model_copy(
            update={
                **draft.model_dump(),
                "version": existing.version + 1,
                "approval_status": ApprovalStatus.PENDING,
            }
        )
        updated.touch()
        return self._art_directions.save(updated)

    def approve(self, art_direction_id: UUID) -> ArtDirection:
        art = self._art_directions.get(art_direction_id)
        if art is None:
            raise ValueError(f"ArtDirection {art_direction_id} not found")
        art.approve()
        return self._art_directions.save(art)

    def _ensure_design_system(self, design_system_id: UUID | None) -> UUID:
        if design_system_id is not None:
            existing = self._design_systems.get(design_system_id)
            if existing is not None:
                return existing.id
        builtin = default_presentation_design_system()
        saved = self._design_systems.save(builtin)
        return saved.id

    @staticmethod
    def _rule_based_draft(
        *,
        brief: PresentationBrief | None,
        preferences: VisualPreferences,
    ) -> ArtDirectionDraft:
        tone = (brief.tone if brief else "professional").strip() or "professional"
        audience = brief.audience if brief else "项目相关方"
        purpose = brief.purpose if brief else "建筑汇报"
        return ArtDirectionDraft(
            concept_name="清晰层级，克制表达",
            rationale=(
                f"面向{audience}的{purpose}，以信息层级和图纸可读性为先，"
                f"语气倾向「{tone}」，密度偏好 {preferences.density.value}。"
            ),
            visual_tone=["克制", "专业", "清晰"],
            emotional_keywords=["可信", "有序"],
            palette_strategy="暖白背景、炭灰正文、低饱和强调色；避免高饱和装饰色。",
            typography_strategy="中文优先可读无体，标题与正文严格分层，图注与来源独立字号。",
            grid_strategy="默认 12 栏网格；图纸页切换 drawing_canvas。",
            image_strategy="现场照片统一色温，允许适度 cover crop；禁止装饰性滤镜堆砌。",
            drawing_strategy="技术图纸默认 contain，禁止拉伸与主体裁切，保留标注清晰度。",
            diagram_strategy="分析图强调关系与路径，避免图标堆砌。",
            annotation_strategy="编号标注与证据照片一一对应，图注短句化。",
            cover_strategy="封面以项目主题与单张主视觉建立第一印象，文字克制。",
            section_strategy="章节页留白充足，标题短、副文更短。",
            content_strategy="内容页按信息任务选择版式族，不套固定项目模板。",
            closing_strategy="收束页突出结论与下一步，避免新信息堆叠。",
            pacing_strategy="开篇建立语境 → 证据/图纸展开 → 比较或策略 → 收束。",
            consistency_rules=[
                "整套共用同一 DesignSystem token",
                "图纸与照片使用不同 fit/crop 策略",
                "来源与图注始终可见",
            ],
            forbidden_styles=[
                "仿古花纹边框",
                "金色渐变",
                "旅游宣传册式装饰",
                "过度科技蓝黑背景",
                "把所有页面做成满版大图或卡片墙",
            ],
        )

