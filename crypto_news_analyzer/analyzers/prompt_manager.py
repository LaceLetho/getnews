"""
动态提示词管理器

负责管理LLM分析的提示词配置和分类规则。
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


@dataclass
class CategoryConfig:
    """分类配置"""
    name: str
    description: str
    criteria: List[str]
    examples: List[str]
    priority: int = 1
    display_emoji: str = "📄"
    display_order: int = 999


class PromptManager:
    """提示词管理器"""
    
    def __init__(self, config_path: str = "./prompts/analysis_prompt.json"):
        """
        初始化提示词管理器
        
        Args:
            config_path: 提示词配置文件路径
        """
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        
    def get_analysis_prompt_template(self) -> str:
        """
        获取分析提示词模板
        
        Returns:
            提示词模板字符串
        """
        return self.load_prompt_template()
    
    def load_prompt_template(self) -> str:
        """
        加载提示词模板
        
        Returns:
            提示词模板字符串
        """
        self._load_config()
        return self.config_data.get("prompt_template", "")
    
    def load_categories_config(self) -> Dict[str, CategoryConfig]:
        """
        加载分类配置
        
        Returns:
            分类配置字典
        """
        self._load_config()
        categories = {}
        
        for name, config in self.config_data.get("categories", {}).items():
            categories[name] = CategoryConfig(
                name=name,
                description=config["description"],
                criteria=config["criteria"],
                examples=config["examples"],
                priority=config.get("priority", 1),
                display_emoji=config.get("display_emoji", "📄"),
                display_order=config.get("display_order", config.get("priority", 999))
            )
        
        return categories
    
    def build_analysis_prompt(self, content: str, title: str = "", source: str = "") -> str:
        """
        构建分析提示词
        
        Args:
            content: 要分析的内容
            title: 内容标题
            source: 内容来源
            
        Returns:
            完整的分析提示词
        """
        template = self.load_prompt_template()
        categories = self.load_categories_config()
        
        # 构建分类描述
        categories_description = self._build_categories_description(categories)
        
        # 构建忽略标准
        ignore_criteria = self._build_ignore_criteria()
        
        # 构建输出格式
        output_format = self.config_data.get("output_format", "")
        
        # 填充模板
        prompt = template.format(
            categories_description=categories_description,
            ignore_criteria=ignore_criteria,
            title=title,
            content=content,
            source=source,
            output_format=output_format
        )
        
        return prompt
    
    def validate_prompt_template(self, template: str) -> bool:
        """
        验证提示词模板有效性
        
        Args:
            template: 提示词模板
            
        Returns:
            是否有效
        """
        try:
            # 检查必需的占位符
            required_placeholders = [
                "{categories_description}",
                "{ignore_criteria}",
                "{title}",
                "{content}",
                "{source}",
                "{output_format}"
            ]
            
            for placeholder in required_placeholders:
                if placeholder not in template:
                    self.logger.error(f"提示词模板缺少必需占位符: {placeholder}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证提示词模板失败: {e}")
            return False
    
    def reload_configuration(self) -> None:
        """重新加载配置"""
        self.config_data = {}
        self._load_config()
        self.logger.info("提示词配置已重新加载")
    
    def get_llm_settings(self) -> Dict[str, Any]:
        """获取LLM设置"""
        # 从主配置文件获取LLM设置，而不是从prompt配置文件
        from ..config.manager import ConfigManager
        
        try:
            config_manager = ConfigManager()
            main_config = config_manager.load_config()
            llm_config = main_config.get("llm_config", {})
            
            # 返回LLM设置，保持向后兼容
            return {
                "temperature": llm_config.get("temperature", 0.1),
                "max_tokens": llm_config.get("max_tokens", 1000),
                "model": llm_config.get("model", "gpt-4"),
                "batch_size": llm_config.get("batch_size", 10)
            }
        except Exception as e:
            self.logger.warning(f"无法从主配置获取LLM设置，使用默认值: {e}")
            return {
                "temperature": 0.1,
                "max_tokens": 1000,
                "model": "gpt-4",
                "batch_size": 10
            }
    
    def _load_config(self) -> None:
        """加载配置文件"""
        if self.config_data:  # 已加载
            return
            
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"提示词配置文件不存在: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            self.logger.info("提示词配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载提示词配置失败: {e}")
            raise
    
    def _build_categories_description(self, categories: Dict[str, CategoryConfig]) -> str:
        """构建分类描述文本"""
        descriptions = []
        
        # 按优先级排序
        sorted_categories = sorted(categories.values(), key=lambda x: x.priority)
        
        for category in sorted_categories:
            desc = f"**{category.name}**: {category.description}\n"
            desc += "标准:\n"
            for criterion in category.criteria:
                desc += f"- {criterion}\n"
            desc += "示例:\n"
            for example in category.examples:
                desc += f"- {example}\n"
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _build_ignore_criteria(self) -> str:
        """构建忽略标准文本"""
        ignore_list = self.config_data.get("ignore_criteria", [])
        return "\n".join(f"- {criterion}" for criterion in ignore_list)


class DynamicCategoryManager:
    """动态分类管理器"""
    
    def __init__(self, config_path: str = "./prompts/analysis_prompt.json"):
        """
        初始化动态分类管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.prompt_manager = PromptManager(config_path)
        self.logger = logging.getLogger(__name__)
    
    def load_categories(self) -> Dict[str, CategoryConfig]:
        """加载分类配置"""
        return self.prompt_manager.load_categories_config()
    
    def add_category(self, name: str, config: CategoryConfig) -> None:
        """
        添加新分类
        
        Args:
            name: 分类名称
            config: 分类配置
        """
        # 这里可以实现动态添加分类的逻辑
        # 目前通过修改配置文件实现
        self.logger.info(f"添加分类: {name}")
    
    def remove_category(self, name: str) -> None:
        """
        移除分类
        
        Args:
            name: 分类名称
        """
        self.logger.info(f"移除分类: {name}")
    
    def update_category(self, name: str, config: CategoryConfig) -> None:
        """
        更新分类配置
        
        Args:
            name: 分类名称
            config: 新的分类配置
        """
        self.logger.info(f"更新分类: {name}")
    
    def get_category_list(self) -> List[str]:
        """获取分类名称列表"""
        categories = self.load_categories()
        category_list = list(categories.keys())
        category_list.extend(["未分类", "忽略"])
        return list(set(category_list))  # 去重
    
    def get_category_by_name(self, name: str) -> Optional[CategoryConfig]:
        """根据名称获取分类配置"""
        categories = self.load_categories()
        return categories.get(name)
    
    def export_categories_config(self) -> Dict[str, Any]:
        """导出分类配置"""
        categories = self.load_categories()
        config = {}
        for name, category in categories.items():
            config[name] = {
                "description": category.description,
                "criteria": category.criteria,
                "examples": category.examples,
                "priority": category.priority,
                "display_emoji": category.display_emoji,
                "display_order": category.display_order
            }
        return config
    
    def import_categories_config(self, config: Dict[str, Any]) -> None:
        """导入分类配置"""
        # 这里可以实现配置导入逻辑
        # 目前通过修改配置文件实现
        self.logger.info(f"导入 {len(config)} 个分类配置")
    
    def get_category_enum(self) -> Enum:
        """
        获取动态生成的分类枚举
        
        Returns:
            ContentCategory枚举类
        """
        categories = self.load_categories()
        return create_content_category_enum(categories)
    
    def validate_category_config(self, config: CategoryConfig) -> bool:
        """
        验证分类配置有效性
        
        Args:
            config: 分类配置
            
        Returns:
            是否有效
        """
        try:
            if not config.name or not config.description:
                return False
            
            if not config.criteria or not isinstance(config.criteria, list):
                return False
            
            if not config.examples or not isinstance(config.examples, list):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证分类配置失败: {e}")
            return False
    
    def reload_categories(self) -> None:
        """重新加载分类配置"""
        self.prompt_manager.reload_configuration()


def create_content_category_enum(categories: Dict[str, CategoryConfig]) -> Enum:
    """
    动态创建内容分类枚举
    
    Args:
        categories: 分类配置字典
        
    Returns:
        ContentCategory枚举类
    """
    category_dict = {}
    
    # 添加配置中的分类
    for name in categories.keys():
        enum_name = name.upper().replace(' ', '_').replace('/', '_')
        category_dict[enum_name] = name
    
    # 添加默认分类
    category_dict['UNCATEGORIZED'] = '未分类'
    category_dict['IGNORED'] = '忽略'
    
    return Enum('ContentCategory', category_dict)