"""Deterministic mock LLM responses for presentation pipeline tests."""

from __future__ import annotations

BRIEF_JSON = """\
{
  "title": "老院区更新概念汇报",
  "presentation_type": "client_review",
  "audience": "医院管理层",
  "purpose": "确认总体改造方向",
  "duration_minutes": 20,
  "target_slide_count": 4,
  "core_message": "通过交通重组与公共空间提升改善老院区体验",
  "decisions_required": ["确认改造范围", "确认分期策略"],
  "audience_concerns": ["施工对运营影响"],
  "tone": "professional",
  "required_sections": ["现状分析", "改造策略"],
  "excluded_topics": [],
  "language": "zh-CN"
}"""

STORYLINE_JSON = """\
{
  "thesis": "交通重组带动老院区整体品质提升",
  "narrative_pattern": "problem_solution",
  "chapters": [
    {
      "id": "ch1",
      "title": "现状与问题",
      "purpose": "建立改造必要性",
      "key_message": "现有交通组织无法满足日常运营",
      "order": 0,
      "estimated_slide_count": 2
    },
    {
      "id": "ch2",
      "title": "改造策略",
      "purpose": "提出总体方向",
      "key_message": "交通重组带动公共空间提升",
      "order": 1,
      "estimated_slide_count": 2
    }
  ]
}"""

PROFESSIONAL_REVIEW_JSON = """\
{
  "issues": [
    {
      "slide_order": 1,
      "category": "consistency",
      "severity": "medium",
      "title": "论点与页面信息不一致",
      "description": "第 2 页核心信息与 Storyline 章节重点不完全一致。",
      "suggestion": "对齐章节 key_message 与 slide message。"
    }
  ]
}"""

FACT_EXTRACTION_JSON = """\
{
  "facts": [
    {
      "key": "site_area",
      "label": "用地面积",
      "value": "12.5 公顷",
      "unit": "公顷",
      "category": "site",
      "confidence": 0.9,
      "chunk_id": null,
      "quote": "项目用地面积约 12.5 公顷"
    },
    {
      "key": "bed_count",
      "label": "床位数",
      "value": "500",
      "unit": "张",
      "category": "program",
      "confidence": 0.85,
      "chunk_id": null,
      "quote": "规划床位 500 张"
    }
  ]
}"""

SLIDE_REPAIR_JSON = """\
{
  "title": "交通现状",
  "message": "现有交通组织无法满足医院日常运营需求。",
  "key_points": ["人车混行", "高峰期通行效率低"]
}"""

SLIDE_PLAN_JSON = """\
{
  "slides": [
    {
      "chapter_id": "ch1",
      "order": 0,
      "title": "院区现状",
      "message": "现有交通组织无法满足医院日常运营需求",
      "slide_type": "content",
      "layout_id": "default",
      "key_points": ["人车混行", "停车不足"],
      "visual_requirements": [{"type": "site_plan", "description": "总平面图标注交通流线", "required": true}],
      "source_citations": [{"document_name": "任务书.pdf", "page_number": 1, "quote": "交通组织混乱", "confidence": 0.9}],
      "speaker_notes": "强调痛点"
    },
    {
      "chapter_id": "ch1",
      "order": 1,
      "title": "核心问题",
      "message": "人车混行导致高峰期通行效率低",
      "slide_type": "content",
      "layout_id": "default",
      "key_points": ["高峰期拥堵", "安全隐患"],
      "visual_requirements": [],
      "source_citations": [],
      "speaker_notes": null
    },
    {
      "chapter_id": "ch2",
      "order": 2,
      "title": "改造策略",
      "message": "通过交通重组释放公共空间潜力",
      "slide_type": "content",
      "layout_id": "default",
      "key_points": ["人车分流", "增设落客区"],
      "visual_requirements": [{"type": "diagram", "description": "交通重组示意", "required": true}],
      "source_citations": [],
      "speaker_notes": null
    },
    {
      "chapter_id": "ch2",
      "order": 3,
      "title": "下一步",
      "message": "建议确认改造范围与分期策略",
      "slide_type": "summary",
      "layout_id": "default",
      "key_points": ["确认范围", "确认分期"],
      "visual_requirements": [],
      "source_citations": [],
      "speaker_notes": "推动决策"
    }
  ]
}"""
