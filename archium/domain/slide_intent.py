"""Per-page slide intent — independent user input before SlideSpec generation.

Users can set page_count (via outline/brief) and page-level instructions
(``SlideIntent``) so each page has an explicit task card, not only section titles.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from archium.domain._base import DomainModel
from archium.domain.visual.visual_grammar import PageArchetype, coerce_page_archetype


class SlideIntent(DomainModel):
    """Compact intent card for one planned page (Slide Intent Card)."""

    order: int = Field(ge=0)
    chapter_id: str = Field(default="", max_length=100)
    # 页面任务
    page_task: str = Field(min_length=1, max_length=500)
    # 中心结论（生成时应优先成为 SlideSpec.message）
    central_conclusion: str = Field(default="", max_length=1000)
    # 必须使用的证据
    required_evidence: list[str] = Field(default_factory=list)
    # 指定素材（文件名、asset id 或描述）
    required_assets: list[str] = Field(default_factory=list)
    # 禁止内容
    forbidden_content: list[str] = Field(default_factory=list)
    # 期望版式（如 photo_evidence_grid / drawing_focus）
    expected_layout: str = Field(default="", max_length=200)
    # Visual Grammar archetype (VG-002); optional until recognition / user sets it.
    page_archetype: PageArchetype | None = None
    # 备注 / 自由说明（对应外部 API 的 page_instructions 条目）
    notes: str = Field(default="", max_length=2000)

    @field_validator("page_archetype", mode="before")
    @classmethod
    def _coerce_page_archetype(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return coerce_page_archetype(value) or value

    def effective_page_intent(self) -> str:
        """Single-line intent used when a compact string is required."""
        if self.central_conclusion.strip():
            return self.central_conclusion.strip()
        return self.page_task.strip()


def format_slide_intent_card(intent: SlideIntent) -> str:
    """Human/LLM-readable block for prompts."""
    lines = [
        "【页面意图卡】",
        f"页序：{intent.order}",
        f"页面任务：{intent.page_task}",
    ]
    if intent.central_conclusion.strip():
        lines.append(f"中心结论：{intent.central_conclusion.strip()}")
    if intent.required_evidence:
        lines.append("必须使用的证据：")
        for item in intent.required_evidence:
            lines.append(f"- {item}")
    if intent.required_assets:
        lines.append("指定素材：")
        for item in intent.required_assets:
            lines.append(f"- {item}")
    if intent.forbidden_content:
        lines.append("禁止内容：")
        for item in intent.forbidden_content:
            lines.append(f"- {item}")
    if intent.expected_layout.strip():
        lines.append(f"期望版式：{intent.expected_layout.strip()}")
    if intent.page_archetype is not None:
        lines.append(f"视觉语法原型：{intent.page_archetype.value}")
    if intent.notes.strip():
        lines.append(f"备注：{intent.notes.strip()}")
    return "\n".join(lines)


def index_slide_intents(intents: list[SlideIntent]) -> dict[int, SlideIntent]:
    return {intent.order: intent for intent in intents}


def slide_intents_from_page_instructions(
    instructions: list[str],
    *,
    start_order: int = 0,
) -> list[SlideIntent]:
    """Map PresentationRequest.page_instructions (index = page order) to intent cards.

    Empty / whitespace-only entries are skipped so sparse lists still work.
    Free-form text becomes both ``page_task`` and ``notes`` until the user
    refines the card in outline review.
    """
    intents: list[SlideIntent] = []
    for offset, raw in enumerate(instructions):
        text = raw.strip()
        if not text:
            continue
        intents.append(
            SlideIntent(
                order=start_order + offset,
                page_task=text[:500],
                notes=text[:2000],
            )
        )
    return intents
