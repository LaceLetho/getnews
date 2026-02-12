"""
测试分类解析器

验证从 analysis_prompt.md 文件中正确解析分类定义
"""

import pytest
from crypto_news_analyzer.analyzers.category_parser import (
    CategoryParser,
    parse_categories_from_prompt,
    get_category_emoji_map
)


def test_parse_categories_from_prompt():
    """测试从提示词文件解析分类"""
    categories = parse_categories_from_prompt()
    
    # 验证解析出了分类
    assert len(categories) > 0
    
    # 验证包含Truth分类
    assert "Truth" in categories
    assert categories["Truth"].name == "真相"
    assert categories["Truth"].emoji == "💡"
    
    # 验证不包含Security分类
    assert "Security" not in categories
    
    # 验证包含其他主要分类
    assert "Whale" in categories
    assert "Fed" in categories
    assert "Regulation" in categories
    assert "NewProject" in categories
    assert "MarketTrend" in categories
    
    # 验证系统默认分类
    assert "Uncategorized" in categories
    assert "Ignored" in categories


def test_category_definition_structure():
    """测试分类定义的结构"""
    categories = parse_categories_from_prompt()
    
    for key, cat in categories.items():
        # 验证必需字段
        assert cat.key == key
        assert cat.name is not None and len(cat.name) > 0
        assert cat.description is not None and len(cat.description) > 0
        assert cat.emoji is not None and len(cat.emoji) > 0


def test_get_category_emoji_map():
    """测试获取emoji映射"""
    emoji_map = get_category_emoji_map()
    
    # 验证Truth分类的emoji
    assert "真相" in emoji_map
    assert emoji_map["真相"] == "💡"
    
    # 验证其他分类的emoji
    assert "大户动向" in emoji_map
    assert emoji_map["大户动向"] == "🐋"
    
    assert "利率事件" in emoji_map
    assert emoji_map["利率事件"] == "📊"
    
    # 验证不包含Security
    assert "安全事件" not in emoji_map


def test_category_parser_caching():
    """测试分类解析器的缓存机制"""
    parser = CategoryParser()
    
    # 第一次解析
    categories1 = parser.parse_categories()
    
    # 第二次解析（应该使用缓存）
    categories2 = parser.parse_categories()
    
    # 验证返回相同的对象
    assert categories1 is categories2
    
    # 强制重新加载
    categories3 = parser.parse_categories(force_reload=True)
    
    # 验证内容相同但对象不同
    assert len(categories3) == len(categories1)
    assert categories3 is not categories1


def test_get_category_names():
    """测试获取分类名称列表"""
    parser = CategoryParser()
    names = parser.get_category_names()
    
    # 验证包含Truth
    assert "真相" in names
    
    # 验证不包含Security
    assert "安全事件" not in names
    
    # 验证包含其他主要分类
    assert "大户动向" in names
    assert "利率事件" in names
    assert "美国政府监管政策" in names


def test_get_category_by_name():
    """测试根据名称获取分类"""
    parser = CategoryParser()
    
    # 获取Truth分类
    truth_cat = parser.get_category_by_name("真相")
    assert truth_cat is not None
    assert truth_cat.key == "Truth"
    assert truth_cat.emoji == "💡"
    
    # 获取不存在的分类
    nonexistent = parser.get_category_by_name("不存在的分类")
    assert nonexistent is None


def test_get_category_by_key():
    """测试根据key获取分类"""
    parser = CategoryParser()
    
    # 获取Truth分类
    truth_cat = parser.get_category_by_key("Truth")
    assert truth_cat is not None
    assert truth_cat.name == "真相"
    assert truth_cat.emoji == "💡"
    
    # 获取不存在的分类
    nonexistent = parser.get_category_by_key("NonExistent")
    assert nonexistent is None


def test_all_categories_have_emojis():
    """测试所有分类都有emoji"""
    categories = parse_categories_from_prompt()
    
    for key, cat in categories.items():
        assert cat.emoji is not None
        assert len(cat.emoji) > 0
        # 验证emoji是Unicode字符
        assert ord(cat.emoji[0]) > 127


def test_category_descriptions():
    """测试分类描述"""
    categories = parse_categories_from_prompt()
    
    # Truth分类应该有描述
    truth_cat = categories["Truth"]
    assert "真相" in truth_cat.description or "揭露" in truth_cat.description
    
    # Whale分类应该有描述
    whale_cat = categories["Whale"]
    assert "大户" in whale_cat.description or "巨鲸" in whale_cat.description


def test_parser_handles_missing_file():
    """测试解析器处理文件不存在的情况"""
    parser = CategoryParser(prompt_file_path="./nonexistent/file.md")
    
    with pytest.raises(FileNotFoundError):
        parser.parse_categories()


def test_invalidate_cache():
    """测试缓存失效"""
    parser = CategoryParser()
    
    # 第一次解析
    categories1 = parser.parse_categories()
    
    # 使缓存失效
    parser.invalidate_cache()
    
    # 再次解析（应该重新加载）
    categories2 = parser.parse_categories()
    
    # 验证内容相同但对象不同
    assert len(categories2) == len(categories1)
    assert categories2 is not categories1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
