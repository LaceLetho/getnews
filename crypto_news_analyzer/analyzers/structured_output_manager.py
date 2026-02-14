"""
结构化输出管理器

使用instructor等工具强制大模型返回结构化数据，确保输出格式的一致性和可解析性。
"""

import json
import logging
from typing import Dict, Any, List, Optional, Type, Union
from dataclasses import dataclass
from pathlib import Path
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
    字段定义和描述来自 prompts/analysis_prompt.md 中的 Output Format 部分。
    """
    model_config = {"json_schema_extra": {
        "example": {
            "time": "Mon, 15 Jan 2024 14:30:00 +0000",
            "category": "Whale",
            "weight_score": 85,
            "summary": "某巨鲸地址转移10000 ETH到交易所",
            "source": "https://example.com/news/123",
            "related_sources": [
                "https://example.com/related1",
                "https://example.com/related2"
            ]
        }
    }}
    
    # 字段定义参考 prompts/analysis_prompt.md 的 Output Format 部分
    time: str = Field(..., description="RFC 2822 格式时间")
    category: str = Field(..., description="Whale | MacroLiquidity | Regulation | NewProject | Arbitrage | Truth | MonetarySystem | MarketTrend")
    weight_score: int = Field(..., ge=0, le=100, description="0-100 (整数，根据[Scoring Rubric]打分)")
    summary: str = Field(..., min_length=1, description="根据 [Core Directives] 使用中文编写你的总结")
    source: str = Field(..., description="保留该条消息的原始 URL")
    related_sources: List[str] = Field(
        default_factory=list,
        description="所有相关信息源链接的数组，包括：1) 系统爬取提供的原始信息源URL，2) 你使用web_search工具搜索到的相关链接，3) 你使用x_search工具搜索到的相关推文链接。如果没有额外的相关链接，可以为空数组[]"
    )
    
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
    
    @field_validator('related_sources')
    @classmethod
    def validate_related_sources(cls, v: List[str]) -> List[str]:
        """验证相关信息源列表"""
        if v is None:
            return []
        
        validated = []
        for url in v:
            if url and url.strip():
                url = url.strip()
                if url.startswith('http://') or url.startswith('https://'):
                    validated.append(url)
        
        return validated


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
        batch_mode: bool = False,
        enable_web_search: bool = False
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
            enable_web_search: 是否启用web_search工具（仅Grok支持）
            
        Returns:
            结构化的分析结果
            
        Raises:
            ValidationError: 验证失败
            Exception: 其他错误
        """
        if self.library == StructuredOutputLibrary.INSTRUCTOR:
            return self._force_with_instructor(
                llm_client, messages, model, max_retries, temperature, batch_mode, enable_web_search
            )
        else:
            return self._force_with_native_json(
                llm_client, messages, model, max_retries, temperature, batch_mode, enable_web_search
            )
    
    def _force_with_instructor(
        self,
        llm_client: Any,
        messages: List[Dict[str, str]],
        model: str,
        max_retries: int,
        temperature: float,
        batch_mode: bool,
        enable_web_search: bool = False
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """使用instructor库强制结构化输出"""
        try:
            import instructor
            
            # 如果还没有设置instructor客户端，现在设置
            if self.instructor_client is None:
                self.instructor_client = self.setup_instructor_client(llm_client)
            
            # 选择响应模型
            response_model = BatchAnalysisResult if batch_mode else StructuredAnalysisResult
            
            # 构建调用参数
            call_params = {
                "model": model,
                "messages": messages,
                "response_model": response_model,
                "max_retries": max_retries,
                "temperature": temperature
            }
            
            # 如果启用web_search工具（仅Grok支持）
            if enable_web_search:
                call_params["tools"] = [
                    {"type": "web_search"},
                    {"type": "x_search"}
                ]
                logger.info("已启用web_search和x_search工具，Grok将自动搜索重要信息")
            
            # 拦截HTTP请求
            captured_request = self._capture_http_request(
                lambda: self.instructor_client.chat.completions.create(**call_params)
            )
            
            # 打印捕获的完整HTTP请求
            if captured_request:
                self._log_captured_http_request(captured_request)
            
            # 实际调用（已经在capture中执行了，这里获取结果）
            result = captured_request.get('result') if captured_request else None
            
            if result is None:
                # 如果拦截失败，直接调用
                result = self.instructor_client.chat.completions.create(**call_params)
            
            logger.info(f"成功获取结构化响应 (batch_mode={batch_mode}, web_search={enable_web_search})")
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
        batch_mode: bool,
        enable_web_search: bool = False
    ) -> Union[StructuredAnalysisResult, BatchAnalysisResult]:
        """使用原生JSON模式强制结构化输出"""
        try:
            # 添加JSON格式要求到系统消息
            json_instruction = self._build_json_instruction(batch_mode)
            
            # 修改消息以包含JSON格式要求
            modified_messages = self._add_json_instruction_to_messages(messages, json_instruction)
            
            # 构建调用参数
            call_params = {
                "model": model,
                "messages": modified_messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"}  # OpenAI JSON模式
            }
            
            # 如果启用web_search工具（仅Grok支持）
            if enable_web_search:
                call_params["tools"] = [
                    {"type": "web_search"},
                    {"type": "x_search"}
                ]
                logger.info("已启用web_search和x_search工具，Grok将自动搜索重要信息")
            
            # 调用LLM
            response = llm_client.chat.completions.create(**call_params)
            
            # 解析响应
            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            
            # 验证和转换为Pydantic模型
            if batch_mode:
                result = BatchAnalysisResult(**parsed_data)
            else:
                result = StructuredAnalysisResult(**parsed_data)
            
            logger.info(f"成功获取原生JSON结构化响应 (batch_mode={batch_mode}, web_search={enable_web_search})")
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
        """
        构建JSON格式指令
        
        注意：此方法从 prompts/analysis_prompt.md 动态读取 Output Format 部分
        """
        # 读取 analysis_prompt.md 中的 Output Format 部分
        try:
            prompt_path = Path("prompts/analysis_prompt.md")
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 提取 Output Format 部分
                import re
                match = re.search(r'# Output Format\s+(.*?)(?=\n#|\Z)', content, re.DOTALL)
                if match:
                    output_format_section = match.group(1).strip()
                    
                    if batch_mode:
                        return f"""
你必须返回一个JSON对象，格式如下：
{{
    "results": [
        // 这里是分析结果数组，每个元素的格式见下方定义
    ]
}}

注意：
- results可以是空列表[]，表示所有内容被过滤
- 每个结果对象的格式定义如下：

{output_format_section}
"""
                    else:
                        return f"""
{output_format_section}
"""
        except Exception as e:
            logger.warning(f"无法从 analysis_prompt.md 读取 Output Format: {e}，使用默认格式")
        
        # 如果读取失败，使用默认格式
        if batch_mode:
            return """
你必须返回一个JSON对象，格式如下：
{
    "results": [
        {
            "time": "RFC 2822 格式时间",
            "category": "Whale | MacroLiquidity | Regulation | NewProject | Arbitrage | Truth | MonetarySystem | MarketTrend",
            "weight_score": 0-100 (整数),
            "summary": "中文总结",
            "source": "原始 URL",
            "related_sources": ["相关链接数组"]
        }
    ]
}

注意：results可以是空列表[]
"""
        else:
            return """
你必须返回一个JSON对象，格式如下：
{
    "time": "RFC 2822 格式时间",
    "category": "Whale | MacroLiquidity | Regulation | NewProject | Arbitrage | Truth | MonetarySystem | MarketTrend",
    "weight_score": 0-100 (整数),
    "summary": "中文总结",
    "source": "原始 URL",
    "related_sources": ["相关链接数组"]
}
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
        
        # 验证可选的related_sources字段
        if 'related_sources' in result:
            if not isinstance(result['related_sources'], list):
                errors.append("related_sources字段必须是列表")
            else:
                for i, url in enumerate(result['related_sources']):
                    if not isinstance(url, str):
                        errors.append(f"related_sources[{i}]必须是字符串")
                    elif not (url.startswith('http://') or url.startswith('https://')):
                        errors.append(f"related_sources[{i}]必须是有效的URL")
        
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
        
        注意：示例格式参考 prompts/analysis_prompt.md 的 Output Format 部分
        
        Args:
            batch_mode: 是否批量模式
            
        Returns:
            示例响应字典
        """
        single_example = {
            "time": "Mon, 15 Jan 2024 14:30:00 +0000",
            "category": "Whale",
            "weight_score": 85,
            "summary": "某巨鲸地址转移10000 ETH到交易所",
            "source": "https://example.com/news/123",
            "related_sources": [
                "https://etherscan.io/tx/0x123",
                "https://twitter.com/whale_alert/status/123"
            ]
        }
        
        if batch_mode:
            return {
                "results": [
                    single_example,
                    {
                        "time": "Mon, 15 Jan 2024 15:45:00 +0000",
                        "category": "Regulation",
                        "weight_score": 95,
                        "summary": "SEC批准现货比特币ETF",
                        "source": "https://example.com/news/456",
                        "related_sources": [
                            "https://sec.gov/announcement/456",
                            "https://twitter.com/sec/status/456"
                        ]
                    }
                ]
            }
        else:
            return single_example

    def _capture_http_request(self, api_call_func):
        """
        拦截HTTP请求，捕获实际发送的内容
        
        Args:
            api_call_func: 要执行的API调用函数
            
        Returns:
            包含请求详情和结果的字典
        """
        captured = {'request': None, 'result': None}
        
        try:
            # 尝试通过httpx拦截
            import httpx
            
            # 保存原始的request方法
            original_request = httpx.Client.request
            
            def intercepted_request(self, method, url, **kwargs):
                # 捕获请求
                captured['request'] = {
                    'method': method,
                    'url': str(url),
                    'headers': dict(kwargs.get('headers', {})),
                    'json': kwargs.get('json'),
                    'content': kwargs.get('content')
                }
                # 调用原始方法
                return original_request(self, method, url, **kwargs)
            
            # 替换方法
            httpx.Client.request = intercepted_request
            
            # 执行API调用
            captured['result'] = api_call_func()
            
            # 恢复原始方法
            httpx.Client.request = original_request
            
        except Exception as e:
            logger.warning(f"HTTP请求拦截失败: {e}")
            # 如果拦截失败，直接执行
            try:
                captured['result'] = api_call_func()
            except Exception as call_error:
                logger.error(f"API调用失败: {call_error}")
                raise
        
        return captured
    
    def _log_captured_http_request(self, captured: Dict[str, Any]) -> None:
        """
        打印捕获的完整HTTP请求
        
        Args:
            captured: 捕获的请求信息
        """
        import json
        separator = "=" * 80
        
        request = captured.get('request')
        if not request:
            logger.warning("未能捕获HTTP请求详情")
            return
        
        logger.info(f"\n{separator}")
        logger.info("🌐 实际发送的完整HTTP请求")
        logger.info(f"{separator}\n")
        
        # 1. 请求行和头部
        logger.info(f"📡 HTTP请求:")
        logger.info(f"   {request.get('method', 'POST')} {request.get('url', 'N/A')}")
        logger.info(f"   Content-Type: application/json")
        
        # 打印关键headers（隐藏敏感信息）
        headers = request.get('headers', {})
        if headers:
            logger.info(f"\n   Headers:")
            for key, value in headers.items():
                if key.lower() in ['authorization', 'api-key']:
                    logger.info(f"      {key}: {value[:20]}...***")
                elif key.lower() in ['content-type', 'user-agent']:
                    logger.info(f"      {key}: {value}")
        
        # 2. 请求体
        request_body = request.get('json')
        if request_body:
            logger.info(f"\n📦 请求体 (JSON):")
            logger.info(f"{'-' * 80}")
            
            # 简化messages显示
            display_body = request_body.copy()
            if 'messages' in display_body:
                simplified_messages = []
                for msg in display_body['messages']:
                    content = msg.get('content', '')
                    if len(content) > 300:
                        simplified_msg = {
                            'role': msg['role'],
                            'content': f"{content[:150]}...[省略{len(content)-300}字符]...{content[-150:]}"
                        }
                    else:
                        simplified_msg = msg
                    simplified_messages.append(simplified_msg)
                display_body['messages'] = simplified_messages
            
            # 打印JSON
            try:
                json_str = json.dumps(display_body, indent=2, ensure_ascii=False)
                logger.info(json_str)
            except Exception as e:
                logger.warning(f"无法序列化请求体: {e}")
                logger.info(str(display_body))
            
            logger.info(f"{'-' * 80}")
        
        # 3. 统计信息
        logger.info(f"\n📊 请求统计:")
        if request_body:
            logger.info(f"   • messages数量: {len(request_body.get('messages', []))}")
            logger.info(f"   • tools数量: {len(request_body.get('tools', []))}")
            logger.info(f"   • 是否有tool_choice: {'是' if 'tool_choice' in request_body else '否'}")
            
            # 计算大致的请求大小
            try:
                request_size = len(json.dumps(request_body, ensure_ascii=False).encode('utf-8'))
                logger.info(f"   • 请求体大小: ~{request_size:,} bytes")
            except:
                pass
        
        logger.info(f"\n{separator}\n")
