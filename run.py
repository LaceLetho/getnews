#!/usr/bin/env python3
"""
加密货币新闻分析工具 - 运行脚本

薄封装入口，委托到包内主入口。
"""

import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto_news_analyzer.main import main

if __name__ == "__main__":
    main()
