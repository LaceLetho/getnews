# Railway 部署指南

本文档说明如何将加密货币新闻分析工具部署到 Railway 平台。

## 前置准备

### 1. 安装 Railway CLI（可选）

```bash
# macOS
brew install railway

# 或使用 npm
npm install -g @railway/cli
```

### 2. 准备必要的 API 密钥

在部署前，请确保已获取以下 API 密钥：

- **LLM_API_KEY**: MiniMax API 密钥（必需）
- **TELEGRAM_BOT_TOKEN**: Telegram Bot Token（必需）
- **TELEGRAM_CHANNEL_ID**: Telegram 频道 ID（必需）
- **X_CT0**: X/Twitter CT0 Token（可选）
- **X_AUTH_TOKEN**: X/Twitter Auth Token（可选）

## 部署方式

### 方式一：通过 Railway Dashboard（推荐）

1. **登录 Railway**
   - 访问 https://railway.app
   - 使用 GitHub 账号登录

2. **创建新项目**
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 授权并选择你的仓库

3. **配置环境变量**
   
   在 Railway Dashboard 的 Variables 标签页添加以下环境变量：

   ```bash
   # 必需配置
   LLM_API_KEY=your_minimax_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHANNEL_ID=your_channel_id
   
   # 可选配置
   X_CT0=your_x_ct0_token
   X_AUTH_TOKEN=your_x_auth_token
   
   # 运行配置
   TIME_WINDOW_HOURS=24
   EXECUTION_INTERVAL=21600
   CONFIG_PATH=/app/config.json
   
   # 调试配置（可选）
   DEBUG=false
   PYTHONLOGLEVEL=INFO
   ```

4. **配置部署设置**
   
   Railway 会自动检测 `railway.toml` 文件并使用其中的配置：
   - Builder: DOCKERFILE
   - Start Command: `/app/docker-entrypoint.sh schedule`
   - Restart Policy: ON_FAILURE (最多重试 3 次)

5. **部署**
   - 点击 "Deploy" 按钮
   - Railway 会自动构建 Docker 镜像并部署

### 方式二：通过 Railway CLI

1. **登录 Railway**
   ```bash
   railway login
   ```

2. **初始化项目**
   ```bash
   railway init
   ```

3. **设置环境变量**
   ```bash
   railway variables set LLM_API_KEY=your_minimax_api_key
   railway variables set TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   railway variables set TELEGRAM_CHANNEL_ID=your_channel_id
   railway variables set TIME_WINDOW_HOURS=24
   railway variables set EXECUTION_INTERVAL=21600
   ```

4. **部署**
   ```bash
   railway up
   ```

## 配置说明

### railway.toml 配置

项目已包含 `railway.toml` 配置文件，主要配置如下：

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "/app/docker-entrypoint.sh schedule"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
healthcheckTimeout = 300
```

### 运行模式

系统支持两种运行模式：

1. **定时调度模式（默认）**: `schedule`
   - 按照 `EXECUTION_INTERVAL` 设置的间隔定期执行
   - 适合持续运行的场景

2. **一次性执行模式**: `once`
   - 执行一次后退出
   - 适合配合 Railway 的 Cron 功能使用

如需切换到一次性执行模式，可以在 `railway.toml` 中修改：

```toml
[deploy]
startCommand = "/app/docker-entrypoint.sh once"
```

或使用 Railway 的 Cron 功能：

```toml
[deploy]
cronSchedule = "0 */6 * * *"  # 每6小时执行一次
startCommand = "/app/docker-entrypoint.sh once"
```

## 数据持久化

### Railway Volumes

Railway 支持持久化存储，如需保存数据：

1. 在 Railway Dashboard 中创建 Volume
2. 挂载到 `/app/data` 目录
3. 系统会自动将数据库和日志保存到该目录

### 配置文件

默认使用容器内的 `config.json`。如需自定义配置：

1. 在 Railway Dashboard 上传自定义 `config.json`
2. 或通过环境变量覆盖配置项

## 监控和日志

### 查看日志

**通过 Dashboard:**
- 在 Railway Dashboard 的 Deployments 标签页查看实时日志

**通过 CLI:**
```bash
railway logs
```

### 健康检查

系统包含健康检查机制：
- 检查间隔: 30 秒
- 超时时间: 10 秒
- 重试次数: 3 次
- 启动等待: 30 秒

如果健康检查失败，Railway 会自动重启服务。

## 成本估算

Railway 采用按使用量计费：

- **免费额度**: 每月 $5 免费额度
- **计费项目**:
  - CPU 使用时间
  - 内存使用
  - 网络流量
  - 存储空间

本项目的资源限制：
- 内存: 512MB - 1GB
- CPU: 0.25 - 0.5 核心

预计每月成本: $5-15（取决于执行频率）

## 故障排查

### 部署失败

1. **检查 Dockerfile**
   ```bash
   # 本地测试构建
   docker build -t crypto-news-analyzer .
   ```

2. **检查环境变量**
   - 确保所有必需的环境变量已设置
   - 检查 API 密钥是否有效

3. **查看构建日志**
   - 在 Railway Dashboard 查看详细的构建日志

### 运行时错误

1. **查看应用日志**
   ```bash
   railway logs
   ```

2. **检查健康检查状态**
   - 在 Railway Dashboard 查看 Deployments 状态

3. **验证 API 连接**
   - 检查 LLM API 是否可访问
   - 检查 Telegram Bot 是否配置正确

### 常见问题

**Q: 容器启动后立即退出**
- 检查 `startCommand` 是否正确
- 确认 `docker-entrypoint.sh` 有执行权限
- 查看日志了解具体错误

**Q: 健康检查失败**
- 增加 `healthcheckTimeout` 时间
- 检查应用是否正常初始化
- 查看应用日志排查问题

**Q: 数据丢失**
- 确保已配置 Railway Volume
- 检查数据目录挂载是否正确

## 更新部署

### 自动部署

Railway 支持 GitHub 自动部署：
- 推送到主分支会自动触发部署
- 可在 Settings 中配置部署分支

### 手动部署

```bash
# 通过 CLI
railway up

# 或在 Dashboard 中点击 "Redeploy"
```

## 安全建议

1. **环境变量管理**
   - 不要在代码中硬编码敏感信息
   - 使用 Railway 的环境变量功能
   - 定期轮换 API 密钥

2. **访问控制**
   - 限制 Railway 项目的访问权限
   - 使用团队功能管理协作者

3. **日志安全**
   - 确保日志中不包含敏感信息
   - 定期清理旧日志

## 参考资源

- [Railway 官方文档](https://docs.railway.com)
- [Railway CLI 文档](https://docs.railway.com/reference/cli-api)
- [Docker 最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [项目 README](./README.md)
