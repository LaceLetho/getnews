"""
主控制器测试

测试MainController的核心功能，包括一次性执行和定时调度。
"""

import pytest
import tempfile
import os
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from crypto_news_analyzer.execution_coordinator import MainController, ExecutionStatus, ExecutionMode
from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult


class TestMainController:
    """主控制器测试类"""
    
    @pytest.fixture
    def temp_config_file(self):
        """创建临时配置文件"""
        config_data = {
            "execution_interval": 10,  # 10秒用于测试
            "time_window_hours": 24,
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": ":memory:"  # 使用内存数据库
            },
            "llm_config": {
                "model": "MiniMax-M2.1",
                "temperature": 0.1,
                "max_tokens": 1000,
                "prompt_config_path": "./prompts/analysis_prompt.json",
                "batch_size": 10
            },
            "rss_sources": [
                {
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "description": "Test RSS source"
                }
            ],
            "x_sources": [],
            "rest_api_sources": []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # 清理
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_controller(self, temp_config_file):
        """创建模拟的主控制器"""
        # Clean up any existing history file
        import os
        history_file = "./data/execution_history.json"
        if os.path.exists(history_file):
            os.remove(history_file)
        
        controller = MainController(temp_config_file)
        
        # 模拟组件初始化
        with patch.object(controller, 'initialize_system', return_value=True):
            controller._initialized = True
            
            # 创建模拟组件
            controller.config_manager = Mock()
            controller.config_manager.config_data = {
                "time_window_hours": 24,
                "execution_interval": 10,
                "storage": {"database_path": ":memory:"},
                "llm_config": {}
            }
            controller.config_manager.load_config.return_value = controller.config_manager.config_data
            controller.config_manager.get_rss_sources.return_value = []
            controller.config_manager.get_x_sources.return_value = []
            controller.config_manager.get_auth_config.return_value = Mock(
                X_CT0="", X_AUTH_TOKEN="", LLM_API_KEY="test_key",
                TELEGRAM_BOT_TOKEN="test_token", TELEGRAM_CHANNEL_ID="test_channel"
            )
            controller.config_manager.get_storage_config.return_value = Mock(
                database_path=":memory:", retention_days=30
            )
            controller.config_manager.validate_storage_path.return_value = True
            # Add getters for execution_interval and time_window_hours
            controller.config_manager.get_execution_interval.return_value = 10
            controller.config_manager.get_time_window_hours.return_value = 24
            
            controller.data_manager = Mock()
            controller.data_manager.get_content_items.return_value = []
            controller.llm_analyzer = Mock()
            controller.content_classifier = Mock()
            controller.report_generator = Mock()
            controller.telegram_sender = Mock()
            controller.error_manager = Mock()
        
        return controller
    
    def test_controller_initialization(self, temp_config_file):
        """测试控制器初始化"""
        controller = MainController(temp_config_file)
        
        assert controller.config_path == temp_config_file
        assert not controller._initialized
        assert controller.current_execution is None
        assert len(controller.execution_history) == 0
    
    def test_validate_prerequisites_success(self, mock_controller):
        """测试前提条件验证成功"""
        result = mock_controller.validate_prerequisites()
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_prerequisites_missing_config(self):
        """测试前提条件验证失败 - 配置文件不存在"""
        controller = MainController("nonexistent_config.json")
        
        result = controller.validate_prerequisites()
        
        assert result["valid"] is False
        assert any("配置文件不存在" in error for error in result["errors"])
    
    def test_run_once_success(self, mock_controller):
        """测试一次性执行成功"""
        # 模拟工作流成功
        mock_controller.coordinate_workflow = Mock(return_value={
            "success": True,
            "items_processed": 5,
            "categories_found": {"大户动向": 2, "利率事件": 3},
            "errors": [],
            "report_sent": True
        })
        
        result = mock_controller.run_once()
        
        assert result.success is True
        assert result.items_processed == 5
        assert result.categories_found == {"大户动向": 2, "利率事件": 3}
        assert result.report_sent is True
        assert len(mock_controller.execution_history) == 1
    
    def test_run_once_failure(self, mock_controller):
        """测试一次性执行失败"""
        # 模拟工作流失败
        mock_controller.coordinate_workflow = Mock(side_effect=Exception("Test error"))
        
        result = mock_controller.run_once()
        
        assert result.success is False
        assert "Test error" in result.errors
        assert len(mock_controller.execution_history) == 1
    
    def test_coordinate_workflow_complete(self, mock_controller):
        """测试完整工作流协调"""
        # 模拟各阶段成功
        mock_controller._execute_crawling_stage = Mock(return_value={
            "success": True,
            "content_items": [Mock()],
            "crawl_status": Mock(),
            "errors": []
        })
        
        mock_controller._execute_analysis_stage = Mock(return_value={
            "success": True,
            "categorized_items": {"大户动向": [Mock()]},
            "analysis_results": {"item1": Mock()},
            "errors": []
        })
        
        mock_controller._execute_reporting_stage = Mock(return_value={
            "success": True,
            "report_content": "Test report",
            "errors": []
        })
        
        mock_controller._execute_sending_stage = Mock(return_value={
            "success": True,
            "errors": []
        })
        
        result = mock_controller.coordinate_workflow()
        
        assert result["success"] is True
        assert result["items_processed"] == 1
        assert "大户动向" in result["categories_found"]
        assert result["report_sent"] is True
    
    def test_scheduler_start_stop(self, mock_controller):
        """测试调度器启动和停止"""
        # 启动调度器
        mock_controller.start_scheduler(1)  # 1秒间隔用于测试
        
        assert mock_controller._scheduler_thread is not None
        assert mock_controller._scheduler_thread.is_alive()
        
        # 等待一小段时间
        time.sleep(0.1)
        
        # 停止调度器
        mock_controller.stop_scheduler()
        
        # 等待线程结束
        time.sleep(0.2)
        
        assert not mock_controller._scheduler_thread.is_alive()
    
    def test_execution_status_tracking(self, mock_controller):
        """测试执行状态跟踪"""
        # 初始状态
        assert mock_controller.get_execution_status() is None
        assert not mock_controller.is_execution_running()
        
        # 模拟执行开始
        mock_controller.coordinate_workflow = Mock(return_value={
            "success": True,
            "items_processed": 0,
            "categories_found": {},
            "errors": [],
            "report_sent": False
        })
        
        # 在另一个线程中执行，以便可以检查状态
        def run_execution():
            mock_controller.run_once()
        
        thread = threading.Thread(target=run_execution)
        thread.start()
        
        # 等待执行开始
        time.sleep(0.1)
        
        # 检查执行状态
        status = mock_controller.get_execution_status()
        if status:  # 可能执行太快已经完成
            assert status.status in [ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED]
        
        thread.join()
        
        # 检查执行历史
        assert len(mock_controller.execution_history) == 1
    
    def test_environment_config_override(self, mock_controller):
        """测试环境变量配置覆盖"""
        # 设置环境变量
        os.environ["TIME_WINDOW_HOURS"] = "48"
        os.environ["EXECUTION_INTERVAL"] = "7200"
        os.environ["LLM_API_KEY"] = "env_api_key"
        
        try:
            # 为这个测试使用真实的配置管理器
            from crypto_news_analyzer.config.manager import ConfigManager
            mock_controller.config_manager = ConfigManager(mock_controller.config_path)
            mock_controller.config_manager.config_data = {
                "time_window_hours": 24,
                "execution_interval": 3600,
                "storage": {"database_path": ":memory:"},
                "llm_config": {}
            }
            
            mock_controller.setup_environment_config()
            
            # 验证getter方法返回环境变量的值
            assert mock_controller.config_manager.get_time_window_hours() == 48
            assert mock_controller.config_manager.get_execution_interval() == 7200
            
            # 验证认证配置从环境变量读取
            auth_config = mock_controller.config_manager.get_auth_config()
            assert auth_config.LLM_API_KEY == "env_api_key"
            
        finally:
            # 清理环境变量
            for key in ["TIME_WINDOW_HOURS", "EXECUTION_INTERVAL", "LLM_API_KEY"]:
                if key in os.environ:
                    del os.environ[key]
    
    def test_execution_history_limit(self, mock_controller):
        """测试执行历史限制"""
        # 添加多个执行结果
        for i in range(15):
            result = Mock()
            result.execution_id = f"exec_{i}"
            mock_controller.execution_history.append(result)
        
        # 获取限制数量的历史
        history = mock_controller.get_execution_history(limit=5)
        assert len(history) == 5
        
        # 获取所有历史
        all_history = mock_controller.get_execution_history(limit=0)
        assert len(all_history) == 15
    
    def test_system_status(self, mock_controller):
        """测试系统状态获取"""
        status = mock_controller.get_system_status()
        
        assert "initialized" in status
        assert "scheduler_running" in status
        assert "current_execution" in status
        assert "execution_history_count" in status
        assert "next_execution_time" in status
        
        assert status["initialized"] is True
        assert status["scheduler_running"] is False
        assert status["execution_history_count"] == 0
    
    def test_resource_cleanup(self, mock_controller):
        """测试资源清理"""
        # 启动调度器
        mock_controller.start_scheduler(1)
        
        # 执行清理
        mock_controller.cleanup_resources()
        
        # 验证调度器已停止
        assert not (mock_controller._scheduler_thread and mock_controller._scheduler_thread.is_alive())
        
        # 验证数据管理器清理被调用
        mock_controller.data_manager.close.assert_called_once()
    
    @patch('crypto_news_analyzer.execution_coordinator.get_data_source_factory')
    def test_crawling_stage_success(self, mock_factory, mock_controller):
        """测试数据爬取阶段成功"""
        # 模拟数据源工厂
        mock_crawler = Mock()
        mock_crawler.crawl.return_value = [Mock(spec=ContentItem)]
        mock_factory.return_value.create_source.return_value = mock_crawler
        
        # 模拟RSS源
        mock_rss_source = Mock()
        mock_rss_source.name = "Test RSS"
        mock_rss_source.to_dict.return_value = {"name": "Test RSS"}
        mock_controller.config_manager.get_rss_sources.return_value = [mock_rss_source]
        
        result = mock_controller._execute_crawling_stage(24)
        
        assert result["success"] is True
        assert len(result["content_items"]) > 0
        assert result["crawl_status"] is not None
    
    def test_analysis_stage_success(self, mock_controller):
        """测试内容分析阶段成功"""
        # 创建模拟内容项
        content_items = [Mock(spec=ContentItem) for _ in range(3)]
        for i, item in enumerate(content_items):
            item.id = f"item_{i}"
        
        # 模拟数据管理器返回内容项
        mock_controller.data_manager.get_content_items.return_value = content_items
        
        # 模拟分析结果
        from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
        mock_analysis_results = []
        for i, item in enumerate(content_items):
            analysis = StructuredAnalysisResult(
                time="2024-01-01 12:00:00",
                category="大户动向" if i % 2 == 0 else "利率事件",
                weight_score=80,
                summary=f"Test summary {i}",
                source=f"https://example.com/{i}"
            )
            mock_analysis_results.append(analysis)
        
        mock_controller.llm_analyzer.analyze_content_batch.return_value = mock_analysis_results
        
        result = mock_controller._execute_analysis_stage(content_items)
        
        assert result["success"] is True
        assert len(result["categorized_items"]) > 0
        assert len(result["analysis_results"]) > 0
    
    def test_reporting_stage_success(self, mock_controller):
        """测试报告生成阶段成功"""
        categorized_items = {"大户动向": [Mock()]}
        analysis_results = {"item1": Mock()}
        
        mock_controller.report_generator.generate_telegram_report.return_value = "Test report content"
        
        result = mock_controller._execute_reporting_stage(
            categorized_items, analysis_results, Mock(), 24
        )
        
        assert result["success"] is True
        assert result["report_content"] == "Test report content"
    
    def test_sending_stage_success(self, mock_controller):
        """测试报告发送阶段成功"""
        mock_send_result = Mock()
        mock_send_result.success = True
        mock_send_result.message_id = 12345
        
        mock_controller.telegram_sender.send_report.return_value = mock_send_result
        
        result = mock_controller._execute_sending_stage("Test report")
        
        assert result["success"] is True
    
    def test_sending_stage_no_telegram(self, mock_controller):
        """测试报告发送阶段 - 无Telegram配置"""
        mock_controller.telegram_sender = None
        
        with patch.object(mock_controller, '_save_report_backup', return_value="/tmp/backup.md"):
            result = mock_controller._execute_sending_stage("Test report")
        
        assert result["success"] is True  # 应该成功，因为保存了本地备份


@pytest.mark.integration
class TestMainControllerIntegration:
    """主控制器集成测试"""
    
    @pytest.fixture
    def temp_config_file(self):
        """创建临时配置文件"""
        config_data = {
            "execution_interval": 10,
            "time_window_hours": 24,
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": ":memory:"
            },
            "llm_config": {
                "model": "MiniMax-M2.1",
                "temperature": 0.1,
                "max_tokens": 1000,
                "prompt_config_path": "./prompts/analysis_prompt.json",
                "batch_size": 10
            },
            "rss_sources": [],
            "x_sources": [],
            "rest_api_sources": []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # 清理
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_full_workflow_with_mock_components(self, temp_config_file):
        """测试完整工作流程（使用模拟组件）"""
        controller = MainController(temp_config_file)
        
        # 模拟系统初始化成功
        with patch.object(controller, 'initialize_system', return_value=True):
            controller._initialized = True
            
            # 模拟所有组件
            controller.config_manager = Mock()
            controller.config_manager.config_data = {
                "time_window_hours": 24,
                "execution_interval": 10,
                "storage": {"database_path": ":memory:"},
                "llm_config": {}
            }
            controller.config_manager.load_config.return_value = controller.config_manager.config_data
            controller.config_manager.get_rss_sources.return_value = []
            controller.config_manager.get_x_sources.return_value = []
            controller.config_manager.get_auth_config.return_value = Mock(
                X_CT0="", X_AUTH_TOKEN="", LLM_API_KEY="test_key",
                TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID=""
            )
            controller.config_manager.get_storage_config.return_value = Mock(
                database_path=":memory:", retention_days=30
            )
            controller.config_manager.validate_storage_path.return_value = True
            # Add getters for execution_interval and time_window_hours
            controller.config_manager.get_execution_interval.return_value = 10
            controller.config_manager.get_time_window_hours.return_value = 24
            
            controller.data_manager = Mock()
            controller.data_manager.add_content_items.return_value = 0
            controller.data_manager.save_crawl_status = Mock()
            controller.data_manager.get_content_items.return_value = []
            
            controller.llm_analyzer = Mock()
            controller.llm_analyzer.batch_analyze.return_value = []
            controller.llm_analyzer.analyze_content_batch.return_value = []
            
            controller.content_classifier = Mock()
            controller.report_generator = Mock()
            controller.report_generator.generate_report.return_value = "Test report"
            controller.report_generator.generate_telegram_report.return_value = "Test report"
            
            controller.telegram_sender = None  # 模拟无Telegram配置
            
            # 执行工作流
            result = controller.run_once()
            
            # 验证结果
            assert result.success is True
            assert result.items_processed == 0  # 没有实际内容项
            assert len(controller.execution_history) == 1


if __name__ == "__main__":
    pytest.main([__file__])