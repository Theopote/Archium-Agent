<timestamp>Thursday, Jul 23, 2026, 4:13 PM (UTC+8)</timestamp>
<user_query>
Archium 逐模块检查：第一轮架构体检

我建议从现在开始，不再继续横向增加大型能力，而是进入：

模块盘点
→ 找重复与断链
→ 修复缺陷
→ 删除遗留
→ 补齐测试
→ 收紧边界
→ 真实项目验收

本轮先完成了对以下内容的初步检查：

项目定位与入口；
Python 工程配置；
依赖组织；
Legacy 边界；
CI 和测试分层；
文档与代码一致性；
主架构描述。

当前仓库仍明确标记为 v0.2-alpha.5、Not ready，并把真实项目闭环作为当前重点，因此下一阶段确实应该以稳定性和收敛为主，而不是继续堆功能。

一、建议的完整检查顺序

后续逐模块按以下顺序推进：

批次	模块	核心检查内容
1	工程骨架与 CI	依赖、入口、Legacy、测试、文档一致性
2	Domain	模型重复、不变量、枚举膨胀、跨层依赖
3	Application	Service 过大、职责重叠、事务边界、编排重复
4	Workflow	状态机、暂停恢复、审批失效、路线分发
5	Database	ORM、Repository、Mapper、迁移、并发和事务
6	Parsing / Knowledge	文档解析、事实账本、分块、引用与冲突
7	Mission / Storyline	任务规划、叙事模式、审批和 lineage
8	Visual Planning	DesignBrief、Layout、容量、拆页和素材匹配
9	RenderScene	节点模型、闭合契约、版本兼容、Scene Patch
10	Studio	选择、拖拽、多选、评论、Undo、性能
11	Rendering / PPTX	PptxGen、原生能力、字体、图片、Master/Layout
12	QA / Delivery	Visual QA、Round-trip、阻断、交付清单
13	UI	页面结构、信息架构、重复入口和状态同步
14	Security / Configuration	Key、文件安全、外部命令、配置和隐私
15	Tests / Fixtures	单测真实性、Golden、E2E、真实项目覆盖
16	文档与删除阶段	过期文档、实验代码、无引用模型、死入口
二、第一模块：工程骨架与项目入口
结论
基础较完整，但存在“正式主产品 + 大量遗留兼容 + 高复杂度测试基础设施”并存的问题。

当前正式入口是：

archium；
streamlit run app.py；

同时继续打包：

archium-legacy；
legacy* Python 包。

这在 Alpha 早期可以接受，但现在进入收敛阶段，应开始隔离 Legacy。

问题 1：Legacy 仍属于正式安装包

setuptools 当前包含：

include = ["archium*", "legacy*"]

并公开：

archium-legacy = "legacy.main:main"

README 虽然明确称其为 v0.1 实验 CLI，但它仍：

被正式安装；
被 mypy 配置覆盖；
与主项目共享依赖；
可能继续产生兼容负担。
建议

短期不要直接删除，先完成隔离：

legacy/
→ 不被 archium 主包导入
→ 不参与主产品数据库
→ 不参与正式配置模型
→ 不共享主链 Service
→ 不出现在普通 UI 和文档主导航

之后选择：

方案 A：迁出仓库

放到：

archium-legacy

独立仓库或历史 Tag。

方案 B：保留源码但不默认安装

移除：

include = ["legacy*"]
archium-legacy = ...

改为开发者按需运行。

验收标准

全仓库检查：

rg "from legacy|import legacy" archium

结果必须为空。
</user_query>