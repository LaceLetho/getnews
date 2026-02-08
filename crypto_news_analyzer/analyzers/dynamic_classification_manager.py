"""
动态分类管理器

根据大模型返回结果自动发现和管理分类，支持运行时分类变更和适应。
实现分类一致性验证和统计功能。
"""

import logging
from typing import List, Dict, Set, Any, Optional
from collections import Counter
from datetime import datetime

from .structured_output_manager import StructuredAnalysisResult


class DynamicClassificationManager:
    """
    动态分类管理器
    
    功能：
    - 根据大模型返回结果自动发现和管理分类
    - 实现分类一致性验证和统计功能
    - 支持运行时分类变更和适应
    - 不在代码中硬编码具体类别
    
    验证需求: 5.8, 5.9, 5.10
    """
    
    def __init__(self):
        """初始化动态分类管理器"""
        self.logger = logging.getLogger(__name__)
        
        # 当前会话中发现的分类
        self._current_categories: Set[str] = set()
        
        # 分类统计信息
        self._category_stats: Counter = Counter()
        
        # 分类历史记录（用于追踪分类变化）
        self._category_history: List[Dict[str, Any]] = []
        
        # 分类一致性警告阈值
        self._consistency_threshold = 0.8
        
        self.logger.info("动态分类管理器已初始化")
    
    def extract_categories_from_response(
        self,
        response_data: List[StructuredAnalysisResult]
    ) -> Set[str]:
        """
        从大模型响应中提取分类
        
        Args:
            response_data: 结构化分析结果列表
            
        Returns:
            分类名称集合
            
        验证需求: 5.8 - 支持动态分类，不在代码中硬编码具体类别
        """
        categories = set()
        
        for result in response_data:
            if result.category and result.category.strip():
                categories.add(result.category.strip())
        
        self.logger.info(f"从响应中提取到 {len(categories)} 个分类: {categories}")
        
        return categories
    
    def update_category_registry(self, new_categories: Set[str]) -> None:
        """
        更新分类注册表
        
        Args:
            new_categories: 新发现的分类集合
            
        验证需求: 5.9 - 根据返回数据中的类别数量动态展示分类
        """
        # 记录新增的分类
        added_categories = new_categories - self._current_categories
        if added_categories:
            self.logger.info(f"发现新分类: {added_categories}")
        
        # 记录消失的分类
        removed_categories = self._current_categories - new_categories
        if removed_categories:
            self.logger.info(f"分类不再出现: {removed_categories}")
        
        # 更新当前分类集合
        self._current_categories = new_categories.copy()
        
        # 记录分类变更历史
        self._category_history.append({
            "timestamp": datetime.now(),
            "categories": list(new_categories),
            "added": list(added_categories),
            "removed": list(removed_categories)
        })
        
        self.logger.info(f"分类注册表已更新，当前共有 {len(self._current_categories)} 个分类")
    
    def get_current_categories(self) -> List[str]:
        """
        获取当前分类列表
        
        Returns:
            当前分类名称列表（排序后）
            
        验证需求: 5.9 - 根据返回数据中的类别数量动态展示分类
        """
        return sorted(list(self._current_categories))
    
    def validate_category_consistency(
        self,
        categories: Set[str],
        previous_categories: Optional[Set[str]] = None
    ) -> bool:
        """
        验证分类一致性
        
        检查新的分类集合与之前的分类是否保持一致性。
        如果变化过大，可能表示提示词或模型行为发生了变化。
        
        Args:
            categories: 当前分类集合
            previous_categories: 之前的分类集合（如果为None，使用内部记录）
            
        Returns:
            是否一致（True表示一致性良好）
            
        验证需求: 5.10 - 支持分类标准的灵活变动
        """
        if previous_categories is None:
            previous_categories = self._current_categories
        
        # 如果是第一次运行，没有历史数据，认为一致
        if not previous_categories:
            self.logger.info("首次运行，无历史分类数据，跳过一致性验证")
            return True
        
        # 计算Jaccard相似度
        intersection = len(categories & previous_categories)
        union = len(categories | previous_categories)
        
        if union == 0:
            similarity = 1.0
        else:
            similarity = intersection / union
        
        is_consistent = similarity >= self._consistency_threshold
        
        if not is_consistent:
            self.logger.warning(
                f"分类一致性较低: {similarity:.2f} < {self._consistency_threshold}。"
                f"新分类: {categories}，旧分类: {previous_categories}"
            )
        else:
            self.logger.info(f"分类一致性良好: {similarity:.2f}")
        
        return is_consistent
    
    def handle_category_changes(
        self,
        old_categories: Set[str],
        new_categories: Set[str]
    ) -> None:
        """
        处理分类变更
        
        当检测到分类发生变化时，记录变更信息并更新统计。
        
        Args:
            old_categories: 旧分类集合
            new_categories: 新分类集合
            
        验证需求: 5.10 - 支持分类标准的灵活变动
        """
        added = new_categories - old_categories
        removed = old_categories - new_categories
        
        if added or removed:
            self.logger.info(
                f"分类发生变更 - 新增: {added}, 移除: {removed}"
            )
            
            # 记录变更事件
            change_event = {
                "timestamp": datetime.now(),
                "type": "category_change",
                "added": list(added),
                "removed": list(removed),
                "old_count": len(old_categories),
                "new_count": len(new_categories)
            }
            
            self._category_history.append(change_event)
    
    def get_category_statistics(self) -> Dict[str, int]:
        """
        获取分类统计信息
        
        Returns:
            分类统计字典，键为分类名称，值为出现次数
            
        验证需求: 5.9 - 根据返回数据中的类别数量动态展示分类
        """
        return dict(self._category_stats)
    
    def update_statistics(
        self,
        results: List[StructuredAnalysisResult]
    ) -> None:
        """
        更新分类统计信息
        
        Args:
            results: 分析结果列表
        """
        for result in results:
            if result.category:
                self._category_stats[result.category] += 1
        
        self.logger.debug(f"分类统计已更新: {dict(self._category_stats)}")
    
    def process_analysis_results(
        self,
        results: List[StructuredAnalysisResult],
        validate_consistency: bool = True
    ) -> Dict[str, Any]:
        """
        处理分析结果（一站式方法）
        
        提取分类、更新注册表、验证一致性、更新统计。
        
        Args:
            results: 分析结果列表
            validate_consistency: 是否验证一致性
            
        Returns:
            处理结果字典，包含分类信息和一致性状态
        """
        # 提取分类
        new_categories = self.extract_categories_from_response(results)
        
        # 验证一致性（如果需要）
        is_consistent = True
        if validate_consistency and self._current_categories:
            is_consistent = self.validate_category_consistency(new_categories)
            
            # 处理分类变更
            if not is_consistent:
                self.handle_category_changes(self._current_categories, new_categories)
        
        # 更新注册表
        self.update_category_registry(new_categories)
        
        # 更新统计
        self.update_statistics(results)
        
        return {
            "categories": self.get_current_categories(),
            "category_count": len(new_categories),
            "is_consistent": is_consistent,
            "statistics": self.get_category_statistics()
        }
    
    def get_category_history(self) -> List[Dict[str, Any]]:
        """
        获取分类变更历史
        
        Returns:
            分类历史记录列表
        """
        return self._category_history.copy()
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._category_stats.clear()
        self.logger.info("分类统计信息已重置")
    
    def reset_all(self) -> None:
        """重置所有数据（包括分类注册表和历史）"""
        self._current_categories.clear()
        self._category_stats.clear()
        self._category_history.clear()
        self.logger.info("动态分类管理器已完全重置")
    
    def set_consistency_threshold(self, threshold: float) -> None:
        """
        设置一致性阈值
        
        Args:
            threshold: 一致性阈值（0.0-1.0）
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("一致性阈值必须在0.0到1.0之间")
        
        self._consistency_threshold = threshold
        self.logger.info(f"一致性阈值已设置为: {threshold}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取管理器状态摘要
        
        Returns:
            状态摘要字典
        """
        return {
            "current_categories": self.get_current_categories(),
            "category_count": len(self._current_categories),
            "total_items_processed": sum(self._category_stats.values()),
            "statistics": self.get_category_statistics(),
            "history_count": len(self._category_history),
            "consistency_threshold": self._consistency_threshold
        }
    
    def export_state(self) -> Dict[str, Any]:
        """
        导出管理器状态（用于持久化）
        
        Returns:
            状态字典
        """
        return {
            "current_categories": list(self._current_categories),
            "category_stats": dict(self._category_stats),
            "category_history": self._category_history,
            "consistency_threshold": self._consistency_threshold,
            "export_timestamp": datetime.now().isoformat()
        }
    
    def import_state(self, state: Dict[str, Any]) -> None:
        """
        导入管理器状态（用于恢复）
        
        Args:
            state: 状态字典
        """
        self._current_categories = set(state.get("current_categories", []))
        self._category_stats = Counter(state.get("category_stats", {}))
        self._category_history = state.get("category_history", [])
        self._consistency_threshold = state.get("consistency_threshold", 0.8)
        
        self.logger.info(
            f"状态已导入: {len(self._current_categories)} 个分类, "
            f"{len(self._category_history)} 条历史记录"
        )
