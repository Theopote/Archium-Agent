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
      "reviewer_layer": "architectural",
      "slide_order": 1,
      "category": "consistency",
      "severity": "medium",
      "title": "论点与页面信息不一致",
      "description": "第 2 页核心信息与 Storyline 章节重点不完全一致。",
      "suggestion": "对齐章节 key_message 与 slide message。"
    }
  ]
}"""

LAYER_REVIEW_JSON = """\
{
  "issues": [
    {
      "reviewer_layer": "content",
      "slide_order": 0,
      "category": "content",
      "severity": "medium",
      "title": "结论表述不够聚焦",
      "description": "第 1 页核心结论可进一步提炼为单一决策点。",
      "suggestion": "压缩为一句可决策表述。"
    },
    {
      "reviewer_layer": "evidence",
      "slide_order": 1,
      "category": "citation",
      "severity": "high",
      "title": "缺少资料引用",
      "description": "第 2 页论断未关联项目资料片段。",
      "suggestion": "补充 chunk 引用。"
    },
    {
      "reviewer_layer": "layout",
      "slide_order": 0,
      "category": "length",
      "severity": "suggestion",
      "title": "要点略多",
      "description": "第 1 页要点超过建议数量。",
      "suggestion": "合并相近要点。"
    }
  ]
}"""

BRIEF_ALIGNMENT_MISMATCH_JSON = """\
{
  "aligned": false,
  "confidence": 0.88,
  "gap_summary": "Slide 结论聚焦交通问题，但未回应 Brief 中公共空间提升与分期决策诉求。",
  "suggestion": "增加一页总结公共空间策略，并在末页明确分期决策选项。"
}"""

BRIEF_ALIGNMENT_OK_JSON = """\
{
  "aligned": true,
  "confidence": 0.92,
  "gap_summary": "",
  "suggestion": null
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

SLIDE_SPLIT_JSON = """\
{
  "narrative_reason": "问题成因与改造策略属于不同叙事块，应分两页呈现",
  "source": {
    "title": "交通组织 — 问题与原因",
    "message": "人车混行与落客不足是当前主要交通矛盾。",
    "key_points": [
      "现状：人车混行 35%",
      "原因：落客区不足",
      "原因：货运与就医流线冲突",
      "策略一：分离人车动线",
      "策略二：增设落客缓冲"
    ],
    "citation_indices": [0],
    "visual_indices": []
  },
  "continuation": {
    "title": "交通组织 — 补充策略",
    "message": "通过分时货运优化剩余流线冲突。",
    "key_points": ["策略三：优化货运时段"],
    "citation_indices": [],
    "visual_indices": [0]
  }
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
