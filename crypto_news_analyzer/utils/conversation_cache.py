"""
会话ID持久化管理模块
用于在重启后保持conversation_id不变，提高缓存命中率
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime


class ConversationIdManager:
    """管理conversation_id的持久化存储"""
    
    def __init__(self, cache_dir: str = "./data/cache"):
        """
        初始化会话ID管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "conversation_id.json"
        self.logger = logging.getLogger(__name__)
        
        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_or_create_conversation_id(self, service_name: str = "default") -> str:
        """
        获取或创建会话ID
        
        Args:
            service_name: 服务名称，用于区分不同服务的会话ID
            
        Returns:
            会话ID字符串
        """
        try:
            # 尝试从缓存文件读取
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if service_name in data:
                    conversation_id = data[service_name]['conversation_id']
                    self.logger.info(f"从缓存加载会话ID [{service_name}]: {conversation_id}")
                    return conversation_id
            
            # 如果不存在，创建新的会话ID
            conversation_id = str(uuid.uuid4())
            self._save_conversation_id(service_name, conversation_id)
            self.logger.info(f"创建新会话ID [{service_name}]: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            self.logger.error(f"读取会话ID失败: {e}，创建临时会话ID")
            return str(uuid.uuid4())
    
    def _save_conversation_id(self, service_name: str, conversation_id: str) -> None:
        """
        保存会话ID到缓存文件
        
        Args:
            service_name: 服务名称
            conversation_id: 会话ID
        """
        try:
            # 读取现有数据
            data = {}
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 更新数据
            data[service_name] = {
                'conversation_id': conversation_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 写入文件
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.debug(f"会话ID已保存到缓存文件: {self.cache_file}")
            
        except Exception as e:
            self.logger.error(f"保存会话ID失败: {e}")
    
    def update_conversation_id(self, service_name: str, conversation_id: str) -> None:
        """
        更新会话ID
        
        Args:
            service_name: 服务名称
            conversation_id: 新的会话ID
        """
        self._save_conversation_id(service_name, conversation_id)
    
    def clear_conversation_id(self, service_name: Optional[str] = None) -> bool:
        """
        清除会话ID
        
        Args:
            service_name: 服务名称，如果为None则清除所有
            
        Returns:
            是否成功清除
        """
        try:
            if not self.cache_file.exists():
                return True
            
            if service_name is None:
                # 删除整个文件
                self.cache_file.unlink()
                self.logger.info("已清除所有会话ID")
                return True
            
            # 只删除指定服务的会话ID
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if service_name in data:
                del data[service_name]
                
                if data:
                    # 还有其他服务的数据，写回文件
                    with open(self.cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    # 没有数据了，删除文件
                    self.cache_file.unlink()
                
                self.logger.info(f"已清除会话ID [{service_name}]")
                return True
            
            return True
            
        except Exception as e:
            self.logger.error(f"清除会话ID失败: {e}")
            return False
    
    def get_all_conversation_ids(self) -> dict:
        """
        获取所有会话ID
        
        Returns:
            包含所有服务会话ID的字典
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"读取所有会话ID失败: {e}")
            return {}
