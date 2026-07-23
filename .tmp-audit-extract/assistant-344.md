## 问题 12–13 已落地

### 问题 12：能力矩阵去虚高
- README 旧四列（已实现 / 有测试 / 已接主流程 / **可稳定使用**）已替换为：
  **代码 · 自动测试 · 真实项目验收 · 发布等级**
- 等级：`Prototype` → `Experimental` → `Preview` → `Beta` → `Stable`（+ `Deprecated`）
- 完整表：`docs/release-capability-matrix.md`
- 当前多为 **Preview / Experimental**；明确 **只有 Beta/Stable 才接近可稳定使用**

### 问题 13：关键用户任务剧本
- 新增 `docs/user-task-playbooks.md`：剧本 **A–E**（新建汇报 / 模板填充 / PPT 美化 / 页面复活 / Studio 闭环）
- 写清通过标准、自动化映射、发版检查表
- Beta 发布决策已挂上剧本 A + Playbooks 门禁

### 守卫
`tests/unit/test_release_capability_docs.py`：`5 passed`；链接检查通过。

发版时不要再用「单测绿」代替剧本验收。未提交。