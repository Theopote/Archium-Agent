"""Mock LLM JSON responses for workstream planning tests."""

TEMPLE_WORKSTREAM_PLAN_JSON = """{
  "workstreams": [
    {
      "title": "历史研究",
      "workstream_type": "historical_research",
      "objective": "梳理清凉寺历史沿革与形制依据",
      "questions": ["哪些历史信息可核验？"],
      "inputs_required": ["地方志", "现场照片"],
      "activities": ["文献梳理", "形制可信度评估"],
      "outputs": ["历史沿革摘要", "可信度评估"],
      "dependency_indices": [],
      "blocking_gap_indices": [1],
      "priority": "high",
      "effort_level": "high",
      "recommended": true,
      "reason": "重建任务依赖历史依据"
    },
    {
      "title": "案例分析",
      "workstream_type": "case_study",
      "objective": "比较同类宗教建筑重建策略",
      "questions": ["当代重建如何处理历史表达？"],
      "inputs_required": ["历史研究输出"],
      "activities": ["案例筛选", "策略比较"],
      "outputs": ["案例比较表"],
      "dependency_indices": [0],
      "blocking_gap_indices": [],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "服务重建策略比较"
    },
    {
      "title": "重建策略比较",
      "workstream_type": "design_strategy",
      "objective": "比较历史复原、传统语汇新建与当代表达",
      "questions": ["何种策略最可接受？"],
      "inputs_required": ["历史研究", "案例分析"],
      "activities": ["策略框架", "优缺点比较"],
      "outputs": ["策略比较结论"],
      "dependency_indices": [0, 1],
      "blocking_gap_indices": [],
      "priority": "critical",
      "effort_level": "medium",
      "recommended": true,
      "reason": "直接服务甲方决策"
    },
    {
      "title": "汇报制作",
      "workstream_type": "presentation",
      "objective": "形成概念设计汇报",
      "questions": [],
      "inputs_required": ["策略比较结论"],
      "activities": ["Brief", "Storyline", "SlideSpec"],
      "outputs": ["概念汇报"],
      "dependency_indices": [2],
      "blocking_gap_indices": [],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "用户明确要求概念汇报"
    }
  ],
  "planning_notes": "未推荐施工图或完整建筑设计工作流"
}"""

GREEN_CAMPUS_WORKSTREAM_PLAN_JSON = """{
  "workstreams": [
    {
      "title": "目标体系梳理",
      "workstream_type": "technical_study",
      "objective": "建立园区绿色低碳目标与评价框架",
      "questions": ["优先减碳路径是什么？"],
      "inputs_required": ["园区现状资料"],
      "activities": ["目标分层", "指标筛选"],
      "outputs": ["目标体系"],
      "dependency_indices": [],
      "blocking_gap_indices": [],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "专项咨询核心工作"
    },
    {
      "title": "技术筛选",
      "workstream_type": "sustainability",
      "objective": "筛选适用的低碳技术措施",
      "questions": ["哪些技术可落地？"],
      "inputs_required": ["目标体系"],
      "activities": ["技术清单", "适用性评估"],
      "outputs": ["技术筛选表"],
      "dependency_indices": [0],
      "blocking_gap_indices": [],
      "priority": "high",
      "effort_level": "high",
      "recommended": true,
      "reason": "服务专项建议报告"
    },
    {
      "title": "实施路线",
      "workstream_type": "implementation",
      "objective": "提出分阶段实施建议",
      "questions": [],
      "inputs_required": ["技术筛选表"],
      "activities": ["分期建议"],
      "outputs": ["实施路线图"],
      "dependency_indices": [1],
      "blocking_gap_indices": [],
      "priority": "medium",
      "effort_level": "medium",
      "recommended": true,
      "reason": "形成可执行建议"
    }
  ],
  "planning_notes": "不包含施工图、设备选型与正式碳认证"
}"""

CYCLIC_WORKSTREAM_PLAN_JSON = """{
  "workstreams": [
    {
      "title": "A",
      "workstream_type": "other",
      "objective": "A",
      "dependency_indices": [1],
      "priority": "medium",
      "effort_level": "low",
      "recommended": true
    },
    {
      "title": "B",
      "workstream_type": "other",
      "objective": "B",
      "dependency_indices": [0],
      "priority": "medium",
      "effort_level": "low",
      "recommended": true
    }
  ],
  "planning_notes": "故意构造依赖环"
}"""
