#!/bin/bash
# Docker 构建测试脚本
# 用于验证 Dockerfile 和 docker-compose 配置

set -e  # 遇到错误立即退出

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Archium Agent Docker 构建测试 ===${NC}\n"

# 1. 检查 Docker 环境
echo "1️⃣  检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    echo "请访问 https://www.docker.com/products/docker-desktop 安装 Docker Desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker 守护进程未运行${NC}"
    echo "请启动 Docker Desktop"
    exit 1
fi

echo -e "${GREEN}✅ Docker 已安装并运行${NC}"
docker --version
docker-compose --version || docker compose version
echo ""

# 2. 检查必要文件
echo "2️⃣  检查必要文件..."
REQUIRED_FILES=(
    "Dockerfile.all-in-one"
    "docker-compose.yml"
    ".dockerignore"
    "pyproject.toml"
    "archium/infrastructure/renderers/pptxgen/package.json"
    "app.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ 缺少文件: $file${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✅ 所有必要文件存在${NC}\n"

# 3. 清理旧的构建产物
echo "3️⃣  清理旧的构建产物..."
docker-compose down -v 2>/dev/null || true
docker rmi archium-agent_archium 2>/dev/null || true
echo -e "${GREEN}✅ 清理完成${NC}\n"

# 4. 构建镜像
echo "4️⃣  开始构建 Docker 镜像..."
echo "⏱️  预计耗时 5-10 分钟（首次构建）"
echo ""

START_TIME=$(date +%s)

if docker-compose build --no-cache; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo -e "${GREEN}✅ 镜像构建成功${NC}"
    echo "⏱️  构建耗时: ${DURATION} 秒"
else
    echo -e "${RED}❌ 镜像构建失败${NC}"
    exit 1
fi
echo ""

# 5. 检查镜像
echo "5️⃣  检查镜像信息..."
IMAGE_ID=$(docker images -q archium-agent_archium)
if [ -z "$IMAGE_ID" ]; then
    echo -e "${RED}❌ 镜像未找到${NC}"
    exit 1
fi

IMAGE_SIZE=$(docker images archium-agent_archium --format "{{.Size}}")
echo -e "${GREEN}✅ 镜像已创建${NC}"
echo "📦 镜像 ID: $IMAGE_ID"
echo "💾 镜像大小: $IMAGE_SIZE"
echo ""

# 6. 测试容器启动
echo "6️⃣  测试容器启动..."
if docker-compose up -d; then
    echo -e "${GREEN}✅ 容器启动成功${NC}"
else
    echo -e "${RED}❌ 容器启动失败${NC}"
    docker-compose logs
    exit 1
fi
echo ""

# 7. 等待服务就绪
echo "7️⃣  等待服务就绪（最多 60 秒）..."
for i in {1..60}; do
    if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 服务已就绪${NC}"
        break
    fi

    if [ $i -eq 60 ]; then
        echo -e "${RED}❌ 服务启动超时${NC}"
        echo "查看日志:"
        docker-compose logs --tail=50
        docker-compose down
        exit 1
    fi

    echo -n "."
    sleep 1
done
echo ""

# 8. 运行健康检查
echo "8️⃣  运行健康检查..."

# 检查容器状态
CONTAINER_STATUS=$(docker-compose ps --format json | jq -r '.[0].State' 2>/dev/null || docker-compose ps -q | xargs docker inspect -f '{{.State.Status}}')
if [ "$CONTAINER_STATUS" != "running" ]; then
    echo -e "${RED}❌ 容器状态异常: $CONTAINER_STATUS${NC}"
    docker-compose logs
    docker-compose down
    exit 1
fi
echo -e "${GREEN}✅ 容器运行正常${NC}"

# 检查健康端点
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/_stcore/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ 健康检查通过 (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}❌ 健康检查失败 (HTTP $HTTP_CODE)${NC}"
    docker-compose down
    exit 1
fi
echo ""

# 9. 测试内部依赖
echo "9️⃣  测试内部依赖..."

# 检查 Python 版本
PYTHON_VERSION=$(docker-compose exec -T archium python --version)
echo "🐍 $PYTHON_VERSION"

# 检查 Node.js 版本
NODE_VERSION=$(docker-compose exec -T archium node --version)
echo "🟢 Node.js $NODE_VERSION"

# 检查 pptxgenjs
if docker-compose exec -T archium test -d /app/archium/infrastructure/renderers/pptxgen/node_modules/pptxgenjs; then
    echo -e "${GREEN}✅ pptxgenjs 已安装${NC}"
else
    echo -e "${RED}❌ pptxgenjs 未安装${NC}"
    docker-compose down
    exit 1
fi

# 检查关键 Python 包
echo "检查 Python 包..."
REQUIRED_PACKAGES=("streamlit" "sqlalchemy" "pydantic" "langchain")
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if docker-compose exec -T archium python -c "import $pkg" 2>/dev/null; then
        echo -e "  ${GREEN}✅ $pkg${NC}"
    else
        echo -e "  ${RED}❌ $pkg${NC}"
        docker-compose down
        exit 1
    fi
done
echo ""

# 10. 测试数据持久化
echo "🔟 测试数据持久化..."
if [ -d "./data" ]; then
    echo -e "${GREEN}✅ data 目录已挂载${NC}"
else
    echo -e "${YELLOW}⚠️  data 目录不存在（首次运行正常）${NC}"
fi
echo ""

# 11. 性能测试
echo "1️⃣1️⃣ 性能测试..."
echo "📊 容器资源使用情况:"
docker stats --no-stream archium-agent
echo ""

# 12. 清理（可选）
echo "1️⃣2️⃣ 测试完成"
echo ""
read -p "是否停止并清理容器？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose down
    echo -e "${GREEN}✅ 容器已停止并清理${NC}"
else
    echo -e "${YELLOW}容器继续运行中${NC}"
    echo "访问: http://localhost:8501"
    echo "停止命令: docker-compose down"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 所有测试通过！${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "📝 测试报告:"
echo "  - 构建时间: ${DURATION} 秒"
echo "  - 镜像大小: ${IMAGE_SIZE}"
echo "  - 容器状态: 运行正常"
echo "  - 健康检查: 通过"
echo "  - 依赖检查: 通过"
echo ""
echo "下一步:"
echo "  1. 测试实际功能（创建项目、生成汇报）"
echo "  2. 测试不同平台（Windows/macOS/Linux）"
echo "  3. 更新 README.md，添加 Docker 部署说明"
echo "  4. 发布到 Docker Hub（可选）"
echo ""
