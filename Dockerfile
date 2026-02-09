# 多阶段构建 - 构建阶段
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.11-slim

# 设置标签
LABEL maintainer="crypto-news-analyzer"
LABEL description="加密货币新闻分析工具"
LABEL version="1.0.0"

# 安装Node.js和运行时依赖
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 验证Node.js和npm安装
RUN node --version && npm --version

# 全局安装bird工具
RUN npm install -g @steipete/bird@latest

# 验证bird工具安装
RUN bird --version || echo "Bird工具安装完成，但可能需要配置认证信息"

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建必要的目录并设置权限
RUN mkdir -p /app/data /app/logs /app/prompts /home/appuser/.bird && \
    chown -R appuser:appuser /app /home/appuser && \
    chmod -R 755 /app

# 切换到非root用户
USER appuser

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 默认环境变量（可通过docker run -e 覆盖）
ENV TIME_WINDOW_HOURS=24
ENV EXECUTION_INTERVAL=3600
ENV CONFIG_PATH=/app/config.json

# Bird工具相关环境变量
ENV BIRD_CONFIG_PATH=/home/appuser/.bird/config.json

# 健康检查（用于Docker环境，Railway使用进程存活状态）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); from crypto_news_analyzer.execution_coordinator import MainController; controller = MainController(); status = controller.get_system_status(); sys.exit(0 if status['initialized'] or not status.get('scheduler_running', False) else 1)" || exit 1

# 注意：这是一个后台worker服务，不暴露HTTP端口

# 设置入口点脚本
COPY --chown=appuser:appuser docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 默认命令
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["once"]