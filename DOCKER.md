# Docker 部署指南

本文档详细介绍如何使用 Docker 容器化部署加密货币新闻分析工具。

## 目录

- [快速开始](#快速开始)
- [构建镜像](#构建镜像)
- [运行模式](#运行模式)
- [环境变量配置](#环境变量配置)
- [数据卷挂载](#数据卷挂载)
- [健康检查](#健康检查)
- [安全最佳实践](#安全最佳实践)
- [故障排除](#故障排除)

## 快速开始

### 1. 准备配置文件

复制环境变量模板并填入配置：

```bash
cp .env.docker.template .env.docker
# 编辑 .env.docker 文件，填入实际的API密钥和配置
```

### 2. 构建镜像

```bash
# 使用构建脚本
./docker-build.sh

# 或直接使用 Docker 命令
docker build -t crypto-news-analyzer:latest .
```

### 3. 运行容器

```bash
# 一次性执行
docker run --rm --env-file .env.docker \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  crypto-news-analyzer:latest once

# 定时调度（后台运行）
docker run -d --name crypto-analyzer \
  --env-file .env.docker \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  crypto-news-analyzer:latest schedule
```

## 构建镜像

### 基本构建

```bash
docker build -t crypto-news-analyzer:latest .
```

### 使用构建脚本

构建脚本提供了更多选项和便利功能：

```bash
# 基本构建
./docker-build.sh

# 自定义标签
./docker-build.sh --tag v1.0.0

# 多平台构建
./docker-build.sh --platform linux/amd64,linux/arm64

# 构建并推送到仓库
./docker-build.sh --registry myregistry.com --push

# 不使用缓存
./docker-build.sh --no-cache

# 查看帮助
./docker-build.sh --help
```

### 构建参数

可以通过 `--build-arg` 传递构建时参数：

```bash
docker build --build-arg VERSION=1.0.0 -t crypto-news-analyzer:v1.0.0 .
```

## 运行模式

容器支持三种运行模式：

### 1. 一次性执行模式 (once)

执行完整的数据收集和分析工作流后自动退出：

```bash
docker run --rm --env-file .env.docker \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  crypto-news-analyzer:latest once
```

**适用场景：**
- 手动触发执行
- CI/CD 流水线
- 定时任务（配合 cron）

### 2. 定时调度模式 (schedule)

容器持续运行，按配置的间隔自动执行任务：

```bash
docker run -d --name crypto-analyzer \
  --env-file .env.docker \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  crypto-news-analyzer:latest schedule
```

**适用场景：**
- 生产环境持续运行
- 自动化数据收集
- 服务器部署

### 3. 命令监听模式 (command)

*注：此模式尚未完全实现，当前会回退到定时调度模式*

```bash
docker run -d --name crypto-analyzer \
  --env-file .env.docker \
  crypto-news-analyzer:latest command
```

## 环境变量配置

### 必需配置

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `LLM_API_KEY` | LLM服务API密钥 | `sk-xxx...` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot令牌 | `123456:ABC-DEF...` |
| `TELEGRAM_CHANNEL_ID` | Telegram频道ID | `@mychannel` 或 `-1001234567890` |

### 可选配置

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `TIME_WINDOW_HOURS` | `24` | 数据时间窗口（小时） |
| `EXECUTION_INTERVAL` | `3600` | 执行间隔（秒） |
| `X_CT0` | - | X/Twitter认证参数 |
| `X_AUTH_TOKEN` | - | X/Twitter认证令牌 |
| `DEBUG` | `false` | 启用调试模式 |
| `TZ` | - | 容器时区 |

### 配置文件

除了环境变量，还可以挂载自定义配置文件：

```bash
docker run --rm \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/prompts:/app/prompts \
  crypto-news-analyzer:latest once
```

## 数据卷挂载

### 推荐的卷挂载

```bash
docker run -d \
  -v $(pwd)/data:/app/data \          # 数据库和存储
  -v $(pwd)/logs:/app/logs \          # 日志文件
  -v $(pwd)/config.json:/app/config.json \  # 配置文件
  -v $(pwd)/prompts:/app/prompts \    # 提示词配置
  crypto-news-analyzer:latest schedule
```

### 卷说明

| 挂载点 | 用途 | 是否必需 |
|--------|------|----------|
| `/app/data` | SQLite数据库、缓存文件 | 推荐 |
| `/app/logs` | 应用日志文件 | 推荐 |
| `/app/config.json` | 主配置文件 | 可选 |
| `/app/prompts` | LLM提示词配置 | 可选 |

### 权限注意事项

容器以非root用户（UID 1001）运行，确保挂载的目录有正确的权限：

```bash
# 创建目录并设置权限
mkdir -p data logs
chown -R 1001:1001 data logs

# 或者使用当前用户权限
sudo chown -R $(id -u):$(id -g) data logs
```

## 健康检查

容器内置了健康检查机制，会定期检查：

- 配置文件有效性
- 目录权限
- Python环境
- 系统运行状态
- 日志错误情况

### 查看健康状态

```bash
# 查看容器健康状态
docker ps

# 查看健康检查日志
docker inspect --format='{{json .State.Health}}' crypto-analyzer

# 手动执行健康检查
docker exec crypto-analyzer python /app/docker-healthcheck.py
```

### 健康检查配置

健康检查每30秒执行一次，超时时间10秒，启动期5秒，最多重试3次。

## 安全最佳实践

### 1. 非root用户运行

容器默认以非root用户（UID 1001）运行，提高安全性。

### 2. 最小权限原则

只挂载必需的目录，避免挂载整个文件系统。

### 3. 敏感信息管理

```bash
# 使用 Docker secrets（Docker Swarm）
echo "your_api_key" | docker secret create llm_api_key -

# 使用环境变量文件
docker run --env-file .env.docker crypto-news-analyzer:latest

# 避免在命令行中直接传递敏感信息
# 错误示例：
# docker run -e LLM_API_KEY=sk-xxx... crypto-news-analyzer:latest
```

### 4. 网络安全

```bash
# 使用自定义网络
docker network create crypto-net
docker run --network crypto-net crypto-news-analyzer:latest
```

### 5. 资源限制

```bash
docker run --memory=512m --cpus=1.0 crypto-news-analyzer:latest
```

## 故障排除

### 常见问题

#### 1. 权限错误

```
ERROR: 数据目录不可写: /app/data
```

**解决方案：**
```bash
# 检查目录权限
ls -la data/

# 修复权限
chown -R 1001:1001 data logs
```

#### 2. 配置文件错误

```
ERROR: 配置文件验证失败
```

**解决方案：**
```bash
# 验证配置文件格式
python -m json.tool config.json

# 检查必需字段
grep -E "(time_window_hours|execution_interval|auth)" config.json
```

#### 3. 网络连接问题

```
ERROR: RSS源不可访问
```

**解决方案：**
```bash
# 检查网络连接
docker run --rm crypto-news-analyzer:latest curl -I https://www.panewslab.com

# 检查DNS解析
docker run --rm crypto-news-analyzer:latest nslookup www.panewslab.com
```

#### 4. 内存不足

```
ERROR: 系统资源不足
```

**解决方案：**
```bash
# 增加内存限制
docker run --memory=1g crypto-news-analyzer:latest

# 监控资源使用
docker stats crypto-analyzer
```

### 调试技巧

#### 1. 启用调试模式

```bash
docker run -e DEBUG=true crypto-news-analyzer:latest
```

#### 2. 查看日志

```bash
# 查看容器日志
docker logs crypto-analyzer

# 实时跟踪日志
docker logs -f crypto-analyzer

# 查看应用日志
docker exec crypto-analyzer tail -f /app/logs/crypto_news_analyzer.log
```

#### 3. 进入容器调试

```bash
# 进入运行中的容器
docker exec -it crypto-analyzer /bin/bash

# 运行临时调试容器
docker run -it --entrypoint /bin/bash crypto-news-analyzer:latest
```

#### 4. 检查系统状态

```bash
# 执行健康检查
docker exec crypto-analyzer python /app/docker-healthcheck.py

# 检查进程状态
docker exec crypto-analyzer ps aux

# 检查磁盘使用
docker exec crypto-analyzer df -h
```

#### 5. 验证构建配置

```bash
# 使用构建脚本的内置验证
./docker-build.sh --verbose

# 测试构建（不使用缓存）
docker build --no-cache -t crypto-news-analyzer:test .
```

### 性能优化

#### 1. 镜像优化

- 使用多阶段构建减小镜像大小
- 合理使用 `.dockerignore` 文件
- 选择合适的基础镜像

#### 2. 运行时优化

```bash
# 设置合适的资源限制
docker run --memory=512m --cpus=1.0 crypto-news-analyzer:latest

# 使用 tmpfs 挂载临时目录
docker run --tmpfs /tmp crypto-news-analyzer:latest
```

#### 3. 存储优化

```bash
# 使用命名卷而不是绑定挂载
docker volume create crypto-data
docker run -v crypto-data:/app/data crypto-news-analyzer:latest
```

## 生产环境部署

### 1. 使用 Docker Compose

参考 `docker-compose.yml` 文件进行生产环境部署。

### 2. 监控和日志

```bash
# 集成日志收集
docker run --log-driver=syslog crypto-news-analyzer:latest

# 使用监控工具
docker run --name crypto-analyzer \
  --label prometheus.scrape=true \
  crypto-news-analyzer:latest
```

### 3. 备份和恢复

```bash
# 备份数据
docker run --rm -v crypto-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/crypto-data-backup.tar.gz -C /data .

# 恢复数据
docker run --rm -v crypto-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/crypto-data-backup.tar.gz -C /data
```

## 更新和维护

### 1. 更新镜像

```bash
# 拉取最新镜像
docker pull crypto-news-analyzer:latest

# 停止旧容器
docker stop crypto-analyzer

# 启动新容器
docker run -d --name crypto-analyzer-new \
  --env-file .env.docker \
  -v crypto-data:/app/data \
  crypto-news-analyzer:latest schedule

# 删除旧容器
docker rm crypto-analyzer
docker rename crypto-analyzer-new crypto-analyzer
```

### 2. 清理资源

```bash
# 清理未使用的镜像
docker image prune

# 清理未使用的卷
docker volume prune

# 清理未使用的网络
docker network prune
```

---

如有问题，请查看项目文档或提交 Issue。