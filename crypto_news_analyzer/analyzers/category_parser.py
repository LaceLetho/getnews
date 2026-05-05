"""
分类解析器

从 analysis_prompt.md 文件中解析分类定义，作为系统的唯一真实来源。
"""

import re
import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class CategoryDefinition:
    """分类定义"""
    key: str  # 英文key，如 "Whale"
    name: str  # 中文名称，如 "大户动向"
    description: str  # 描述
    emoji: str  # 图标（从描述或默认映射推断）


class CategoryParser:
    """
    分类解析器

    从 analysis_prompt.md 文件中解析分类定义。
    格式示例：
    # Categories (仅关注以下分类)
    - **Whale:** 大户/机构资金流向、链上巨鲸异动、大户持仓态度变化。
    - **Fed:** 美联储利率政策调整、美联储委员发言...
    """

    # 默认emoji映射（作为后备）
    DEFAULT_EMOJI_MAP = {
        "AlphaInsight": "🧠",
        "CorrelatedAssets": "📈",
        "Whale": "🐋",
        "MacroLiquidity": "📊",
        "Regulation": "🏛️",
        "NewProject": "🚀",
        "Arbitrage": "💰",
        "Truth": "💡",
        "MonetarySystem": "💵",
        "BlackSwan": "🦢",
        "Security": "🔒",  # 保留以防旧配置
        "Fed": "📊",  # 保留以防旧配置
    }

    # 英文key到中文名称的映射（从描述推断）
    KEY_TO_CHINESE_NAME = {
        "AlphaInsight": "深度洞察",
        "CorrelatedAssets": "相关资产",
        "Whale": "大户动向",
        "MacroLiquidity": "宏观流动性",
        "Regulation": "监管政策",
        "NewProject": "新产品",
        "Arbitrage": "套利机会",
        "Truth": "真相",
        "MonetarySystem": "货币体系",
        "BlackSwan": "黑天鹅",
        "Security": "安全事件",  # 保留以防旧配置
        "Fed": "利率事件",  # 保留以防旧配置
    }

    def __init__(self, prompt_file_path: str = "./prompts/analysis_prompt.md"):
        """
        初始化分类解析器

        Args:
            prompt_file_path: 提示词文件路径
        """
        self.prompt_file_path = Path(prompt_file_path)
        self._cached_categories: Dict[str, CategoryDefinition] = {}
        self._cache_valid = False

    def parse_categories(self, force_reload: bool = False) -> Dict[str, CategoryDefinition]:
        """
        解析分类定义

        Args:
            force_reload: 是否强制重新加载

        Returns:
            分类定义字典，key为英文key，value为CategoryDefinition
        """
        if self._cache_valid and not force_reload:
            return self._cached_categories

        try:
            content = self._load_prompt_file()
            categories = self._parse_categories_from_content(content)

            # 添加系统默认分类
            categories["Uncategorized"] = CategoryDefinition(
                key="Uncategorized",
                name="未分类",
                description="无法归类的内容",
                emoji="📄"
            )
            categories["Ignored"] = CategoryDefinition(
                key="Ignored",
                name="忽略",
                description="应该被忽略的内容",
                emoji="🚫"
            )

            self._cached_categories = categories
            self._cache_valid = True

            logger.info(f"成功解析 {len(categories)} 个分类定义")
            return categories

        except Exception as e:
            logger.error(f"解析分类定义失败: {e}")
            # 返回空字典或抛出异常
            raise

    def get_category_names(self) -> List[str]:
        """
        获取所有分类的中文名称列表

        Returns:
            中文名称列表
        """
        categories = self.parse_categories()
        return [cat.name for cat in categories.values()]

    def get_category_emoji_map(self) -> Dict[str, str]:
        """
        获取分类名称到emoji的映射

        Returns:
            {中文名称: emoji} 的字典
        """
        categories = self.parse_categories()
        return {cat.name: cat.emoji for cat in categories.values()}

    def get_category_by_name(self, name: str) -> CategoryDefinition:
        """
        根据中文名称获取分类定义

        Args:
            name: 中文名称

        Returns:
            分类定义，如果不存在则返回None
        """
        categories = self.parse_categories()
        for cat in categories.values():
            if cat.name == name:
                return cat
        return None

    def get_category_by_key(self, key: str) -> CategoryDefinition:
        """
        根据英文key获取分类定义

        Args:
            key: 英文key

        Returns:
            分类定义，如果不存在则返回None
        """
        categories = self.parse_categories()
        return categories.get(key)

    def _load_prompt_file(self) -> str:
        """加载提示词文件内容"""
        if not self.prompt_file_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.prompt_file_path}")

        with open(self.prompt_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _parse_categories_from_content(self, content: str) -> Dict[str, CategoryDefinition]:
        """
        从内容中解析分类定义

        格式：
        # Category Definitions (严格分类)
        - **Whale:** - 必须涉及**大额**资金流向...
        - **Fed:** - 仅限美联储（Fed）官员发言...

        Args:
            content: 提示词文件内容

        Returns:
            分类定义字典
        """
        categories = {}

        # 查找 "# Category Definitions" 部分
        category_section_pattern = r'# Category Definitions[^\n]*\n(.*?)(?=\n#|\Z)'
        section_match = re.search(category_section_pattern, content, re.DOTALL)

        if not section_match:
            logger.warning("未找到 '# Category Definitions' 部分")
            return categories

        section_content = section_match.group(1)

        # 在该部分中查找分类定义行
        # 格式: - **Key:** - 描述 或 - **Key:** 描述
        line_pattern = r'- \*\*(\w+):\*\*\s*-?\s*(.+?)(?=\n-|\Z)'
        matches = re.finditer(line_pattern, section_content, re.DOTALL)

        for match in matches:
            key = match.group(1)
            description = match.group(2).strip()
            # 移除多余的换行和空格
            description = ' '.join(description.split())

            # 推断中文名称
            chinese_name = self._extract_chinese_name(key, description)

            # 获取emoji
            emoji = self._get_emoji_for_category(key, chinese_name)

            categories[key] = CategoryDefinition(
                key=key,
                name=chinese_name,
                description=description,
                emoji=emoji
            )

            logger.debug(f"解析分类: {key} -> {chinese_name} {emoji}")

        if not categories:
            logger.warning("未找到任何分类定义")

        return categories

    def _extract_chinese_name(self, key: str, description: str) -> str:
        """
        从key和描述中提取中文名称

        策略：
        1. 优先使用预定义映射
        2. 如果没有映射，从描述中提取第一个中文词组

        Args:
            key: 英文key
            description: 分类描述

        Returns:
            中文名称
        """
        # 优先使用预定义映射
        if key in self.KEY_TO_CHINESE_NAME:
            return self.KEY_TO_CHINESE_NAME[key]

        # 匹配中文字符序列
        chinese_pattern = r'[\u4e00-\u9fff]+'
        matches = re.findall(chinese_pattern, description)

        if matches:
            # 返回第一个匹配的中文词组
            return matches[0]

        # 如果没有中文，返回key
        return key

    def _get_emoji_for_category(self, key: str, chinese_name: str) -> str:
        """
        获取分类的emoji图标

        优先级：
        1. 从英文key映射获取
        2. 返回默认图标

        Args:
            key: 英文key
            chinese_name: 中文名称

        Returns:
            emoji图标
        """
        # 从英文key映射获取
        if key in self.DEFAULT_EMOJI_MAP:
            return self.DEFAULT_EMOJI_MAP[key]

        # 返回默认图标
        return "📄"

    def invalidate_cache(self) -> None:
        """使缓存失效，下次调用时重新解析"""
        self._cache_valid = False
        logger.debug("分类缓存已失效")


# 全局单例
_global_parser: CategoryParser = None


def get_category_parser(prompt_file_path: str = "./prompts/analysis_prompt.md") -> CategoryParser:
    """
    获取全局分类解析器单例

    Args:
        prompt_file_path: 提示词文件路径

    Returns:
        CategoryParser实例
    """
    global _global_parser

    if _global_parser is None:
        _global_parser = CategoryParser(prompt_file_path)

    return _global_parser


def parse_categories_from_prompt(prompt_file_path: str = "./prompts/analysis_prompt.md") -> Dict[str, CategoryDefinition]:
    """
    从提示词文件解析分类定义（便捷函数）

    Args:
        prompt_file_path: 提示词文件路径

    Returns:
        分类定义字典
    """
    parser = get_category_parser(prompt_file_path)
    return parser.parse_categories()


def get_category_emoji_map(prompt_file_path: str = "./prompts/analysis_prompt.md") -> Dict[str, str]:
    """
    获取分类emoji映射（便捷函数）

    Args:
        prompt_file_path: 提示词文件路径

    Returns:
        {中文名称: emoji} 的字典
    """
    parser = get_category_parser(prompt_file_path)
    return parser.get_category_emoji_map()
