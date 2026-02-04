#!/usr/bin/env python3
"""
Docker容器健康检查脚本

检查容器内应用程序的健康状态，用于Docker HEALTHCHECK指令。
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/app')

try:
    from crypto_news_analyzer.execution_coordinator import MainController
    from crypto_news_analyzer.config.manager import ConfigManager
except ImportError as e:
    print(f"模块导入失败: {e}")
    sys.exit(1)


def check_config_file():
    """检查配置文件是否存在且有效"""
    config_path = os.getenv('CONFIG_PATH', '/app/config.json')
    
    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        return False
    
    try:
        config_manager = ConfigManager(config_path)
        config_data = config_manager.load_config()
        
        # 检查必需的配置项
        required_keys = ['time_window_hours', 'execution_interval', 'storage', 'auth']
        for key in required_keys:
            if key not in config_data:
                print(f"配置文件缺少必需项: {key}")
                return False
        
        return True
    except Exception as e:
        print(f"配置文件验证失败: {e}")
        return False


def check_directories():
    """检查必需的目录是否存在且可写"""
    required_dirs = ['/app/data', '/app/logs', '/app/prompts']
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            print(f"目录不存在: {dir_path}")
            return False
        
        if not os.access(dir_path, os.W_OK):
            print(f"目录不可写: {dir_path}")
            return False
    
    return True


def check_python_environment():
    """检查Python环境和依赖"""
    try:
        # 检查核心模块
        import requests
        import feedparser
        import sqlite3
        
        # 检查应用模块
        from crypto_news_analyzer.main import main
        from crypto_news_analyzer.storage.data_manager import DataManager
        from crypto_news_analyzer.crawlers.rss_crawler import RSSCrawler
        
        return True
    except ImportError as e:
        print(f"Python环境检查失败: {e}")
        return False


def check_system_status():
    """检查系统运行状态"""
    try:
        controller = MainController()
        status = controller.get_system_status()
        
        # 如果调度器正在运行，检查是否正常
        if status.get('scheduler_running', False):
            # 调度器运行中，检查是否有异常
            current_exec = status.get('current_execution')
            if current_exec and current_exec.get('status') == 'failed':
                print("当前执行失败")
                return False
        
        return True
    except Exception as e:
        print(f"系统状态检查失败: {e}")
        return False


def check_recent_logs():
    """检查最近的日志是否有严重错误"""
    log_file = '/app/logs/crypto_news_analyzer.log'
    
    if not os.path.exists(log_file):
        # 日志文件不存在不算错误（可能是首次运行）
        return True
    
    try:
        # 检查最近5分钟的日志
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 检查最近的错误日志
        recent_errors = 0
        for line in reversed(lines[-100:]):  # 检查最后100行
            if 'ERROR' in line or 'CRITICAL' in line:
                recent_errors += 1
                if recent_errors > 5:  # 如果最近有太多错误
                    print("检测到过多的错误日志")
                    return False
        
        return True
    except Exception as e:
        print(f"日志检查失败: {e}")
        return True  # 日志检查失败不影响健康状态


def main():
    """主健康检查函数"""
    print("开始容器健康检查...")
    
    checks = [
        ("配置文件", check_config_file),
        ("目录权限", check_directories),
        ("Python环境", check_python_environment),
        ("系统状态", check_system_status),
        ("日志检查", check_recent_logs),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            if check_func():
                print(f"✓ {check_name}: 通过")
            else:
                print(f"✗ {check_name}: 失败")
                all_passed = False
        except Exception as e:
            print(f"✗ {check_name}: 异常 - {e}")
            all_passed = False
    
    if all_passed:
        print("健康检查通过")
        sys.exit(0)
    else:
        print("健康检查失败")
        sys.exit(1)


if __name__ == "__main__":
    main()