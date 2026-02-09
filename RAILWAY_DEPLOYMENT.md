# Railway 部署指南

## 问题诊断

### "Service Unavailable" 错误

如果遇到 `Attempt #1 failed with service unavailable` 错误，通常是因为：

1. **HTTP健康检查失败**：Railway 默认期望 web 服务提供 HTTP 端点
2. **端口暴露误导**：暴露端口会让 Railway 认为这是 web 服务
3. **启动时间过长**：应用初始化超过健康检查超时时间

## 解决方案

### 1. 配置为 Worker 服务

本应用是后台任务调度器（worker），不是 web 服务：

- ✅ 已移除 `healthcheckPath` 配置
- ✅ 已移除 `EXPOSE 8080` 端口声明
- ✅ Railway 将通过进程存活状态判断服务健康

### 2. 环境变量配置

在 Railway 项目设置中配置以下环境变量：

```bash
# 必需的环境变量
XAI_API_KEY=your_xai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Bird工具认证（用于Twitter数据）
BIRD_COOKIE_CT0=your_twitter_ct0
BIRD_COOKIE_AUTH_TOKEN=your_twitter_auth_token

# 可选配置
TIME_WINDOW_HOURS=24
EXECUTION_INTERVAL=3600
CONFIG_PATH=/app/config.json
```

### 3. 部署命令

Railway 会自动使用 `railway.toml` 中的配置：

```toml
[deploy]
startCommand = "/app/docker-entrypoint.sh schedule"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**运行模式说明**：

- **schedule 模式（推荐）**：定时调度 + Telegram命令触发的混合模式
  - 自动按配置的间隔执行任务
  - 同时监听Telegram命令（如 `/run`）手动触发执行
  - 两种触发方式共享并发控制，不会冲突
  - 适合生产环境使用

- **once 模式**：执行一次后退出
  - 用于测试或手动触发单次执行
  - 不启动定时调度器和命令监听器

### 4. Telegram命令触发配置

如果要启用Telegram命令触发功能，需要在 `config.json` 中配置：

```json
{
  "telegram_commands": {
    "enabled": true,
    "authorized_users": [
      {
        "user_id": "your_telegram_user_id",
        "username": "your_username",
        "permissions": ["run", "status", "help"]
      }
    ],
    "execution_timeout_minutes": 30,
    "max_concurrent_executions": 1,
    "command_rate_limit": {
      "max_commands_per_hour": 10,
      "cooldown_minutes": 5
    }
  }
}
```

**获取你的Telegram User ID**：
1. 在Telegram中搜索 `@userinfobot`
2. 发送 `/start` 命令
3. Bot会返回你的User ID

**可用命令**：
- `/run` - 立即触发一次执行（不影响定时调度）
- `/status` - 查询系统运行状态
- `/help` - 显示帮助信息

### 5. 验证部署

部署成功后，检查日志应该看到：

```
[INFO] 启动加密货币新闻分析工具容器
[INFO] 容器版本: 1.0.0
[INFO] 验证环境变量配置...
[INFO] 环境验证通过
[INFO] 启动定时调度模式
[INFO] 定时调度器已启动，间隔: 3600 秒
[INFO] 启动Telegram命令监听器...
[INFO] Telegram命令监听器已启动
[INFO] 系统运行在混合模式：定时调度 + 命令触发
[INFO] 等待停止信号 (Ctrl+C 或 SIGTERM)...
```

如果未配置Telegram命令功能，会看到：

```
[INFO] Telegram命令处理器未配置，仅运行定时调度模式
```

## 常见问题

### Q: 为什么移除了健康检查端点？

A: 本应用是后台 worker，不提供 HTTP 服务。Railway 会通过进程是否运行来判断服务健康。

### Q: 如何查看应用日志？

A: 在 Railway 控制台的 "Deployments" 标签页查看实时日志。

### Q: 应用多久执行一次？

A: 默认每小时执行一次（3600秒），可通过 `EXECUTION_INTERVAL` 环境变量调整。

### Q: 如何手动触发执行？

A: 有两种方式：
1. **通过Telegram命令**（推荐）：向Bot发送 `/run` 命令
2. **通过Railway控制台**：重启服务，或使用 Railway CLI：
```bash
railway run /app/docker-entrypoint.sh once
```

### Q: 定时执行和命令触发会冲突吗？

A: 不会。系统使用并发控制机制，确保同一时间只有一个执行在进行。如果定时任务正在执行，命令触发会被拒绝并返回提示信息。

## 监控建议

1. **日志监控**：定期检查 Railway 日志确保任务正常执行
2. **Telegram通知**：配置正确后会收到分析报告
3. **重启策略**：已配置失败自动重启，最多重试3次

## 持久化存储

### 创建 Volume（必须手动操作）

Railway 的 volumes **不能通过配置文件创建**，必须在控制台手动创建：

#### 步骤 1：创建第一个 Volume（数据库）

1. 打开 Railway 项目控制台
2. 按 `⌘K`（Mac）或 `Ctrl+K`（Windows）打开命令面板
3. 输入 "New Volume" 并选择
4. 或者：右键点击项目画布 → 选择 "New Volume"
5. 选择你的服务（crypto-news-analyzer）
6. 配置 Volume：
   - **Mount Path**: `/app/data`
   - 点击 "Add" 创建

#### 步骤 2：创建第二个 Volume（日志）

**重要**：Railway 目前**每个服务只能挂载一个 Volume**。

由于限制，你需要选择：
- **推荐方案**：只创建 `/app/data` volume（数据库最重要）
- 日志可以通过 Railway 控制台查看，不需要持久化

如果未来 Railway 支持多个 volumes，可以按相同步骤创建：
- **Mount Path**: `/app/logs`

### Volume 配置说明

创建 volume 后，Railway 会自动提供环境变量：
- `RAILWAY_VOLUME_NAME` - Volume 名称
- `RAILWAY_VOLUME_MOUNT_PATH` - 挂载路径（如 `/app/data`）

### 存储内容

#### `/app/data` Volume（推荐创建）
- `crypto_news.db` - SQLite 数据库（新闻、分析结果）
- `cache/market_snapshot.json` - 市场快照缓存（30分钟TTL）

#### `/app/logs`（可选，通过 Railway 日志查看）
- 应用日志可以在 Railway 控制台的 "Deployments" → "Logs" 查看
- 不需要持久化存储

### 存储说明

1. **手动创建**：Volumes 必须在 Railway 控制台手动创建（不能通过配置文件）
2. **单 Volume 限制**：每个服务目前只能挂载一个 volume
3. **数据保留**：容器重启、重新部署时数据不会丢失
4. **容量限制**：Railway 免费计划提供 1GB volume 空间
5. **清理策略**：应用配置了自动清理（默认保留30天数据）

### 重要提示

- Volume 在**运行时**挂载，不在构建时挂载
- 如果在构建时写入数据，不会持久化到 volume
- Volume 不会在 pre-deploy 命令时挂载
- **权限说明**：容器以 root 用户运行以匹配 Railway Volume 权限

### 查看存储使用情况

在 Railway 控制台：
1. 点击项目画布上的 Volume 图标
2. 查看 volume 的使用情况和容量
3. Pro 用户可以实时调整 volume 大小（Live Resize）

### 手动清理数据

如果需要清理旧数据：

```bash
# 使用 Railway CLI 连接到容器
railway run bash

# 查看数据库大小
du -sh /app/data/crypto_news.db

# 查看日志大小
du -sh /app/logs/

# 清理30天前的日志（如果需要）
find /app/logs/ -name "*.log" -mtime +30 -delete
```

### 备份建议

定期备份重要数据：

```bash
# 下载数据库文件
railway run cat /app/data/crypto_news.db > backup_$(date +%Y%m%d).db

# 或使用 Railway CLI
railway volume download data ./backup/
```

## 故障排查

如果部署后仍有问题：

1. 检查环境变量是否完整配置
2. 查看 Railway 日志中的错误信息
3. 验证 API keys 是否有效
4. 确认 Telegram bot token 和 chat ID 正确

## 成本优化

- Railway 按使用时间计费
- Worker 服务比 web 服务成本更低
- 可以调整 `EXECUTION_INTERVAL` 减少执行频率
- Volume 存储：免费计划提供 1GB，超出部分按量计费

## Volume 注意事项

1. **手动创建**：必须在 Railway 控制台手动创建，不能通过 `railway.toml` 配置
2. **单 Volume 限制**：目前每个服务只能挂载一个 volume
3. **优先级**：建议只创建 `/app/data` volume（数据库最重要）
4. **数据迁移**：如果之前已部署但没有 volume，旧数据会丢失（新 volume 是空的）
5. **删除服务**：删除 Railway 服务时，volumes 也会被删除（数据永久丢失）
6. **容量监控**：定期检查 volume 使用情况，避免超出配额
7. **权限说明**：容器以 root 用户运行以匹配 Railway Volume 权限（Railway 推荐做法）
