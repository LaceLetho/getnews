# Docker 部署指南

本文档介绍如何使用Docker部署加密货币新闻分析工具。

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

## 快速开始

### 1. 构建镜像

```bash
# 基础构建
./docker-build.sh

# 清理构建（删除旧镜像）
./docker-build.sh --clean
```

### 2. 配置环境变量

编辑 `.env.docker` 文件，设置必要的认证信息：

```bash
# X/Twitter认证
x_ct0=your_ct0_token_here
x_auth_token=your_auth_token_here

# LLM API配置
llm_api_key=your_llm_api_key_here

# Telegram配置
telegram_bot_token=your_telegram_bot_token_here
telegram_channel_id=your_channel_id_here
```

### 3. 运行容器

#### 一次性执行模式

```bash
# 使用docker-compose（推荐）
docker-compose run --rm crypto-news-analyzer

# 直接使用docker
docker run --rm \
  --env-file .env.docker \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  crypto-news-analyzer:latest once
```

#### 定时调度模式

```bash
# 启动定时调度服务
docker-compose --profile scheduler up -d

# 查看日志
docker-compose logs -f crypto-news-scheduler

# 停止服务
docker-compose --profile scheduler down
```

## 配置说明

### 环境变量配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `TIME_WINDOW_HOURS` | 时间窗口（小时） | 24 | 否 |
| `EXECUTION_INTERVAL` | 执行间隔（秒） | 3600 | 否 |
| `x_ct0` | X/Twitter CT0令牌 | - | 是 |
| `x_auth_token` | X/Twitter认证令牌 | - | 是 |
| `llm_api_key` | LLM API密钥 | - | 是 |
| `telegram_bot_token` | Telegram Bot令牌 | - | 是 |
| `telegram_channel_id` | Telegram频道ID | - | 是 |

### Bird工具配置

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `BIRD_EXECUTABLE_PATH` | Bird工具路径 | bird |
| `BIRD_TIMEOUT_SECONDS` | 超时时间 | 300 |
| `BIRD_MAX_RETRIES` | 最大重试次数 | 3 |
| `BIRD_OUTPUT_FORMAT` | 输出格式 | json |
| `BIRD_RATE_LIMIT_DELAY` | 速率限制延迟 | 1.0 |
| `BIRD_CONFIG_PATH` | 配置文件路径 | /home/appuser/.bird/config.json |

### 数据卷挂载

- `./config.json` → `/app/config.json` (只读)
- `./prompts/` → `/app/prompts/` (只读)
- `./data/` → `/app/data/` (读写)
- `./logs/` → `/app/logs/` (读写)
- `bird_config` → `/home/appuser/.bird/` (读写)

## 运行模式

### 1. 一次性执行模式 (once)

执行完整的数据收集和分析工作流后自动退出。

```bash
docker-compose run --rm crypto-news-analyzer once
```

### 2. 定时调度模式 (schedule)

持续运行，按配置的间隔执行任务。

```bash
docker-compose --profile scheduler up -d
```

### 3. 命令监听模式 (command)

监听Telegram命令，手动触发执行（未来实现）。

```bash
docker-compose --profile commander up -d
```

## 监控和日志

### 查看日志

```bash
# 查看实时日志
docker-compose logs -f crypto-news-analyzer

# 查看最近100行日志
docker-compose logs --tail 100 crypto-news-analyzer

# 查看特定时间的日志
docker-compose logs --since "2024-01-01T00:00:00" crypto-news-analyzer
```

### 健康检查

```bash
# 检查容器健康状态
docker-compose ps

# 查看健康检查详情
docker inspect crypto-news-analyzer | jq '.[0].State.Health'
```

### 资源监控

```bash
# 查看资源使用情况
docker stats crypto-news-analyzer

# 查看容器详细信息
docker-compose top
```

## 故障排除

### 常见问题

#### 1. Bird工具认证失败

**症状**: 日志显示"bird工具不可用"或认证错误

**解决方案**:
1. 检查环境变量 `x_ct0` 和 `x_auth_token` 是否正确设置
2. 验证X/Twitter账户状态
3. 检查bird工具配置文件

```bash
# 进入容器检查bird工具
docker-compose exec crypto-news-analyzer bird --version
docker-compose exec crypto-news-analyzer bird --help
```

#### 2. 内存不足

**症状**: 容器被OOM Killer终止

**解决方案**:
1. 增加Docker内存限制
2. 调整docker-compose.yml中的资源限制
3. 减少批处理大小

```yaml
deploy:
  resources:
    limits:
      memory: 2G  # 增加内存限制
```

#### 3. 网络连接问题

**症状**: API调用失败或超时

**解决方案**:
1. 检查网络连接
2. 调整超时设置
3. 检查防火墙配置

```bash
# 测试网络连接
docker-compose exec crypto-news-analyzer curl -I https://api.openai.com
docker-compose exec crypto-news-analyzer curl -I https://api.telegram.org
```

#### 4. 权限问题

**症状**: 无法写入数据或日志文件

**解决方案**:
1. 检查目录权限
2. 确保数据目录存在

```bash
# 创建并设置权限
mkdir -p data logs
chmod 755 data logs
```

### 调试模式

启用调试模式获取更详细的日志：

```bash
# 设置调试环境变量
echo "DEBUG=true" >> .env.docker

# 重新启动容器
docker-compose down
docker-compose up -d
```

### 清理和重置

```bash
# 停止所有服务
docker-compose down

# 清理数据卷（注意：会删除所有数据）
docker-compose down -v

# 清理镜像
docker rmi crypto-news-analyzer:latest

# 完全重建
./docker-build.sh --clean
```

## 生产部署建议

### 1. 安全配置

- 使用Docker secrets管理敏感信息
- 定期更新基础镜像
- 启用容器安全扫描
- 限制容器权限

### 2. 监控和告警

- 集成Prometheus监控
- 配置日志聚合（如ELK Stack）
- 设置健康检查告警
- 监控资源使用情况

### 3. 备份策略

- 定期备份数据卷
- 备份配置文件
- 测试恢复流程

### 4. 高可用性

- 使用Docker Swarm或Kubernetes
- 配置负载均衡
- 实现故障转移

## 支持

如遇到问题，请：

1. 查看日志文件
2. 检查配置文件
3. 验证环境变量
4. 参考故障排除部分

更多信息请参考项目文档或提交Issue。