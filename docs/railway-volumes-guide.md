# Railway Volumes 快速指南

## 重要提示

⚠️ **Railway Volumes 必须在控制台手动创建，不能通过配置文件创建**

⚠️ **每个服务目前只能挂载一个 Volume**

## 创建 Volume 步骤

### 方法 1：使用命令面板（推荐）

1. 打开 Railway 项目控制台
2. 按 `⌘K`（Mac）或 `Ctrl+K`（Windows/Linux）
3. 输入 "New Volume" 并选择
4. 选择你的服务
5. 设置 Mount Path: `/app/data`
6. 点击 "Add" 创建

### 方法 2：右键菜单

1. 在项目画布空白处右键点击
2. 选择 "New Volume"
3. 选择你的服务
4. 设置 Mount Path: `/app/data`
5. 点击 "Add" 创建

## 推荐配置

由于单 Volume 限制，**只创建数据库 volume**：

```
Mount Path: /app/data
```

这个 volume 会存储：
- `crypto_news.db` - SQLite 数据库
- `cache/` - 市场快照缓存

日志可以通过 Railway 控制台查看，不需要持久化。

## 存储内容

### `/app/data` Volume（推荐创建）
- `crypto_news.db` - SQLite 数据库（新闻、分析结果）
- `cache/market_snapshot.json` - 市场快照缓存（30分钟TTL）

### `/app/logs`（不需要 Volume）
- 日志通过 Railway 控制台查看：Deployments → Logs
- 实时日志流，无需持久化存储

## 验证 Volume

创建后验证：

1. **查看 Volume**
   - 在项目画布上应该看到一个 Volume 图标
   - 点击查看详情和使用情况

2. **检查环境变量**
   
   在本地运行：
   ```bash
   railway variables | grep RAILWAY_VOLUME
   ```
   
   应该看到：
   ```
   RAILWAY_VOLUME_NAME=...
   RAILWAY_VOLUME_MOUNT_PATH=/app/data
   ```

## 常用操作

### 查看数据库内容

**查看本地开发环境的数据库：**
```bash
sqlite3 ./data/crypto_news.db "SELECT COUNT(*) FROM news;"
```

**查看远程 Railway 环境的数据库：**

Railway CLI 的 `railway run` 命令在本地环境执行，无法直接访问远程容器。要查看远程数据库，使用以下方法：

1. **通过 Railway Dashboard**（推荐）
   - 访问 https://railway.app
   - 进入项目 → 服务 → Deployments
   - 使用 Web Terminal 执行：
     ```bash
     sqlite3 /app/data/crypto_news.db "SELECT COUNT(*) FROM news;"
     ```

2. **通过应用日志**
   - 在本地运行：`railway logs`
   - 查看应用执行时的数据库操作日志

### 查看日志

**查看远程日志：**
```bash
railway logs
```

**查看本地日志：**
```bash
tail -f ./logs/crypto_news_analyzer.log
```

### 下载备份

#### 方法 1: 使用 Python HTTP 服务器（最简单）

1. SSH 登录到 Railway 服务器：

2. 在服务器上启动 HTTP 服务器：
```bash
cd /app/data
python3 -m http.server 8080
```

3. 在 Railway 控制台中：
   - 进入服务设置 → Networking
   - 添加公共域名（Generate Domain）
   - 记下生成的 URL（例如：https://your-service.railway.app）

4. 使用 curl 下载（使用 HTTPS，不要加端口号）：
```bash
curl -O https://your-service.railway.app/crypto_news.db
```

   或在浏览器访问（使用 HTTPS）：https://your-service.railway.app/

   会显示文件列表，点击文件即可下载

5. 下载完成后，在 Railway shell 中按 Ctrl+C 停止服务器

#### 方法 2: 使用 uploadserver（支持上传和下载）

1. SSH 登录并安装：
```bash
pip install uploadserver
```

2. 启动服务器：
```bash
cd /app/data
python3 -m uploadserver 8080
```

3. 通过公共 URL 访问下载页面

#### 方法 3: 使用 Railway Volume Dump Template

如果上述方法不可行，使用官方模板：
- 模板地址：https://railway.com/template/EBwdAh
- 需要临时断开 volume 并重新挂载到 dump 服务

### 清理空间

通过 Railway Dashboard 的 Web Terminal：

```bash
# 查看空间使用
du -sh /app/data/*
du -sh /app/logs/*

# 清理旧日志（保留最近7天）
find /app/logs/ -name "*.log" -mtime +7 -delete
```

## 容量管理

### 免费计划限制
- 1GB volume 空间
- 超出部分按量计费

### 应用自动清理
配置在 `config.json`：
```json
{
  "storage": {
    "retention_days": 30,
    "max_storage_mb": 1000,
    "cleanup_frequency": "daily"
  }
}
```

### 手动调整保留期
如果空间不足，可以减少保留天数：
```bash
# 在 Railway 环境变量中设置（如果应用支持）
RETENTION_DAYS=7
```

或修改 `config.json` 后重新部署。

## 故障排查

### Volume 未创建
- 检查 `railway.toml` 语法是否正确
- 确认已推送到 Railway 连接的分支
- 查看部署日志是否有错误

### 数据丢失
- 确认 volume 配置在数据写入前已生效
- 检查 Railway 控制台 volumes 是否存在
- 旧部署的数据不会自动迁移到新 volume

### 空间不足
- 在 Railway 控制台查看 volume 使用情况
- 减少 `retention_days` 配置
- 手动清理旧数据
- 考虑升级 Railway 计划

## 最佳实践

1. **定期备份**：重要数据定期下载备份
2. **监控容量**：设置告警避免超出配额
3. **合理保留**：根据实际需求调整 `retention_days`
4. **日志轮转**：避免日志文件无限增长
