#!/usr/bin/env python3
"""
Token使用追踪示例

展示如何使用TokenUsageTracker记录和查看LLM调用的token使用情况。
重点关注cached_tokens以优化缓存命中率。
"""

import os
from openai import OpenAI
from crypto_news_analyzer.analyzers.token_usage_tracker import TokenUsageTracker

# 初始化追踪器（保存最近50次调用）
tracker = TokenUsageTracker(max_records=50)

# 初始化OpenAI客户端（使用xAI Grok API）
XAI_API_KEY = os.getenv("XAI_API_KEY")
client = OpenAI(base_url="https://api.x.ai/v1", api_key=XAI_API_KEY)

# 进行LLM调用
completion = client.chat.completions.create(
    model="grok-beta",
    messages=[
        {"role": "system", "content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."},
        {"role": "user", "content": "What is the meaning of life, the universe, and everything?"}
    ]
)

# 记录token使用情况
if completion.usage:
    usage = completion.usage
    tracker.record_usage(
        model="grok-beta",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cached_tokens=getattr(usage.prompt_tokens_details, 'cached_tokens', 0) if hasattr(usage, 'prompt_tokens_details') else 0
    )
    
    # 打印原始usage信息
    print("原始Usage信息:")
    print(usage.to_json())
    print()

# 显示统计信息
print(tracker.format_summary())
print()
print(tracker.format_recent_records(count=10))
