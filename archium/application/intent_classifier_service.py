"""Classify freeform entry text into a primary project orientation."""

from __future__ import annotations

from archium.config.settings import Settings, get_settings
from archium.domain.intent.entry_intent import EntryIntentResult, EntryOrientation
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.entry_intent_schemas import EntryIntentDraft
from archium.prompts.entry_intent import (
    ENTRY_INTENT_SYSTEM_PROMPT,
    build_entry_intent_user_prompt,
)

_VALID = {item.value for item in EntryOrientation}
DEFAULT_CONFIDENCE_THRESHOLD = 0.55


class IntentClassifierService:
    """Deprecated entry router — superseded by ContextIntelligenceService / ProjectContext.

    Kept for unit tests and backward-compatible API only; UI must not call this.
    """

    def __init__(
        self,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._llm = llm
        self._settings = settings or get_settings()
        self._threshold = confidence_threshold

    def classify(self, user_text: str) -> EntryIntentResult:
        text = user_text.strip()
        if not text:
            raise WorkflowError("请先描述你的项目情况")

        try:
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=ENTRY_INTENT_SYSTEM_PROMPT,
                    user_prompt=build_entry_intent_user_prompt(user_text=text),
                    temperature=0.2,
                    json_mode=True,
                ),
                EntryIntentDraft,
            )
        except Exception as exc:  # noqa: BLE001 — degrade to manual choice
            return EntryIntentResult.uncertain(
                text,
                rationale=f"自动判断失败，请手动选择主路径。（{exc}）",
            )

        orientation_raw = (draft.orientation or "").strip().lower()
        if orientation_raw not in _VALID:
            return EntryIntentResult.uncertain(
                text,
                rationale=f"模型返回未知取向「{draft.orientation}」，请手动选择。",
            )

        confidence = float(draft.confidence)
        confidence = max(0.0, min(1.0, confidence))
        result = EntryIntentResult(
            orientation=EntryOrientation(orientation_raw),
            confidence=confidence,
            rationale=(draft.rationale or "").strip(),
            suggested_next=(draft.suggested_next or "").strip(),
            raw_input=text,
        )
        return result.with_confirmation_flag(threshold=self._threshold)
