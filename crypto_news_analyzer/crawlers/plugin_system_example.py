#!/usr/bin/env python3
"""
数据源插件系统使用示例

演示如何使用新的插件化数据源系统，包括：
1. 使用工厂创建数据源
2. 配置验证
3. 扩展新的数据源类型
4. 批量管理数据源
"""

import sys
import os
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.crawlers import (  # noqa: E402
    get_data_source_factory,
    DataSourceInterface,
    ConfigValidationError
)
from crypto_news_analyzer.models import ContentItem, create_content_item_from_raw  # noqa: E402
from datetime import datetime  # noqa: E402


class CustomNewsCrawler(DataSourceInterface):
    """
    自定义新闻爬取器示例

    演示如何实现自定义数据源类型
    """

    def __init__(self, time_window_hours: int, **kwargs):
        self.time_window_hours = time_window_hours
        self.custom_param = kwargs.get('custom_param', 'default_value')
        print(f"自定义新闻爬取器初始化，时间窗口: {time_window_hours}小时")

    def get_source_type(self) -> str:
        return "custom_news"

    def get_supported_config_fields(self) -> List[str]:
        return ["name", "api_key", "category", "language", "custom_param"]

    def get_required_config_fields(self) -> List[str]:
        return ["name", "api_key"]

    def validate_config(self, config: Dict[str, Any]) -> bool:
        required_fields = self.get_required_config_fields()
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ConfigValidationError(
                f"缺少必需的配置字段: {missing_fields}",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            )

        # 验证API密钥格式
        api_key = config.get("api_key", "")
        if not api_key.startswith("custom_"):
            raise ConfigValidationError(
                "API密钥必须以 'custom_' 开头",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            )

        return True

    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        """模拟爬取数据"""
        print(f"开始爬取自定义新闻源: {config.get('name', 'Unknown')}")

        # 模拟返回一些测试数据
        mock_items = [
            create_content_item_from_raw(
                title="自定义新闻标题 1",
                content="这是一条来自自定义数据源的模拟新闻内容。",
                url="https://example.com/news/1",
                publish_time=datetime.now(),
                source_name=config.get("name", "Custom Source"),
                source_type=self.get_source_type()
            ),
            create_content_item_from_raw(
                title="自定义新闻标题 2",
                content="这是另一条来自自定义数据源的模拟新闻内容。",
                url="https://example.com/news/2",
                publish_time=datetime.now(),
                source_name=config.get("name", "Custom Source"),
                source_type=self.get_source_type()
            )
        ]

        print(f"自定义新闻源爬取完成，获得 {len(mock_items)} 条内容")
        return mock_items

    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_items = []
        results = []

        for source_config in sources:
            try:
                items = self.crawl(source_config)
                all_items.extend(items)

                results.append({
                    "source_name": source_config.get("name", "Unknown"),
                    "status": "success",
                    "item_count": len(items),
                    "error_message": None
                })
            except Exception as e:
                results.append({
                    "source_name": source_config.get("name", "Unknown"),
                    "status": "error",
                    "item_count": 0,
                    "error_message": str(e)
                })

        return {
            'items': all_items,
            'results': results,
            'total_items': len(all_items)
        }

    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        base_info = super().get_source_info(config)
        base_info.update({
            "custom_features": ["模拟数据生成", "自定义参数支持"],
            "version": "1.0.0"
        })
        return base_info

    def cleanup(self) -> None:
        print("自定义新闻爬取器资源清理完成")


def demonstrate_basic_usage():
    """演示基本使用方法"""
    print("=== 演示基本使用方法 ===")

    # 获取工厂实例
    factory = get_data_source_factory()

    # 查看可用的数据源类型
    print(f"可用的数据源类型: {factory.get_available_source_types()}")

    # 创建RSS数据源实例
    rss_source = factory.create_source("rss", time_window_hours=24)
    print(f"创建RSS数据源: {type(rss_source).__name__}")

    # 验证RSS配置
    rss_config = {
        "name": "示例RSS源",
        "url": "https://example.com/rss.xml",
        "description": "示例RSS订阅源"
    }

    is_valid = factory.validate_source_config("rss", rss_config)
    print(f"RSS配置验证结果: {is_valid}")

    # 获取RSS数据源信息
    rss_info = factory.get_source_info("rss")
    print(f"RSS数据源信息: {rss_info['features']}")

    # 清理资源
    rss_source.cleanup()


def demonstrate_custom_source():
    """演示自定义数据源"""
    print("\n=== 演示自定义数据源 ===")

    factory = get_data_source_factory()

    # 注册自定义数据源
    factory.register_source("custom_news", CustomNewsCrawler)
    print("注册自定义数据源: custom_news")

    # 查看更新后的数据源类型
    print(f"更新后的数据源类型: {factory.get_available_source_types()}")

    # 创建自定义数据源实例
    custom_source = factory.create_source(
        "custom_news",
        time_window_hours=12,
        custom_param="example_value"
    )

    # 验证自定义数据源配置
    custom_config_valid = {
        "name": "示例自定义源",
        "api_key": "custom_abc123",
        "category": "crypto",
        "language": "zh-CN"
    }

    custom_config_invalid = {
        "name": "示例自定义源",
        "api_key": "invalid_key"  # 不符合格式要求
    }

    try:
        is_valid = factory.validate_source_config("custom_news", custom_config_valid)
        print(f"有效自定义配置验证结果: {is_valid}")
    except Exception as e:
        print(f"有效自定义配置验证失败: {e}")

    try:
        is_valid = factory.validate_source_config("custom_news", custom_config_invalid)
        print(f"无效自定义配置验证结果: {is_valid}")
    except Exception as e:
        print(f"无效自定义配置验证失败（预期）: {e}")

    # 使用自定义数据源爬取数据
    try:
        items = custom_source.crawl(custom_config_valid)
        print(f"自定义数据源爬取结果: {len(items)} 条内容")
        for item in items:
            print(f"  - {item.title}")
    except Exception as e:
        print(f"自定义数据源爬取失败: {e}")

    # 清理资源
    custom_source.cleanup()


def demonstrate_batch_operations():
    """演示批量操作"""
    print("\n=== 演示批量操作 ===")

    factory = get_data_source_factory()

    # 准备多个数据源配置
    configs = {
        "rss": [
            {
                "name": "RSS源1",
                "url": "https://example1.com/rss.xml",
                "description": "第一个RSS源"
            },
            {
                "name": "RSS源2",
                "url": "https://example2.com/rss.xml",
                "description": "第二个RSS源"
            }
        ],
        "rest_api": [
            {
                "name": "API源1",
                "endpoint": "https://api.example.com/news",
                "method": "GET",
                "response_mapping": {
                    "title_field": "title",
                    "content_field": "content",
                    "url_field": "url",
                    "time_field": "published_at"
                }
            }
        ]
    }

    # 批量验证配置
    validation_errors = factory.validate_all_configs(configs)
    if validation_errors:
        print("配置验证错误:")
        for source_type, errors in validation_errors.items():
            print(f"  {source_type}: {errors}")
    else:
        print("所有配置验证通过")

    # 批量创建数据源实例
    try:
        sources = factory.create_all_sources(configs, time_window_hours=24)
        print("成功创建数据源实例:")
        for source_type, source_list in sources.items():
            print(f"  {source_type}: {len(source_list)} 个实例")

        # 清理所有实例
        factory.cleanup_all_sources(sources)
        print("批量清理完成")

    except Exception as e:
        print(f"批量创建数据源失败: {e}")


def demonstrate_error_handling():
    """演示错误处理"""
    print("\n=== 演示错误处理 ===")

    factory = get_data_source_factory()

    # 尝试创建不存在的数据源类型
    try:
        factory.create_source("unknown_type", time_window_hours=24)  # expected to fail
    except ValueError as e:
        print(f"创建未知数据源类型失败（预期）: {e}")

    # 尝试验证无效配置
    try:
        invalid_config = {"invalid": "config"}
        factory.validate_source_config("rss", invalid_config)
    except Exception as e:
        print(f"验证无效配置失败（预期）: {e}")

    # 演示数据源特定错误
    try:
        rss_source = factory.create_source("rss", time_window_hours=24)
        invalid_rss_config = {
            "name": "无效RSS",
            "url": "not_a_valid_url"
        }
        rss_source.validate_config(invalid_rss_config)
    except ConfigValidationError as e:
        print(f"RSS配置验证错误（预期）: {e}")
    except Exception as e:
        print(f"其他错误: {e}")


def main():
    """主演示函数"""
    print("数据源插件系统使用示例")
    print("=" * 50)

    try:
        demonstrate_basic_usage()
        demonstrate_custom_source()
        demonstrate_batch_operations()
        demonstrate_error_handling()

        print("\n" + "=" * 50)
        print("🎉 所有演示完成！插件系统工作正常。")

        # 显示最终的工厂统计信息
        factory = get_data_source_factory()
        stats = factory.get_factory_stats()
        print("\n最终统计:")
        print(f"  注册的数据源类型: {stats['registered_types']}")
        print(f"  总数: {stats['registered_types_count']}")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
