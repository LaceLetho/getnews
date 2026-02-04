#!/bin/bash

# 加密货币新闻分析工具 Docker 构建脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker环境
check_docker() {
    log_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行，请启动Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    log_info "Docker环境检查通过"
}

# 清理旧镜像
cleanup_old_images() {
    log_info "清理旧镜像..."
    
    # 停止并删除旧容器
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # 删除旧镜像
    docker rmi crypto-news-analyzer:latest 2>/dev/null || true
    
    # 清理未使用的镜像
    docker image prune -f
    
    log_info "清理完成"
}

# 构建镜像
build_image() {
    log_info "开始构建Docker镜像..."
    
    # 构建镜像
    docker build \
        --tag crypto-news-analyzer:latest \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --progress=plain \
        .
    
    if [ $? -eq 0 ]; then
        log_info "镜像构建成功"
    else
        log_error "镜像构建失败"
        exit 1
    fi
}

# 验证镜像
verify_image() {
    log_info "验证镜像..."
    
    # 检查镜像是否存在
    if ! docker images | grep -q "crypto-news-analyzer"; then
        log_error "镜像验证失败：镜像不存在"
        exit 1
    fi
    
    # 运行基本测试
    log_info "运行基本测试..."
    docker run --rm crypto-news-analyzer:latest python -c "
import sys
sys.path.insert(0, '/app')
from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.crawlers.bird_dependency_manager import BirdDependencyManager
print('✓ 核心模块导入成功')
print('✓ Bird工具依赖管理器可用')
"
    
    if [ $? -eq 0 ]; then
        log_info "镜像验证成功"
    else
        log_error "镜像验证失败"
        exit 1
    fi
}

# 显示使用说明
show_usage() {
    log_info "=== Docker镜像构建完成 ==="
    echo
    log_info "使用方法："
    echo
    echo "1. 一次性执行："
    echo "   docker-compose run --rm crypto-news-analyzer"
    echo
    echo "2. 定时调度模式："
    echo "   docker-compose --profile scheduler up -d"
    echo
    echo "3. 查看日志："
    echo "   docker-compose logs -f crypto-news-analyzer"
    echo
    echo "4. 停止服务："
    echo "   docker-compose down"
    echo
    echo "5. 清理数据："
    echo "   docker-compose down -v"
    echo
    log_info "配置文件："
    echo "  - 主配置: ./config.json"
    echo "  - 环境变量: ./.env.docker"
    echo "  - 提示词配置: ./prompts/"
    echo
    log_info "数据目录："
    echo "  - 数据库: ./data/"
    echo "  - 日志: ./logs/"
    echo
    log_warn "注意事项："
    echo "  - 请确保已设置X/Twitter认证环境变量"
    echo "  - 请确保已设置LLM API密钥"
    echo "  - 请确保已设置Telegram Bot配置"
}

# 主函数
main() {
    log_info "开始构建加密货币新闻分析工具Docker镜像"
    
    # 检查参数
    CLEAN_BUILD=false
    if [[ "$1" == "--clean" ]]; then
        CLEAN_BUILD=true
        log_info "启用清理构建模式"
    fi
    
    # 执行构建流程
    check_docker
    
    if [[ "$CLEAN_BUILD" == "true" ]]; then
        cleanup_old_images
    fi
    
    build_image
    verify_image
    show_usage
    
    log_info "构建流程完成！"
}

# 执行主函数
main "$@"