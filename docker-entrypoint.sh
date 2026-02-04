#!/bin/bash
set -e

# 加密货币新闻分析工具 Docker 入口点脚本
# 支持一次性执行模式和定时调度模式

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
    fi
}

# 信号处理函数
cleanup() {
    log_info "接收到停止信号，正在清理资源..."
    if [[ -n "$MAIN_PID" ]]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    log_info "清理完成，退出"
    exit 0
}

# 设置信号处理
trap cleanup SIGTERM SIGINT

# 验证环境变量
validate_environment() {
    log_info "验证环境变量配置..."
    
    local validation_failed=false
    
    # 验证数值类型的环境变量
    if [[ -n "$TIME_WINDOW_HOURS" ]] && ! [[ "$TIME_WINDOW_HOURS" =~ ^[0-9]+$ ]]; then
        log_error "TIME_WINDOW_HOURS 必须是正整数，当前值: $TIME_WINDOW_HOURS"
        validation_failed=true
    fi
    
    if [[ -n "$EXECUTION_INTERVAL" ]] && ! [[ "$EXECUTION_INTERVAL" =~ ^[0-9]+$ ]]; then
        log_error "EXECUTION_INTERVAL 必须是正整数，当前值: $EXECUTION_INTERVAL"
        validation_failed=true
    fi
    
    # 验证配置文件路径
    if [[ -n "$CONFIG_PATH" ]] && [[ ! -f "$CONFIG_PATH" ]]; then
        log_warn "配置文件不存在: $CONFIG_PATH，将使用默认配置"
    fi
    
    # 验证必要目录
    local required_dirs=("/app/data" "/app/logs" "/app/prompts")
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_info "创建目录: $dir"
            mkdir -p "$dir"
        fi
    done
    
    # 验证权限
    if [[ ! -w "/app/data" ]]; then
        log_error "数据目录不可写: /app/data"
        validation_failed=true
    fi
    
    if [[ ! -w "/app/logs" ]]; then
        log_error "日志目录不可写: /app/logs"
        validation_failed=true
    fi
    
    if [[ "$validation_failed" == "true" ]]; then
        log_error "环境验证失败，退出"
        exit 1
    fi
    
    log_info "环境验证通过"
}

# 显示配置信息
show_configuration() {
    log_info "=== 容器配置信息 ==="
    log_info "运行模式: ${1:-once}"
    log_info "时间窗口: ${TIME_WINDOW_HOURS:-24} 小时"
    log_info "执行间隔: ${EXECUTION_INTERVAL:-3600} 秒"
    log_info "配置文件: ${CONFIG_PATH:-/app/config.json}"
    log_info "Python路径: ${PYTHONPATH:-/app}"
    log_info "用户: $(whoami)"
    log_info "工作目录: $(pwd)"
    log_info "========================"
}

# 检查系统健康状态
health_check() {
    log_debug "执行健康检查..."
    
    # 检查Python环境
    if ! python -c "import sys; print(f'Python {sys.version}')" 2>/dev/null; then
        log_error "Python环境检查失败"
        return 1
    fi
    
    # 检查核心模块
    if ! python -c "from crypto_news_analyzer.main import main" 2>/dev/null; then
        log_error "核心模块导入失败"
        return 1
    fi
    
    log_debug "健康检查通过"
    return 0
}

# 主函数
main() {
    local mode="${1:-once}"
    
    log_info "启动加密货币新闻分析工具容器"
    log_info "容器版本: 1.0.0"
    
    # 验证环境
    validate_environment
    
    # 显示配置
    show_configuration "$mode"
    
    # 健康检查
    if ! health_check; then
        log_error "健康检查失败，退出"
        exit 1
    fi
    
    # 设置配置文件路径参数
    local config_arg=""
    if [[ -n "$CONFIG_PATH" ]] && [[ -f "$CONFIG_PATH" ]]; then
        config_arg="--config $CONFIG_PATH"
    fi
    
    # 根据模式执行
    case "$mode" in
        "once"|"one_time")
            log_info "启动一次性执行模式"
            python /app/run.py --mode once $config_arg &
            MAIN_PID=$!
            ;;
        "schedule"|"scheduled")
            log_info "启动定时调度模式"
            log_info "调度间隔: ${EXECUTION_INTERVAL:-3600} 秒"
            python /app/run.py --mode schedule $config_arg &
            MAIN_PID=$!
            ;;
        "command")
            log_info "启动命令监听模式"
            log_warn "命令监听模式尚未实现，使用定时调度模式"
            python /app/run.py --mode schedule $config_arg &
            MAIN_PID=$!
            ;;
        *)
            log_error "未知的运行模式: $mode"
            log_info "支持的模式: once, schedule, command"
            exit 1
            ;;
    esac
    
    # 等待主进程
    log_info "主进程 PID: $MAIN_PID"
    wait "$MAIN_PID"
    local exit_code=$?
    
    log_info "主进程退出，状态码: $exit_code"
    exit $exit_code
}

# 如果脚本被直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi