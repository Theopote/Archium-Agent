@echo off
REM Docker 构建测试脚本 (Windows)
REM 用于验证 Dockerfile 和 docker-compose 配置

setlocal enabledelayedexpansion

echo ========================================
echo Archium Agent Docker 构建测试 (Windows)
echo ========================================
echo.

REM 1. 检查 Docker 环境
echo 1. 检查 Docker 环境...
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Docker 未安装
    echo 请访问 https://www.docker.com/products/docker-desktop 安装 Docker Desktop
    exit /b 1
)

docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Docker 守护进程未运行
    echo 请启动 Docker Desktop
    exit /b 1
)

echo [OK] Docker 已安装并运行
docker --version
docker-compose --version
echo.

REM 2. 检查必要文件
echo 2. 检查必要文件...
set "MISSING_FILES="
if not exist "Dockerfile.all-in-one" set "MISSING_FILES=!MISSING_FILES! Dockerfile.all-in-one"
if not exist "docker-compose.yml" set "MISSING_FILES=!MISSING_FILES! docker-compose.yml"
if not exist ".dockerignore" set "MISSING_FILES=!MISSING_FILES! .dockerignore"
if not exist "pyproject.toml" set "MISSING_FILES=!MISSING_FILES! pyproject.toml"
if not exist "archium\infrastructure\renderers\pptxgen\package.json" set "MISSING_FILES=!MISSING_FILES! package.json"

if not "!MISSING_FILES!"=="" (
    echo [X] 缺少文件:!MISSING_FILES!
    exit /b 1
)
echo [OK] 所有必要文件存在
echo.

REM 3. 清理旧的构建产物
echo 3. 清理旧的构建产物...
docker-compose down -v >nul 2>nul
docker rmi archium-agent_archium >nul 2>nul
echo [OK] 清理完成
echo.

REM 4. 构建镜像
echo 4. 开始构建 Docker 镜像...
echo 预计耗时 5-10 分钟（首次构建）
echo.

set START_TIME=%time%
docker-compose build --no-cache
if %errorlevel% neq 0 (
    echo [X] 镜像构建失败
    exit /b 1
)

echo [OK] 镜像构建成功
echo.

REM 5. 检查镜像
echo 5. 检查镜像信息...
for /f "tokens=*" %%i in ('docker images -q archium-agent_archium') do set IMAGE_ID=%%i
if "!IMAGE_ID!"=="" (
    echo [X] 镜像未找到
    exit /b 1
)

for /f "tokens=*" %%i in ('docker images archium-agent_archium --format "{{.Size}}"') do set IMAGE_SIZE=%%i
echo [OK] 镜像已创建
echo 镜像 ID: !IMAGE_ID!
echo 镜像大小: !IMAGE_SIZE!
echo.

REM 6. 测试容器启动
echo 6. 测试容器启动...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [X] 容器启动失败
    docker-compose logs
    exit /b 1
)
echo [OK] 容器启动成功
echo.

REM 7. 等待服务就绪
echo 7. 等待服务就绪（最多 60 秒）...
set /a COUNT=0
:wait_loop
set /a COUNT+=1
curl -s http://localhost:8501/_stcore/health >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] 服务已就绪
    goto service_ready
)

if !COUNT! geq 60 (
    echo [X] 服务启动超时
    echo 查看日志:
    docker-compose logs --tail=50
    docker-compose down
    exit /b 1
)

echo|set /p="."
timeout /t 1 /nobreak >nul
goto wait_loop

:service_ready
echo.

REM 8. 运行健康检查
echo 8. 运行健康检查...
for /f "tokens=*" %%i in ('curl -s -o nul -w "%%{http_code}" http://localhost:8501/_stcore/health') do set HTTP_CODE=%%i
if "!HTTP_CODE!"=="200" (
    echo [OK] 健康检查通过 (HTTP !HTTP_CODE!)
) else (
    echo [X] 健康检查失败 (HTTP !HTTP_CODE!)
    docker-compose down
    exit /b 1
)
echo.

REM 9. 测试内部依赖
echo 9. 测试内部依赖...
docker-compose exec -T archium python --version
docker-compose exec -T archium node --version

docker-compose exec -T archium test -d /app/archium/infrastructure/renderers/pptxgen/node_modules/pptxgenjs
if %errorlevel% equ 0 (
    echo [OK] pptxgenjs 已安装
) else (
    echo [X] pptxgenjs 未安装
    docker-compose down
    exit /b 1
)
echo.

REM 10. 测试数据持久化
echo 10. 测试数据持久化...
if exist "data" (
    echo [OK] data 目录已挂载
) else (
    echo [!] data 目录不存在（首次运行正常）
)
echo.

REM 11. 性能测试
echo 11. 性能测试...
echo 容器资源使用情况:
docker stats --no-stream archium-agent
echo.

REM 12. 测试完成
echo ========================================
echo 所有测试通过！
echo ========================================
echo.
echo 测试报告:
echo   - 镜像大小: !IMAGE_SIZE!
echo   - 容器状态: 运行正常
echo   - 健康检查: 通过
echo   - 依赖检查: 通过
echo.
echo 访问应用: http://localhost:8501
echo.

set /p CLEANUP="是否停止并清理容器？(y/n): "
if /i "!CLEANUP!"=="y" (
    docker-compose down
    echo [OK] 容器已停止并清理
) else (
    echo 容器继续运行中
    echo 停止命令: docker-compose down
)

echo.
echo 下一步:
echo   1. 测试实际功能（创建项目、生成汇报）
echo   2. 测试不同平台（Windows/macOS/Linux）
echo   3. 更新 README.md
echo.

endlocal
