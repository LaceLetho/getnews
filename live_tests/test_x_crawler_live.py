#!/usr/bin/env python3
"""
X爬取器线上测试脚本

测试基于bird工具的X爬取器是否能够获取有效的线上消息。
使用.env文件中配置的认证参数进行测试。
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from crypto_news_analyzer.crawlers.x_crawler import XCrawler
from crypto_news_analyzer.models import XSource, BirdConfig
from crypto_news_analyzer.utils.logging import get_logger

def load_env_file():
    """加载.env文件中的环境变量"""
    env_file = project_root / ".env"
    if not env_file.exists():
        print("❌ .env文件不存在")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    
    print("✅ 已加载.env文件")
    return True

def load_config():
    """加载配置文件"""
    config_file = project_root / "config.json"
    if not config_file.exists():
        print("❌ config.json文件不存在")
        return None
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print("✅ 已加载config.json")
    return config

def test_bird_dependency():
    """测试bird工具依赖"""
    print("\n🔍 检查bird工具依赖...")
    
    try:
        from crypto_news_analyzer.crawlers.bird_dependency_manager import BirdDependencyManager
        
        bird_config = BirdConfig()
        dependency_manager = BirdDependencyManager(bird_config)
        status = dependency_manager.check_bird_availability()
        
        if status.available:
            print(f"✅ Bird工具可用")
            print(f"   版本: {status.version}")
            print(f"   路径: {status.executable_path}")
            return True
        else:
            print(f"❌ Bird工具不可用: {status.error_message}")
            print("\n💡 安装建议:")
            print("   1. 确保已安装bird工具")
            print("   2. 检查PATH环境变量")
            print("   3. 验证bird工具可执行权限")
            return False
            
    except Exception as e:
        print(f"❌ 检查bird工具依赖时出错: {str(e)}")
        return False

def test_x_crawler_initialization():
    """测试X爬取器初始化"""
    print("\n🔍 测试X爬取器初始化...")
    
    try:
        # 创建BirdConfig
        bird_config = BirdConfig(
            executable_path="bird",
            timeout_seconds=300,
            max_retries=3,
            output_format="json",
            rate_limit_delay=1.0
        )
        
        # 初始化X爬取器
        crawler = XCrawler(time_window_hours=4, bird_config=bird_config)
        
        print("✅ X爬取器初始化成功")
        print(f"   认证状态: {'已认证' if crawler.authenticated else '未认证'}")
        
        return crawler
        
    except Exception as e:
        print(f"❌ X爬取器初始化失败: {str(e)}")
        return None

def test_authentication(crawler):
    """测试认证功能"""
    print("\n🔍 测试X认证...")
    
    try:
        auth_result = crawler.authenticate()
        
        if auth_result:
            print("✅ X认证成功")
            return True
        else:
            print("❌ X认证失败")
            print("💡 请检查.env文件中的X_CT0和X_AUTH_TOKEN参数")
            return False
            
    except Exception as e:
        print(f"❌ 认证测试时出错: {str(e)}")
        return False

def test_list_crawling(crawler, config):
    """测试列表爬取功能"""
    print("\n🔍 测试X列表爬取...")
    
    try:
        x_sources = config.get('x_sources', [])
        if not x_sources:
            print("❌ 配置文件中没有X源")
            return False
        
        # 选择第一个列表源进行测试
        test_source = None
        for source in x_sources:
            if source.get('type') == 'list':
                test_source = source
                break
        
        if not test_source:
            print("❌ 配置文件中没有列表类型的X源")
            return False
        
        print(f"📋 测试源: {test_source['name']}")
        print(f"🔗 URL: {test_source['url']}")
        
        # 爬取列表
        items = crawler.crawl_list(test_source['url'])
        
        print(f"✅ 列表爬取成功，获得 {len(items)} 条内容")
        
        # 显示前几条内容的摘要
        if items:
            print("\n📄 内容摘要:")
            for i, item in enumerate(items[:3]):  # 只显示前3条
                print(f"   {i+1}. {item.title[:60]}...")
                print(f"      时间: {item.publish_time}")
                print(f"      链接: {item.url}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ 列表爬取测试失败: {str(e)}")
        return False

def test_batch_crawling(crawler, config):
    """测试批量爬取功能"""
    print("\n🔍 测试批量爬取...")
    
    try:
        x_sources_config = config.get('x_sources', [])
        if not x_sources_config:
            print("❌ 配置文件中没有X源")
            return False
        
        # 转换为XSource对象
        x_sources = []
        for source_config in x_sources_config:
            x_source = XSource(
                name=source_config['name'],
                url=source_config['url'],
                type=source_config['type']
            )
            x_sources.append(x_source)
        
        print(f"📋 测试 {len(x_sources)} 个X源")
        
        # 批量爬取
        results = crawler.crawl_all_sources(x_sources)
        
        print(f"✅ 批量爬取完成")
        
        # 显示结果统计
        success_count = sum(1 for r in results if r.status == "success")
        error_count = sum(1 for r in results if r.status == "error")
        total_items = sum(r.item_count for r in results if r.status == "success")
        
        print(f"📊 结果统计:")
        print(f"   成功: {success_count}/{len(results)}")
        print(f"   失败: {error_count}/{len(results)}")
        print(f"   总内容数: {total_items}")
        
        # 显示详细结果
        print(f"\n📋 详细结果:")
        for result in results:
            status_icon = "✅" if result.status == "success" else "❌"
            print(f"   {status_icon} {result.source_name}: {result.item_count} 条内容")
            if result.error_message:
                print(f"      错误: {result.error_message}")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ 批量爬取测试失败: {str(e)}")
        return False

def test_diagnostics(crawler):
    """测试诊断功能"""
    print("\n🔍 获取诊断信息...")
    
    try:
        diagnostic_info = crawler.get_diagnostic_info()
        
        print("✅ 诊断信息:")
        print(f"   时间窗口: {diagnostic_info.get('time_window_hours')} 小时")
        print(f"   认证状态: {'已认证' if diagnostic_info.get('authenticated') else '未认证'}")
        
        bird_info = diagnostic_info.get('bird_wrapper_info')
        if bird_info:
            print(f"   Bird工具状态:")
            dependency_status = bird_info.get('dependency_status', {})
            print(f"     可用性: {'可用' if dependency_status.get('available') else '不可用'}")
            print(f"     版本: {dependency_status.get('version', 'N/A')}")
            print(f"     路径: {dependency_status.get('executable_path', 'N/A')}")
            print(f"     连接测试: {'通过' if bird_info.get('connection_test') else '失败'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取诊断信息失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始X爬取器线上测试")
    print("=" * 50)
    
    # 加载环境变量
    if not load_env_file():
        return False
    
    # 检查必需的环境变量
    required_env_vars = ['X_CT0', 'X_AUTH_TOKEN']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing_vars)}")
        print("💡 请检查.env文件中的X_CT0和X_AUTH_TOKEN配置")
        return False
    
    print("✅ 环境变量检查通过")
    
    # 加载配置文件
    config = load_config()
    if not config:
        return False
    
    # 测试bird工具依赖
    if not test_bird_dependency():
        return False
    
    # 初始化X爬取器
    crawler = test_x_crawler_initialization()
    if not crawler:
        return False
    
    # 测试认证
    if not test_authentication(crawler):
        return False
    
    # 测试列表爬取
    if not test_list_crawling(crawler, config):
        return False
    
    # 测试批量爬取
    if not test_batch_crawling(crawler, config):
        return False
    
    # 测试诊断功能
    test_diagnostics(crawler)
    
    # 清理资源
    crawler.cleanup()
    
    print("\n" + "=" * 50)
    print("🎉 所有测试完成！X爬取器工作正常")
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 测试过程中发生未预期的错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)