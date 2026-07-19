# 跨平台部署与依赖优化方案

## 📋 目录

1. [当前架构分析](#当前架构分析)
2. [痛点识别](#痛点识别)
3. [优化方案](#优化方案)
   - [方案A：容器化部署（推荐）](#方案a容器化部署推荐)
   - [方案B：微服务化渲染层](#方案b微服务化渲染层)
   - [方案C：纯Python渲染方案](#方案c纯python渲染方案)
4. [实施路线图](#实施路线图)
5. [迁移指南](#迁移指南)

---

## 当前架构分析

### 技术栈

**Python 后端**
- Streamlit UI 框架
- LangGraph 工作流编排
- SQLAlchemy ORM + SQLite/PostgreSQL
- LangChain LLM 集成

**Node.js 渲染层**
- PptxGenJS (v3.12.0) - 用于生成可编辑 PPTX
- Marp CLI (可选) - Markdown 转 PDF

### 调用链路

```
Python Application
    ├─> PptxGenCliRunner (archium/infrastructure/renderers/pptxgen_cli.py)
    │   └─> subprocess.run(["node", "render.mjs", "--input", spec.json, "--output", output.pptx])
    │       └─> Node.js Script (archium/infrastructure/renderers/pptxgen/render.mjs)
    │           └─> PptxGenJS Library
    │
    └─> MarpCliRunner (archium/infrastructure/renderers/marp_cli.py)
        └─> subprocess.run(["marp", input.md, "-o", output.pdf])
```

### 依赖检测机制

```python
# archium/infrastructure/renderers/pptxgen_cli.py:31-36
def is_available(self) -> bool:
    if shutil.which(self.command) is None:  # 检查 node 命令
        return False
    if not self.script_path.exists():  # 检查 render.mjs
        return False
    return (self.script_path.parent / "node_modules" / "pptxgenjs").exists()  # 检查依赖
```

---

## 痛点识别

### 1. **环境配置复杂度**

**问题：**
- 用户需要同时安装 Python 3.11+ 和 Node.js 18+
- 需要在特定目录运行 `npm install`
- 不同操作系统的 Node 安装路径不一致

**实际案例：**
```bash
# Windows 用户常见错误
FileNotFoundError: [WinError 2] 系统找不到指定的文件。
# 原因：node.exe 不在 PATH 中

# macOS/Linux 用户常见错误
RenderingError: 未检测到 PptxGenJS 运行时
# 原因：npm install 未执行或在错误的目录
```

### 2. **路径处理问题**

**问题：**
- Windows 路径包含空格或中文字符时，subprocess 调用易失败
- 相对路径与绝对路径混用导致脚本找不到资源

**代码位置：**
```python
# archium/infrastructure/renderers/pptxgen_cli.py:66-82
resolved_input = input_path.resolve()  # 必须转绝对路径
resolved_output = output_path.resolve()
result = subprocess.run(
    [self.command, str(script_path), "--input", str(resolved_input), ...],
    cwd=str(script_path.parent),  # 必须设置工作目录
)
```

### 3. **跨平台一致性差**

| 平台 | 常见问题 |
|------|---------|
| **Windows** | 中文路径、权限问题、node.exe 路径 |
| **macOS** | npm 全局安装路径、Rosetta 兼容性 (M1/M2) |
| **Linux** | 不同发行版的 Node 包管理器差异 |

### 4. **错误诊断困难**

当前错误消息：
```python
raise RenderingError(f"PptxGenJS 导出失败：{detail or '未知错误'}")
```

**问题：**
- 用户看到错误时，不知道是 Node 未安装、依赖未安装，还是脚本执行失败
- 无结构化日志，难以远程诊断

---

## 优化方案

### 方案A：容器化部署（推荐）

#### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
├────────────────────────┬────────────────────────────────────┤
│  archium-app           │  archium-renderer (可选)           │
│  ┌──────────────────┐  │  ┌──────────────────────────────┐  │
│  │ Python 3.11      │  │  │ Node.js 18 + PptxGenJS       │  │
│  │ Streamlit        │──┼─>│ Express API (端口 3000)      │  │
│  │ LangGraph        │  │  │                              │  │
│  │ SQLite/PostgreSQL│  │  └──────────────────────────────┘  │
│  └──────────────────┘  │                                    │
│  端口 8501             │  可选：分离渲染服务                 │
└────────────────────────┴────────────────────────────────────┘
```

#### 实施方案

**选项1：单容器方案（简单部署）**

适用场景：个人用户、小团队、快速演示

```dockerfile
# Dockerfile.all-in-one
FROM python:3.11-slim

# 安装 Node.js
RUN apt-get update && apt-get install -y \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# 安装 Node 依赖
COPY archium/infrastructure/renderers/pptxgen/package*.json \
     archium/infrastructure/renderers/pptxgen/
RUN cd archium/infrastructure/renderers/pptxgen && npm install

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

**docker-compose.yml**
```yaml
version: '3.8'

services:
  archium:
    build:
      context: .
      dockerfile: Dockerfile.all-in-one
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    environment:
      - DATABASE_PATH=/app/data/database/archium.db
      - LOG_LEVEL=INFO
    restart: unless-stopped
```

**用户使用流程：**
```bash
# 1. 克隆项目
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent

# 2. 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 添加 LLM API keys

# 3. 一键启动
docker-compose up -d

# 4. 访问
open http://localhost:8501
```

**优点：**
- ✅ 一键部署，无需用户安装 Python 或 Node
- ✅ 环境隔离，不污染用户系统
- ✅ 跨平台一致性（Windows/macOS/Linux）
- ✅ 易于版本管理和回滚

**缺点：**
- ❌ 镜像体积较大（~500MB）
- ❌ 首次构建耗时（5-10分钟）

---

**选项2：多容器方案（生产部署）**

适用场景：企业部署、多用户环境、需要横向扩展

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  # Python 应用服务
  app:
    build:
      context: .
      dockerfile: Dockerfile.app
    ports:
      - "8501:8501"
    depends_on:
      - db
      - renderer
    environment:
      - DATABASE_URL=postgresql://archium:password@db:5432/archium
      - PPTX_RENDERER_URL=http://renderer:3000
      - REDIS_URL=redis://cache:6379/0
    volumes:
      - app-data:/app/data
    restart: always

  # Node.js 渲染服务
  renderer:
    build:
      context: ./archium/infrastructure/renderers/pptxgen
      dockerfile: Dockerfile.renderer
    expose:
      - "3000"
    environment:
      - NODE_ENV=production
      - MAX_WORKERS=4
    restart: always
    deploy:
      replicas: 2  # 负载均衡
      resources:
        limits:
          memory: 512M

  # PostgreSQL 数据库
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=archium
      - POSTGRES_USER=archium
      - POSTGRES_PASSWORD=password
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: always

  # Redis 缓存（可选）
  cache:
    image: redis:7-alpine
    restart: always

volumes:
  app-data:
  db-data:
```

**Dockerfile.renderer**
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --production

COPY . .

EXPOSE 3000
CMD ["node", "server.mjs"]
```

**server.mjs** (新增渲染微服务)
```javascript
import express from 'express';
import { renderPresentation } from './render.mjs';

const app = express();
app.use(express.json({ limit: '50mb' }));

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '1.0.0' });
});

// 渲染接口
app.post('/render', async (req, res) => {
  try {
    const { spec, output_format = 'pptx' } = req.body;
    const result = await renderPresentation(spec, output_format);
    res.json({ success: true, file: result });
  } catch (error) {
    res.status(500).json({ 
      success: false, 
      error: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Renderer service listening on port ${PORT}`);
});
```

---

### 方案B：微服务化渲染层

#### 架构改造

**当前（同步subprocess）：**
```python
# Python 同步等待 Node 进程完成
result = subprocess.run([node, script, ...], capture_output=True)
if result.returncode != 0:
    raise RenderingError(...)
```

**改造后（HTTP API）：**
```python
# Python 通过 HTTP 调用渲染服务
import httpx

class PptxRendererClient:
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=60.0)
    
    def render(self, spec: dict, output_path: Path) -> Path:
        response = self.client.post(
            f"{self.base_url}/render",
            json={"spec": spec, "output_format": "pptx"}
        )
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return output_path
    
    def health_check(self) -> bool:
        try:
            r = self.client.get(f"{self.base_url}/health", timeout=5.0)
            return r.status_code == 200
        except:
            return False
```

**配置切换：**
```python
# settings.py
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 新增渲染服务配置
    pptx_renderer_mode: str = Field(
        default="subprocess",  # "subprocess" | "http"
        description="PPTX 渲染模式：subprocess (本地) 或 http (微服务)"
    )
    pptx_renderer_url: str = Field(
        default="http://localhost:3000",
        description="HTTP 模式下的渲染服务地址"
    )
```

**自动降级策略：**
```python
class AdaptivePptxRenderer:
    """自适应渲染器：优先 HTTP，降级到 subprocess"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http_client = PptxRendererClient(settings.pptx_renderer_url)
        self.subprocess_runner = PptxGenCliRunner(settings)
    
    def render(self, spec_path: Path, output_path: Path) -> Path:
        # 1. 尝试 HTTP 模式
        if self.settings.pptx_renderer_mode == "http":
            if self.http_client.health_check():
                try:
                    return self.http_client.render(spec_path, output_path)
                except Exception as e:
                    logger.warning(f"HTTP 渲染失败，降级到本地: {e}")
        
        # 2. 降级到 subprocess
        if self.subprocess_runner.is_available():
            return self.subprocess_runner.render(spec_path, output_path)
        
        # 3. 两种方式都不可用
        raise RenderingError(
            "无可用的 PPTX 渲染服务。请确保：\n"
            "1. 渲染微服务正在运行 (HTTP 模式)，或\n"
            "2. 已安装 Node.js 和 pptxgenjs 依赖 (本地模式)"
        )
```

#### 优点

- ✅ **解耦架构**：Python 和 Node 独立开发、部署、扩展
- ✅ **错误隔离**：Node 进程崩溃不影响 Python 应用
- ✅ **易于监控**：HTTP 接口便于添加指标、日志、追踪
- ✅ **负载均衡**：多个渲染服务实例并行处理
- ✅ **渐进式迁移**：保留 subprocess 作为后备方案

#### 缺点

- ❌ **网络开销**：本地部署时，HTTP 调用比 subprocess 略慢（~50ms）
- ❌ **额外维护**：需要维护 Express 服务代码

---

### 方案C：纯Python渲染方案

#### 技术选型

替换 PptxGenJS，使用纯 Python 库：

| 库名 | 优点 | 缺点 |
|------|------|------|
| **python-pptx** | 纯 Python、稳定、社区活跃 | API 较低级，需要手动布局 |
| **pptx-builder** | 基于 python-pptx 的高级封装 | 功能较少，文档欠缺 |
| **aspose-slides** | 功能强大、商业支持 | 收费（免费版有限制） |

#### 实施方案

**方案C1：逐步迁移（推荐）**

1. **保留现有 PptxGenJS 渲染器**
2. **新增 python-pptx 渲染器**
3. **通过配置切换**

```python
# settings.py
pptx_renderer_backend: str = Field(
    default="pptxgen",  # "pptxgen" | "python-pptx"
    description="PPTX 渲染后端选择"
)
```

```python
# archium/infrastructure/renderers/python_pptx_renderer.py
from pptx import Presentation
from pptx.util import Inches, Pt

class PythonPptxRenderer:
    """纯 Python 的 PPTX 渲染器"""
    
    def render(self, layout_plan: LayoutPlan, output_path: Path) -> Path:
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        
        for slide_plan in layout_plan.slides:
            slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白布局
            self._render_slide(slide, slide_plan)
        
        prs.save(str(output_path))
        return output_path
    
    def _render_slide(self, slide, slide_plan: SlidePlan):
        for element in slide_plan.elements:
            if element.role == "title":
                self._add_title(slide, element)
            elif element.role == "image":
                self._add_image(slide, element)
            # ... 其他元素类型
```

**优点：**
- ✅ **零外部依赖**：不需要 Node.js
- ✅ **部署简单**：pip install 即可
- ✅ **调试方便**：Python 栈内调试

**缺点：**
- ❌ **开发工作量大**：需要重新实现所有布局逻辑
- ❌ **功能差距**：python-pptx 的图表、形状支持不如 PptxGenJS
- ❌ **迁移风险**：现有 PPTX 输出可能有差异

**时间估算：**
- 基础功能（文本、图片、形状）：2-3 周
- 高级功能（图表、表格、动画）：4-6 周
- 测试和修复差异：2-3 周
- **总计：8-12 周**

---

## 实施路线图

### 阶段1：容器化（Week 1-2）

**目标：** 提供一键部署的 Docker 方案

- [ ] 创建 `Dockerfile.all-in-one`
- [ ] 编写 `docker-compose.yml`
- [ ] 编写用户文档 `docs/deployment/docker-quickstart.md`
- [ ] 测试 Windows/macOS/Linux 平台
- [ ] 发布 Docker Hub 镜像（可选）

**交付物：**
```
Archium-Agent/
├── Dockerfile.all-in-one
├── docker-compose.yml
├── .dockerignore
└── docs/deployment/
    ├── docker-quickstart.md
    └── troubleshooting.md
```

### 阶段2：微服务化（Week 3-4）

**目标：** 将渲染层抽离为独立服务

- [ ] 实现 Express 渲染服务 (`server.mjs`)
- [ ] 创建 `PptxRendererClient` HTTP 客户端
- [ ] 实现自动降级逻辑 (`AdaptivePptxRenderer`)
- [ ] 添加健康检查和监控端点
- [ ] 编写多容器 `docker-compose.production.yml`

**配置示例：**
```yaml
# .env
PPTX_RENDERER_MODE=http
PPTX_RENDERER_URL=http://renderer:3000
```

### 阶段3：纯Python方案（Week 5-12，可选）

**目标：** 完全消除 Node.js 依赖

- [ ] 实现 `PythonPptxRenderer` 基础版
- [ ] 迁移常用布局（hero, content, comparison）
- [ ] 对比测试：PptxGenJS vs python-pptx 输出
- [ ] 渐进式迁移：默认 pptxgen，提供 python-pptx 选项

---

## 迁移指南

### 对于现有用户

**当前使用本地部署的用户：**

1. **无需改动**：继续使用 subprocess 模式
2. **可选升级**：使用 Docker 一键部署，简化环境管理

**迁移步骤：**
```bash
# 1. 备份数据
cp -r data data.backup

# 2. 停止当前服务
# (Ctrl+C 停止 Streamlit)

# 3. 启动 Docker 版本
docker-compose up -d

# 4. 数据迁移（Docker 自动挂载 ./data）
# 无需手动操作
```

### 对于新用户

**推荐流程：**

```bash
# 方式1：Docker 一键部署（推荐）
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent
docker-compose up -d
open http://localhost:8501

# 方式2：传统部署（需要 Python + Node）
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent
pip install -e .
cd archium/infrastructure/renderers/pptxgen && npm install && cd -
streamlit run app.py
```

### 配置兼容性

所有方案向后兼容现有配置：

```python
# .env (现有配置保持不变)
OPENAI_API_KEY=sk-xxx
DATABASE_PATH=data/database/archium.db

# 新增可选配置
PPTX_RENDERER_MODE=subprocess  # 或 http
PPTX_RENDERER_URL=http://localhost:3000
```

---

## 成本效益分析

### 开发成本

| 方案 | 开发时间 | 维护成本 | 技术风险 |
|------|---------|---------|---------|
| **A1: 单容器** | 1-2 周 | 低 | 低 |
| **A2: 多容器** | 2-3 周 | 中 | 低 |
| **B: 微服务化** | 3-4 周 | 中 | 中 |
| **C: 纯Python** | 8-12 周 | 高 | 高 |

### 用户体验提升

| 指标 | 当前 | 方案A | 方案B | 方案C |
|------|-----|-------|-------|-------|
| **环境配置时间** | 30-60 分钟 | 5 分钟 | 5 分钟 | 15 分钟 |
| **跨平台一致性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **部署成功率** | 70% | 95% | 95% | 90% |
| **错误诊断难度** | 高 | 低 | 中 | 中 |

---

## 建议与决策

### 短期（1-2个月）

✅ **立即实施：方案A1（单容器Docker）**

**理由：**
- 最小开发成本（1-2周）
- 立即解决用户环境配置痛点
- 不改变现有代码架构，风险低

**优先级：** P0

### 中期（3-6个月）

✅ **逐步实施：方案B（微服务化）**

**理由：**
- 为企业部署提供更好的扩展性
- 解耦架构便于后续优化
- 可以与容器方案共存

**优先级：** P1

### 长期（6-12个月）

⚠️ **评估后决定：方案C（纯Python）**

**建议：**
- 先收集用户反馈，确认 Node.js 依赖是否仍是主要痛点
- 如果容器化方案解决了大部分问题，纯Python方案的优先级可降低
- 如果需要高度定制化渲染逻辑，再投入资源开发

**优先级：** P2（待评估）

---

## 附录

### A. 错误处理增强

当前错误消息不够友好，建议改进：

**当前：**
```
RenderingError: PptxGenJS 导出失败：未知错误
```

**改进后：**
```
╭─ PPTX 渲染失败 ────────────────────────────────────────────╮
│                                                             │
│  原因：未检测到 Node.js 运行时                              │
│                                                             │
│  解决方案：                                                 │
│  1. [推荐] 使用 Docker 一键部署：                           │
│     docker-compose up -d                                    │
│                                                             │
│  2. 手动安装 Node.js：                                      │
│     • Windows: https://nodejs.org/download/                 │
│     • macOS: brew install node                              │
│     • Linux: apt install nodejs npm                         │
│                                                             │
│  3. 安装渲染依赖：                                          │
│     cd archium/infrastructure/renderers/pptxgen             │
│     npm install                                             │
│                                                             │
│  文档：docs/deployment/troubleshooting.md                   │
╰─────────────────────────────────────────────────────────────╯
```

### B. 健康检查脚本

```python
# scripts/check_dependencies.py
import shutil
import sys
from pathlib import Path

def check_dependencies():
    """检查所有运行时依赖"""
    issues = []
    
    # 检查 Python
    if sys.version_info < (3, 11):
        issues.append("❌ Python 版本过低，需要 3.11+")
    else:
        print("✅ Python 3.11+")
    
    # 检查 Node.js
    if shutil.which("node") is None:
        issues.append("❌ 未安装 Node.js")
    else:
        print("✅ Node.js")
    
    # 检查 pptxgenjs
    pptxgen_path = Path("archium/infrastructure/renderers/pptxgen/node_modules/pptxgenjs")
    if not pptxgen_path.exists():
        issues.append("❌ 未安装 pptxgenjs (运行 npm install)")
    else:
        print("✅ pptxgenjs")
    
    if issues:
        print("\n⚠️  发现问题：")
        for issue in issues:
            print(f"  {issue}")
        print("\n建议使用 Docker 部署：docker-compose up -d")
        sys.exit(1)
    else:
        print("\n✅ 所有依赖检查通过")

if __name__ == "__main__":
    check_dependencies()
```

使用方式：
```bash
python scripts/check_dependencies.py
```

---

## 总结

本方案提供了三种优化路径，推荐按以下顺序实施：

1. **立即行动**：Docker 单容器方案（1-2周）→ 解决 80% 用户痛点
2. **逐步优化**：微服务化架构（3-4周）→ 提升企业部署能力
3. **长期考虑**：纯Python方案（评估后决定）→ 完全消除跨语言依赖

**预期收益：**
- 用户部署成功率从 70% 提升到 95%+
- 环境配置时间从 30-60 分钟缩短到 5 分钟
- 跨平台一致性显著提升
- 降低技术支持负担
