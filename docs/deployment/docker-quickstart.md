# Docker 快速部署指南

本指南帮助你使用 Docker 一键部署 Archium Agent，无需手动配置 Python 和 Node.js 环境。

## 前置要求

- Docker Desktop（Windows/macOS）或 Docker Engine（Linux）
- Docker Compose（通常已包含在 Docker Desktop 中）

### 安装 Docker

| 平台 | 安装方式 |
|------|---------|
| **Windows** | [下载 Docker Desktop](https://www.docker.com/products/docker-desktop) |
| **macOS** | [下载 Docker Desktop](https://www.docker.com/products/docker-desktop) 或 `brew install --cask docker` |
| **Linux (Ubuntu)** | `sudo apt install docker.io docker-compose` |

验证安装：
```bash
docker --version
docker-compose --version
```

---

## 快速启动（5分钟）

### 1. 克隆项目

```bash
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent
```

### 2. 配置环境变量（可选）

如果需要使用 LLM 功能，创建 `.env` 文件：

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，添加你的 API Keys
# Windows: notepad .env
# macOS/Linux: nano .env
```

`.env` 示例内容：
```bash
# OpenAI API Key
OPENAI_API_KEY=sk-your-openai-key

# 或者使用 Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-your-key

# 或者使用 DeepSeek
DEEPSEEK_API_KEY=sk-your-deepseek-key

# 可选：自定义 API 端点（用于代理或本地模型）
# OPENAI_BASE_URL=https://your-proxy.com/v1
```

### 3. 启动服务

```bash
docker-compose up -d
```

**首次启动说明：**
- 构建镜像需要 5-10 分钟（取决于网速）
- 后续启动只需 10-20 秒

### 4. 访问应用

打开浏览器访问：http://localhost:8501

---

## 常用命令

### 查看日志

```bash
# 实时查看日志
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail=100
```

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart
```

### 更新到最新版本

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建镜像
docker-compose build

# 3. 重启服务
docker-compose up -d
```

### 完全清理（包括数据）

⚠️ **警告：此操作会删除所有数据，请先备份！**

```bash
# 停止并删除容器、网络
docker-compose down

# 删除数据卷
docker volume rm archium-agent_db-data

# 删除本地数据目录（如果需要）
rm -rf data uploads
```

---

## 数据持久化

Docker 版本会将数据保存在本地目录，即使容器删除也不会丢失：

```
Archium-Agent/
├── data/              # 数据库和工作流检查点
│   └── database/
│       ├── archium.db
│       └── workflow_checkpoints.db
└── uploads/           # 用户上传的文件
```

**备份数据：**
```bash
# 创建备份
tar -czf archium-backup-$(date +%Y%m%d).tar.gz data/ uploads/

# 恢复备份
tar -xzf archium-backup-20260720.tar.gz
```

---

## 配置说明

### 环境变量

在 `docker-compose.yml` 的 `environment` 部分可以修改配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_PATH` | SQLite 数据库路径 | `/app/data/database/archium.db` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `OPENAI_API_KEY` | OpenAI API Key | 从 `.env` 读取 |
| `ANTHROPIC_API_KEY` | Anthropic API Key | 从 `.env` 读取 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 从 `.env` 读取 |

### 端口映射

默认映射 `8501:8501`，如果端口冲突，可以修改：

```yaml
ports:
  - "8080:8501"  # 改为访问 http://localhost:8080
```

---

## 高级部署（生产环境）

### 使用 PostgreSQL（推荐多用户场景）

编辑 `docker-compose.yml`，取消注释 `db` 服务：

```yaml
services:
  archium:
    environment:
      - DATABASE_URL=postgresql://archium:changeme@db:5432/archium
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_PASSWORD=your-secure-password
    volumes:
      - db-data:/var/lib/postgresql/data
```

启动：
```bash
docker-compose up -d
```

### 使用渲染微服务（可选）

如果需要高性能渲染，可以启用独立的渲染服务：

1. 取消注释 `docker-compose.yml` 中的 `renderer` 服务
2. 修改 `archium` 服务的环境变量：
   ```yaml
   environment:
     - PPTX_RENDERER_MODE=http
     - PPTX_RENDERER_URL=http://renderer:3000
   ```

3. 重启服务：
   ```bash
   docker-compose up -d
   ```

### 反向代理（Nginx）

生产环境建议使用 Nginx 反向代理：

```nginx
# /etc/nginx/sites-available/archium
server {
    listen 80;
    server_name archium.yourcompany.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/archium /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 故障排查

### 1. 容器无法启动

**检查日志：**
```bash
docker-compose logs archium
```

**常见原因：**
- 端口 8501 被占用 → 修改 `docker-compose.yml` 的端口映射
- 数据目录权限问题 → `chmod -R 755 data uploads`

### 2. 无法访问 http://localhost:8501

**检查容器状态：**
```bash
docker-compose ps
```

应该看到：
```
NAME            STATE    PORTS
archium-agent   Up       0.0.0.0:8501->8501/tcp
```

**测试连接：**
```bash
curl http://localhost:8501/_stcore/health
```

### 3. PPTX 渲染失败

**检查 Node.js 依赖：**
```bash
docker-compose exec archium node --version
docker-compose exec archium ls -la archium/infrastructure/renderers/pptxgen/node_modules
```

**重新安装依赖：**
```bash
docker-compose exec archium bash -c "cd archium/infrastructure/renderers/pptxgen && npm install"
docker-compose restart
```

### 4. 内存不足

**增加 Docker 内存限制：**

Docker Desktop → Settings → Resources → Memory → 调整到至少 4GB

或在 `docker-compose.yml` 中添加：
```yaml
services:
  archium:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 5. 中文文件名乱码

**确保容器使用 UTF-8 编码：**
```yaml
services:
  archium:
    environment:
      - LANG=C.UTF-8
      - LC_ALL=C.UTF-8
```

---

## 性能优化

### 1. 启用 PostgreSQL

SQLite 在多用户场景下可能成为瓶颈，切换到 PostgreSQL：

```yaml
services:
  archium:
    environment:
      - DATABASE_URL=postgresql://archium:password@db:5432/archium
```

### 2. 使用 Redis 缓存（可选）

添加 Redis 服务：
```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped

  archium:
    environment:
      - REDIS_URL=redis://redis:6379/0
```

### 3. 镜像优化

**减小镜像体积：**
- 使用 `.dockerignore` 排除不必要的文件
- 多阶段构建（仅用于生产镜像）

```dockerfile
# .dockerignore
.git
.venv
__pycache__
*.pyc
tests/
docs/
```

---

## 监控与日志

### 集成 Prometheus（可选）

```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### 日志收集

**使用 Docker 日志驱动：**
```yaml
services:
  archium:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 安全建议

### 1. 使用强密码

修改 `.env` 中的数据库密码：
```bash
DB_PASSWORD=$(openssl rand -base64 32)
```

### 2. 限制网络访问

仅允许本地访问：
```yaml
ports:
  - "127.0.0.1:8501:8501"
```

### 3. 定期备份

设置自动备份脚本：
```bash
#!/bin/bash
# backup.sh
docker-compose exec -T archium sqlite3 /app/data/database/archium.db .dump > backup-$(date +%Y%m%d).sql
```

添加到 crontab：
```bash
0 2 * * * /path/to/backup.sh
```

---

## 与传统部署对比

| 特性 | Docker 部署 | 传统部署 |
|------|------------|---------|
| **环境配置** | 自动化，5分钟 | 手动，30-60分钟 |
| **依赖管理** | 内置 Python + Node | 需手动安装 |
| **跨平台** | 完全一致 | 需分别适配 |
| **版本回滚** | `git checkout + docker-compose build` | 复杂 |
| **资源隔离** | 完全隔离 | 可能冲突 |
| **性能开销** | 轻微（~5%） | 无 |

---

## 下一步

- 📖 [用户指南](../studio-user-guide.md)
- 🔧 [配置参考](../configuration-reference.md)
- 🐛 [问题排查](./troubleshooting.md)
- 🚀 [生产部署最佳实践](./production-deployment.md)

---

## 获取帮助

- GitHub Issues: https://github.com/Theopote/Archium-Agent/issues
- 文档: https://github.com/Theopote/Archium-Agent/wiki
- 讨论区: https://github.com/Theopote/Archium-Agent/discussions
