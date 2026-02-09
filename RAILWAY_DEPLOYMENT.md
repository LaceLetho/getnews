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

### 4. 验证部署

部署成功后，检查日志应该看到：

```
[INFO] 启动加密货币新闻分析工具容器
[INFO] 容器版本: 1.0.0
[INFO] 验证环境变量配置...
[INFO] 环境验证通过
[INFO] 启动定时调度模式
```

## 常见问题

### Q: 为什么移除了健康检查端点？

A: 本应用是后台 worker，不提供 HTTP 服务。Railway 会通过进程是否运行来判断服务健康。

### Q: 如何查看应用日志？

A: 在 Railway 控制台的 "Deployments" 标签页查看实时日志。

### Q: 应用多久执行一次？

A: 默认每小时执行一次（3600秒），可通过 `EXECUTION_INTERVAL` 环境变量调整。

### Q: 如何手动触发执行？

A: 在 Railway 控制台重启服务，或使用 Railway CLI：
```bash
railway run /app/docker-entrypoint.sh once
```

## 监控建议

1. **日志监控**：定期检查 Railway 日志确保任务正常执行
2. **Telegram通知**：配置正确后会收到分析报告
3. **重启策略**：已配置失败自动重启，最多重试3次

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
