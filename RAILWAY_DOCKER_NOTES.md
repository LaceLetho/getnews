# Railway Docker 部署说明

## Railway 不支持 Docker Compose

Railway 平台**不支持 Docker Compose**。根据 [Railway 官方社区](https://station.railway.com/questions/can-i-deploy-using-docker-compose-in-rai-bd39da16) 的说明，需要将 docker-compose 中的服务手动拆分为独立的 Railway 服务。

## 已移除的文件

为了适配 Railway 部署，已移除以下 docker-compose 相关文件：

- `docker-compose.yml` - Docker Compose 配置文件
- `docker-build.sh` - 包含 docker-compose 命令的构建脚本
- `DOCKER.md` - Docker Compose 部署文档

## 保留的 Docker 文件

以下文件已保留，可直接用于 Railway 部署：

- `Dockerfile` - Railway 支持标准 Dockerfile
- `docker-entrypoint.sh` - 容器入口脚本
- `.dockerignore` - Docker 构建忽略文件

## Railway 部署方式

### 1. 使用 Dockerfile 部署

Railway 会自动检测项目根目录的 `Dockerfile` 并使用它构建镜像。

### 2. 运行模式

通过 Railway 的环境变量或启动命令配置运行模式：

```bash
# 一次性执行模式
/app/docker-entrypoint.sh once

# 定时调度模式（推荐用于 Railway）
/app/docker-entrypoint.sh schedule
```

### 3. 环境变量配置

在 Railway Dashboard 中配置以下环境变量：

**必需：**
- `LLM_API_KEY` - LLM API 密钥
- `TELEGRAM_BOT_TOKEN` - Telegram Bot Token
- `TELEGRAM_CHANNEL_ID` - Telegram 频道 ID

**可选：**
- `X_CT0` - X/Twitter CT0 Token
- `X_AUTH_TOKEN` - X/Twitter Auth Token
- `TIME_WINDOW_HOURS` - 时间窗口（默认 24 小时）
- `EXECUTION_INTERVAL` - 执行间隔（默认 21600 秒 = 6 小时）

### 4. 数据持久化

如需持久化数据，在 Railway 中创建 Volume 并挂载到：
- `/app/data` - 数据库文件
- `/app/logs` - 日志文件

## 本地测试

### 使用 uv 直接运行（推荐）

```bash
# 复制环境变量模板
cp .env.template .env

# 编辑 .env 填入实际配置
# 然后运行
uv run python -m crypto_news_analyzer.main
```

### 使用 Docker 测试

```bash
# 构建镜像
docker build -t crypto-news-analyzer .

# 一次性执行
docker run --rm \
  -e LLM_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHANNEL_ID=your_channel \
  crypto-news-analyzer once

# 定时调度模式
docker run --rm \
  -e LLM_API_KEY=your_key \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHANNEL_ID=your_channel \
  crypto-news-analyzer schedule
```

## 相关文档

- [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) - Railway 详细部署指南
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - 部署检查清单
- [.env.template](./.env.template) - 环境变量模板
