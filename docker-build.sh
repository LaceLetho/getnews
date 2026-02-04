#!/bin/bash
set -e

# 加密货币新闻分析工具 Docker 构建脚本
# 提供便捷的容器构建、标签管理和推送功能

# 默认配置
IMAGE_NAME="crypto-news-analyzer"
IMAGE_TAG="latest"
REGISTRY=""
BUILD_ARGS=""
PLATFORM=""
NO_CACHE=false
PUSH=false
VERBOSE=false

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
加密货币新闻分析工具 Docker 构建脚本

用法: $0 [选项]

选项:
    -n, --name NAME         镜像名称 (默认: crypto-news-analyzer)
    -t, --tag TAG          镜像标签 (默认: latest)
    -r, --registry REG     镜像仓库地址
    -p, --platform PLAT    目标平台 (如: linux/amd64,linux/arm64)
    --no-cache             不使用构建缓存
    --push                 构建完成后推送到仓库
    --build-arg ARG        传递构建参数
    -v, --verbose          详细输出
    -h, --help             显示此帮助信息

示例:
    # 基本构建
    $0

    # 构建并推送到仓库
    $0 --registry myregistry.com --push

    # 多平台构建
    $0 --platform linux/amd64,linux/arm64

    # 使用自定义标签
    $0 --tag v1.0.0

    # 不使用缓存构建
    $0 --no-cache

    # 传递构建参数
    $0 --build-arg VERSION=1.0.0
EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -n|--name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -r|--registry)
                REGISTRY="$2"
                shift 2
                ;;
            -p|--platform)
                PLATFORM="$2"
                shift 2
                ;;
            --no-cache)
                NO_CACHE=true
                shift
                ;;
            --push)
                PUSH=true
                shift
                ;;
            --build-arg)
                BUILD_ARGS="$BUILD_ARGS --build-arg $2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 验证环境
validate_environment() {
    log_info "验证构建环境..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在 PATH 中"
        exit 1
    fi
    
    # 检查Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon 未运行"
        exit 1
    fi
    
    # 检查必需文件
    local required_files=("Dockerfile" "requirements.txt" "docker-entrypoint.sh" "docker-healthcheck.py")
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "必需文件不存在: $file"
            exit 1
        fi
    done
    
    # 检查脚本可执行权限
    local executable_files=("docker-entrypoint.sh" "docker-healthcheck.py")
    for file in "${executable_files[@]}"; do
        if [[ ! -x "$file" ]]; then
            log_warn "文件不可执行，正在修复: $file"
            chmod +x "$file"
        fi
    done
    
    # 检查应用程序结构
    local required_dirs=("crypto_news_analyzer" "prompts" "data" "logs")
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_error "必需目录不存在: $dir"
            exit 1
        fi
    done
    
    # 检查核心应用文件
    local core_files=("run.py" "config.json" "crypto_news_analyzer/__init__.py" "crypto_news_analyzer/main.py")
    for file in "${core_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "核心应用文件不存在: $file"
            exit 1
        fi
    done
    
    log_info "环境验证通过"
}

# 构建镜像
build_image() {
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$full_image_name"
    fi
    
    log_info "开始构建镜像: $full_image_name"
    
    # 构建Docker命令
    local docker_cmd="docker build"
    
    # 添加构建参数
    if [[ "$NO_CACHE" == "true" ]]; then
        docker_cmd="$docker_cmd --no-cache"
    fi
    
    if [[ -n "$PLATFORM" ]]; then
        docker_cmd="$docker_cmd --platform $PLATFORM"
    fi
    
    if [[ -n "$BUILD_ARGS" ]]; then
        docker_cmd="$docker_cmd $BUILD_ARGS"
    fi
    
    # 添加标签
    docker_cmd="$docker_cmd -t $full_image_name"
    
    # 添加构建上下文
    docker_cmd="$docker_cmd ."
    
    log_debug "执行命令: $docker_cmd"
    
    # 执行构建
    if [[ "$VERBOSE" == "true" ]]; then
        eval $docker_cmd
    else
        eval $docker_cmd > /dev/null
    fi
    
    if [[ $? -eq 0 ]]; then
        log_info "镜像构建成功: $full_image_name"
    else
        log_error "镜像构建失败"
        exit 1
    fi
    
    # 显示镜像信息
    local image_size=$(docker images --format "table {{.Size}}" "$full_image_name" | tail -n 1)
    log_info "镜像大小: $image_size"
}

# 推送镜像
push_image() {
    if [[ "$PUSH" != "true" ]]; then
        return
    fi
    
    if [[ -z "$REGISTRY" ]]; then
        log_warn "未指定仓库地址，跳过推送"
        return
    fi
    
    local full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    
    log_info "推送镜像到仓库: $full_image_name"
    
    if docker push "$full_image_name"; then
        log_info "镜像推送成功"
    else
        log_error "镜像推送失败"
        exit 1
    fi
}

# 显示构建信息
show_build_info() {
    log_info "=== 构建配置 ==="
    log_info "镜像名称: $IMAGE_NAME"
    log_info "镜像标签: $IMAGE_TAG"
    log_info "仓库地址: ${REGISTRY:-未设置}"
    log_info "目标平台: ${PLATFORM:-默认}"
    log_info "使用缓存: $([ "$NO_CACHE" == "true" ] && echo "否" || echo "是")"
    log_info "推送镜像: $([ "$PUSH" == "true" ] && echo "是" || echo "否")"
    log_info "构建参数: ${BUILD_ARGS:-无}"
    log_info "=================="
}

# 清理函数
cleanup() {
    log_info "清理临时文件..."
    # 这里可以添加清理逻辑
}

# 主函数
main() {
    # 设置清理陷阱
    trap cleanup EXIT
    
    # 解析参数
    parse_args "$@"
    
    # 显示构建信息
    show_build_info
    
    # 验证环境
    validate_environment
    
    # 构建镜像
    build_image
    
    # 推送镜像
    push_image
    
    log_info "构建完成！"
    
    # 显示使用示例
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$full_image_name"
    fi
    
    echo
    log_info "使用示例:"
    echo "  # 一次性执行"
    echo "  docker run --rm -v \$(pwd)/config.json:/app/config.json $full_image_name once"
    echo
    echo "  # 定时调度"
    echo "  docker run -d -v \$(pwd)/config.json:/app/config.json $full_image_name schedule"
    echo
    echo "  # 使用环境变量"
    echo "  docker run --rm --env-file .env.docker $full_image_name once"
}

# 如果脚本被直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi