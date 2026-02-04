#!/usr/bin/env python3
"""
调试RSS爬取问题的脚本
"""

import feedparser
import requests
from datetime import datetime, timedelta
from dateutil import parser as date_parser

def test_rss_source(url, name):
    print(f"\n=== 测试RSS源: {name} ===")
    print(f"URL: {url}")
    
    try:
        # 获取RSS内容
        response = requests.get(url, timeout=10)
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"HTTP请求失败: {response.status_code}")
            return
        
        # 解析RSS
        feed = feedparser.parse(response.content)
        
        print(f"RSS标题: {feed.feed.get('title', 'N/A')}")
        print(f"条目总数: {len(feed.entries)}")
        
        if feed.bozo:
            print(f"RSS解析警告: {feed.bozo_exception}")
        
        # 检查最近的条目
        cutoff_time = datetime.now() - timedelta(hours=4)
        print(f"时间窗口截止时间: {cutoff_time}")
        
        recent_count = 0
        for i, entry in enumerate(feed.entries[:10]):  # 只检查前10条
            print(f"\n--- 条目 {i+1} ---")
            print(f"标题: {entry.get('title', 'N/A')[:100]}...")
            
            # 检查时间字段
            time_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
            publish_time = None
            
            for field in time_fields:
                time_struct = getattr(entry, field, None)
                if time_struct:
                    try:
                        publish_time = datetime(*time_struct[:6])
                        print(f"发布时间 ({field}): {publish_time}")
                        break
                    except:
                        continue
            
            if not publish_time:
                # 尝试字符串时间
                string_fields = ['published', 'updated', 'created']
                for field in string_fields:
                    time_str = getattr(entry, field, '')
                    if time_str:
                        try:
                            publish_time = date_parser.parse(time_str)
                            print(f"发布时间 ({field}): {publish_time}")
                            break
                        except:
                            continue
            
            if publish_time:
                is_recent = publish_time >= cutoff_time
                print(f"是否在时间窗口内: {is_recent}")
                if is_recent:
                    recent_count += 1
            else:
                print("无法解析发布时间")
        
        print(f"\n4小时内的条目数: {recent_count}")
        
    except Exception as e:
        print(f"测试失败: {e}")

def main():
    # 测试配置中的RSS源
    rss_sources = [
        {
            "name": "PANews",
            "url": "https://www.panewslab.com/zh/rss/newsflash.xml"
        },
        {
            "name": "CoinDesk", 
            "url": "https://www.coindesk.com/arc/outboundfeeds/rss"
        },
        {
            "name": "BlockBeats",
            "url": "https://api.theblockbeats.news/v2/rss/all"
        },
        {
            "name": "Cointelegraph",
            "url": "https://cointelegraph.com/rss"
        },
        {
            "name": "TechFlow",
            "url": "https://www.techflowpost.com/api/client/common/rss.xml"
        }
    ]
    
    for source in rss_sources:
        test_rss_source(source["url"], source["name"])

if __name__ == "__main__":
    main()