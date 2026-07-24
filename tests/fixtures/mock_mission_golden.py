"""Deterministic Mock LLM payloads for mission golden cases M1–M6."""

from __future__ import annotations

from archium.infrastructure.llm import LLMRequest

# ── M1 清凉寺（reuse existing temple fixtures via imports in selector） ──
from tests.fixtures.mock_deliverable_responses import (
    GREEN_CAMPUS_DELIVERABLE_PLAN_JSON,
    TEMPLE_DELIVERABLE_PLAN_JSON,
)
from tests.fixtures.mock_mission_responses import (
    FIRE_STATION_MISSION_JSON,
    TEMPLE_MISSION_JSON,
)
from tests.fixtures.mock_workstream_responses import (
    GREEN_CAMPUS_WORKSTREAM_PLAN_JSON,
    TEMPLE_WORKSTREAM_PLAN_JSON,
)

M2_LIBRARY_MISSION_JSON = """{
  "title": "大学图书馆改造策划",
  "task_statement": "在不停业条件下推进大学图书馆功能、空间与运营改造，并形成改造汇报与分期路线图",
  "task_natures": ["renovation", "adaptive_reuse", "planning"],
  "domains": ["education", "culture"],
  "intervention_scales": ["building", "space"],
  "requested_service_depths": ["project_diagnosis", "programming", "presentation_production"],
  "project_context": "既有图书馆需改造，教学科研不能中断",
  "current_situation": "功能老化、空间利用率低、运营压力大，需分期改造",
  "primary_problems": ["功能与空间错配", "不停业施工约束", "运营与分期冲突"],
  "desired_changes": ["优化功能布局", "提升空间体验", "形成可执行分期"],
  "in_scope": ["用户需求调研", "现状诊断", "案例研究", "改造汇报", "分期路线图"],
  "out_of_scope": ["施工图设计", "家具采购招标"],
  "stakeholders": [
    {"name": "图书馆馆长", "role": "业主代表", "concerns": ["不停业", "阅览体验"]},
    {"name": "师生用户", "role": "使用者", "concerns": ["座位", "噪音", "开放时间"]}
  ],
  "decision_context": "需确认改造重点与分期策略",
  "decisions_required": ["改造优先级", "分期实施路径"],
  "known_constraints": [
    {"name": "运营约束", "value": "改造期间需维持基本开放", "source": "user", "verification_status": "user_confirmed", "importance": "high"}
  ],
  "key_unknowns": ["高峰使用时段分布", "可关闭区域范围", "预算上限"],
  "research_questions": ["同类高校图书馆如何分期不停业改造？"],
  "design_question_summaries": ["如何在不停业约束下平衡功能、空间与运营？"],
  "evaluation_criteria": [{"name": "不停业可行性", "description": "分期方案需保证基本服务连续", "weight": 0.4}],
  "uncertainty_level": "medium",
  "confidence": 0.55,
  "knowledge_gaps": [
    {"category": "operation", "question": "改造期间哪些区域必须保持开放？", "why_it_matters": "决定分期切分", "priority": "high", "blocking": false},
    {"category": "program", "question": "师生最优先改善的功能是什么？", "why_it_matters": "影响改造重点", "priority": "high", "blocking": false}
  ],
  "assumptions": [],
  "clarifying_questions": [
    {"question": "改造期间是否必须不停业并保持部分开放的阅览与借还服务？", "why_asked": "决定不停业策略", "blocking": false, "can_assume": true, "suggested_assumption": "必须维持基本开放"},
    {"question": "功能上更优先改善座位供给、数字学习空间还是藏书布局？", "why_asked": "确定功能重点", "blocking": false, "can_assume": true, "suggested_assumption": "座位与学习空间优先"}
  ],
  "design_questions": [
    {"question": "如何在不停业约束下组织功能、空间与分期？", "related_problem": "运营与施工冲突", "desired_outcome": "可执行的分期改造框架"}
  ]
}"""

M2_LIBRARY_WORKSTREAM_JSON = """{
  "workstreams": [
    {
      "title": "用户需求与现状诊断",
      "workstream_type": "user_research",
      "objective": "梳理师生需求与现状空间问题",
      "questions": ["高峰时段痛点是什么？"],
      "inputs_required": ["使用数据", "现场踏勘"],
      "activities": ["访谈", "空间诊断"],
      "outputs": ["需求与诊断摘要"],
      "dependency_indices": [],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "改造必须基于真实使用"
    },
    {
      "title": "案例研究",
      "workstream_type": "case_study",
      "objective": "比较不停业分期改造案例",
      "questions": ["哪些分期策略有效？"],
      "inputs_required": ["诊断摘要"],
      "activities": ["案例筛选", "策略提取"],
      "outputs": ["案例启示"],
      "dependency_indices": [0],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "服务分期决策"
    },
    {
      "title": "功能空间与分期策略",
      "workstream_type": "programming",
      "objective": "提出功能、空间、运营与分期方案",
      "questions": ["如何分区关闭？"],
      "inputs_required": ["需求诊断", "案例启示"],
      "activities": ["功能重组", "分期切分"],
      "outputs": ["分期策略"],
      "dependency_indices": [0, 1],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "形成改造主线"
    },
    {
      "title": "改造汇报制作",
      "workstream_type": "presentation",
      "objective": "输出改造汇报",
      "inputs_required": ["分期策略"],
      "activities": ["汇报组织"],
      "outputs": ["改造汇报"],
      "dependency_indices": [2],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "用户明确要求汇报"
    }
  ],
  "planning_notes": "围绕功能、空间、运营、分期，不做固定图书馆模板"
}"""

M2_LIBRARY_DELIVERABLE_JSON = """{
  "deliverables": [
    {
      "id": "del-diag",
      "title": "现状与需求诊断",
      "deliverable_type": "report",
      "purpose": "固化诊断结论",
      "audience": "馆方",
      "content_scope": ["需求", "现状问题"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "6页"
    },
    {
      "id": "del-roadmap",
      "title": "分期改造路线图",
      "deliverable_type": "implementation_roadmap",
      "purpose": "明确不停业分期路径",
      "audience": "馆方/校方",
      "content_scope": ["分期", "开放策略"],
      "source_workstream_indices": [2],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "4页"
    },
    {
      "id": "del-reno-ppt",
      "title": "图书馆改造汇报",
      "deliverable_type": "presentation",
      "purpose": "汇报改造方向与分期",
      "audience": "校方决策层",
      "content_scope": ["诊断", "策略", "分期"],
      "source_workstream_indices": [2, 3],
      "recommendation": "required",
      "format": "pptx",
      "expected_length": "12-16页"
    }
  ],
  "planning_notes": "推荐改造汇报与分期路线图"
}"""

M3_HOSPITAL_ENV_MISSION_JSON = """{
  "title": "医院环境体验提升策略",
  "task_statement": "针对既有医院环境与患者体验问题，形成诊断与策略建议，而非新建医院方案",
  "task_natures": ["assessment", "strategy", "consulting"],
  "domains": ["healthcare"],
  "intervention_scales": ["building", "space"],
  "requested_service_depths": ["project_diagnosis", "decision_support", "presentation_production"],
  "project_context": "既有医院希望提升环境体验，不是新建院区",
  "current_situation": "候诊拥挤、流线混乱、导视不清，需快速措施与中长期措施",
  "primary_problems": ["患者旅程体验差", "流线交叉", "导视不足"],
  "desired_changes": ["改善候诊体验", "理顺流线", "明确导视层级"],
  "in_scope": ["患者旅程分析", "环境诊断", "快速措施", "中长期策略", "决策汇报"],
  "out_of_scope": ["新建医院方案", "施工图设计", "医疗工艺专项设计"],
  "stakeholders": [
    {"name": "医院管理层", "role": "决策方", "concerns": ["患者满意度", "可实施性"]},
    {"name": "患者与家属", "role": "使用者", "concerns": ["等候", "找路", "舒适度"]}
  ],
  "decision_context": "需确认优先改造点与措施分层",
  "decisions_required": ["快速措施清单", "中长期策略方向"],
  "known_constraints": [
    {"name": "建设边界", "value": "不新建医院，聚焦既有环境提升", "source": "user", "verification_status": "user_confirmed", "importance": "high"}
  ],
  "key_unknowns": ["高峰候诊时长", "可调整空间范围"],
  "research_questions": ["患者旅程中哪些节点最影响体验？"],
  "design_question_summaries": ["如何在不大拆大建前提下改善患者旅程？"],
  "evaluation_criteria": [{"name": "体验改善可感知性", "description": "措施应对应旅程痛点", "weight": 0.4}],
  "uncertainty_level": "medium",
  "confidence": 0.6,
  "knowledge_gaps": [
    {"category": "operation", "question": "各科室高峰候诊时段如何分布？", "why_it_matters": "影响快速措施优先级", "priority": "medium", "blocking": false}
  ],
  "assumptions": [],
  "clarifying_questions": [
    {"question": "本轮是否排除新建院区或改扩建主体工程？", "why_asked": "避免误判为新建医院", "blocking": false, "can_assume": true, "suggested_assumption": "排除新建，聚焦环境提升"},
    {"question": "更优先处理候诊、导视还是就医流线？", "why_asked": "确定策略重点", "blocking": false, "can_assume": true, "suggested_assumption": "候诊与导视优先"}
  ],
  "design_questions": [
    {"question": "如何用快速与中长期措施改善患者旅程？", "related_problem": "体验痛点分散", "desired_outcome": "分层措施包"}
  ]
}"""

M3_HOSPITAL_ENV_WORKSTREAM_JSON = """{
  "workstreams": [
    {
      "title": "患者旅程分析",
      "workstream_type": "user_research",
      "objective": "描绘患者从进入到离开的体验节点",
      "questions": ["最长痛点在哪里？"],
      "inputs_required": ["现场观察", "访谈"],
      "activities": ["旅程图", "痛点标注"],
      "outputs": ["患者旅程图"],
      "dependency_indices": [],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "环境提升必须以患者旅程为锚"
    },
    {
      "title": "环境与流线诊断",
      "workstream_type": "site_analysis",
      "objective": "诊断候诊、流线与导视问题",
      "inputs_required": ["患者旅程图"],
      "activities": ["流线核查", "导视评估"],
      "outputs": ["诊断清单"],
      "dependency_indices": [0],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "支撑措施分层"
    },
    {
      "title": "快速与中长期策略",
      "workstream_type": "design_strategy",
      "objective": "提出快速措施与中长期措施",
      "inputs_required": ["诊断清单"],
      "activities": ["措施分层", "优先级排序"],
      "outputs": ["策略包"],
      "dependency_indices": [1],
      "priority": "critical",
      "effort_level": "medium",
      "recommended": true,
      "reason": "服务管理决策"
    },
    {
      "title": "决策汇报",
      "workstream_type": "presentation",
      "objective": "形成决策汇报",
      "inputs_required": ["策略包"],
      "activities": ["汇报组织"],
      "outputs": ["决策汇报"],
      "dependency_indices": [2],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "用户需要决策支持"
    }
  ],
  "planning_notes": "不是新建医院工作流"
}"""

M3_HOSPITAL_ENV_DELIVERABLE_JSON = """{
  "deliverables": [
    {
      "id": "del-journey",
      "title": "患者旅程与环境诊断",
      "deliverable_type": "report",
      "purpose": "固化诊断",
      "audience": "医院管理层",
      "content_scope": ["旅程", "候诊", "流线", "导视"],
      "source_workstream_indices": [0, 1],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "8页"
    },
    {
      "id": "del-decision-ppt",
      "title": "环境提升决策汇报",
      "deliverable_type": "presentation",
      "purpose": "汇报快速与中长期措施",
      "audience": "医院管理层",
      "content_scope": ["诊断", "快速措施", "中长期措施"],
      "source_workstream_indices": [2, 3],
      "recommendation": "required",
      "format": "pptx",
      "expected_length": "10-14页"
    },
    {
      "id": "del-new-hospital",
      "title": "新建医院方案汇报",
      "deliverable_type": "presentation",
      "purpose": "不在本轮范围",
      "audience": "无",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "not_recommended",
      "format": "pptx",
      "notes": "任务是环境提升，不是新建医院",
      "decision_served": "无"
    }
  ],
  "planning_notes": "推荐决策汇报，不推荐新建医院方案"
}"""

M4_VILLAGE_MISSION_JSON = """{
  "title": "村庄更新前期策划",
  "task_statement": "围绕人口、产业、空间、居民与运营形成村庄更新策划，避免套用固定乡村模板",
  "task_natures": ["urban_renewal", "planning", "research"],
  "domains": ["urban", "housing"],
  "intervention_scales": ["village", "site"],
  "requested_service_depths": ["information_collection", "project_diagnosis", "implementation_strategy"],
  "project_context": "多主体参与的村庄更新，资料与诉求分散",
  "current_situation": "人口外流、产业脆弱、公共空间不足、居民参与机制不清",
  "primary_problems": ["利益相关方复杂", "居民诉求不清", "实施机制缺失"],
  "desired_changes": ["资源盘点", "明确居民需求", "建立实施机制"],
  "in_scope": ["资源盘点", "居民需求调研", "实施机制建议", "更新策略框架"],
  "out_of_scope": ["固定美丽乡村模板套用", "施工图设计"],
  "stakeholders": [
    {"name": "村委会", "role": "基层组织", "concerns": ["可实施性", "公平性"]},
    {"name": "常住居民", "role": "使用者", "concerns": ["住房", "就业", "公共空间"]},
    {"name": "乡镇政府", "role": "主管部门", "concerns": ["产业", "安全", "资金"]},
    {"name": "返乡青年", "role": "潜在经营者", "concerns": ["业态", "运营"]}
  ],
  "decision_context": "需确认更新切入点与参与机制",
  "decisions_required": ["优先更新议题", "居民参与方式"],
  "known_constraints": [],
  "key_unknowns": ["常住人口结构", "可盘活闲置资产", "居民参与意愿"],
  "research_questions": ["如何组织有代表性的居民参与？"],
  "design_question_summaries": ["如何在多方诉求下形成可落地的更新机制？"],
  "evaluation_criteria": [{"name": "参与代表性", "description": "需覆盖不同居民群体", "weight": 0.35}],
  "uncertainty_level": "high",
  "confidence": 0.45,
  "knowledge_gaps": [
    {"category": "stakeholder", "question": "不同居民群体的核心诉求分别是什么？", "why_it_matters": "避免单一模板", "priority": "critical", "blocking": false},
    {"category": "operation", "question": "村庄更新的实施与运维主体是谁？", "why_it_matters": "决定机制设计", "priority": "high", "blocking": false}
  ],
  "assumptions": [],
  "clarifying_questions": [
    {"question": "是否需要组织居民参与工作坊或入户访谈？", "why_asked": "决定调研方法", "blocking": false, "can_assume": true, "suggested_assumption": "需要居民参与"},
    {"question": "本轮更关注产业、人居环境还是公共空间？", "why_asked": "确定切入点", "blocking": false, "can_assume": true, "suggested_assumption": "人居与公共空间优先"}
  ],
  "design_questions": [
    {"question": "如何建立可代表多方利益的更新实施机制？", "related_problem": "主体复杂", "desired_outcome": "参与与实施机制草案"}
  ]
}"""

M4_VILLAGE_WORKSTREAM_JSON = """{
  "workstreams": [
    {
      "title": "资源盘点",
      "workstream_type": "document_review",
      "objective": "盘点人口、产业、空间与闲置资源",
      "inputs_required": ["村志", "用地资料"],
      "activities": ["资料梳理", "现场核对"],
      "outputs": ["资源清单"],
      "dependency_indices": [],
      "priority": "high",
      "effort_level": "high",
      "recommended": true,
      "reason": "更新需建立在资源现实上"
    },
    {
      "title": "居民需求调研",
      "workstream_type": "user_research",
      "objective": "收集不同居民群体诉求",
      "questions": ["谁缺席了讨论？"],
      "inputs_required": ["资源清单"],
      "activities": ["访谈", "工作坊"],
      "outputs": ["需求图谱"],
      "dependency_indices": [0],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "必须有居民参与"
    },
    {
      "title": "实施机制设计",
      "workstream_type": "implementation",
      "objective": "提出组织、资金与运维机制",
      "inputs_required": ["需求图谱"],
      "activities": ["机制比较", "职责划分"],
      "outputs": ["实施机制建议"],
      "dependency_indices": [1],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "避免停留在概念蓝图"
    }
  ],
  "planning_notes": "不生成固定乡村模板章节"
}"""

M4_VILLAGE_DELIVERABLE_JSON = """{
  "deliverables": [
    {
      "id": "del-inventory",
      "title": "村庄资源盘点",
      "deliverable_type": "report",
      "purpose": "固化资源与问题",
      "audience": "村委会/乡镇",
      "content_scope": ["人口", "产业", "空间"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "8页"
    },
    {
      "id": "del-participation",
      "title": "居民需求与参与机制",
      "deliverable_type": "memo",
      "purpose": "明确参与路径",
      "audience": "村委会",
      "content_scope": ["需求", "参与方式"],
      "source_workstream_indices": [1, 2],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "5页"
    },
    {
      "id": "del-template",
      "title": "标准美丽乡村模板文本",
      "deliverable_type": "other",
      "purpose": "不建议",
      "audience": "无",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "not_recommended",
      "format": "markdown",
      "notes": "禁止套用固定乡村模板",
      "decision_served": "无"
    }
  ],
  "planning_notes": "推荐资源盘点、居民需求与实施机制，不套模板"
}"""

M5_FIRE_WORKSTREAM_JSON = """{
  "workstreams": [
    {
      "title": "功能策划",
      "workstream_type": "programming",
      "objective": "组织执勤、训练、生活与后勤功能",
      "questions": ["车辆出动流线如何最短？"],
      "inputs_required": ["用地指标", "规范要点"],
      "activities": ["功能分区", "流线推演"],
      "outputs": ["功能策划"],
      "dependency_indices": [],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "新建消防站核心工作"
    },
    {
      "title": "规范研究",
      "workstream_type": "regulation_review",
      "objective": "核对消防站相关规范与技术要求",
      "inputs_required": ["功能策划"],
      "activities": ["规范摘录", "符合性检查"],
      "outputs": ["规范符合性清单"],
      "dependency_indices": [0],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "公共安全项目必须合规"
    }
  ],
  "planning_notes": "指标已明确，不进入面积待确认路径"
}"""

M5_FIRE_DELIVERABLE_JSON = """{
  "deliverables": [
    {
      "id": "del-program",
      "title": "功能策划说明",
      "deliverable_type": "design_brief",
      "purpose": "固化功能与流线",
      "audience": "主管部门",
      "content_scope": ["功能分区", "车辆流线", "训练与生活"],
      "source_workstream_indices": [0],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "6页"
    },
    {
      "id": "del-code",
      "title": "规范研究纪要",
      "deliverable_type": "checklist",
      "purpose": "列出规范符合性要点",
      "audience": "设计团队",
      "content_scope": ["规范条款", "风险点"],
      "source_workstream_indices": [1],
      "recommendation": "required",
      "format": "markdown",
      "expected_length": "4页"
    },
    {
      "id": "del-area-gap",
      "title": "面积待确认清单",
      "deliverable_type": "question_list",
      "purpose": "不需要",
      "audience": "无",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "not_recommended",
      "format": "markdown",
      "notes": "用地与面积已明确，无需面积待确认",
      "decision_served": "无"
    }
  ],
  "planning_notes": "推荐功能策划和规范研究"
}"""


M6_GREEN_CAMPUS_MISSION_JSON = """{
  "title": "园区绿色低碳专项建议",
  "task_statement": "为产业园区提供绿色低碳专项咨询建议，不是完整建筑设计",
  "task_natures": ["consulting", "technical_study"],
  "domains": ["sustainability", "industrial"],
  "intervention_scales": ["campus", "system"],
  "requested_service_depths": ["technical_proposal", "implementation_strategy"],
  "project_context": "园区管理方希望获得可落地的低碳专项建议",
  "current_situation": "已有运营园区，需要目标、技术与实施路径，而非方案设计",
  "primary_problems": ["目标不清", "技术路径分散", "实施节奏不明"],
  "desired_changes": ["建立目标体系", "筛选适用技术", "形成实施路线"],
  "in_scope": ["目标体系", "技术筛选", "实施路线建议"],
  "out_of_scope": ["施工图", "设备选型", "正式碳认证", "完整建筑设计"],
  "stakeholders": [
    {"name": "园区管理方", "role": "委托方", "concerns": ["可落地性", "成本", "分期"]}
  ],
  "decision_context": "需确认专项目标与技术优先级",
  "decisions_required": ["目标优先级", "首批技术措施"],
  "known_constraints": [
    {"name": "任务边界", "value": "专项咨询，不开展完整建筑设计", "source": "user", "verification_status": "user_confirmed", "importance": "high"}
  ],
  "key_unknowns": ["现有能耗基线精度"],
  "research_questions": ["哪些低碳技术与园区业态最匹配？"],
  "design_question_summaries": ["如何在不进入施工图的前提下给出可执行建议？"],
  "evaluation_criteria": [{"name": "可实施性", "description": "建议应可分期落地", "weight": 0.4}],
  "uncertainty_level": "medium",
  "confidence": 0.7,
  "knowledge_gaps": [
    {"category": "other", "question": "园区现有能耗与碳排基线完整度如何？", "why_it_matters": "影响目标设定精度", "priority": "medium", "blocking": false}
  ],
  "assumptions": [],
  "clarifying_questions": [
    {"question": "本轮是否排除施工图、设备选型与正式碳认证？", "why_asked": "锁定咨询边界", "blocking": false, "can_assume": true, "suggested_assumption": "全部排除"}
  ],
  "design_questions": [
    {"question": "如何用目标-技术-实施三层结构组织专项建议？", "related_problem": "咨询易发散", "desired_outcome": "清晰专项报告结构"}
  ]
}"""


M7_CONCEPT_CULTURAL_CENTER_MISSION_JSON = """{
  "title": "黄土高原文化中心概念探索",
  "task_statement": "探索一种嵌入黄土高原地域文化、服务村民与游客的小型文化中心概念方向",
  "task_natures": ["planning", "research"],
  "domains": ["culture", "architecture"],
  "intervention_scales": ["village", "site"],
  "requested_service_depths": ["concept_planning", "preliminary_research", "presentation_production"],
  "project_context": "仅有初步想法，无任务书与精确指标",
  "current_situation": "项目处于概念萌芽阶段，地点与规模待确认",
  "primary_problems": ["项目定位不清", "缺少基础资料", "目标用户与体验未定义"],
  "desired_changes": ["建立可讨论的概念方向", "明确设计使命与假设", "形成概念汇报框架"],
  "in_scope": ["概念策划", "地域文化研究", "概念汇报"],
  "out_of_scope": ["施工图设计", "精确面积指标"],
  "stakeholders": [
    {"name": "村民", "role": "在地使用者", "concerns": ["社区归属", "日常可用性"]},
    {"name": "游客", "role": "外来体验者", "concerns": ["文化体验", "可达性"]}
  ],
  "decision_context": "需先确认概念方向再进入方案深化",
  "decisions_required": ["项目定位", "核心体验策略"],
  "known_constraints": [],
  "key_unknowns": ["精确用地", "建设规模", "投资来源"],
  "research_questions": ["关中乡村公共文化空间有哪些可借鉴模式？"],
  "design_question_summaries": ["如何让文化中心同时服务村民日常与游客体验？"],
  "evaluation_criteria": [{"name": "概念可讨论性", "description": "方向清晰且留有验证空间", "weight": 0.4}],
  "uncertainty_level": "high",
  "confidence": 0.45,
  "design_intent": {
    "theme": "黄土高原地域文化再生",
    "problem_statement": "在缺乏完整任务书时，如何建立可讨论的文化中心概念方向？",
    "social_background": "乡村人口外流与本土文化记忆断层",
    "cultural_context": "窑洞、台地景观与关中民俗",
    "target_users": ["村民", "游客"],
    "desired_experience": "在地认同与开放交流并存",
    "core_questions": ["建筑如何成为社区生活的延伸？"],
    "research_needed": ["同类乡村文化空间案例", "人口与游客趋势"],
    "working_assumptions": ["假定位于陕西关中乡村，规模约 500–800㎡，待确认"]
  },
  "knowledge_gaps": [
    {"category": "site", "question": "具体用地与可达性条件？", "why_it_matters": "影响概念尺度", "priority": "medium", "blocking": false}
  ],
  "assumptions": [
    {"statement": "假定项目位于陕西关中乡村", "reason": "用户未提供精确地点", "requires_confirmation": true}
  ],
  "clarifying_questions": [
    {"question": "更优先服务村民日常还是游客体验？", "why_asked": "影响功能重心", "blocking": false, "can_assume": true, "suggested_assumption": "两者并重，日常与节庆兼顾"}
  ],
  "design_questions": [
    {"question": "如何用低信息密度启动高价值概念讨论？", "related_problem": "资料缺失", "desired_outcome": "可迭代的概念框架"}
  ]
}"""

M7_CONCEPT_CULTURAL_CENTER_WORKSTREAM_JSON = """{
  "workstreams": [
    {
      "title": "地域文化与社会背景研究",
      "workstream_type": "case_study",
      "objective": "梳理黄土高原地域文化与使用情境",
      "questions": ["哪些文化要素应进入空间策略？"],
      "inputs_required": ["用户想法"],
      "activities": ["文献与案例研究"],
      "outputs": ["文化语境摘要"],
      "dependency_indices": [],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "概念探索需先建立语境"
    },
    {
      "title": "概念策划与体验框架",
      "workstream_type": "programming",
      "objective": "形成概念定位、用户与体验假设",
      "questions": ["核心体验是什么？"],
      "inputs_required": ["文化语境摘要"],
      "activities": ["概念框架", "假设清单"],
      "outputs": ["概念策划 v0.1"],
      "dependency_indices": [0],
      "priority": "critical",
      "effort_level": "high",
      "recommended": true,
      "reason": "建立可讨论的概念方向"
    },
    {
      "title": "概念汇报制作",
      "workstream_type": "presentation",
      "objective": "输出概念探索汇报",
      "inputs_required": ["概念策划 v0.1"],
      "activities": ["叙事组织"],
      "outputs": ["概念汇报"],
      "dependency_indices": [1],
      "priority": "high",
      "effort_level": "medium",
      "recommended": true,
      "reason": "用户需要汇报载体"
    }
  ],
  "notes": "概念探索工作路径"
}"""

M7_CONCEPT_CULTURAL_CENTER_DELIVERABLE_JSON = """{
  "deliverables": [
    {
      "id": "del-concept-ppt",
      "title": "文化中心概念探索汇报",
      "deliverable_type": "presentation",
      "purpose": "呈现概念方向、假设与待研究项",
      "audience": "委托方/团队内部",
      "content_scope": ["设计使命", "文化语境", "概念框架", "待确认假设"],
      "expected_length": "15-20页",
      "required": true,
      "selected": true,
      "notes": "概念草稿，非正式交付"
    }
  ]
}"""


CASE_MOCKS: dict[str, dict[str, str]] = {
    "case_m1_temple": {
        "mission": TEMPLE_MISSION_JSON,
        "workstream": TEMPLE_WORKSTREAM_PLAN_JSON,
        "deliverable": TEMPLE_DELIVERABLE_PLAN_JSON,
    },
    "case_m2_library": {
        "mission": M2_LIBRARY_MISSION_JSON,
        "workstream": M2_LIBRARY_WORKSTREAM_JSON,
        "deliverable": M2_LIBRARY_DELIVERABLE_JSON,
    },
    "case_m3_hospital_env": {
        "mission": M3_HOSPITAL_ENV_MISSION_JSON,
        "workstream": M3_HOSPITAL_ENV_WORKSTREAM_JSON,
        "deliverable": M3_HOSPITAL_ENV_DELIVERABLE_JSON,
    },
    "case_m4_village": {
        "mission": M4_VILLAGE_MISSION_JSON,
        "workstream": M4_VILLAGE_WORKSTREAM_JSON,
        "deliverable": M4_VILLAGE_DELIVERABLE_JSON,
    },
    "case_m5_fire_station": {
        "mission": FIRE_STATION_MISSION_JSON,
        "workstream": M5_FIRE_WORKSTREAM_JSON,
        "deliverable": M5_FIRE_DELIVERABLE_JSON,
    },
    "case_m6_green_campus": {
        "mission": M6_GREEN_CAMPUS_MISSION_JSON,
        "workstream": GREEN_CAMPUS_WORKSTREAM_PLAN_JSON,
        "deliverable": GREEN_CAMPUS_DELIVERABLE_PLAN_JSON,
    },
    "case_m7_concept_cultural_center": {
        "mission": M7_CONCEPT_CULTURAL_CENTER_MISSION_JSON,
        "workstream": M7_CONCEPT_CULTURAL_CENTER_WORKSTREAM_JSON,
        "deliverable": M7_CONCEPT_CULTURAL_CENTER_DELIVERABLE_JSON,
    },
}


def make_mission_case_selector(case_id: str):
    """Return a MockLLM selector bound to one golden mission case."""
    mocks = CASE_MOCKS[case_id]

    def selector(request: LLMRequest) -> str | None:
        prompt = request.user_prompt
        if "DeliverablePlan JSON" in prompt:
            return mocks["deliverable"]
        if "WorkstreamPlan JSON" in prompt:
            return mocks["workstream"]
        if "ProjectMission JSON" in prompt or "根据澄清结果修订 ProjectMission JSON" in prompt:
            return mocks["mission"]
        return None

    return selector
