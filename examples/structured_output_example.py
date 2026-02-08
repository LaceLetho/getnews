"""
结构化输出管理器使用示例

演示如何使用StructuredOutputManager强制大模型返回结构化数据。
"""

import os
from openai import OpenAI
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult
)


def example_single_analysis():
    """示例：单个内容分析"""
    print("=" * 60)
    print("示例 1: 单个内容分析")
    print("=" * 60)
    
    # 初始化管理器
    manager = StructuredOutputManager(library="instructor")
    
    # 创建OpenAI客户端
    api_key = os.getenv("LLM_API_KEY", "your-api-key-here")
    client = OpenAI(api_key=api_key)
    
    # 设置instructor客户端
    instructor_client = manager.setup_instructor_client(client)
    
    # 准备消息
    messages = [
        {
            "role": "system",
            "content": "你是一个加密货币新闻分析专家。请分析以下新闻并返回结构化结果。"
        },
        {
            "role": "user",
            "content": """
分析这条新闻：
标题：某巨鲸地址转移10000 ETH到交易所
内容：链上数据显示，一个持有大量ETH的巨鲸地址在今天凌晨将10000 ETH转移到Binance交易所。
时间：2024-01-01 12:00
来源：https://example.com/news/123

请返回：时间、分类、重要性评分(0-100)、摘要和来源链接。
"""
        }
    ]
    
    try:
        # 使用instructor强制结构化输出
        result = manager.force_structured_response(
            llm_client=instructor_client,
            messages=messages,
            model="gpt-4",
            max_retries=3,
            temperature=0.1,
            batch_mode=False
        )
        
        print("\n✓ 成功获取结构化响应:")
        print(f"  时间: {result.time}")
        print(f"  分类: {result.category}")
        print(f"  评分: {result.weight_score}")
        print(f"  摘要: {result.summary}")
        print(f"  来源: {result.source}")
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")


def example_batch_analysis():
    """示例：批量内容分析"""
    print("\n" + "=" * 60)
    print("示例 2: 批量内容分析")
    print("=" * 60)
    
    # 初始化管理器
    manager = StructuredOutputManager(library="instructor")
    
    # 创建OpenAI客户端
    api_key = os.getenv("LLM_API_KEY", "your-api-key-here")
    client = OpenAI(api_key=api_key)
    
    # 设置instructor客户端
    instructor_client = manager.setup_instructor_client(client)
    
    # 准备消息
    messages = [
        {
            "role": "system",
            "content": "你是一个加密货币新闻分析专家。请分析以下新闻列表并返回结构化结果列表。"
        },
        {
            "role": "user",
            "content": """
分析以下新闻列表：

1. 标题：某巨鲸地址转移10000 ETH到交易所
   内容：链上数据显示，一个持有大量ETH的巨鲸地址在今天凌晨将10000 ETH转移到Binance交易所。
   时间：2024-01-01 12:00
   来源：https://example.com/news/123

2. 标题：某DeFi协议发现严重漏洞
   内容：安全公司发现某知名DeFi协议存在严重漏洞，可能导致资金损失。
   时间：2024-01-01 13:30
   来源：https://example.com/news/456

请为每条新闻返回：时间、分类、重要性评分(0-100)、摘要和来源链接。
"""
        }
    ]
    
    try:
        # 使用instructor强制结构化输出（批量模式）
        result = manager.force_structured_response(
            llm_client=instructor_client,
            messages=messages,
            model="gpt-4",
            max_retries=3,
            temperature=0.1,
            batch_mode=True
        )
        
        print(f"\n✓ 成功获取 {len(result.results)} 条结构化响应:")
        for i, item in enumerate(result.results, 1):
            print(f"\n  新闻 {i}:")
            print(f"    时间: {item.time}")
            print(f"    分类: {item.category}")
            print(f"    评分: {item.weight_score}")
            print(f"    摘要: {item.summary}")
            print(f"    来源: {item.source}")
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")


def example_validation():
    """示例：输出验证"""
    print("\n" + "=" * 60)
    print("示例 3: 输出验证")
    print("=" * 60)
    
    manager = StructuredOutputManager()
    
    # 测试有效的单个结果
    valid_response = {
        "time": "2024-01-01 12:00",
        "category": "大户动向",
        "weight_score": 85,
        "summary": "某巨鲸地址转移10000 ETH到交易所",
        "source": "https://example.com/news/123"
    }
    
    result = manager.validate_output_structure(valid_response)
    print(f"\n有效响应验证: {'✓ 通过' if result.is_valid else '✗ 失败'}")
    if result.errors:
        print(f"  错误: {result.errors}")
    
    # 测试无效的结果（缺少字段）
    invalid_response = {
        "time": "2024-01-01 12:00",
        "category": "大户动向"
        # 缺少其他必需字段
    }
    
    result = manager.validate_output_structure(invalid_response)
    print(f"\n无效响应验证: {'✓ 通过' if result.is_valid else '✗ 失败'}")
    if result.errors:
        print(f"  错误: {result.errors}")
    
    # 测试批量结果（空列表）
    empty_batch = {"results": []}
    
    result = manager.validate_output_structure(empty_batch)
    print(f"\n空批量结果验证: {'✓ 通过' if result.is_valid else '✗ 失败'}")
    if result.warnings:
        print(f"  警告: {result.warnings}")


def example_error_recovery():
    """示例：错误恢复"""
    print("\n" + "=" * 60)
    print("示例 4: 错误恢复")
    print("=" * 60)
    
    manager = StructuredOutputManager()
    
    # 测试从markdown代码块恢复
    malformed_response = """
这是一些解释文本
```json
{
    "time": "2024-01-01 12:00",
    "category": "大户动向",
    "weight_score": 85,
    "summary": "某巨鲸地址转移10000 ETH到交易所",
    "source": "https://example.com/news/123"
}
```
更多解释
"""
    
    result = manager.handle_malformed_response(malformed_response, batch_mode=False)
    if result:
        print("\n✓ 成功从markdown代码块恢复:")
        print(f"  分类: {result.category}")
        print(f"  评分: {result.weight_score}")
    else:
        print("\n✗ 无法恢复响应")


def example_schema_inspection():
    """示例：Schema检查"""
    print("\n" + "=" * 60)
    print("示例 5: Schema检查")
    print("=" * 60)
    
    manager = StructuredOutputManager()
    
    # 获取支持的库
    libraries = manager.get_supported_libraries()
    print(f"\n支持的库: {', '.join(libraries)}")
    
    # 获取输出schema
    schema = manager.get_output_schema()
    print(f"\n输出Schema字段:")
    for field_name in schema.get("properties", {}).keys():
        field_info = schema["properties"][field_name]
        print(f"  - {field_name}: {field_info.get('description', 'N/A')}")
    
    # 创建示例响应
    example = manager.create_example_response(batch_mode=False)
    print(f"\n单个结果示例:")
    import json
    print(json.dumps(example, ensure_ascii=False, indent=2))
    
    example_batch = manager.create_example_response(batch_mode=True)
    print(f"\n批量结果示例:")
    print(json.dumps(example_batch, ensure_ascii=False, indent=2))


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("结构化输出管理器使用示例")
    print("=" * 60)
    
    # 检查API密钥
    if not os.getenv("LLM_API_KEY"):
        print("\n⚠️  警告: 未设置LLM_API_KEY环境变量")
        print("   某些示例需要实际的API调用，将跳过这些示例。")
        print("   其他示例（验证、恢复、Schema检查）仍然可以运行。\n")
    
    # 运行不需要API的示例
    example_validation()
    example_error_recovery()
    example_schema_inspection()
    
    # 如果有API密钥，运行需要API的示例
    if os.getenv("LLM_API_KEY"):
        try:
            example_single_analysis()
            example_batch_analysis()
        except Exception as e:
            print(f"\n⚠️  API调用示例失败: {e}")
            print("   这可能是因为API密钥无效或网络问题。")
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
