"""
结构化输出管理器

使用instructor等工具强制大模型返回结构化数据，确保输出格式的一致性和可解析性。
"""

import json
import logging
from typing import Dict, Any, List, Optional, Type, Union
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator, ValidationError
from enum import Enum

logger = logging.getLogger(__name__)


class StructuredOutputLibrary(Enum):
    """支持的结构化输出库"""
    INSTRUCTOR = "instructor"
    NATIVE_JSON = "native_json"  # 使用原生JSON模式


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class StructuredAnalysisResult(BaseModel):
    """
    结构化分析结果模型
    
    这是大模型必须返回的标准格式，包含所有必需字段。
    """
    model_config = {"json_schema_extra": {
        "example": {
            "time": "2024-01-01 12:00",
            "category": "大户动向",
            "weight_score": 85,
            "summary": "某巨鲸地址转移10000 ETH到交易所",
            "source": "https://example.com/news/123"
        }
    }}
    
    time: str = Field(..., description="发布时间，保持原始RFC 2822格式（如 'Mon, 15 Jan 2024 14:30:00 +0000'）")
    category: str = Field(..., description="动态分类类别，由大模型返回决定")
    weight_score: int = Field(..., ge=0, le=100, description="重要性评分，0-100之间")
    summary: str = Field(..., min_length=1, description="内容摘要，不能为空")
    source: str = Field(..., description="原文链接URL")
    
    @field_validator('time')
    @classmethod
    def validate_time(cls, v: str) -> str:
        """验证时间格式"""
        if not v or not v.strip():
            raise ValueError("时间不能为空")
        return v.strip()
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        """验证分类不为空"""
        if not v or not v.strip():
            raise ValueError("分类不能为空")
        return v.strip()
    
    @field_validator('summary')
    @classmethod
    def validate_summary(cls, v: str) -> str:
        """验证摘要不为空"""
        if not v or not v.strip():
            raise ValueError("摘要不能为空")
        return v.strip()
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """验证来源URL"""
        if not v or not v.strip():
            raise ValueError("来源URL不能为空")
        # 基本URL格式验证
        v = v.strip()
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError(f"来源必须是有效的URL: {v}")
        return v


class BatchAnalysisResult(BaseModel):
    """批量分析结果容器"""
    results: List[StructuredAnalysisResult] = Field(
        default_factory=list,
        description="分析结果列表，可以为空列表表示所有内容被过滤"
    )
    
    @field_validator('results')
    @classmethod
    def validate_results(cls, v: List[StructuredAnalysisResult]) -> List[StructuredAnalysisResult]:
        """验证结果列表"""
        if v is None:
            return []
        return v


class StructuredOutputManager:
    """
    结构化输出管理器
    
    负责强制大模型返回标准JSON格式，实现输出格式验证和错误恢复机制。
    支持多种结构化输出库的集成（instructor等）。
    """
    
    def __init__(self, library: str = "instructor"):
        """
        初始化结构化输出管理器
        
        Args:
            library: 使用的结构化输出库名称，默认为"instructor"
        """
        self.library = self._validate_library(library)
        self.output_schema = self._build_output_schema()
        self.instructor_client = None
        
        logger.info(f"初始化结构化输出管理器，使用库: {self.library.value}")
    
    def _validate_library(self, library: str) -> StructuredOutputLibrary:
        """验证并返回支持的库"""
        try:
            return StructuredOutputLibrary(library.lower())
        except ValueError:
            logger.warning(f"不支持的库 '{library}'，使用默认库 'instructor'")
            return StructuredOutputLibrary.INSTRUCTOR
    
    def _build_output_schema(self) -> Dict[str, Any]:
        """构建输出数据结构的JSON Schema"""
        return StructuredAnalysisResult.model_json_schema()
    
    def setup_output_schema(self, schema: Optional[Dict[str, Any]] = None) -> None:
        """
        设置输出数据结构的schema
        
        Args:
            schema: 自定义的JSON Schema，如果为None则使用默认schema
        """
        if schema is not None:
            self.output_schema = schema
            logger.info("已设置自定义输出schema")
        else:
            self.output_schema = self._build_output_schema()
            logger.info("使用默认输出schema")
    
    def setup_instructor_client(self, llm_client: Any) -> Any:
        """
        设置instructor客户端
        
        Args:
            llm_client: LLM客户端（如OpenAI客户端）
            
        Returns:
            配置好的instructor客户端
        """
        if self.library != StructuredOutputLibrary.INSTRUCTOR:
            logger.warning(f"当前使用的库是 {self.library.value}，不需要instructor客户端")
            return llm_client
        
        try:
            import instructor
            
            # 检测客户端类型并使用相应的patch方法
            client_type = type(llm_client).__name__
            
            if 'OpenAI' in client_type:
                self.instructor_client = instructor.from_openai(llm_client)
                logger.info("已配置OpenAI instructor客户端")
            elif 'Anthropic' in client_type:
                self.instructor_client = instructor.from_anthropic(llm_client)
                logger.info("已配置Anthropic instructor客户端")
            else:
                # 尝试通用patch
                self.instructor_client = instructor.patch(llm_client)
                logger.info(f"已配置通用instructor客户端 ({client_type})")
            
            return self.instructor_client
            
        except ImportError:
            logger.error("未安装instructor库，请运行: pip3 install instructor")
            raise
        except Exception as e:
            logger.error(f"配置instructor客户端失败: {e}")
            raise
    
    def force_structured_response(
        self,
        llm_client: Any,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        max_retries: int = 3,
        temperature: float = 0.1,
        batch_mode: bool = False
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """
        强制大模型返回结构化响应
        
        Args:
            llm_client: LLM客户端
            messages: 消息列表
            model: 模型名称
            max_retries: 最大重试次数
            temperature: 温度参数
            batch_mode: 是否批量模式（返回列表）
            
        Returns:
            结构化的分析结果
            
        Raises:
            ValidationError: 验证失败
            Exception: 其他错误
        """
        if self.library == StructuredOutputLibrary.INSTRUCTOR:
            return self._force_with_instructor(
                llm_client, messages, model, max_retries, temperature, batch_mode
            )
        else:
            return self._force_with_native_json(
                llm_client, messages, model, max_retries, temperature, batch_mode
            )
    
    def _force_with_instructor(
        self,
        llm_client: Any,
        messages: List[Dict[str, str]],
        model: str,
        max_retries: int,
        temperature: float,
        batch_mode: bool
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """使用instructor库强制结构化输出"""
        try:
            import instructor
            
            # 如果还没有设置instructor客户端，现在设置
            if self.instructor_client is None:
                self.instructor_client = self.setup_instructor_client(llm_client)
            
            # 选择响应模型
            response_model = BatchAnalysisResult if batch_mode else StructuredAnalysisResult
            
            # 调用instructor
            result = self.instructor_client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                temperature=temperature
            )
            
            logger.info(f"成功获取结构化响应 (batch_mode={batch_mode})")
            return result
            
        except ValidationError as e:
            logger.error(f"结构化输出验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"使用instructor强制结构化输出失败: {e}")
            raise
    
    def _force_with_native_json(
        self,
        llm_client: Any,
        messages: List[Dict[str, str]],
        model: str,
        max_retries: int,
        temperature: float,
        batch_mode: bool
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """使用原生JSON模式强制结构化输出"""
        try:
            # 添加JSON格式要求到系统消息
            json_instruction = self._build_json_instruction(batch_mode)
            
            # 修改消息以包含JSON格式要求
            modified_messages = self._add_json_instruction_to_messages(messages, json_instruction)
            
            # 调用LLM
            response = llm_client.chat.completions.create(
                model=model,
                messages=modified_messages,
                temperature=temperature,
                response_format={"type": "json_object"}  # OpenAI JSON模式
            )
            
            # 解析响应
            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            
            # 验证和转换为Pydantic模型
            if batch_mode:
                result = BatchAnalysisResult(**parsed_data)
            else:
                result = StructuredAnalysisResult(**parsed_data)
            
            logger.info(f"成功获取原生JSON结构化响应 (batch_mode={batch_mode})")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            # 尝试恢复
            return self._handle_malformed_json(content, batch_mode)
        except ValidationError as e:
            logger.error(f"结构化输出验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"使用原生JSON模式失败: {e}")
            raise
    
    def _build_json_instruction(self, batch_mode: bool) -> str:
        """构建JSON格式指令"""
        if batch_mode:
            return """
你必须返回一个JSON对象，格式如下：
{
    "results": [
        {
            "time": "发布时间(保持原始RFC 2822格式)",
            "category": "分类类别",
            "weight_score": 0-100的整数,
            "summary": "内容摘要",
            "source": "原文链接URL"
        }
    ]
}

注意：
- results可以是空列表[]，表示所有内容被过滤
- 每个结果对象必须包含所有5个字段
- time保持原始RFC 2822格式（如 'Mon, 15 Jan 2024 14:30:00 +0000'）
- weight_score必须是0-100之间的整数
- source必须是有效的URL（以http://或https://开头）
"""
        else:
            return """
你必须返回一个JSON对象，格式如下：
{
    "time": "发布时间(保持原始RFC 2822格式)",
    "category": "分类类别",
    "weight_score": 0-100的整数,
    "summary": "内容摘要",
    "source": "原文链接URL"
}

注意：
- 必须包含所有5个字段
- time保持原始RFC 2822格式（如 'Mon, 15 Jan 2024 14:30:00 +0000'）
- weight_score必须是0-100之间的整数
- source必须是有效的URL（以http://或https://开头）
"""
    
    def _add_json_instruction_to_messages(
        self,
        messages: List[Dict[str, str]],
        json_instruction: str
    ) -> List[Dict[str, str]]:
        """将JSON格式指令添加到消息中"""
        modified_messages = messages.copy()
        
        # 查找系统消息
        system_message_index = None
        for i, msg in enumerate(modified_messages):
            if msg.get('role') == 'system':
                system_message_index = i
                break
        
        # 添加JSON指令
        if system_message_index is not None:
            # 追加到现有系统消息
            modified_messages[system_message_index]['content'] += f"\n\n{json_instruction}"
        else:
            # 创建新的系统消息
            modified_messages.insert(0, {
                'role': 'system',
                'content': json_instruction
            })
        
        return modified_messages
    
    def validate_output_structure(self, response: Dict[str, Any]) -> ValidationResult:
        """
        验证输出结构的有效性
        
        Args:
            response: 待验证的响应字典
            
        Returns:
            ValidationResult对象，包含验证结果和错误信息
        """
        errors = []
        warnings = []
        
        # 检查是否是批量结果
        is_batch = 'results' in response
        
        if is_batch:
            # 验证批量结果
            if not isinstance(response.get('results'), list):
                errors.append("results字段必须是列表")
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
            
            # 验证每个结果项
            for i, item in enumerate(response['results']):
                item_errors = self._validate_single_result(item)
                errors.extend([f"结果项{i}: {err}" for err in item_errors])
            
            # 空列表是有效的（表示所有内容被过滤）
            if len(response['results']) == 0:
                warnings.append("结果列表为空，所有内容可能被过滤")
        else:
            # 验证单个结果
            errors = self._validate_single_result(response)
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("输出结构验证通过")
        else:
            logger.warning(f"输出结构验证失败: {errors}")
        
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
    
    def _validate_single_result(self, result: Dict[str, Any]) -> List[str]:
        """验证单个结果项"""
        errors = []
        
        # 检查必需字段
        required_fields = ['time', 'category', 'weight_score', 'summary', 'source']
        for field in required_fields:
            if field not in result:
                errors.append(f"缺少必需字段: {field}")
        
        # 验证字段类型和值
        if 'time' in result and not isinstance(result['time'], str):
            errors.append("time字段必须是字符串")
        
        if 'category' in result and not isinstance(result['category'], str):
            errors.append("category字段必须是字符串")
        
        if 'weight_score' in result:
            if not isinstance(result['weight_score'], int):
                errors.append("weight_score字段必须是整数")
            elif not 0 <= result['weight_score'] <= 100:
                errors.append("weight_score必须在0-100之间")
        
        if 'summary' in result:
            if not isinstance(result['summary'], str):
                errors.append("summary字段必须是字符串")
            elif not result['summary'].strip():
                errors.append("summary不能为空")
        
        if 'source' in result:
            if not isinstance(result['source'], str):
                errors.append("source字段必须是字符串")
            elif not (result['source'].startswith('http://') or result['source'].startswith('https://')):
                errors.append("source必须是有效的URL")
        
        return errors
    
    def handle_malformed_response(
        self,
        response: str,
        batch_mode: bool = False
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult, None]:
        """
        处理格式错误的响应，尝试恢复
        
        Args:
            response: 原始响应字符串
            batch_mode: 是否批量模式
            
        Returns:
            恢复后的结构化结果，如果无法恢复则返回None
        """
        logger.warning("尝试恢复格式错误的响应")
        
        try:
            # 尝试从markdown代码块中提取JSON
            json_str = self._extract_json_from_markdown(response)
            if json_str:
                parsed_data = json.loads(json_str)
                
                # 验证并转换
                if batch_mode:
                    return BatchAnalysisResult(**parsed_data)
                else:
                    return StructuredAnalysisResult(**parsed_data)
            
            # 尝试直接解析
            parsed_data = json.loads(response)
            if batch_mode:
                return BatchAnalysisResult(**parsed_data)
            else:
                return StructuredAnalysisResult(**parsed_data)
                
        except Exception as e:
            logger.error(f"无法恢复格式错误的响应: {e}")
            return None
    
    def _handle_malformed_json(
        self,
        response: str,
        batch_mode: bool
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """处理格式错误的JSON"""
        result = self.handle_malformed_response(response, batch_mode)
        if result is None:
            raise ValueError(f"无法解析响应为有效的JSON: {response[:200]}...")
        return result
    
    def _extract_json_from_markdown(self, text: str) -> Optional[str]:
        """从markdown代码块中提取JSON"""
        import re
        
        # 匹配 ```json ... ``` 或 ``` ... ```
        patterns = [
            r'```json\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def get_supported_libraries(self) -> List[str]:
        """
        获取支持的结构化输出库列表
        
        Returns:
            支持的库名称列表
        """
        return [lib.value for lib in StructuredOutputLibrary]
    
    def get_output_schema(self) -> Dict[str, Any]:
        """
        获取当前的输出schema
        
        Returns:
            JSON Schema字典
        """
        return self.output_schema
    
    def create_example_response(self, batch_mode: bool = False) -> Dict[str, Any]:
        """
        创建示例响应，用于测试和文档
        
        Args:
            batch_mode: 是否批量模式
            
        Returns:
            示例响应字典
        """
        single_example = {
            "time": "2024-01-01 12:00",
            "category": "大户动向",
            "weight_score": 85,
            "summary": "某巨鲸地址转移10000 ETH到交易所",
            "source": "https://example.com/news/123"
        }
        
        if batch_mode:
            return {
                "results": [
                    single_example,
                    {
                        "time": "2024-01-01 13:30",
                        "category": "安全事件",
                        "weight_score": 95,
                        "summary": "某DeFi协议发现严重漏洞",
                        "source": "https://example.com/news/456"
                    }
                ]
            }
        else:
            return single_example
