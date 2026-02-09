"""
配置持久化一致性属性测试

使用Hypothesis进行属性测试，验证配置保存和加载的一致性。
**功能: crypto-news-analyzer, 属性 2: 配置持久化一致性**
**验证: 需求 1.8**
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, Any, List

from crypto_news_analyzer.config.manager import ConfigManager


# 策略定义：生成有效的配置数据
@st.composite
def valid_rss_source(draw):
    """生成有效的RSS源配置"""
    name = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    url = draw(st.sampled_from([
        "https://example.com/rss.xml",
        "http://test.com/feed.xml",
        "https://news.site.com/rss",
        "https://crypto.news/feed.xml"
    ]))
    description = draw(st.text(max_size=200))
    
    return {
        "name": name,
        "url": url,
        "description": description
    }


@st.composite
def valid_x_source(draw):
    """生成有效的X源配置"""
    name = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    url = draw(st.sampled_from([
        "https://x.com/i/lists/1234567890",
        "https://x.com/username",
        "https://x.com/i/lists/9876543210"
    ]))
    source_type = draw(st.sampled_from(["list", "timeline"]))
    
    return {
        "name": name,
        "url": url,
        "type": source_type
    }


@st.composite
def valid_rest_api_source(draw):
    """生成有效的REST API源配置"""
    name = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    endpoint = draw(st.sampled_from([
        "https://api.example.com/news",
        "https://crypto-api.com/v1/news",
        "https://news-service.com/api/crypto"
    ]))
    method = draw(st.sampled_from(["GET", "POST"]))
    
    return {
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "headers": {"Content-Type": "application/json"},
        "params": {"limit": draw(st.integers(min_value=1, max_value=100))},
        "response_mapping": {
            "title_field": "title",
            "content_field": "content",
            "url_field": "url",
            "time_field": "timestamp"
        }
    }


@st.composite
def valid_storage_config(draw):
    """生成有效的存储配置"""
    return {
        "retention_days": draw(st.integers(min_value=1, max_value=365)),
        "max_storage_mb": draw(st.integers(min_value=100, max_value=10000)),
        "cleanup_frequency": draw(st.sampled_from(["daily", "weekly", "monthly"])),
        "database_path": draw(st.sampled_from([
            "./data/crypto_news.db",
            "/tmp/test.db",
            "./test_data/db.sqlite"
        ]))
    }


@st.composite
def valid_auth_config(draw):
    """生成有效的认证配置"""
    return {
        "X_CT0": draw(st.text(max_size=100)),  # 可以为空
        "X_AUTH_TOKEN": draw(st.text(max_size=200)),  # 可以为空
        "LLM_API_KEY": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        "TELEGRAM_BOT_TOKEN": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        "TELEGRAM_CHANNEL_ID": draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    }


@st.composite
def valid_llm_config(draw):
    """生成有效的LLM配置"""
    return {
        "model": draw(st.sampled_from(["gpt-4", "gpt-3.5-turbo", "claude-3"])),
        "temperature": draw(st.floats(min_value=0.0, max_value=2.0)),
        "max_tokens": draw(st.integers(min_value=100, max_value=4000)),
        "prompt_config_path": "./prompts/analysis_prompt.json",
        "batch_size": draw(st.integers(min_value=1, max_value=50))
    }


@st.composite
def valid_config(draw):
    """生成完整的有效配置"""
    return {
        "execution_interval": draw(st.integers(min_value=60, max_value=86400)),  # 1分钟到1天
        "time_window_hours": draw(st.integers(min_value=1, max_value=168)),  # 1小时到1周
        "storage": draw(valid_storage_config()),
        "auth": draw(valid_auth_config()),
        "llm_config": draw(valid_llm_config()),
        "rss_sources": draw(st.lists(valid_rss_source(), min_size=0, max_size=10)),
        "x_sources": draw(st.lists(valid_x_source(), min_size=0, max_size=5)),
        "rest_api_sources": draw(st.lists(valid_rest_api_source(), min_size=0, max_size=3))
    }


class TestConfigPersistenceProperties:
    """配置持久化一致性属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    @given(config_data=valid_config())
    @settings(max_examples=100, deadline=None)
    def test_config_persistence_consistency(self, config_data: Dict[str, Any]):
        """
        属性测试：配置持久化一致性
        
        **功能: crypto-news-analyzer, 属性 2: 配置持久化一致性**
        **验证: 需求 1.8**
        
        对于任何有效的配置参数，保存后重新读取应该得到相同的配置值
        """
        # 创建配置管理器
        manager = ConfigManager(self.config_path)
        
        # 假设：配置数据是有效的（通过策略保证）
        assume(manager.validate_config(config_data))
        
        # 保存配置
        manager.save_config(config_data)
        
        # 重新加载配置
        loaded_config = manager.load_config()
        
        # 验证：保存和加载的配置应该完全一致
        assert loaded_config == config_data, f"配置不一致：\n原始: {config_data}\n加载: {loaded_config}"
        
        # 验证：配置文件确实存在
        assert os.path.exists(self.config_path), "配置文件应该存在"
        
        # 验证：配置文件内容可以被JSON解析
        with open(self.config_path, 'r', encoding='utf-8') as f:
            file_content = json.load(f)
        assert file_content == config_data, "文件内容与原始配置不一致"
    
    @given(config_data=valid_config())
    @settings(max_examples=50, deadline=None)
    def test_multiple_save_load_cycles(self, config_data: Dict[str, Any]):
        """
        属性测试：多次保存加载循环的一致性
        
        验证多次保存和加载操作不会改变配置数据
        """
        manager = ConfigManager(self.config_path)
        assume(manager.validate_config(config_data))
        
        original_config = config_data.copy()
        
        # 执行多次保存加载循环
        for _ in range(3):
            manager.save_config(config_data)
            config_data = manager.load_config()
        
        # 验证：经过多次循环后配置仍然一致
        assert config_data == original_config, "多次保存加载后配置发生变化"
    
    @given(
        config1=valid_config(),
        config2=valid_config()
    )
    @settings(max_examples=50, deadline=None)
    def test_config_overwrite_consistency(self, config1: Dict[str, Any], config2: Dict[str, Any]):
        """
        属性测试：配置覆盖的一致性
        
        验证用新配置覆盖旧配置后，加载的是新配置
        """
        manager = ConfigManager(self.config_path)
        assume(manager.validate_config(config1))
        assume(manager.validate_config(config2))
        assume(config1 != config2)  # 确保两个配置不同
        
        # 保存第一个配置
        manager.save_config(config1)
        loaded_config1 = manager.load_config()
        assert loaded_config1 == config1
        
        # 用第二个配置覆盖
        manager.save_config(config2)
        loaded_config2 = manager.load_config()
        
        # 验证：加载的是第二个配置，不是第一个
        assert loaded_config2 == config2, "覆盖后加载的不是新配置"
        assert loaded_config2 != config1, "覆盖后仍然是旧配置"
    
    @given(config_data=valid_config())
    @settings(max_examples=30, deadline=None)
    def test_config_file_format_consistency(self, config_data: Dict[str, Any]):
        """
        属性测试：配置文件格式的一致性
        
        验证保存的配置文件格式正确且可读
        """
        manager = ConfigManager(self.config_path)
        assume(manager.validate_config(config_data))
        
        # 保存配置
        manager.save_config(config_data)
        
        # 直接读取文件内容
        with open(self.config_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # 验证：文件内容是有效的JSON
        parsed_content = json.loads(file_content)
        assert parsed_content == config_data, "文件中的JSON内容与原始配置不一致"
        
        # 验证：文件格式良好（可以重新解析）
        reparsed_content = json.loads(json.dumps(parsed_content))
        assert reparsed_content == config_data, "重新解析后的内容不一致"
    
    @given(config_data=valid_config())
    @settings(max_examples=30, deadline=None)
    def test_config_validation_after_persistence(self, config_data: Dict[str, Any]):
        """
        属性测试：持久化后配置验证的一致性
        
        验证保存并重新加载的配置仍然通过验证
        """
        manager = ConfigManager(self.config_path)
        assume(manager.validate_config(config_data))
        
        # 保存配置
        manager.save_config(config_data)
        
        # 重新加载配置
        loaded_config = manager.load_config()
        
        # 验证：重新加载的配置仍然有效
        assert manager.validate_config(loaded_config), "重新加载的配置验证失败"
        
        # 验证：可以从重新加载的配置中提取各种组件
        try:
            rss_sources = manager.get_rss_sources()
            x_sources = manager.get_x_sources()
            auth_config = manager.get_auth_config()
            storage_config = manager.get_storage_config()
            
            # 验证：提取的组件数量正确
            assert len(rss_sources) == len(config_data.get("rss_sources", []))
            assert len(x_sources) == len(config_data.get("x_sources", []))
            
        except Exception as e:
            pytest.fail(f"从重新加载的配置中提取组件失败: {e}")


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])