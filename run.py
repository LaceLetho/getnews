#!/usr/bin/env python3
"""
加密货币新闻分析工具 - 运行脚本

支持一次性执行和定时调度两种模式。
"""

import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto_news_analyzer.main import main

if __name__ == "__main__":
    main()