#!/usr/bin/env python3
"""
报告生成和发送系统示例

演示如何使用ReportGenerator和TelegramSender生成和发送加密货币新闻分析报告。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta
from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
from crypto_news_analyzer.reporters import (
    ReportGenerator, 
    TelegramSender, 
    TelegramConfig,
    create_analyzed_data
)


def create_sample_data():
    """创建示例数据"""
    current_time = datetime.now()
    
    # 创建示例内容项
    content_items = [
        ContentItem(
            id="item1",
            title="某巨鲸地址转移10000 ETH到交易所",
            content="据链上数据显示，一个持有大量ETH的巨鲸地址在今日凌晨将10000 ETH转移到Binance交易所，引发市场关注。",
            url="https://example.com/news1",
            publish_time=current_time - timedelta(hours=2),
            source_name="链上数据监控",
            source_type="rss"
        ),
        ContentItem(
            id="item2", 
            title="美联储主席鲍威尔发表鹰派言论",
            content="美联储主席鲍威尔在今日的讲话中表示，将继续采取措施控制通胀，暗示可能进一步加息。",
            url="https://example.com/news2",
            publish_time=current_time - timedelta(hours=1),
            source_name="财经新闻",
            source_type="x"
        ),
        ContentItem(
            id="item3",
            title="新的Layer2解决方案正式上线",
            content="一个新的以太坊Layer2扩容解决方案今日正式上线，承诺提供更低的交易费用和更快的确认速度。",
            url="https://example.com/news3", 
            publish_time=current_time - timedelta(minutes=30),
            source_name="技术资讯",
            source_type="rss"
        )
    ]
    
    # 创建分析结果
    analysis_results = {
        "item1": AnalysisResult(
            content_id="item1",
            category="大户动向",
            confidence=0.92,
            reasoning="检测到大额ETH转移，符合巨鲸资金流动特征",
            should_ignore=False,
            key_points=["10000 ETH转移", "转入交易所", "可能抛售信号"]
        ),
        "item2": AnalysisResult(
            content_id="item2", 
            category="利率事件",
            confidence=0.88,
            reasoning="美联储主席发表关于货币政策的重要讲话",
            should_ignore=False,
            key_points=["鹰派言论", "加息预期", "通胀控制"]
        ),
        "item3": AnalysisResult(
            content_id="item3",
            category="新产品", 
            confidence=0.75,
            reasoning="新的技术解决方案上线，属于创新产品类别",
            should_ignore=False,
            key_points=["Layer2扩容", "降低费用", "提升速度"]
        )
    }
    
    # 按类别分组内容
    categorized_items = {
        "大户动向": [content_items[0]],
        "利率事件": [content_items[1]], 
        "新产品": [content_items[2]],
        "美国政府监管政策": [],
        "安全事件": [],
        "市场新现象": [],
        "未分类": []
    }
    
    # 创建爬取状态
    crawl_status = CrawlStatus(
        rss_results=[
            CrawlResult(source_name="链上数据监控", status="success", item_count=1, error_message=None),
            CrawlResult(source_name="技术资讯", status="success", item_count=1, error_message=None)
        ],
        x_results=[
            CrawlResult(source_name="财经新闻", status="success", item_count=1, error_message=None)
        ],
        total_items=3,
        execution_time=current_time
    )
    
    return categorized_items, analysis_results, crawl_status, current_time


def demonstrate_report_generation():
    """演示报告生成"""
    print("=== 报告生成演示 ===")
    
    # 创建示例数据
    categorized_items, analysis_results, crawl_status, current_time = create_sample_data()
    
    # 创建分析数据对象
    analyzed_data = create_analyzed_data(
        categorized_items, 
        analysis_results, 
        24,  # 24小时时间窗口
        current_time
    )
    
    # 创建报告生成器
    generator = ReportGenerator(include_summary=True)
    
    # 生成报告
    report = generator.generate_report(analyzed_data, crawl_status)
    
    print("生成的报告:")
    print("=" * 80)
    print(report)
    print("=" * 80)
    
    return report


async def demonstrate_telegram_sending(report: str):
    """演示Telegram发送（需要有效的Bot Token和Channel ID）"""
    print("\n=== Telegram发送演示 ===")
    
    # 注意：这里使用的是示例配置，实际使用时需要替换为真实的Bot Token和Channel ID
    config = TelegramConfig(
        bot_token="123456789:ABCDEF1234567890abcdef1234567890ABC",  # 示例Token
        channel_id="@example_channel"  # 示例频道
    )
    
    print(f"配置信息:")
    print(f"- Bot Token: {config.bot_token[:10]}...")
    print(f"- Channel ID: {config.channel_id}")
    print(f"- 最大消息长度: {config.max_message_length}")
    
    # 创建发送器
    async with TelegramSender(config) as sender:
        # 验证配置（这会失败，因为使用的是示例配置）
        print("\n验证配置...")
        validation_result = await sender.validate_configuration()
        
        if validation_result.success:
            print("✅ 配置验证成功")
            
            # 发送报告
            print("\n发送报告...")
            send_result = await sender.send_report(report)
            
            if send_result.success:
                print(f"✅ 报告发送成功，消息ID: {send_result.message_id}")
                print(f"发送部分: {send_result.parts_sent}/{send_result.total_parts}")
            else:
                print(f"❌ 报告发送失败: {send_result.error_message}")
        else:
            print(f"❌ 配置验证失败: {validation_result.error_message}")
            print("💡 这是预期的，因为使用的是示例配置")
            
            # 演示消息分割功能
            print("\n演示消息分割功能...")
            parts = sender.split_long_message(report)
            print(f"报告被分割为 {len(parts)} 个部分:")
            for i, part in enumerate(parts, 1):
                print(f"  部分 {i}: {len(part)} 字符")
            
            # 保存备份
            print("\n保存报告备份...")
            backup_path = sender.save_report_backup(report)
            if backup_path:
                print(f"✅ 报告备份已保存到: {backup_path}")


def demonstrate_error_handling():
    """演示错误处理"""
    print("\n=== 错误处理演示 ===")
    
    # 创建一个会导致错误的场景
    from crypto_news_analyzer.reporters.report_generator import validate_report_data, AnalyzedData
    
    # 创建无效数据
    invalid_data = AnalyzedData(
        categorized_items="invalid",  # 应该是字典
        analysis_results={},
        time_window_hours=-1,  # 应该大于0
        start_time=datetime.now(),
        end_time=datetime.now() - timedelta(hours=1)  # 结束时间早于开始时间
    )
    
    # 创建有效的爬取状态
    crawl_status = CrawlStatus(
        rss_results=[],
        x_results=[],
        total_items=0,
        execution_time=datetime.now()
    )
    
    # 验证数据
    errors = validate_report_data(invalid_data, crawl_status)
    
    print("数据验证错误:")
    for error in errors:
        print(f"  ❌ {error}")
    
    # 演示错误报告生成
    generator = ReportGenerator()
    error_report = generator._generate_error_report("演示错误", crawl_status)
    
    print("\n生成的错误报告:")
    print("-" * 40)
    print(error_report[:500] + "..." if len(error_report) > 500 else error_report)
    print("-" * 40)


async def main():
    """主函数"""
    print("🚀 加密货币新闻分析报告生成和发送系统演示")
    print("=" * 60)
    
    # 演示报告生成
    report = demonstrate_report_generation()
    
    # 演示Telegram发送
    await demonstrate_telegram_sending(report)
    
    # 演示错误处理
    demonstrate_error_handling()
    
    print("\n✨ 演示完成！")
    print("\n📝 使用说明:")
    print("1. 要实际发送到Telegram，请替换示例配置中的Bot Token和Channel ID")
    print("2. 确保Bot已添加到目标频道并具有发送消息权限")
    print("3. 可以通过修改ReportGenerator的include_summary参数控制是否包含总结")
    print("4. TelegramSender支持自动分割长消息以适应Telegram限制")


if __name__ == "__main__":
    asyncio.run(main())