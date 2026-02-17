"""
测试结构化输出管理器

测试StructuredOutputManager类的核心功能，包括：
- 结构化输出强制
- 输出格式验证
- 错误恢复机制
- 多种库支持
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from pydantic import ValidationError

from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult,
    ValidationResult,
    StructuredOutputLibrary
)


class TestStructuredAnalysisResult:
    """测试StructuredAnalysisResult数据模型"""
    
    def test_valid_result_creation(self):
        """测试创建有效的结果对象"""
        result = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="大户动向",
            weight_score=85,
            title="某巨鲸地址转移10000 ETH到交易所",

            body="某巨鲸地址转移10000 ETH到交易所",
            source="https://example.com/news/123"
        )
        
        assert result.time == "2024-01-01 12:00"
        assert result.category == "大户动向"
        assert result.weight_score == 85
        assert result.summary == "某巨鲸地址转移10000 ETH到交易所"
        assert result.source == "https://example.com/news/123"
    
    def test_weight_score_validation(self):
        """测试weight_score的范围验证"""
        # 有效范围
        result = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=0,
            title="测试",

            body="测试",
            source="https://example.com"
        )
        assert result.weight_score == 0
        
        result = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=100,
            title="测试",

            body="测试",
            source="https://example.com"
        )
        assert result.weight_score == 100
        
        # 无效范围
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="测试",
                weight_score=-1,
                title="测试",

                body="测试",
                source="https://example.com"
            )
        
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="测试",
                weight_score=101,
                title="测试",

                body="测试",
                source="https://example.com"
            )
    
    def test_empty_field_validation(self):
        """测试空字段验证"""
        # 空时间
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="",
                category="测试",
                weight_score=50,
                title="测试",

                body="测试",
                source="https://example.com"
            )
        
        # 空分类
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="",
                weight_score=50,
                title="测试",

                body="测试",
                source="https://example.com"
            )
        
        # 空摘要
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="测试",
                weight_score=50,
                summary="",
                source="https://example.com"
            )
    
    def test_source_url_validation(self):
        """测试source URL验证"""
        # 有效URL
        result = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=50,
            title="测试",

            body="测试",
            source="https://example.com/news"
        )
        assert result.source == "https://example.com/news"
        
        result = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=50,
            title="测试",

            body="测试",
            source="http://example.com/news"
        )
        assert result.source == "http://example.com/news"
        
        # 无效URL
        with pytest.raises(ValidationError):
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="测试",
                weight_score=50,
                title="测试",

                body="测试",
                source="not-a-url"
            )


class TestBatchAnalysisResult:
    """测试BatchAnalysisResult数据模型"""
    
    def test_empty_batch_result(self):
        """测试空批量结果（所有内容被过滤）"""
        batch = BatchAnalysisResult(results=[])
        assert batch.results == []
        assert len(batch.results) == 0
    
    def test_batch_with_multiple_results(self):
        """测试包含多个结果的批量结果"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="大户动向",
                weight_score=85,
                title="测试1",

                body="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 13:00",
                category="安全事件",
                weight_score=95,
                title="测试2",

                body="测试2",
                source="https://example.com/2"
            )
        ]
        
        batch = BatchAnalysisResult(results=results)
        assert len(batch.results) == 2
        assert batch.results[0].category == "大户动向"
        assert batch.results[1].category == "安全事件"


class TestStructuredOutputManager:
    """测试StructuredOutputManager类"""
    
    def test_initialization(self):
        """测试初始化"""
        manager = StructuredOutputManager(library="instructor")
        assert manager.library == StructuredOutputLibrary.INSTRUCTOR
        assert manager.output_schema is not None
    
    def test_unsupported_library_fallback(self):
        """测试不支持的库回退到默认库"""
        manager = StructuredOutputManager(library="unsupported")
        assert manager.library == StructuredOutputLibrary.INSTRUCTOR
    
    def test_get_supported_libraries(self):
        """测试获取支持的库列表"""
        manager = StructuredOutputManager()
        libraries = manager.get_supported_libraries()
        assert "instructor" in libraries
        assert "native_json" in libraries
    
    def test_get_output_schema(self):
        """测试获取输出schema"""
        manager = StructuredOutputManager()
        schema = manager.get_output_schema()
        
        assert "properties" in schema
        assert "time" in schema["properties"]
        assert "category" in schema["properties"]
        assert "weight_score" in schema["properties"]
        assert "summary" in schema["properties"]
        assert "source" in schema["properties"]
    
    def test_setup_output_schema(self):
        """测试设置自定义schema"""
        manager = StructuredOutputManager()
        
        custom_schema = {"custom": "schema"}
        manager.setup_output_schema(custom_schema)
        assert manager.output_schema == custom_schema
        
        # 重置为默认
        manager.setup_output_schema(None)
        assert "properties" in manager.output_schema
    
    def test_validate_output_structure_single_valid(self):
        """测试验证单个有效结果"""
        manager = StructuredOutputManager()
        
        response = {
            "time": "2024-01-01 12:00",
            "category": "大户动向",
            "weight_score": 85,
            "summary": "测试摘要",
            "source": "https://example.com/news"
        }
        
        result = manager.validate_output_structure(response)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_output_structure_single_invalid(self):
        """测试验证单个无效结果"""
        manager = StructuredOutputManager()
        
        # 缺少必需字段
        response = {
            "time": "2024-01-01 12:00",
            "category": "大户动向"
            # 缺少其他字段
        }
        
        result = manager.validate_output_structure(response)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_validate_output_structure_batch_valid(self):
        """测试验证批量有效结果"""
        manager = StructuredOutputManager()
        
        response = {
            "results": [
                {
                    "time": "2024-01-01 12:00",
                    "category": "大户动向",
                    "weight_score": 85,
                    "summary": "测试1",
                    "source": "https://example.com/1"
                },
                {
                    "time": "2024-01-01 13:00",
                    "category": "安全事件",
                    "weight_score": 95,
                    "summary": "测试2",
                    "source": "https://example.com/2"
                }
            ]
        }
        
        result = manager.validate_output_structure(response)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_output_structure_batch_empty(self):
        """测试验证空批量结果"""
        manager = StructuredOutputManager()
        
        response = {"results": []}
        
        result = manager.validate_output_structure(response)
        assert result.is_valid
        assert len(result.warnings) > 0  # 应该有警告
    
    def test_validate_output_structure_batch_invalid(self):
        """测试验证批量无效结果"""
        manager = StructuredOutputManager()
        
        response = {
            "results": [
                {
                    "time": "2024-01-01 12:00",
                    "category": "大户动向",
                    "weight_score": 150,  # 超出范围
                    "summary": "测试",
                    "source": "https://example.com"
                }
            ]
        }
        
        result = manager.validate_output_structure(response)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_create_example_response_single(self):
        """测试创建单个示例响应"""
        manager = StructuredOutputManager()
        example = manager.create_example_response(batch_mode=False)
        
        assert "time" in example
        assert "category" in example
        assert "weight_score" in example
        assert "summary" in example
        assert "source" in example
    
    def test_create_example_response_batch(self):
        """测试创建批量示例响应"""
        manager = StructuredOutputManager()
        example = manager.create_example_response(batch_mode=True)
        
        assert "results" in example
        assert isinstance(example["results"], list)
        assert len(example["results"]) > 0
    
    def test_extract_json_from_markdown(self):
        """测试从markdown代码块提取JSON"""
        manager = StructuredOutputManager()
        
        # 带json标记的代码块
        text = """
这是一些文本
```json
{
    "time": "2024-01-01 12:00",
    "category": "测试",
    "weight_score": 50,
    "summary": "测试",
    "source": "https://example.com"
}
```
更多文本
"""
        
        json_str = manager._extract_json_from_markdown(text)
        assert json_str is not None
        data = json.loads(json_str)
        assert data["category"] == "测试"
        
        # 不带json标记的代码块
        text2 = """
```
{
    "time": "2024-01-01 12:00",
    "category": "测试2",
    "weight_score": 60,
    "summary": "测试2",
    "source": "https://example.com"
}
```
"""
        
        json_str2 = manager._extract_json_from_markdown(text2)
        assert json_str2 is not None
        data2 = json.loads(json_str2)
        assert data2["category"] == "测试2"
    
    def test_handle_malformed_response_with_markdown(self):
        """测试处理包含markdown的格式错误响应"""
        manager = StructuredOutputManager()
        
        response = """
这是一些解释文本
```json
{
    "time": "2024-01-01 12:00",
    "category": "大户动向",
    "weight_score": 85,
    "summary": "测试摘要",
    "source": "https://example.com/news"
}
```
"""
        
        result = manager.handle_malformed_response(response, batch_mode=False)
        assert result is not None
        assert isinstance(result, StructuredAnalysisResult)
        assert result.category == "大户动向"
    
    def test_handle_malformed_response_invalid(self):
        """测试处理无法恢复的格式错误响应"""
        manager = StructuredOutputManager()
        
        response = "这不是有效的JSON"
        
        result = manager.handle_malformed_response(response, batch_mode=False)
        assert result is None
    
    def test_setup_instructor_client_openai(self):
        """测试设置OpenAI instructor客户端"""
        manager = StructuredOutputManager(library="instructor")
        
        # 测试当instructor未安装时的错误处理
        # 由于instructor已安装，我们只测试客户端类型检测逻辑
        mock_client = Mock()
        mock_client.__class__.__name__ = "OpenAI"
        
        # 这个测试验证方法存在且可以被调用
        # 实际的instructor集成将在集成测试中验证
        assert hasattr(manager, 'setup_instructor_client')
        assert callable(manager.setup_instructor_client)
    
    def test_build_json_instruction_single(self):
        """测试构建单个结果的JSON指令"""
        manager = StructuredOutputManager()
        instruction = manager._build_json_instruction(batch_mode=False)
        
        assert "time" in instruction
        assert "category" in instruction
        assert "weight_score" in instruction
        assert "summary" in instruction
        assert "source" in instruction
    
    def test_build_json_instruction_batch(self):
        """测试构建批量结果的JSON指令"""
        manager = StructuredOutputManager()
        instruction = manager._build_json_instruction(batch_mode=True)
        
        assert "results" in instruction
        assert "[]" in instruction  # 提到空列表
    
    def test_add_json_instruction_to_messages_with_system(self):
        """测试向已有系统消息添加JSON指令"""
        manager = StructuredOutputManager()
        
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "分析这个"}
        ]
        
        instruction = "JSON格式要求"
        result = manager._add_json_instruction_to_messages(messages, instruction)
        
        assert len(result) == 2
        assert "JSON格式要求" in result[0]["content"]
        assert "你是一个助手" in result[0]["content"]
    
    def test_add_json_instruction_to_messages_without_system(self):
        """测试向没有系统消息的消息列表添加JSON指令"""
        manager = StructuredOutputManager()
        
        messages = [
            {"role": "user", "content": "分析这个"}
        ]
        
        instruction = "JSON格式要求"
        result = manager._add_json_instruction_to_messages(messages, instruction)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "JSON格式要求" in result[0]["content"]


class TestValidationResult:
    """测试ValidationResult数据类"""
    
    def test_valid_result(self):
        """测试有效的验证结果"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_invalid_result_with_errors(self):
        """测试包含错误的验证结果"""
        result = ValidationResult(
            is_valid=False,
            errors=["错误1", "错误2"],
            warnings=["警告1"]
        )
        
        assert not result.is_valid
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
