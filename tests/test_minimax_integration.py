#!/usr/bin/env python3
"""
MiniMax API集成测试

使用真实的MiniMax API测试LLM分析功能
"""

import os
import sys
import pytest
from datetime import datetime
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.models import ContentItem, AnalysisResult


class TestMinimaxIntegration:
    """MiniMax API集成测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化"""
        # 加载环境变量
        load_dotenv()
        
        # 检查MiniMax API key
        cls.llm_api_key = os.getenv('llm_api_key')
        
        if not cls.llm_api_key:
            pytest.skip("缺少LLM API key，跳过MiniMax集成测试")
        
        # 创建MiniMax分析器
        cls.llm_analyzer = LLMAnalyzer(
            api_key=cls.llm_api_key,
            model="MiniMax-M2.1",  # 使用MiniMax模型
            mock_mode=False  # 使用真实API
        )
        
        print(f"使用MiniMax API Key: {cls.llm_api_key[:20]}...")
    
    def test_minimax_api_analysis(self):
        """测试MiniMax API分析功能"""
        print(f"\n测试MiniMax API分析...")
        
        # 测试内容 - 明确的大户动向内容
        test_content = "某知名巨鲸地址在过去24小时内转移了15000个ETH到Binance交易所，总价值约5000万美元。这一举动引发了市场关注，分析师认为可能预示着大户对市场的看法发生变化。"
        test_title = "巨鲸转移大量ETH到交易所"
        test_source = "MiniMax集成测试"
        
        try:
            result = self.llm_analyzer.analyze_content(test_content, test_title, test_source)
            
            # 验证结果结构
            assert isinstance(result, AnalysisResult)
            assert isinstance(result.category, str)
            assert isinstance(result.confidence, float)
            assert isinstance(result.reasoning, str)
            assert isinstance(result.should_ignore, bool)
            assert isinstance(result.key_points, list)
            
            # 验证结果合理性
            assert 0 <= result.confidence <= 1
            assert len(result.reasoning) > 0
            
            print(f"✅ MiniMax分析成功:")
            print(f"   分类: {result.category}")
            print(f"   置信度: {result.confidence:.2f}")
            print(f"   推理: {result.reasoning}")
            print(f"   关键点: {result.key_points}")
                
        except Exception as e:
            print(f"❌ MiniMax API调用失败: {e}")
            raise
    
    def test_minimax_performance_metrics(self):
        """测试MiniMax API性能指标"""
        print(f"\n测试性能指标...")
        
        test_content = "测试内容用于性能评估"
        
        # 进行多次调用测试性能
        times = []
        success_count = 0
        
        for i in range(3):  # 测试3次
            try:
                start_time = datetime.now()
                result = self.llm_analyzer.analyze_content(
                    f"{test_content} - 第{i+1}次测试", 
                    f"性能测试{i+1}", 
                    "性能测试"
                )
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                times.append(duration)
                success_count += 1
                
                print(f"   第{i+1}次调用: {duration:.2f}秒 - {result.category}")
                
            except Exception as e:
                print(f"   第{i+1}次调用失败: {e}")
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"✅ 性能统计:")
            print(f"   成功率: {success_count}/3 ({success_count/3*100:.1f}%)")
            print(f"   平均响应时间: {avg_time:.2f}秒")
            print(f"   最快响应: {min_time:.2f}秒")
            print(f"   最慢响应: {max_time:.2f}秒")
        else:
            print(f"❌ 所有调用都失败了")


if __name__ == "__main__":
    # 运行MiniMax集成测试
    pytest.main([__file__, "-v", "-s"])