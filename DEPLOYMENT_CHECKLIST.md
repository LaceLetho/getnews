# Railway 部署检查清单

在部署到 Railway 之前，请确认以下项目已完成。

## ✅ 配置文件检查

- [x] `Dockerfile` - 多阶段构建，已优化
- [x] `.dockerignore` - 排除不必要的文件
- [x] `railway.toml` - Railway 配置文件
- [x] `.railwayignore` - Railway 部署忽略文件
- [x] `docker-entrypoint.sh` - 入口脚本，有执行权限
- [x] `requirements.txt` - Python 依赖列表
- [x] `config.json` - 应用配置文件（需要确认存在）

## ⚠️ 需要确认的项目

### 1. 配置文件存在性

检查 `config.json` 是否存在：

```bash
ls -la config.json
```

如果不存在，需要创建一个默认配置文件。

### 2. 环境变量准备

确保已准备好以下环境变量的值：

**必需：**
- [ ] `LLM_API_KEY` - MiniMax API 密钥
- [ ] `TELEGRAM_BOT_TOKEN` - Telegram Bot Token
- [ ] `TELEGRAM_CHANNEL_ID` - Telegram 频道 ID

**可选：**
- [ ] `X_CT0` - X/Twitter CT0 Token
- [ ] `X_AUTH_TOKEN` - X/Twitter Auth Token

### 3. 本地测试

在部署前建议先本地测试：

```bash
# 构建镜像
docker build -t crypto-news-analyzer .

# 测试运行（一次性执行）
docker run --rm \
  -e LLM_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHANNEL_ID=your_channel \
  crypto-news-analyzer once

# 测试运行（定时调度，Ctrl+C 停止）
docker run --rm \
  -e LLM_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHANNEL_ID=your_channel \
  crypto-news-analyzer schedule
```

## 📋 Railway 特定配置

### 当前配置状态

| 配置项 | 状态 | 说明 |
|--------|------|------|
| Builder | ✅ DOCKERFILE | 使用 Dockerfile 构建 |
| Start Command | ✅ 已配置 | `/app/docker-entrypoint.sh schedule` |
| Restart Policy | ✅ ON_FAILURE | 失败时重启，最多 3 次 |
| Healthcheck | ✅ 已配置 | 超时 300 秒 |
| Port | ⚠️ 未使用 | 当前应用不需要暴露端口 |
| Volumes | ⚠️ 需手动配置 | 如需持久化数据，需在 Railway 创建 Volume |

### 建议的优化

1. **如果需要持久化数据**：
   - 在 Railway Dashboard 创建 Volume
   - 挂载到 `/app/data` 目录

2. **如果使用 Cron 模式**：
   - 修改 `railway.toml` 中的 `cronSchedule`
   - 将 `startCommand` 改为 `once` 模式

3. **如果需要 Web 界面**（未来功能）：
   - 取消注释 Dockerfile 中的 `EXPOSE 8080`
   - 配置 Railway 的端口映射

## 🔍 部署前最终检查

运行以下命令进行最终检查：

```bash
# 1. 检查 Dockerfile 语法
docker build --no-cache -t crypto-news-analyzer-test .

# 2. 检查入口脚本权限
ls -la docker-entrypoint.sh

# 3. 检查 railway.toml 语法
cat railway.toml

# 4. 检查必要文件是否存在
ls -la config.json requirements.txt

# 5. 验证 Python 依赖
docker run --rm crypto-news-analyzer-test python -c "import crypto_news_analyzer; print('OK')"
```

## 🚀 部署步骤

完成上述检查后，按照以下步骤部署：

1. **推送代码到 GitHub**
   ```bash
   git add .
   git commit -m "准备 Railway 部署"
   git push origin main
   ```

2. **在 Railway 创建项目**
   - 访问 https://railway.app
   - 选择 "Deploy from GitHub repo"
   - 选择你的仓库

3. **配置环境变量**
   - 在 Variables 标签页添加所有必需的环境变量

4. **触发部署**
   - Railway 会自动开始构建和部署

5. **监控部署**
   - 查看 Deployments 标签页的构建日志
   - 确认部署成功

6. **验证运行**
   - 查看应用日志
   - 确认健康检查通过
   - 验证 Telegram 消息发送

## 📊 部署后验证

部署成功后，进行以下验证：

- [ ] 容器成功启动
- [ ] 健康检查通过
- [ ] 日志输出正常
- [ ] Telegram 消息发送成功
- [ ] 数据正确保存（如果配置了 Volume）

## 🐛 故障排查

如果部署失败，按以下顺序排查：

1. **查看构建日志** - 检查 Docker 构建是否成功
2. **查看应用日志** - 检查应用启动是否正常
3. **验证环境变量** - 确认所有必需的环境变量已设置
4. **检查 API 连接** - 验证外部 API 是否可访问
5. **查看健康检查** - 确认健康检查配置是否合理

## 📚 相关文档

- [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) - 详细部署指南
- [README.md](./README.md) - 项目说明
- [.env.docker.template](./.env.docker.template) - 环境变量模板
