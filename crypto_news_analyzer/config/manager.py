"""
配置管理器

负责配置文件的读取、验证和管理。
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from ..models import RSSSource, XSource, AuthConfig, StorageConfig, RESTAPISource


class ConfigManager:
    """配置文件管理器"""
    
    def __init__(self, config_path: str = "./config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置数据字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式无效
        """
        try:
            if not self.config_path.exists():
                self.logger.info(f"配置文件不存在，创建默认配置: {self.config_path}")
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            if not self.validate_config(self.config_data):
                raise ValueError("配置文件验证失败")
                
            self.logger.info("配置文件加载成功")
            return self.config_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件格式无效: {e}")
            raise
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置文件有效性
        
        Args:
            config: 配置数据
            
        Returns:
            是否有效
        """
        try:
            # 验证必需的顶级字段
            required_fields = [
                "execution_interval", "time_window_hours", 
                "storage", "auth", "llm_config"
            ]
            
            for field in required_fields:
                if field not in config:
                    self.logger.error(f"缺少必需配置字段: {field}")
                    return False
            
            # 验证时间窗口参数
            if not isinstance(config["time_window_hours"], int) or config["time_window_hours"] <= 0:
                self.logger.error("时间窗口参数必须为正整数")
                return False
            
            # 验证执行间隔
            if not isinstance(config["execution_interval"], int) or config["execution_interval"] <= 0:
                self.logger.error("执行间隔必须为正整数")
                return False
            
            # 验证存储配置
            storage_config = config["storage"]
            if not isinstance(storage_config.get("retention_days"), int) or storage_config["retention_days"] <= 0:
                self.logger.error("数据保留天数必须为正整数")
                return False
            
            # 验证认证配置格式
            auth_config = config["auth"]
            auth_fields = ["llm_api_key", "telegram_bot_token", "telegram_channel_id"]
            for field in auth_fields:
                if field not in auth_config or not isinstance(auth_config[field], str):
                    self.logger.error(f"认证配置字段格式无效: {field}")
                    return False
            
            # 验证RSS源配置
            if "rss_sources" in config:
                for source in config["rss_sources"]:
                    if not self._validate_rss_source(source):
                        return False
            
            # 验证X源配置
            if "x_sources" in config:
                for source in config["x_sources"]:
                    if not self._validate_x_source(source):
                        return False
            
            # 验证存储路径
            storage_path = storage_config.get("database_path", "./data/crypto_news.db")
            if not self.validate_storage_path(storage_path):
                return False
            
            self.logger.info("配置文件验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"配置验证过程中出错: {e}")
            return False
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """
        保存配置到文件
        
        Args:
            config: 配置数据
            
        Raises:
            ValueError: 配置数据无效
        """
        if not self.validate_config(config):
            raise ValueError("配置数据验证失败，无法保存")
        
        try:
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            self.config_data = config
            self.logger.info(f"配置已保存到: {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            raise
    
    def get_rss_sources(self) -> List[RSSSource]:
        """获取RSS订阅源列表"""
        sources = []
        for source_data in self.config_data.get("rss_sources", []):
            sources.append(RSSSource(
                name=source_data["name"],
                url=source_data["url"],
                description=source_data["description"]
            ))
        return sources
    
    def get_x_sources(self) -> List[XSource]:
        """获取X/Twitter信息源列表"""
        sources = []
        for source_data in self.config_data.get("x_sources", []):
            sources.append(XSource(
                name=source_data["name"],
                url=source_data["url"],
                type=source_data["type"]
            ))
        return sources
    
    def get_rest_api_sources(self) -> List[RESTAPISource]:
        """获取REST API数据源列表"""
        sources = []
        for source_data in self.config_data.get("rest_api_sources", []):
            sources.append(RESTAPISource(
                name=source_data["name"],
                endpoint=source_data["endpoint"],
                method=source_data["method"],
                headers=source_data.get("headers", {}),
                params=source_data.get("params", {}),
                response_mapping=source_data["response_mapping"]
            ))
        return sources
    
    def get_auth_config(self) -> AuthConfig:
        """获取认证配置"""
        auth_data = self.config_data["auth"]
        return AuthConfig(
            x_ct0=auth_data.get("x_ct0", ""),
            x_auth_token=auth_data.get("x_auth_token", ""),
            llm_api_key=auth_data["llm_api_key"],
            telegram_bot_token=auth_data["telegram_bot_token"],
            telegram_channel_id=auth_data["telegram_channel_id"]
        )
    
    def get_storage_config(self) -> StorageConfig:
        """获取存储配置"""
        storage_data = self.config_data["storage"]
        return StorageConfig(
            retention_days=storage_data.get("retention_days", 30),
            max_storage_mb=storage_data.get("max_storage_mb", 1000),
            cleanup_frequency=storage_data.get("cleanup_frequency", "daily"),
            database_path=storage_data.get("database_path", "./data/crypto_news.db")
        )
    
    def validate_storage_path(self, path: str) -> bool:
        """
        验证存储路径有效性
        
        Args:
            path: 存储路径
            
        Returns:
            是否有效
        """
        try:
            storage_path = Path(path)
            
            # 确保父目录可以创建
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查是否有写权限
            if storage_path.exists():
                if not os.access(storage_path, os.W_OK):
                    self.logger.error(f"存储路径无写权限: {path}")
                    return False
            else:
                # 检查父目录写权限
                if not os.access(storage_path.parent, os.W_OK):
                    self.logger.error(f"存储目录无写权限: {storage_path.parent}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证存储路径失败: {e}")
            return False
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            "execution_interval": 3600,
            "time_window_hours": 24,
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": "./data/crypto_news.db"
            },
            "auth": {
                "x_ct0": "",
                "x_auth_token": "",
                "llm_api_key": "",
                "telegram_bot_token": "",
                "telegram_channel_id": ""
            },
            "llm_config": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_tokens": 1000,
                "prompt_config_path": "./prompts/analysis_prompt.json",
                "batch_size": 10
            },
            "rss_sources": [
                {
                    "name": "PANews",
                    "url": "https://www.panewslab.com/zh/rss/newsflash.xml",
                    "description": "PANews 快讯"
                },
                {
                    "name": "金色财经",
                    "url": "https://www.jinse.com/rss/flash.xml",
                    "description": "金色财经快讯"
                }
            ],
            "x_sources": [
                {
                    "name": "Crypto List 1",
                    "url": "https://x.com/i/lists/1826855418095980750",
                    "type": "list"
                }
            ],
            "rest_api_sources": []
        }
        
        self.save_config(default_config)
    
    def _validate_rss_source(self, source: Dict[str, Any]) -> bool:
        """验证RSS源配置"""
        required_fields = ["name", "url", "description"]
        for field in required_fields:
            if field not in source or not isinstance(source[field], str):
                self.logger.error(f"RSS源配置字段无效: {field}")
                return False
        
        # 简单的URL格式验证
        url = source["url"]
        if not (url.startswith("http://") or url.startswith("https://")):
            self.logger.error(f"RSS源URL格式无效: {url}")
            return False
        
        return True
    
    def _validate_x_source(self, source: Dict[str, Any]) -> bool:
        """验证X源配置"""
        required_fields = ["name", "url", "type"]
        for field in required_fields:
            if field not in source or not isinstance(source[field], str):
                self.logger.error(f"X源配置字段无效: {field}")
                return False
        
        # 验证类型
        if source["type"] not in ["list", "timeline"]:
            self.logger.error(f"X源类型无效: {source['type']}")
            return False
        
        # 简单的URL格式验证
        url = source["url"]
        if not url.startswith("https://x.com/"):
            self.logger.error(f"X源URL格式无效: {url}")
            return False
        
        return True