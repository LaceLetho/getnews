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
    
    def test_minimax_api_basic_analysis(self):
        """测试MiniMax API基本分析功能"""
        print(f"\n测试MiniMax API基本分析...")
        
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
            print(f"   是否忽略: {result.should_ignore}")
            print(f"   关键点: {result.key_points}")
            
            # 对于巨鲸转移内容，期望分类为大户动向
            if result.category == "大户动向":
                print(f"✅ 分类正确识别为大户动向")
            else:
                print(f"⚠️ 分类为 {result.category}，可能需要调整提示词")
                
        except Exception as e:
            print(f"❌ MiniMax API调用失败: {e}")
            # 如果是API key问题，提供更详细的信息
            if "401" in str(e) or "Unauthorized" in str(e):
                print("   可能的原因:")
                print("   1. API key无效或已过期")
                print("   2. API key格式不正确")
                print("   3. 账户余额不足")
            elif "403" in str(e) or "Forbidden" in str(e):
                print("   可能的原因:")
                print("   1. API key没有访问权限")
                print("   2. 请求频率超限")
            raise
    
    def test_minimax_different_content_types(self):
        """测试MiniMax API对不同类型内容的分析"""
        print(f"\n测试不同类型内容分析...")
        
        test_cases = [
            {
                "content": "美联储主席鲍威尔今日表示，考虑到当前通胀水平，央行可能在下次FOMC会议中调整利率政策。",
                "title": "鲍威尔暗示可能调整利率",
                "expected_category": "利率事件"
            },
            {
                "content": "某DeFi协议遭受重入攻击，黑客成功盗取价值500万美元的加密货币。",
                "title": "DeFi协议遭受攻击",
                "expected_category": "安全事件"
            },
            {
                "content": "🚀超高收益率DeFi挖矿项目！立即参与！千载难逢的机会！保证100%收益！",
                "title": "🚀超高收益项目",
                "expected_ignore": True
            }
        ]
        
        for i, case in enumerate(test_cases):
            print(f"\n   测试案例 {i+1}: {case['title']}")
            
            try:
                result = self.llm_analyzer.analyze_content(
                    case["content"], 
                    case["title"], 
                    "MiniMax测试"
                )
                
                print(f"     分类: {result.category}")
                print(f"     置信度: {result.confidence:.2f}")
                print(f"     是否忽略: {result.should_ignore}")
                
                # 检查期望的分类
                if "expected_category" in case:
                    if result.category == case["expected_category"]:
                        print(f"     ✅ 分类正确")
                    else:
                        print(f"     ⚠️ 期望分类: {case['expected_category']}, 实际: {result.category}")
                
                # 检查是否应该忽略
                if "expected_ignore" in case:
                    if result.should_ignore == case["expected_ignore"]:
                        print(f"     ✅ 忽略判断正确")
                    else:
                        print(f"     ⚠️ 期望忽略: {case['expected_ignore']}, 实际: {result.should_ignore}")
                
            except Exception as e:
                print(f"     ❌ 分析失败: {e}")
    
    def test_minimax_batch_analysis(self):
        """测试MiniMax API批量分析"""
        print(f"\n测试批量分析...")
        
        # 创建测试内容项
        test_items = [
            ContentItem(
                id="batch_test_1",
                title="巨鲸转移ETH",
                content="某巨鲸地址转移10000个ETH到交易所",
                url="https://example.com/1",
                publish_time=datetime.now(),
                source_name="批量测试源1",
                source_type="rss"
            ),
            ContentItem(
                id="batch_test_2",
                title="美联储政策",
                content="美联储委员发表关于利率政策的重要讲话",
                url="https://example.com/2",
                publish_time=datetime.now(),
                source_name="批量测试源2",
                source_type="rss"
            )
        ]
        
        try:
            start_time = datetime.now()
            results = self.llm_analyzer.batch_analyze(test_items)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            
            assert len(results) == len(test_items)
            
            print(f"✅ 批量分析完成:")
            print(f"   处理项目数: {len(results)}")
            print(f"   总耗时: {duration:.2f}秒")
            print(f"   平均每项: {duration/len(results):.2f}秒")
            
            for i, result in enumerate(results):
                print(f"   项目{i+1}: {result.category} (置信度: {result.confidence:.2f})")
                
        except Exception as e:
            print(f"❌ 批量分析失败: {e}")
            raise
    
    def test_minimax_error_handling(self):
        """测试MiniMax API错误处理"""
        print(f"\n测试错误处理...")
        
        # 测试无效API key
        invalid_analyzer = LLMAnalyzer(
            api_key="invalid_key_test",
            model="MiniMax-M2.1",
            mock_mode=False
        )
        
        try:
            result = invalid_analyzer.analyze_content("测试内容", "测试标题", "测试来源")
            
            # 即使API调用失败，也应该返回有效的AnalysisResult
            assert isinstance(result, AnalysisResult)
            assert result.category == "未分类"
            assert result.confidence == 0.0
            assert "分析失败" in result.reasoning
            
            print(f"✅ 错误处理正确: {result.reasoning}")
            
        except Exception as e:
            print(f"⚠️ 错误处理异常: {e}")
    
    def test_minimax_mock_mode_comparison(self):
        """测试MiniMax真实API与模拟模式的对比"""
        print(f"\n测试真实API与模拟模式对比...")
        
        test_content = "某巨鲸地址转移15000个ETH到Binance交易所"
        test_title = "巨鲸资金转移"
        test_source = "对比测试"
        
        # 模拟模式分析
        mock_analyzer = LLMAnalyzer(
            api_key="mock_key",
            model="MiniMax-M2.1",
            mock_mode=True
        )
        
        mock_result = mock_analyzer.analyze_content(test_content, test_title, test_source)
        
        print(f"模拟模式结果:")
        print(f"   分类: {mock_result.category}")
        print(f"   置信度: {mock_result.confidence:.2f}")
        
        # 真实API分析
        try:
            real_result = self.llm_analyzer.analyze_content(test_content, test_title, test_source)
            
            print(f"真实API结果:")
            print(f"   分类: {real_result.category}")
            print(f"   置信度: {real_result.confidence:.2f}")
            
            # 比较结果
            if mock_result.category == real_result.category:
                print(f"✅ 分类结果一致")
            else:
                print(f"⚠️ 分类结果不同 - 模拟: {mock_result.category}, 真实: {real_result.category}")
                
        except Exception as e:
            print(f"❌ 真实API调用失败: {e}")
    
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