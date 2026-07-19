# Docker 构建测试清单

本文档提供 Docker 构建和部署的完整测试清单。

## 测试环境

- [ ] **Windows 10/11** + Docker Desktop
- [ ] **macOS** (Intel) + Docker Desktop
- [ ] **macOS** (Apple Silicon M1/M2) + Docker Desktop
- [ ] **Linux** (Ubuntu 20.04/22.04) + Docker Engine

## 前置测试

### 环境检查

```bash
# 检查 Docker 版本
docker --version          # 需要 >= 20.10
docker-compose --version  # 需要 >= 1.29

# 检查 Docker 是否运行
docker info

# 检查磁盘空间（至少 5GB）
df -h  # Linux/macOS
wmic logicaldisk get size,freespace,caption  # Windows
```

### 文件完整性检查

```bash
# 必须存在的文件
ls -la Dockerfile.all-in-one
ls -la docker-compose.yml
ls -la .dockerignore
ls -la pyproject.toml
ls -la archium/infrastructure/renderers/pptxgen/package.json
ls -la app.py
```

## 自动化测试

### 运行测试脚本

**Linux/macOS:**
```bash
chmod +x scripts/test_docker_build.sh
./scripts/test_docker_build.sh
```

**Windows:**
```cmd
scripts\test_docker_build.bat
```

**预期结果：**
- ✅ 所有检查项通过
- ✅ 镜像构建成功（5-10 分钟）
- ✅ 容器启动正常
- ✅ 健康检查通过
- ✅ 可访问 http://localhost:8501

## 手动测试

如果自动化脚本失败，或需要深入诊断，按以下步骤手动测试。

### 步骤 1: 构建镜像

```bash
# 清理旧镜像
docker-compose down -v
docker rmi archium-agent_archium 2>/dev/null || true

# 构建新镜像（无缓存）
docker-compose build --no-cache

# 检查构建结果
docker images | grep archium-agent
```

**预期输出：**
```
archium-agent_archium   latest   <IMAGE_ID>   About a minute ago   XXX MB
```

**可接受的镜像大小：** 400MB - 800MB

### 步骤 2: 启动容器

```bash
# 启动容器
docker-compose up -d

# 检查容器状态
docker-compose ps
```

**预期输出：**
```
NAME            STATE     PORTS
archium-agent   Up        0.0.0.0:8501->8501/tcp
```

### 步骤 3: 查看日志

```bash
# 实时日志
docker-compose logs -f

# 最近 50 行
docker-compose logs --tail=50
```

**检查点：**
- [ ] 无 Python 导入错误
- [ ] 无 Node.js 执行错误
- [ ] 看到 "You can now view your Streamlit app" 消息
- [ ] 无 "Address already in use" 错误

### 步骤 4: 健康检查

```bash
# 等待服务启动（最多 60 秒）
for i in {1..60}; do
  curl -f http://localhost:8501/_stcore/health && break
  sleep 1
done

# 检查 HTTP 响应
curl -I http://localhost:8501
```

**预期结果：**
```
HTTP/1.1 200 OK
```

### 步骤 5: 测试内部环境

```bash
# 进入容器
docker-compose exec archium bash

# 检查 Python 版本
python --version  # 应为 3.11.x

# 检查 Node.js 版本
node --version    # 应为 v18.x 或更高

# 检查关键包
python -c "import streamlit; print(streamlit.__version__)"
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
python -c "import langchain; print(langchain.__version__)"

# 检查 pptxgenjs
ls -la /app/archium/infrastructure/renderers/pptxgen/node_modules/pptxgenjs

# 检查数据目录
ls -la /app/data

# 退出容器
exit
```

### 步骤 6: 功能测试

在浏览器访问 http://localhost:8501，进行以下操作：

#### 6.1 基础功能
- [ ] 页面正常加载，无白屏
- [ ] 侧边栏导航可用
- [ ] 可以切换不同页面

#### 6.2 项目管理
- [ ] 创建新项目
- [ ] 编辑项目信息
- [ ] 列表显示正常

#### 6.3 文档上传
- [ ] 上传 PDF 文档
- [ ] 上传 Word 文档
- [ ] 文件列表显示

#### 6.4 PPTX 生成（核心功能）
- [ ] 创建演示文稿
- [ ] 生成布局预览
- [ ] 导出 PPTX 文件
- [ ] PPTX 可用 PowerPoint 打开

**测试用例：**
1. 创建测试项目
2. 上传一个示例文档
3. 生成一个 3-5 页的简单汇报
4. 导出并验证 PPTX 文件

### 步骤 7: 数据持久化测试

```bash
# 创建测试数据后，重启容器
docker-compose restart

# 等待服务恢复
sleep 10

# 验证数据仍然存在
# 在浏览器中检查项目列表
```

**预期结果：**
- [ ] 之前创建的项目仍然存在
- [ ] 上传的文档仍然可访问
- [ ] 数据库连接正常

### 步骤 8: 资源使用测试

```bash
# 监控资源使用（运行 1 分钟）
docker stats archium-agent

# 检查内存使用
docker exec archium-agent free -m

# 检查磁盘使用
docker exec archium-agent df -h
```

**可接受范围：**
- **CPU 使用率（空闲）**: < 5%
- **CPU 使用率（渲染中）**: 30-80%
- **内存使用**: 500MB - 2GB
- **磁盘使用**: < 2GB

### 步骤 9: 网络测试

```bash
# 测试端口绑定
netstat -an | grep 8501  # Linux/macOS
netstat -an | findstr 8501  # Windows

# 从容器内部测试网络
docker-compose exec archium curl http://localhost:8501/_stcore/health
```

### 步骤 10: 清理测试

```bash
# 停止容器
docker-compose down

# 确认容器已停止
docker-compose ps

# 可选：清理所有数据
docker-compose down -v
rm -rf data/ uploads/
```

## 常见问题诊断

### 问题 1: 构建失败

**症状：**
```
ERROR [internal] load metadata for docker.io/library/python:3.11-slim
```

**解决方案：**
```bash
# 检查网络连接
ping docker.io

# 使用国内镜像（中国用户）
# 编辑 /etc/docker/daemon.json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn"
  ]
}

# 重启 Docker
sudo systemctl restart docker
```

### 问题 2: 端口冲突

**症状：**
```
Error starting userland proxy: listen tcp 0.0.0.0:8501: bind: address already in use
```

**解决方案：**
```bash
# 查找占用端口的进程
lsof -i :8501  # Linux/macOS
netstat -ano | findstr :8501  # Windows

# 修改 docker-compose.yml 端口映射
ports:
  - "8080:8501"  # 改为其他端口
```

### 问题 3: npm install 失败

**症状：**
```
npm ERR! network request to https://registry.npmjs.org/pptxgenjs failed
```

**解决方案：**
```bash
# 在 Dockerfile 中添加 npm 镜像配置
RUN npm config set registry https://registry.npmmirror.com
RUN cd archium/infrastructure/renderers/pptxgen && npm install
```

### 问题 4: Python 包安装失败

**症状：**
```
ERROR: Could not find a version that satisfies the requirement streamlit>=1.32.0
```

**解决方案：**
```bash
# 在 Dockerfile 中添加 pip 镜像配置
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 5: 容器启动后无法访问

**症状：**
- 容器状态正常，但浏览器无法访问

**诊断步骤：**
```bash
# 1. 检查容器内部服务
docker-compose exec archium curl http://localhost:8501/_stcore/health

# 2. 检查防火墙
# Windows: 控制面板 -> Windows Defender 防火墙 -> 高级设置
# Linux: sudo ufw status

# 3. 检查 Docker 网络
docker network inspect archium-agent_default
```

### 问题 6: 中文路径或文件名乱码

**症状：**
- 上传的中文文件名显示为乱码

**解决方案：**
```yaml
# 在 docker-compose.yml 中添加环境变量
environment:
  - LANG=C.UTF-8
  - LC_ALL=C.UTF-8
```

## 平台特定注意事项

### Windows

- **路径格式**: 使用 `\` 或 `/` 都可以，Docker 会自动转换
- **WSL2**: 推荐启用 WSL2 后端（设置 -> General -> Use WSL2）
- **性能**: WSL2 性能比 Hyper-V 好 3-5 倍
- **文件监视**: 如果修改代码需要重启容器

### macOS (Apple Silicon)

- **Rosetta**: Docker Desktop 会自动处理 x86/ARM 转换
- **性能**: 原生 ARM 镜像性能更好，但 python:3.11-slim 已支持
- **内存**: 建议分配至少 4GB 内存给 Docker

### Linux

- **权限**: 需要将用户加入 docker 组
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  ```
- **SELinux**: 如果启用，可能需要添加规则
  ```bash
  sudo setenforce 0  # 临时禁用测试
  ```

## 性能基准

### 构建时间

| 环境 | 首次构建 | 增量构建 |
|------|---------|---------|
| Windows (WSL2) | 8-12 分钟 | 2-3 分钟 |
| macOS (M1/M2) | 6-10 分钟 | 1-2 分钟 |
| Linux (Ubuntu) | 5-8 分钟 | 1-2 分钟 |

### 启动时间

| 操作 | 时间 |
|------|------|
| `docker-compose up -d` | 5-10 秒 |
| 服务就绪 | 20-40 秒 |
| 首次页面加载 | 3-5 秒 |

### 内存占用

| 状态 | 内存使用 |
|------|---------|
| 空闲 | 500-800 MB |
| 生成汇报 | 1-1.5 GB |
| PPTX 渲染 | 1.5-2 GB |

## 测试报告模板

完成所有测试后，请填写以下报告：

```
========================================
Docker 构建测试报告
========================================

测试日期: [YYYY-MM-DD]
测试人员: [姓名]
测试平台: [Windows/macOS/Linux]

1. 构建测试
   - 构建时间: [ ] 分钟
   - 镜像大小: [ ] MB
   - 构建结果: [ ] 通过 / [ ] 失败

2. 启动测试
   - 启动时间: [ ] 秒
   - 健康检查: [ ] 通过 / [ ] 失败
   - 日志检查: [ ] 无错误 / [ ] 有警告

3. 功能测试
   - 页面访问: [ ] 正常 / [ ] 异常
   - 项目创建: [ ] 正常 / [ ] 异常
   - 文档上传: [ ] 正常 / [ ] 异常
   - PPTX 生成: [ ] 正常 / [ ] 异常

4. 性能测试
   - CPU 使用率: [ ]%
   - 内存使用: [ ] MB
   - 响应时间: [ ] 秒

5. 问题记录
   [ ] 无问题
   [ ] 有问题（请详细描述）:

6. 总体评价
   [ ] 可以发布
   [ ] 需要修复后发布
   [ ] 不可发布

备注:
```

## 下一步

测试通过后：
1. ✅ 更新 `README.md`，添加 Docker 快速启动章节
2. ✅ 在 GitHub Issues 中关闭相关问题
3. ✅ 准备发布说明
4. ⏭️ 发布到 Docker Hub（可选）
5. ⏭️ 更新文档站点
