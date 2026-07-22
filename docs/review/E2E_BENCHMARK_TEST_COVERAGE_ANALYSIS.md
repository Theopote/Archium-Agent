# E2E Benchmark 测试覆盖分析报告


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 分析时间
2026-07-19

## 分析目标
验证 `E2EBenchmarkService` 的测试覆盖情况

---

## 发现总结

### 关键发现：⚠️ E2EBenchmarkService 没有直接测试

**验证命令**:
```bash
$ grep -r "E2EBenchmarkService" tests/ --include="*.py"
# 无结果

$ grep -r "e2e_benchmark_service" tests/ --include="*.py"
# 无结果
```

**结论**: `E2EBenchmarkService` 确实**没有被现有测试直接调用**。

---

## 现有测试结构

### 1. 架构基准测试 (Architectural Benchmark)
**位置**: `tests/benchmark/architectural_slides/`

**使用的服务**: `BenchmarkService` (不是 E2EBenchmarkService)

```python
# tests/benchmark/architectural_slides/runner.py
from archium.application.visual.benchmark_service import BenchmarkService

def run_case(case_id: str, service: BenchmarkService | None = None):
    # 使用 BenchmarkService，不是 E2EBenchmarkService
```

**CI 覆盖**:
```yaml
# .github/workflows/ci.yml (line 64-65)
- name: Architectural slide benchmark quality gate
  run: pytest tests/benchmark/architectural_slides -v -m architectural_benchmark
```

**状态**: ✅ 有 CI 覆盖，但测试的是 `BenchmarkService`

### 2. E2E 测试目录
**位置**: `tests/e2e/`

**内容**:
```
tests/e2e/
├── __init__.py
├── conftest.py
├── real_projects/
│   ├── artifacts.py
│   ├── loader.py
│   ├── runner.py
│   └── test_real_project_acceptance.py
```

**状态**: ⚠️ 目录存在但不测试 E2EBenchmarkService

### 3. 单元测试
**位置**: `tests/unit/visual/test_benchmark_domain.py`

**测试内容**: 只测试领域模型（`HumanVisualReview`）

```python
# 测试 domain models，不测试 service
from archium.domain.visual.benchmark import HumanVisualReview

def test_human_visual_review_weighted_score():
    review = HumanVisualReview(...)
```

**状态**: ✅ 领域模型有测试，但 Service 层没有

---

## 两个 Benchmark Service 的区别

### BenchmarkService (有测试)
**文件**: `archium/application/visual/benchmark_service.py`

**用途**: 
- 单个幻灯片布局质量评估
- 基于规则的评分
- 现有测试覆盖

**测试**: ✅ `tests/benchmark/architectural_slides/`

### E2EBenchmarkService (无测试)
**文件**: `archium/application/visual/e2e_benchmark_service.py`

**用途**:
- 完整端到端流程验证
- 从文档导入到最终输出
- 模拟真实用户场景

**测试**: ❌ **无直接测试**

---

## CI 配置分析

### 当前 CI 步骤
```yaml
# .github/workflows/ci.yml

# 1. 单元测试和集成测试（排除 smoke）
- name: Pytest
  run: pytest -m "not smoke" --cov=archium --cov-report=term-missing

# 2. 架构基准测试（使用 BenchmarkService）
- name: Architectural slide benchmark quality gate
  run: pytest tests/benchmark/architectural_slides -v -m architectural_benchmark

# 3. PptxGen 烟雾测试
- name: PptxGen smoke test
  run: pytest tests/smoke/test_pptxgen_render.py -v
```

### 问题
- ❌ 没有专门运行 `tests/e2e/` 的步骤
- ❌ 没有测试 `E2EBenchmarkService` 的步骤
- ⚠️ E2E 测试可能被 `pytest -m "not smoke"` 覆盖，但没有专门验证

---

## 建议的原因分析

### 为什么建议认为存在问题？

虽然 API 调用是正确的，但建议的核心关注点是对的：

1. ✅ **E2EBenchmarkService 确实没有被测试执行过**
   - 无直接测试文件
   - CI 不明确覆盖
   - 可能从未真正运行

2. ✅ **如果真的运行过，应该会发现问题**
   - 即使 API 正确，集成问题仍可能存在
   - 依赖注入、数据流、错误处理等

3. ✅ **测试覆盖存在盲区**
   - `BenchmarkService` 有测试
   - `E2EBenchmarkService` 无测试
   - 可能以为覆盖了，实际没有

---

## 潜在风险

### 高风险区域
1. **文档导入流程** (line 118-126)
   - 调用 `IngestionService.import_file()`
   - 错误处理是否正确？
   - 文件路径是否正确？

2. **布局生成流程** (line 146-154)
   - 调用 `VisualEditService.regenerate_layout()`
   - 是否真的能生成布局？
   - 错误是否被正确捕获？

3. **质量评估流程** (line 176-194)
   - 调用 `LayoutValidationService` 和 `DeckQAService`
   - 结果是否正确解析？
   - 评分逻辑是否正确？

### 为什么这些风险未被发现？
- ❌ 没有集成测试验证完整流程
- ❌ 可能只有单元测试（mock 掉依赖）
- ❌ CI 没有强制运行 E2E 验证

---

## 建议的行动计划

### P0: 立即行动（本周）

1. **创建 E2EBenchmarkService 集成测试**
   ```python
   # tests/integration/visual/test_e2e_benchmark_service.py
   
   def test_e2e_benchmark_service_basic_flow(db_session, tmp_path):
       """测试基本的端到端流程"""
       service = E2EBenchmarkService(db_session, tmp_path)
       case = E2EBenchmarkCase(
           case_id="test_case",
           task_description="Test",
           input_documents=["test.md"],
           input_images=[],
           expected_outcomes=...,
       )
       result = service.run_case(case)
       assert result.passed or len(result.failure_reasons) > 0
   ```

2. **验证 API 调用是否真的工作**
   ```python
   def test_ingestion_service_integration(db_session, tmp_path):
       """验证 IngestionService.import_file 能被正确调用"""
       service = E2EBenchmarkService(db_session, tmp_path)
       # 创建测试文件并验证导入
   ```

3. **更新 CI 配置**
   ```yaml
   - name: E2E Benchmark Integration Test
     run: pytest tests/integration/visual/test_e2e_benchmark_service.py -v
   ```

### P1: 短期行动（本月）

4. **创建真实案例测试**
   ```python
   # tests/e2e/test_e2e_benchmark_real_cases.py
   
   @pytest.mark.e2e
   def test_architectural_slide_e2e():
       """使用真实的架构图案例进行端到端测试"""
   ```

5. **添加 E2E 测试标记**
   ```ini
   # pytest.ini
   [pytest]
   markers =
       e2e: End-to-end benchmark tests
       architectural_benchmark: Architectural slide quality gate
   ```

6. **CI 分步执行**
   ```yaml
   - name: E2E Benchmark Tests
     run: pytest -m e2e -v
     if: github.event_name == 'pull_request'
   ```

### P2: 长期改进（持续）

7. **监控测试覆盖率**
   - 确保 E2EBenchmarkService 覆盖率 > 80%
   - 定期审查测试质量

8. **建立 E2E 测试数据集**
   - 创建标准测试案例
   - 维护期望输出基线

9. **添加性能基准**
   - E2E 流程耗时监控
   - 回归检测

---

## 验证清单

### 立即验证项
- [ ] E2EBenchmarkService 是否有任何测试？
- [ ] tests/e2e/ 目录中的测试是否运行？
- [ ] CI 是否执行 E2E 相关测试？
- [ ] pytest 标记是否正确配置？

### 集成验证项
- [ ] IngestionService.import_file() 能否被调用？
- [ ] LayoutPlanRepository.get() 能否返回数据？
- [ ] VisualEditService.regenerate_layout() 能否生成布局？
- [ ] DeckQAService 能否评估结果？

### 端到端验证项
- [ ] 能否从文档导入到生成布局？
- [ ] 能否完整运行一个测试案例？
- [ ] 失败时错误信息是否清晰？
- [ ] 性能是否可接受？

---

## 结论

### 建议的核心判断: ✅ **正确**

虽然具体的 API 调用错误不存在，但建议的核心关注是对的：

**E2EBenchmarkService 很可能从未被真正执行和测试过**

**证据**:
1. ✅ 无直接测试文件
2. ✅ CI 不明确覆盖
3. ✅ 无测试执行记录
4. ✅ 可能存在未发现的集成问题

**推荐优先级**:
- **P0**: 创建基本集成测试（1-2天）
- **P1**: 补充 CI 覆盖（1天）
- **P2**: 建立完整测试套件（1周）

---

## 附录：相关文件清单

### 被测试的服务
- ✅ `archium/application/visual/benchmark_service.py` - 有测试
- ❌ `archium/application/visual/e2e_benchmark_service.py` - **无测试**

### 现有测试
- `tests/benchmark/architectural_slides/` - 测试 BenchmarkService
- `tests/unit/visual/test_benchmark_domain.py` - 测试领域模型
- `tests/e2e/` - 目录存在但内容未知

### CI 配置
- `.github/workflows/ci.yml` - 覆盖架构基准，不覆盖 E2E

---

生成时间: 2026-07-19  
分析者: Kiro (Claude Sonnet 5)  
状态: 建议核心判断正确，需要补充测试覆盖
