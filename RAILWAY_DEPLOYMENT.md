# Railway 部署指南

本文档说明如何将加密货币新闻分析工具部署到 Railway 平台。

## 前置准备

### 准备 API 密钥

在部署前，请确保已获取以下 API 密钥：

**必需：**
- **LLM_API_KEY**: MiniMax API 密钥（从 https://platform.minimax.io 获取）
- **TELEGRAM_BOT_TOKEN**: Telegram Bot Token
- **TELEGRAM_CHANNEL_ID**: Telegram 频道 ID

**可选：**
- **X_CT0**: X/Twitter CT0 Token
- **X_AUTH_TOKEN**: X/Twitter Auth Token

## 部署步骤

### 1. 登录 Railway

访问 https://railway.app 并使用 GitHub 账号登录。

### 2. 创建新项目

1. 点击 "New Project"
2. 选择 "Deploy from GitHub repo"
3. 授权并选择你的仓库

### 3. 配置环境变量

在 Railway Dashboard 的 **Variables** 标签页添加以下环境变量：

```bash
# 必需配置
LLM_API_KEY=your_minimax_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id

# 可选配置
X_CT0=your_x_ct0_token
X_AUTH_TOKEN=your_x_auth_token

# 运行配置（可选，使用默认值即可）
TIME_WINDOW_HOURS=24
EXECUTION_INTERVAL=21600
```

### 4. 部署

点击 "Deploy" 按钮，Railway 会自动：
- 检测 `Dockerfile` 并构建镜像
- 使用 `railway.toml` 中的配置
- 启动应用并开始定时执行

### 5. 验证部署

在 Railway Dashboard 中：
1. 查看 **Deployments** 标签页确认部署成功
2. 查看 **Logs** 标签页检查应用运行日志
3. 确认 Telegram 频道收到消息

## 运行模式

系统支持两种运行模式：

### 定时调度模式（默认）

应用会持续运行，按照 `EXECUTION_INTERVAL` 设置的间隔（默认 6 小时）定期执行任务。

### 一次性执行模式

如需使用 Railway 的 Cron 功能，可以修改 `railway.toml`：

```toml
[deploy]
cronSchedule = "0 */6 * * *"  # 每6小时执行一次
startCommand = "/app/docker-entrypoint.sh once"
```

## 数据持久化（可选）

如需保存历史数据：

1. 在 Railway Dashboard 中创建 **Volume**
2. 挂载到 `/app/data` 目录
3. 系统会自动将数据库和日志保存到该目录

## 监控和日志

### 查看日志

在 Railway Dashboard 的 **Logs** 标签页可以查看实时日志。

### 健康检查

系统包含自动健康检查机制：
- 检查间隔: 30 秒
- 超时时间: 300 秒
- 失败重启: 最多 3 次

## 成本估算

Railway 采用按使用量计费：

- **免费额度**: 每月 $5 免费额度
- **本项目预计成本**: $5-15/月（取决于执行频率）

资源限制：
- 内存: 512MB - 1GB
- CPU: 0.25 - 0.5 核心

## 故障排查

### 部署失败

1. **检查环境变量**: 确保所有必需的环境变量已正确设置
2. **查看构建日志**: 在 Deployments 标签页查看详细的构建日志
3. **验证 API 密钥**: 确认 MiniMax 和 Telegram API 密钥有效

### 运行时错误

1. **查看应用日志**: 在 Logs 标签页查看错误信息
2. **检查 API 连接**: 确认外部 API 可访问
3. **验证配置**: 检查 `config.json` 配置是否正确

### 常见问题

**Q: 容器启动后立即退出**
- 检查环境变量是否完整
- 查看日志了解具体错误原因

**Q: 健康检查失败**
- 检查应用是否正常初始化
- 查看日志排查启动问题

**Q: 没有收到 Telegram 消息**
- 验证 Bot Token 和 Channel ID 是否正确
- 确认 Bot 已添加到目标频道并有发送权限

## 更新部署

### 自动部署

Railway 支持 GitHub 自动部署：
- 推送代码到主分支会自动触发部署
- 可在 Settings 中配置部署分支

### 手动重新部署

在 Railway Dashboard 中点击 "Redeploy" 按钮。

## 本地测试

在部署到 Railway 前，建议先本地测试：

```bash
# 使用 uv 直接运行（推荐）
cp .env.template .env
# 编辑 .env 填入配置
uv run python -m crypto_news_analyzer.main

# 或使用 Docker 测试
docker build -t crypto-news-analyzer .
docker run --rm \
  -e LLM_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHANNEL_ID=your_channel \
  crypto-news-analyzer once
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

## 参考资源

- [Railway 官方文档](https://docs.railway.com)
- [项目 README](./README.md)
- [MiniMax API 文档](https://platform.minimax.io/document)
