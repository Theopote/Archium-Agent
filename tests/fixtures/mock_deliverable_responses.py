"""Mock LLM JSON responses for deliverable planning tests."""

TEMPLE_DELIVERABLE_PLAN_JSON = """{
  "deliverables": [
    {
      "id": "del-mission",
      "title": "项目任务理解",
      "deliverable_type": "task_brief",
      "purpose": "固化本次重建任务边界与未知项",
      "audience": "项目组",
      "content_scope": ["任务陈述", "范围", "未知项"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "2-3页",
      "decision_served": "确认任务边界"
    },
    {
      "id": "del-questions",
      "title": "待确认问题清单",
      "deliverable_type": "question_list",
      "purpose": "跟踪未决问题与假设",
      "audience": "甲方",
      "content_scope": ["关键问题", "建议假设"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "1页",
      "decision_served": "推动甲方补资料"
    },
    {
      "id": "del-case-study",
      "title": "案例研究",
      "deliverable_type": "case_study",
      "purpose": "比较同类重建策略",
      "audience": "甲方/设计团队",
      "content_scope": ["案例比较", "策略启示"],
      "source_workstream_indices": [1],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "4-6页",
      "decision_served": "支撑重建策略选择"
    },
    {
      "id": "del-strategy",
      "title": "重建策略比较",
      "deliverable_type": "memo",
      "purpose": "比较历史复原/传统语汇/当代路径",
      "audience": "甲方",
      "content_scope": ["策略框架", "优缺点"],
      "source_workstream_indices": [2],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "3页",
      "decision_served": "确定重建立场"
    },
    {
      "id": "del-concept-ppt",
      "title": "概念设计汇报",
      "deliverable_type": "presentation",
      "purpose": "向甲方汇报重建策略与概念方向",
      "audience": "甲方",
      "content_scope": ["现状", "策略", "概念"],
      "source_workstream_indices": [2, 3],
      "recommendation": "required",
      "format": "pptx",
      "expected_length": "12-16页",
      "decision_served": "确认概念方向"
    },
    {
      "id": "del-cd",
      "title": "施工图设计包",
      "deliverable_type": "other",
      "purpose": "不在本轮范围",
      "audience": "无",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "not_recommended",
      "format": "markdown",
      "notes": "用户明确 out of scope",
      "decision_served": "无"
    }
  ],
  "planning_notes": "本轮以策划与概念汇报为主，不进入施工图"
}"""

GREEN_CAMPUS_DELIVERABLE_PLAN_JSON = """{
  "deliverables": [
    {
      "id": "del-goals",
      "title": "绿色低碳目标体系",
      "deliverable_type": "report",
      "purpose": "建立专项目标与评价框架",
      "audience": "园区管理方",
      "content_scope": ["目标分层", "指标"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "6-8页",
      "decision_served": "确认专项目标"
    },
    {
      "id": "del-tech",
      "title": "技术筛选建议",
      "deliverable_type": "technical_proposal",
      "purpose": "筛选可落地低碳技术",
      "audience": "技术负责人",
      "content_scope": ["技术清单", "适用性"],
      "source_workstream_indices": [1],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "8页",
      "decision_served": "选定技术路线"
    },
    {
      "id": "del-roadmap",
      "title": "实施路线图",
      "deliverable_type": "implementation_roadmap",
      "purpose": "提出分期实施建议",
      "audience": "园区管理方",
      "content_scope": ["分期", "优先级"],
      "source_workstream_indices": [2],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "4页",
      "decision_served": "确认实施节奏"
    },
    {
      "id": "del-scheme-ppt",
      "title": "完整建筑设计方案汇报",
      "deliverable_type": "presentation",
      "purpose": "不建议作为本轮主成果",
      "audience": "无",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "not_recommended",
      "format": "pptx",
      "notes": "本任务是专项咨询，不是完整建筑设计",
      "decision_served": "无"
    }
  ],
  "planning_notes": "交付专项建议报告，而非默认 20 页方案 PPT"
}"""
