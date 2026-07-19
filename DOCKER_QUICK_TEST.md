# Docker 快速测试指南 (5分钟)

这是一个简化的测试指南，帮助你快速验证 Docker 配置是否正确。

## 前提条件

✅ 已安装 Docker Desktop 并处于运行状态

## 测试步骤

### 1. 构建镜像 (5-10分钟)

```bash
cd Archium-Agent
docker-compose build
```

**期望输出最后一行：**
```
Successfully built xxxxxxxxx
Successfully tagged archium-agent_archium:latest
```

**如果失败：** 查看错误信息，常见原因是网络问题或文件缺失。

---

### 2. 启动容器 (10秒)

```bash
docker-compose up -d
```

**期望输出：**
```
Creating archium-agent ... done
```

**检查状态：**
```bash
docker-compose ps
```

应该看到：
```
NAME            STATE
archium-agent   Up
```

---

### 3. 查看日志 (等待30秒)

```bash
docker-compose logs -f
```

**期望看到：**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

按 `Ctrl+C` 退出日志查看。

---

### 4. 访问应用

在浏览器打开：**http://localhost:8501**

**期望结果：**
- ✅ 页面正常加载
- ✅ 看到 Archium Agent 界面
- ✅ 侧边栏可以点击

---

### 5. 快速功能测试

1. **创建项目**
   - 点击「项目管理」或「新建项目」
   - 输入项目名称：`测试项目`
   - 点击创建

2. **检查数据持久化**
   ```bash
   # 重启容器
   docker-compose restart
   
   # 等待10秒后刷新浏览器
   # 确认「测试项目」仍然存在
   ```

---

### 6. 测试 PPTX 渲染（可选但重要）

1. 进入容器：
   ```bash
   docker-compose exec archium bash
   ```

2. 检查 Node.js 和 pptxgenjs：
   ```bash
   node --version
   ls /app/archium/infrastructure/renderers/pptxgen/node_modules/pptxgenjs
   ```

3. 退出容器：
   ```bash
   exit
   ```

**期望结果：**
- ✅ Node.js 版本显示（如 v18.x）
- ✅ pptxgenjs 目录存在

---

### 7. 清理（可选）

测试完成后停止容器：
```bash
docker-compose down
```

**完全清理（包括数据）：**
```bash
docker-compose down -v
rm -rf data/ uploads/
```

---

## ✅ 测试通过标准

- [x] 镜像构建成功
- [x] 容器启动正常
- [x] 浏览器可访问 http://localhost:8501
- [x] 可以创建项目
- [x] 重启后数据保留
- [x] Node.js 和 pptxgenjs 可用

**如果以上全部通过，说明 Docker 配置正确！**

---

## ❌ 常见问题快速修复

### 问题：构建时网络超时

**症状：** `npm ERR! network` 或 `pip install timeout`

**解决：** 使用国内镜像

编辑 `Dockerfile.all-in-one`，在安装依赖前添加：
```dockerfile
# 添加这两行
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN npm config set registry https://registry.npmmirror.com
```

### 问题：端口 8501 被占用

**症状：** `bind: address already in use`

**解决：** 修改端口

编辑 `docker-compose.yml`：
```yaml
ports:
  - "8080:8501"  # 改为 8080 或其他未使用的端口
```

然后访问 http://localhost:8080

### 问题：容器无法启动

**症状：** `docker-compose ps` 显示 `Exited`

**解决：** 查看详细日志
```bash
docker-compose logs
```

根据错误信息修复。

---

## 🎯 下一步

测试通过后：
1. 阅读完整文档：`docs/deployment/docker-quickstart.md`
2. 运行完整测试：`scripts/test_docker_build.sh`
3. 更新 README.md
4. 开始使用！

---

## 💡 提示

- **首次构建慢很正常**（5-10分钟），后续会快很多
- **保留 `data/` 目录**可以避免数据丢失
- **遇到问题先看日志**：`docker-compose logs`
- **完整测试清单**：`docs/deployment/docker-test-checklist.md`
