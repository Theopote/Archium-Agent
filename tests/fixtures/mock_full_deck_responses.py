"""Deterministic 20-slide mock responses for full-deck golden cases."""

from __future__ import annotations

import json

FULL_DECK_SLIDE_COUNT = 20

_CHAPTERS: tuple[tuple[str, str, int], ...] = (
    ("ch1", "院区现状", 4),
    ("ch2", "问题诊断", 4),
    ("ch3", "改造策略", 6),
    ("ch4", "分期实施", 4),
    ("ch5", "总结决策", 2),
)


def _slide_type(chapter_index: int, slide_index: int, chapter_slide_count: int) -> str:
    if chapter_index == 0 and slide_index == 0:
        return "title"
    if chapter_index == len(_CHAPTERS) - 1 and slide_index == chapter_slide_count - 1:
        return "closing"
    if slide_index == 0:
        return "section"
    return "content"


def build_full_deck_brief() -> dict[str, object]:
    return {
        "title": "老院区更新完整汇报",
        "presentation_type": "client_review",
        "audience": "医院管理层与科室代表",
        "purpose": "确认总体改造方向、分期策略与关键决策项",
        "duration_minutes": 45,
        "target_slide_count": FULL_DECK_SLIDE_COUNT,
        "core_message": "通过交通重组、功能再分配与分期实施，系统性提升老院区运营品质",
        "decisions_required": [
            "确认改造范围与优先级",
            "确认分期实施策略",
            "确认急诊与运营保障方案",
        ],
        "audience_concerns": ["施工对日常运营影响", "投资与分期平衡"],
        "tone": "professional",
        "required_sections": [
            "院区现状",
            "问题诊断",
            "改造策略",
            "分期实施",
            "总结决策",
        ],
        "excluded_topics": [],
        "language": "zh-CN",
    }


def build_full_deck_storyline() -> dict[str, object]:
    chapters = []
    for order, (chapter_id, title, estimated_slide_count) in enumerate(_CHAPTERS):
        chapters.append(
            {
                "id": chapter_id,
                "title": title,
                "purpose": f"展开{title}相关内容",
                "key_message": f"{title}支撑总体改造方向",
                "order": order,
                "estimated_slide_count": estimated_slide_count,
            }
        )
    return {
        "thesis": "以交通重组与功能优化带动老院区系统性更新",
        "narrative_pattern": "problem_solution",
        "narrative_arc": {
            "opening_context": "老院区在持续运营中暴露交通与功能短板",
            "central_problem": "现状交通与功能布局难以支撑服务升级",
            "tension_building": ["流线冲突影响安全", "空间低效限制体验"],
            "turning_point": "需要以系统性更新而非局部修补回应矛盾",
            "proposed_resolution": "以交通重组与功能优化带动整体更新",
            "final_decision": "确认总体方向与实施优先级",
        },
        "chapters": chapters,
    }


def build_full_deck_slide_plan() -> dict[str, object]:
    slides: list[dict[str, object]] = []
    order = 0
    for chapter_index, (chapter_id, chapter_title, chapter_slide_count) in enumerate(_CHAPTERS):
        for slide_index in range(chapter_slide_count):
            slide_type = _slide_type(chapter_index, slide_index, chapter_slide_count)
            title = chapter_title if slide_index == 0 else f"{chapter_title}要点 {slide_index}"
            slides.append(
                {
                    "chapter_id": chapter_id,
                    "order": order,
                    "title": title,
                    "message": f"{chapter_title}需要纳入整体更新策略",
                    "slide_type": slide_type,
                    "layout_id": "default",
                    "key_points": [f"{chapter_title}关键信息 {slide_index + 1}"],
                    "visual_requirements": [],
                    "source_citations": [],
                    "speaker_notes": None,
                }
            )
            order += 1
    if len(slides) != FULL_DECK_SLIDE_COUNT:
        msg = f"expected {FULL_DECK_SLIDE_COUNT} slides, got {len(slides)}"
        raise ValueError(msg)
    return {"slides": slides}


def full_deck_brief_json() -> str:
    return json.dumps(build_full_deck_brief(), ensure_ascii=False)


def full_deck_storyline_json() -> str:
    return json.dumps(build_full_deck_storyline(), ensure_ascii=False)


def full_deck_slide_plan_json() -> str:
    return json.dumps(build_full_deck_slide_plan(), ensure_ascii=False)


FULL_DECK_BRIEF_JSON = full_deck_brief_json()
FULL_DECK_STORYLINE_JSON = full_deck_storyline_json()
FULL_DECK_SLIDE_PLAN_JSON = full_deck_slide_plan_json()
