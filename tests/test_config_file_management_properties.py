"""
配置文件管理属性测试

**功能: crypto-news-analyzer, 属性 3: 配置文件管理**

验证系统的配置文件管理功能，包括：
- 配置文件的创建和维护
- 默认配置文件的自动创建
- 配置文件结构完整性验证
- 信息源URL格式验证

**验证: 需求 2.1, 2.5, 2.8, 2.13**
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, Any, List, Optional
import pytest

from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.models import RSSSource, XSource, RESTAPISource


# 策略生成器
@st.composite
def valid_url(draw):
    """生成有效的URL"""
    protocols = ["http://", "https://"]
    protocol = draw(st.sampled_from(protocols))
    
    # 域名部分
    domain_parts = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=10),
        min_size=1, max_size=3
    ))
    domain = ".".join(domain_parts) + draw(st.sampled_from([".com", ".org", ".net", ".io"]))
    
    # 路径部分（可选）
    path_parts = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd", "Pd")), min_size=1, max_size=15),
        min_size=0, max_size=5
    ))
    path = "/" + "/".join(path_parts) if path_parts else ""
    
    return protocol + domain + path


@st.composite
def valid_rss_source(draw):
    """生成有效的RSS源配置"""
    # 生成非空白字符的名称
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"), min_codepoint=32),
        min_size=1, max_size=50
    )).strip()
    # 确保名称不为空
    if not name:
        name = "RSS Source"
    
    return {
        "name": name,
        "url": draw(valid_url()),
        "description": draw(st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Pd", "Po"), min_codepoint=32),
            min_size=1, max_size=200
        )).strip() or "Description"
    }


@st.composite
def valid_x_source(draw):
    """生成有效的X源配置"""
    base_url = "https://x.com/"
    path_type = draw(st.sampled_from(["i/lists/", "user/"]))
    identifier = draw(st.text(alphabet=st.characters(whitelist_categories=("Nd", "Ll")), min_size=5, max_size=20))
    
    # 生成非空白字符的名称
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"), min_codepoint=32),
        min_size=1, max_size=50
    )).strip()
    if not name:
        name = "X Source"
    
    return {
        "name": name,
        "url": base_url + path_type + identifier,
        "type": draw(st.sampled_from(["list", "timeline"]))
    }


@st.composite
def valid_rest_api_source(draw):
    """生成有效的REST API源配置"""
    # 生成非空白字符的名称
    name = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pc"), min_codepoint=32),
        min_size=1, max_size=50
    )).strip()
    if not name:
        name = "API Source"
    
    return {
        "name": name,
        "endpoint": draw(valid_url()),
        "method": draw(st.sampled_from(["GET", "POST"])),
        "headers": draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=1, max_size=100),
            min_size=0, max_size=5
        )),
        "params": draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(min_size=1, max_size=50), st.integers()),
            min_size=0, max_size=5
        )),
        "response_mapping": {
            "title_field": draw(st.text(min_size=1, max_size=20)),
            "content_field": draw(st.text(min_size=1, max_size=20)),
            "url_field": draw(st.text(min_size=1, max_size=20)),
            "time_field": draw(st.text(min_size=1, max_size=20))
        }
    }


@st.composite
def valid_auth_config(draw):
    """生成有效的认证配置"""
    return {
        "X_CT0": draw(st.text(min_size=0, max_size=100)),
        "X_AUTH_TOKEN": draw(st.text(min_size=0, max_size=200)),
        "LLM_API_KEY": draw(st.text(min_size=1, max_size=100)),
        "TELEGRAM_BOT_TOKEN": draw(st.text(min_size=1, max_size=100)),
        "TELEGRAM_CHANNEL_ID": draw(st.text(min_size=1, max_size=50))
    }


@st.composite
def valid_storage_config(draw):
    """生成有效的存储配置"""
    # 生成安全的文件路径
    path_parts = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
        min_size=1, max_size=3
    ))
    database_path = "./" + "/".join(path_parts) + "/crypto_news.db"
    
    return {
        "retention_days": draw(st.integers(min_value=1, max_value=365)),
        "max_storage_mb": draw(st.integers(min_value=10, max_value=10000)),
        "cleanup_frequency": draw(st.sampled_from(["daily", "weekly", "monthly"])),
        "database_path": database_path
    }


@st.composite
def valid_llm_config(draw):
    """生成有效的LLM配置"""
    # 生成安全的文件路径
    path_parts = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=10),
        min_size=1, max_size=3
    ))
    prompt_config_path = "./" + "/".join(path_parts) + "/analysis_prompt.json"
    
    return {
        "model": draw(st.sampled_from(["gpt-4", "gpt-3.5-turbo", "MiniMax-M2.1"])),
        "temperature": draw(st.floats(min_value=0.0, max_value=2.0)),
        "max_tokens": draw(st.integers(min_value=100, max_value=4000)),
        "prompt_config_path": prompt_config_path,
        "batch_size": draw(st.integers(min_value=1, max_value=50))
    }


@st.composite
def valid_complete_config(draw):
    """生成完整的有效配置"""
    return {
        "execution_interval": draw(st.integers(min_value=60, max_value=86400)),
        "time_window_hours": draw(st.integers(min_value=1, max_value=168)),
        "storage": draw(valid_storage_config()),
        "llm_config": draw(valid_llm_config()),
        "rss_sources": draw(st.lists(valid_rss_source(), min_size=0, max_size=10)),
        "x_sources": draw(st.lists(valid_x_source(), min_size=0, max_size=5)),
        "rest_api_sources": draw(st.lists(valid_rest_api_source(), min_size=0, max_size=3))
    }


@st.composite
def invalid_config_missing_fields(draw):
    """生成缺少必需字段的无效配置"""
    config = draw(valid_complete_config())
    
    # 随机删除一些必需字段
    required_fields = ["execution_interval", "time_window_hours", "storage", "llm_config"]
    fields_to_remove = draw(st.lists(
        st.sampled_from(required_fields),
        min_size=1, max_size=len(required_fields)
    ))
    
    for field in fields_to_remove:
        if field in config:
            del config[field]
    
    return config


@st.composite
def invalid_url_config(draw):
    """生成包含无效URL的配置"""
    config = draw(valid_complete_config())
    
    # 生成无效URL
    invalid_urls = [
        "not-a-url",
        "ftp://invalid.com",
        "http://",
        "https://",
        "",
        "javascript:alert('xss')",
        "file:///etc/passwd"
    ]
    
    invalid_url = draw(st.sampled_from(invalid_urls))
    
    # 随机选择要修改的源类型
    source_type = draw(st.sampled_from(["rss", "x", "rest_api"]))
    
    if source_type == "rss" and config.get("rss_sources"):
        config["rss_sources"][0]["url"] = invalid_url
    elif source_type == "x" and config.get("x_sources"):
        config["x_sources"][0]["url"] = invalid_url
    elif source_type == "rest_api" and config.get("rest_api_sources"):
        config["rest_api_sources"][0]["endpoint"] = invalid_url
    
    return config


class TestConfigFileManagementProperties:
    """配置文件管理属性测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.manager = ConfigManager(self.config_path)
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(config_data=valid_complete_config())
    @settings(max_examples=100, deadline=None)
    def test_config_file_creation_and_maintenance(self, config_data: Dict[str, Any]):
        """
        **属性 3: 配置文件管理 - 配置文件创建和维护**
        **验证: 需求 2.1**
        
        对于任何有效的配置数据，系统应该能够创建和维护配置文件，
        存储所有信息源和分析规则。
        """
        # 确保配置文件不存在
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        
        # 保存配置
        self.manager.save_config(config_data)
        
        # 验证文件已创建
        assert os.path.exists(self.config_path), "配置文件应该被创建"
        
        # 验证文件内容
        with open(self.config_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data == config_data, "保存的配置应该与原始配置一致"
        
        # 验证可以重新加载
        loaded_config = self.manager.load_config()
        assert loaded_config == config_data, "重新加载的配置应该与原始配置一致"
        
        # 验证配置包含所有信息源
        if "rss_sources" in config_data:
            rss_sources = self.manager.get_rss_sources()
            assert len(rss_sources) == len(config_data["rss_sources"]), "RSS源数量应该匹配"
        
        if "x_sources" in config_data:
            x_sources = self.manager.get_x_sources()
            assert len(x_sources) == len(config_data["x_sources"]), "X源数量应该匹配"
        
        if "rest_api_sources" in config_data:
            api_sources = self.manager.get_rest_api_sources()
            assert len(api_sources) == len(config_data["rest_api_sources"]), "REST API源数量应该匹配"
    
    @given(
        original_config=valid_complete_config(),
        modification_type=st.sampled_from(["time_window", "sources", "storage"])
    )
    @settings(max_examples=50, deadline=None)
    def test_config_modification_support(self, original_config: Dict[str, Any], modification_type: str):
        """
        **属性 3: 配置文件管理 - 配置修改支持**
        **验证: 需求 2.5**
        
        系统应该支持用户通过编辑配置文件来增加、删除或修改信息源和分类规则。
        """
        # 保存原始配置
        self.manager.save_config(original_config)
        original_loaded = self.manager.load_config()
        
        # 创建修改后的配置
        modified_config = original_config.copy()
        
        # 根据修改类型进行不同的修改
        if modification_type == "time_window":
            # 修改时间窗口
            modified_config["time_window_hours"] = original_config["time_window_hours"] + 1
        elif modification_type == "sources":
            # 修改RSS源
            if "rss_sources" in modified_config:
                modified_config["rss_sources"] = modified_config["rss_sources"].copy()
                if modified_config["rss_sources"]:
                    # 修改第一个源的名称
                    modified_config["rss_sources"][0] = modified_config["rss_sources"][0].copy()
                    modified_config["rss_sources"][0]["name"] = "Modified " + modified_config["rss_sources"][0]["name"]
                else:
                    # 添加一个新源
                    modified_config["rss_sources"].append({
                        "name": "New RSS Source",
                        "url": "https://example.com/rss",
                        "description": "New source"
                    })
        elif modification_type == "storage":
            # 修改存储配置
            modified_config["storage"] = modified_config["storage"].copy()
            modified_config["storage"]["retention_days"] = original_config["storage"]["retention_days"] + 1
        
        # 保存修改后的配置
        self.manager.save_config(modified_config)
        modified_loaded = self.manager.load_config()
        
        # 验证配置已更新
        assert modified_loaded == modified_config, "修改后的配置应该被正确保存"
        assert modified_loaded != original_config, "修改后的配置应该与原始配置不同"
        
        # 验证信息源的变化被正确处理
        original_rss_count = len(original_config.get("rss_sources", []))
        modified_rss_count = len(modified_config.get("rss_sources", []))
        
        loaded_rss_sources = self.manager.get_rss_sources()
        assert len(loaded_rss_sources) == modified_rss_count, "RSS源数量应该反映最新配置"
    
    def test_default_config_creation_when_missing(self):
        """
        **属性 3: 配置文件管理 - 默认配置创建**
        **验证: 需求 2.8**
        
        当配置文件不存在时，系统应该创建包含预设信息源和默认分类标准的默认配置文件。
        """
        # 确保配置文件不存在
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        
        assert not os.path.exists(self.config_path), "配置文件应该不存在"
        
        # 尝试加载配置（应该触发默认配置创建）
        config = self.manager.load_config()
        
        # 验证文件已创建
        assert os.path.exists(self.config_path), "默认配置文件应该被创建"
        
        # 验证默认配置包含必需字段
        required_fields = ["execution_interval", "time_window_hours", "storage", "llm_config"]
        for field in required_fields:
            assert field in config, f"默认配置应该包含必需字段: {field}"
        
        # 验证默认配置包含预设信息源
        assert "rss_sources" in config, "默认配置应该包含RSS源"
        assert "x_sources" in config, "默认配置应该包含X源"
        assert len(config["rss_sources"]) > 0, "默认配置应该包含预设RSS源"
        
        # 验证默认配置的有效性
        assert self.manager.validate_config(config), "默认配置应该是有效的"
    
    @given(config_data=valid_complete_config())
    @settings(max_examples=50, deadline=None)
    def test_config_structure_integrity_validation(self, config_data: Dict[str, Any]):
        """
        **属性 3: 配置文件管理 - 结构完整性验证**
        **验证: 需求 2.13**
        
        系统应该验证配置文件结构的完整性，确保所有必需字段都存在。
        """
        # 验证完整配置
        assert self.manager.validate_config(config_data), "有效的完整配置应该通过验证"
        
        # 测试缺少必需字段的情况
        required_fields = ["execution_interval", "time_window_hours", "storage", "llm_config"]
        
        for field in required_fields:
            incomplete_config = config_data.copy()
            del incomplete_config[field]
            
            assert not self.manager.validate_config(incomplete_config), \
                f"缺少必需字段 '{field}' 的配置应该验证失败"
        
        # 测试嵌套字段的完整性
        if "storage" in config_data:
            incomplete_storage = config_data.copy()
            incomplete_storage["storage"] = {}
            assert not self.manager.validate_config(incomplete_storage), \
                "存储配置为空时应该验证失败"
        
        if "auth" in config_data:
            incomplete_auth = config_data.copy()
            incomplete_auth["auth"] = {}
            assert not self.manager.validate_config(incomplete_auth), \
                "认证配置为空时应该验证失败"
    
    @given(config_data=invalid_config_missing_fields())
    @settings(max_examples=30, deadline=None)
    def test_missing_fields_detection(self, config_data: Dict[str, Any]):
        """
        **属性 3: 配置文件管理 - 缺失字段检测**
        **验证: 需求 2.13**
        
        对于任何缺少必需字段的配置，系统应该检测到并验证失败。
        """
        # 缺少必需字段的配置应该验证失败
        assert not self.manager.validate_config(config_data), \
            "缺少必需字段的配置应该验证失败"
        
        # 尝试保存无效配置应该抛出异常
        with pytest.raises(ValueError, match="配置数据验证失败"):
            self.manager.save_config(config_data)
    
    @given(config_data=invalid_url_config())
    @settings(max_examples=30, deadline=None)
    def test_url_format_validation(self, config_data: Dict[str, Any]):
        """
        **属性 3: 配置文件管理 - URL格式验证**
        **验证: 需求 2.12 (相关需求)**
        
        系统应该验证配置文件中每个信息源URL的格式有效性。
        """
        # 包含无效URL的配置应该验证失败
        is_valid = self.manager.validate_config(config_data)
        
        # 如果配置中确实包含无效URL，验证应该失败
        has_invalid_url = False
        
        # 检查RSS源URL
        for source in config_data.get("rss_sources", []):
            url = source.get("url", "")
            if not (url.startswith("http://") or url.startswith("https://")) or len(url) < 10:
                has_invalid_url = True
                break
        
        # 检查X源URL
        for source in config_data.get("x_sources", []):
            url = source.get("url", "")
            if not url.startswith("https://x.com/"):
                has_invalid_url = True
                break
        
        # 检查REST API源URL
        for source in config_data.get("rest_api_sources", []):
            endpoint = source.get("endpoint", "")
            if not (endpoint.startswith("http://") or endpoint.startswith("https://")) or len(endpoint) < 10:
                has_invalid_url = True
                break
        
        if has_invalid_url:
            assert not is_valid, f"包含无效URL的配置应该验证失败，但验证通过了。配置: {config_data}"
    
    @given(config_data=valid_complete_config())
    @settings(max_examples=30, deadline=None)
    def test_config_persistence_across_manager_instances(self, config_data: Dict[str, Any]):
        """
        **属性 3: 配置文件管理 - 跨实例持久化**
        **验证: 需求 2.1, 2.5**
        
        配置文件应该在不同的ConfigManager实例之间保持一致性。
        """
        # 使用第一个管理器保存配置
        self.manager.save_config(config_data)
        
        # 创建新的管理器实例
        new_manager = ConfigManager(self.config_path)
        loaded_config = new_manager.load_config()
        
        # 验证配置一致性
        assert loaded_config == config_data, "不同管理器实例应该加载相同的配置"
        
        # 验证信息源解析一致性
        original_rss = self.manager.get_rss_sources()
        new_rss = new_manager.get_rss_sources()
        
        assert len(original_rss) == len(new_rss), "RSS源数量应该一致"
        
        for i, (orig, new) in enumerate(zip(original_rss, new_rss)):
            assert orig.name == new.name, f"第{i}个RSS源名称应该一致"
            assert orig.url == new.url, f"第{i}个RSS源URL应该一致"
            assert orig.description == new.description, f"第{i}个RSS源描述应该一致"
    
    @given(
        time_window=st.integers(min_value=1, max_value=168),
        execution_interval=st.integers(min_value=60, max_value=86400)
    )
    @settings(max_examples=50, deadline=None)
    def test_numeric_parameter_validation(self, time_window: int, execution_interval: int):
        """
        **属性 3: 配置文件管理 - 数值参数验证**
        **验证: 需求 2.13**
        
        系统应该验证数值参数的有效性（正整数）。
        """
        config = {
            "execution_interval": execution_interval,
            "time_window_hours": time_window,
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": "./data/test.db"
            },
            "llm_config": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_tokens": 1000,
                "prompt_config_path": "./prompts/test.json",
                "batch_size": 10
            },
            "rss_sources": [],
            "x_sources": [],
            "rest_api_sources": []
        }
        
        # 有效的正整数应该通过验证
        assert self.manager.validate_config(config), "有效的数值参数应该通过验证"
        
        # 测试无效的时间窗口
        invalid_time_config = config.copy()
        invalid_time_config["time_window_hours"] = 0
        assert not self.manager.validate_config(invalid_time_config), \
            "时间窗口为0应该验证失败"
        
        invalid_time_config["time_window_hours"] = -1
        assert not self.manager.validate_config(invalid_time_config), \
            "负数时间窗口应该验证失败"
        
        # 测试无效的执行间隔
        invalid_interval_config = config.copy()
        invalid_interval_config["execution_interval"] = 0
        assert not self.manager.validate_config(invalid_interval_config), \
            "执行间隔为0应该验证失败"


if __name__ == "__main__":
    pytest.main([__file__])