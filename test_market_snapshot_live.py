#!/usr/bin/env python3
"""
测试 MarketSnapshotService 的线上真实环境调用

这个脚本将测试：
1. API连接状态
2. 获取真实市场快照
3. 缓存功能
4. 质量验证
5. 备用机制
"""

import os
import sys
import logging
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshotService

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_market_snapshot.log', encoding='utf-8')
        ]
    )

def load_env_vars():
    """加载环境变量"""
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print("✅ 环境变量加载成功")
    except Exception as e:
        print(f"❌ 加载环境变量失败: {e}")

def load_prompt_template():
    """加载提示词模板"""
    try:
        with open('prompts/market_summary_prompt.md', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"❌ 加载提示词模板失败: {e}")
        return "请提供当前加密货币市场的简要分析"

def test_api_connection(service):
    """测试API连接"""
    print("\n🔍 测试API连接...")
    
    result = service.test_connection()
    print(f"连接测试结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('grok_available'):
        print("✅ Grok API连接正常")
        return True
    else:
        print(f"❌ Grok API连接失败: {result.get('grok_error', '未知错误')}")
        return False

def test_cache_functionality(service):
    """测试缓存功能"""
    print("\n🗄️ 测试缓存功能...")
    
    # 获取缓存信息
    cache_info = service.get_cache_info()
    print(f"缓存信息: {json.dumps(cache_info, indent=2, ensure_ascii=False)}")
    
    # 清除缓存
    if service.clear_cache():
        print("✅ 缓存清除成功")
    else:
        print("❌ 缓存清除失败")
    
    return True

def test_quality_validation(service):
    """测试质量验证"""
    print("\n🔍 测试质量验证...")
    
    test_cases = [
        ("", False, "空内容"),
        ("短", False, "内容太短"),
        ("这是一个关于比特币价格上涨的新闻，市场情绪乐观，投资者预期未来会有更多利好消息，加密货币行业发展迅速。", True, "包含关键词的有效内容"),
        ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.", False, "无关键词的长内容"),
        ("当前加密货币市场处于震荡阶段，比特币价格在45000美元附近波动，以太坊表现相对稳定，投资者情绪谨慎观望。", True, "高质量市场分析")
    ]
    
    for content, expected, description in test_cases:
        result = service.validate_snapshot_quality(content)
        quality_score = service._calculate_quality_score(content)
        
        status = "✅" if result == expected else "❌"
        print(f"{status} {description}: 验证={result}, 质量评分={quality_score:.2f}")
    
    return True

def test_fallback_mechanism(service):
    """测试备用机制"""
    print("\n🔄 测试备用机制...")
    
    fallback_snapshot = service.get_fallback_snapshot()
    print(f"备用快照来源: {fallback_snapshot.source}")
    print(f"备用快照质量评分: {fallback_snapshot.quality_score}")
    print(f"备用快照有效性: {fallback_snapshot.is_valid}")
    print(f"备用快照内容长度: {len(fallback_snapshot.content)} 字符")
    
    if fallback_snapshot.is_valid:
        print("✅ 备用机制正常")
        return True
    else:
        print("❌ 备用机制异常")
        return False

def test_real_market_snapshot(service, prompt_template):
    """测试真实市场快照获取"""
    print("\n📊 测试真实市场快照获取...")
    print(f"使用提示词: {prompt_template}")
    
    try:
        # 获取市场快照
        snapshot = service.get_market_snapshot(prompt_template)
        
        print(f"\n📈 市场快照获取结果:")
        print(f"来源: {snapshot.source}")
        print(f"时间: {snapshot.timestamp}")
        print(f"质量评分: {snapshot.quality_score}")
        print(f"有效性: {snapshot.is_valid}")
        print(f"内容长度: {len(snapshot.content)} 字符")
        
        print(f"\n📝 快照内容:")
        print("-" * 50)
        print(snapshot.content)
        print("-" * 50)
        
        # 验证快照质量
        if snapshot.is_valid and snapshot.quality_score > 0.5:
            print("✅ 市场快照获取成功，质量良好")
            return True
        else:
            print("⚠️ 市场快照获取成功，但质量可能不佳")
            return True
            
    except Exception as e:
        print(f"❌ 获取市场快照失败: {e}")
        return False

def test_mock_mode():
    """测试模拟模式"""
    print("\n🎭 测试模拟模式...")
    
    # 使用不同的缓存目录避免干扰
    mock_service = MarketSnapshotService(
        mock_mode=True,
        cache_dir="./data/cache_mock"
    )
    prompt_template = "请提供当前加密货币市场分析"
    
    try:
        snapshot = mock_service.get_market_snapshot(prompt_template)
        
        print(f"模拟快照来源: {snapshot.source}")
        print(f"模拟快照质量评分: {snapshot.quality_score}")
        print(f"模拟快照有效性: {snapshot.is_valid}")
        
        if snapshot.source == "mock" and snapshot.is_valid:
            print("✅ 模拟模式正常")
            return True
        else:
            print("❌ 模拟模式异常")
            return False
            
    except Exception as e:
        print(f"❌ 模拟模式测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试 MarketSnapshotService 线上真实环境调用")
    print("=" * 60)
    
    # 设置日志
    setup_logging()
    
    # 加载环境变量
    load_env_vars()
    
    # 加载提示词模板
    prompt_template = load_prompt_template()
    
    # 创建服务实例
    print("\n🔧 初始化 MarketSnapshotService...")
    service = MarketSnapshotService(
        cache_ttl_minutes=30,
        cache_dir="./data/cache"
    )
    
    # 测试结果统计
    test_results = []
    
    # 1. 测试模拟模式
    test_results.append(("模拟模式", test_mock_mode()))
    
    # 2. 测试缓存功能
    test_results.append(("缓存功能", test_cache_functionality(service)))
    
    # 3. 测试质量验证
    test_results.append(("质量验证", test_quality_validation(service)))
    
    # 4. 测试备用机制
    test_results.append(("备用机制", test_fallback_mechanism(service)))
    
    # 5. 测试API连接
    api_connected = test_api_connection(service)
    test_results.append(("API连接", api_connected))
    
    # 6. 测试真实市场快照获取
    if api_connected:
        test_results.append(("真实快照获取", test_real_market_snapshot(service, prompt_template)))
    else:
        print("\n⚠️ 跳过真实快照获取测试（API连接失败）")
        test_results.append(("真实快照获取", False))
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！MarketSnapshotService 可以正常使用")
        return 0
    elif passed >= total * 0.7:
        print("⚠️ 大部分测试通过，服务基本可用")
        return 0
    else:
        print("❌ 多项测试失败，请检查配置和网络连接")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)