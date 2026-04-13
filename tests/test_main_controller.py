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
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
from crypto_news_analyzer.config.llm_registry import LLMConfig, ModelConfig
from crypto_news_analyzer.execution_coordinator import MainController, ExecutionStatus, ExecutionMode
from crypto_news_analyzer.models import AuthConfig, ContentItem, CrawlStatus, CrawlResult, AnalysisResult, StorageConfig
from crypto_news_analyzer.storage.cache_manager import SentMessageCacheManager
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import RepositoryFactory


class TestMainController:
    """主控制器测试类"""

    @pytest.fixture
    def manual_history_controller(self, temp_config_file, tmp_path):
        controller = MainController(temp_config_file)
        controller._initialized = True

        controller.config_manager = Mock()
        controller.config_manager.get_time_window_hours.return_value = 24
        controller.config_manager.config_data = {"llm_config": {"min_weight_score": 50}}

        database_path = tmp_path / "analysis_history.db"
        controller.data_manager = DataManager(
            StorageConfig(database_path=str(database_path))
        )
        controller.cache_manager = SentMessageCacheManager(
            StorageConfig(database_path=str(database_path))
        )
        repositories = RepositoryFactory.create_repositories(
            StorageConfig(database_path=str(database_path)),
            data_manager=controller.data_manager,
            cache_manager=controller.cache_manager,
        )
        controller.analysis_repository = repositories["analysis"]
        controller.ingestion_repository = repositories["ingestion"]
        controller.content_repository = repositories["content"]
        controller.cache_repository = repositories["cache"]

        yield controller

        controller.cache_manager.close()
        controller.data_manager.close()

    def _seed_analysis_success(
        self,
        controller,
        recipient_key,
        execution_time,
        time_window_hours=6,
        items_count=1,
    ):
        with controller.data_manager._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO analysis_execution_log
                (chat_id, execution_time, time_window_hours, items_count, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    recipient_key,
                    execution_time.isoformat(),
                    time_window_hours,
                    items_count,
                    True,
                    None,
                ),
            )
            conn.commit()

    def _build_content_item(self, item_id="item_1"):
        now = datetime.now(timezone.utc)
        return ContentItem(
            id=item_id,
            title=f"title_{item_id}",
            content=f"content_{item_id}",
            url=f"https://example.com/{item_id}",
            publish_time=now - timedelta(hours=1),
            source_name="test",
            source_type="rss",
        )

    def _build_structured_analysis_result(self, item_id="item_1"):
        return StructuredAnalysisResult(
            time="Thu, 26 Mar 2026 04:00:00 +0000",
            category="大户动向",
            weight_score=80,
            title=f"analysis_title_{item_id}",
            body=f"analysis_body_{item_id}",
            source=f"https://example.com/{item_id}",
            related_sources=[],
        )

    def _seed_cached_title(
        self,
        controller,
        recipient_key,
        sent_at,
        title,
        body="body",
        category="大户动向",
        time_text="Thu, 26 Mar 2026 04:00:00 +0000",
    ):
        with controller.cache_manager._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sent_message_cache
                (title, body, category, time, sent_at, recipient_key)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    body,
                    category,
                    time_text,
                    sent_at.isoformat(),
                    recipient_key,
                ),
            )
            conn.commit()

    def _configure_manual_analysis_success(self, controller, content_item):
        controller.llm_analyzer = Mock()
        controller.llm_analyzer.analyze_content_batch.return_value = [
            self._build_structured_analysis_result(content_item.id)
        ]
        controller._execute_reporting_stage = Mock(
            return_value={
                "success": True,
                "report_content": "# Test report",
                "errors": [],
            }
        )

    def _fetch_analysis_rows(self, controller):
        with controller.data_manager._get_connection() as conn:
            return [dict(row) for row in conn.execute(
                """
                SELECT chat_id, time_window_hours, items_count, success, error_message
                FROM analysis_execution_log
                ORDER BY id ASC
                """
            ).fetchall()]
    
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
                "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [{"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}],
                "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
                "temperature": 0.1,
                "max_tokens": 1000,
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
                "llm_config": {
                    "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                    "fallback_models": [],
                    "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "batch_size": 10
                }
            }
            controller.config_manager.load_config.return_value = controller.config_manager.config_data
            controller.config_manager.get_rss_sources.return_value = []
            controller.config_manager.get_x_sources.return_value = []
            controller.config_manager.get_auth_config.return_value = Mock(
                X_CT0="", X_AUTH_TOKEN="",
                KIMI_API_KEY="test_kimi_key", GROK_API_KEY="test_grok_key",
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
            controller.analysis_repository = Mock()
            controller.content_repository = Mock()
            controller.content_repository.get_recent_content_items.return_value = []
            controller.cache_repository = Mock()
            controller.llm_analyzer = Mock()
            controller.report_generator = Mock()
            controller.telegram_sender = Mock()
            controller.error_manager = Mock()
        
        return controller
    
    def test_controller_initialization(self, temp_config_file):
        """测试控制器初始化"""
        history_file = "./data/execution_history.json"
        if os.path.exists(history_file):
            os.remove(history_file)

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
    controller = MainController("nonexistent_config.jsonc")
        
        result = controller.validate_prerequisites()
        
        assert result["valid"] is False
        assert any("配置文件不存在" in error for error in result["errors"])

    def test_validate_prerequisites_ingestion_scope_skips_analysis_auth(self, mock_controller):
        mock_controller.config_manager.get_auth_config.side_effect = ValueError("LLM API密钥不能为空")

        result = mock_controller.validate_prerequisites(validation_scope="ingestion")

        assert result["valid"] is True
        mock_controller.config_manager.get_auth_config.assert_not_called()

    def test_validate_prerequisites_analysis_scope_requires_analysis_auth(self, mock_controller):
        mock_controller.config_manager.get_auth_config.side_effect = ValueError("LLM API密钥不能为空")

        result = mock_controller.validate_prerequisites(validation_scope="analysis-service")

        assert result["valid"] is False
        assert any("LLM API密钥不能为空" in error for error in result["errors"])
    
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
    
    def test_environment_config_override_via_config_manager_getters(self, mock_controller):
        """测试环境变量配置通过ConfigManager getter生效"""
        # 设置环境变量
        os.environ["TIME_WINDOW_HOURS"] = "48"
        os.environ["EXECUTION_INTERVAL"] = "7200"
        os.environ["KIMI_API_KEY"] = "env_kimi_key"
        
        try:
            # 为这个测试使用真实的配置管理器
            from crypto_news_analyzer.config.manager import ConfigManager
            mock_controller.config_manager = ConfigManager(mock_controller.config_path)
            mock_controller.config_manager.config_data = {
                "time_window_hours": 24,
                "execution_interval": 3600,
                "storage": {"database_path": ":memory:"},
                "llm_config": {
                    "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                    "fallback_models": [],
                    "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
                }
            }
            
            # 验证getter方法返回环境变量的值
            assert mock_controller.config_manager.get_time_window_hours() == 48
            assert mock_controller.config_manager.get_execution_interval() == 7200
            
            # 验证认证配置从环境变量读取
            auth_config = mock_controller.config_manager.get_auth_config()
            assert auth_config.KIMI_API_KEY == "env_kimi_key"
            
        finally:
            # 清理环境变量
            for key in ["TIME_WINDOW_HOURS", "EXECUTION_INTERVAL", "KIMI_API_KEY"]:
                if key in os.environ:
                    del os.environ[key]

    def test_crawling_stage_uses_env_driven_bird_config(self, mock_controller, monkeypatch):
        captured = {}

        class FakeXCrawler:
            def crawl(self, _source):
                return []

        class FakeFactory:
            def create_source(self, source_type, time_window_hours, **kwargs):
                captured["source_type"] = source_type
                captured["time_window_hours"] = time_window_hours
                captured["bird_config"] = kwargs.get("bird_config")
                captured["data_manager"] = kwargs.get("data_manager")
                return FakeXCrawler()

        x_source = Mock()
        x_source.name = "Test X"
        x_source.to_dict.return_value = {
            "name": "Test X",
            "url": "https://x.com/i/lists/1234567890",
            "type": "list",
        }

        mock_controller.config_manager.get_rss_sources.return_value = []
        mock_controller.config_manager.get_x_sources.return_value = [x_source]
        mock_controller.config_manager.get_rest_api_sources.return_value = []
        mock_controller.config_manager.get_x_auth_credentials.return_value = {
            "X_CT0": "ct0",
            "X_AUTH_TOKEN": "auth",
        }

        from crypto_news_analyzer.config.manager import ConfigManager

        real_manager = ConfigManager(mock_controller.config_path)
        real_manager.config_data = {
            "storage": {"database_path": ":memory:", "retention_days": 30, "max_storage_mb": 1000},
            "llm_config": {},
        }
        mock_controller.config_manager.get_bird_config.side_effect = real_manager.get_bird_config

        monkeypatch.setenv("BIRD_MAX_PAGE", "5")
        monkeypatch.setenv("BIRD_TIMEOUT_SECONDS", "123")
        monkeypatch.setattr(
            "crypto_news_analyzer.execution_coordinator.get_data_source_factory",
            lambda: FakeFactory(),
        )

        result = mock_controller._execute_crawling_stage(time_window_hours=6)

        assert result["success"] is True
        assert captured["source_type"] == "x"
        assert captured["time_window_hours"] == 6
        assert captured["data_manager"] is mock_controller.data_manager
        assert captured["bird_config"].bird_max_page == 5
        assert captured["bird_config"].timeout_seconds == 123
    
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
        mock_controller.config_manager.get_rest_api_sources.return_value = []
        
        result = mock_controller._execute_crawling_stage(24)
        
        assert result["success"] is True
        assert len(result["content_items"]) > 0
        assert result["crawl_status"] is not None

    @patch('crypto_news_analyzer.execution_coordinator.get_data_source_factory')
    def test_crawling_stage_uses_x_auth_credentials_without_loading_analysis_auth(
        self,
        mock_factory,
        mock_controller,
    ):
        mock_crawler = Mock()
        mock_crawler.crawl.return_value = [Mock(spec=ContentItem)]
        mock_factory.return_value.create_source.return_value = mock_crawler

        mock_rss_source = Mock()
        mock_rss_source.name = "Test RSS"
        mock_rss_source.to_dict.return_value = {"name": "Test RSS"}
        mock_controller.config_manager.get_rss_sources.return_value = [mock_rss_source]

        mock_x_source = Mock()
        mock_x_source.name = "Test X"
        mock_x_source.to_dict.return_value = {"name": "Test X"}
        mock_controller.config_manager.get_x_sources.return_value = [mock_x_source]
        mock_controller.config_manager.get_rest_api_sources.return_value = []
        mock_controller.config_manager.get_x_auth_credentials.return_value = {
            "X_CT0": "ct0-token",
            "X_AUTH_TOKEN": "auth-token",
        }
        mock_controller.config_manager.get_auth_config.side_effect = ValueError("LLM API密钥不能为空")

        result = mock_controller._execute_crawling_stage(24)

        assert result["success"] is True
        mock_controller.config_manager.get_x_auth_credentials.assert_called_once()
        mock_controller.config_manager.get_auth_config.assert_not_called()
    
    def test_analysis_stage_success(self, mock_controller):
        """测试内容分析阶段成功"""
        # 创建模拟内容项
        content_items = [Mock(spec=ContentItem) for _ in range(3)]
        for i, item in enumerate(content_items):
            item.id = f"item_{i}"
        
        # 模拟数据管理器返回内容项
        mock_controller.content_repository.get_recent_content_items.return_value = content_items
        
        # 模拟分析结果
        from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
        mock_analysis_results = []
        for i, item in enumerate(content_items):
            analysis = StructuredAnalysisResult(
                time="2024-01-01 12:00:00",
                category="大户动向" if i % 2 == 0 else "利率事件",
                weight_score=80,
                title=f"Test title {i}",
                body=f"Test body {i}",
                source=f"https://example.com/{i}",
                related_sources=[],
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

    def test_manual_recipient_key_prevents_api_and_telegram_collisions(self, manual_history_controller):
        controller = manual_history_controller

        api_recipient_key = controller._normalize_manual_recipient_key("api", "123")
        telegram_recipient_key = controller._normalize_manual_recipient_key("telegram", "123")

        controller.data_manager.log_analysis_execution(
            chat_id=api_recipient_key,
            time_window_hours=4,
            items_count=2,
            success=True,
        )

        assert api_recipient_key == "api:123"
        assert telegram_recipient_key == "telegram:123"
        assert controller.data_manager.get_last_successful_analysis_time(api_recipient_key) is not None
        assert controller.data_manager.get_last_successful_analysis_time(telegram_recipient_key) is None

    def test_failed_manual_last_success_does_not_advance_on_api_report_failure(self, manual_history_controller):
        controller = manual_history_controller
        recipient_key = controller._normalize_manual_recipient_key("api", "123")
        prior_success = datetime.now(timezone.utc) - timedelta(hours=12)
        content_item = self._build_content_item()

        self._seed_analysis_success(controller, recipient_key, prior_success)

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        controller._execute_analysis_stage = Mock(
            return_value={
                "success": True,
                "categorized_items": {"大户动向": [Mock()]},
                "analysis_results": {content_item.id: Mock()},
                "errors": [],
            }
        )
        controller._execute_reporting_stage = Mock(
            return_value={
                "success": False,
                "report_content": "",
                "errors": ["report generation failed"],
            }
        )

        result = controller.analyze_by_time_window(
            chat_id="123",
            time_window_hours=3,
            manual_source="api",
        )

        assert result["success"] is False
        assert controller.data_manager.get_last_successful_analysis_time(recipient_key) == prior_success

        rows = self._fetch_analysis_rows(controller)
        assert len(rows) == 2
        assert rows[0]["chat_id"] == "api:123"
        assert rows[0]["success"] == 1
        assert rows[1]["chat_id"] == "api:123"
        assert rows[1]["success"] == 0

    def test_successful_manual_completion_writes_one_normalized_history_row(self, manual_history_controller):
        controller = manual_history_controller
        content_item = self._build_content_item()

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        controller._execute_analysis_stage = Mock(
            return_value={
                "success": True,
                "categorized_items": {"大户动向": [Mock()]},
                "analysis_results": {content_item.id: Mock()},
                "errors": [],
            }
        )
        controller._execute_reporting_stage = Mock(
            return_value={
                "success": True,
                "report_content": "# Test report",
                "errors": [],
            }
        )

        report_content = controller.get_markdown_report_for_api(3, user_id="123")

        assert report_content == "# Test report"

        rows = self._fetch_analysis_rows(controller)
        assert rows == [
            {
                "chat_id": "api:123",
                "time_window_hours": 3,
                "items_count": 1,
                "success": 1,
                "error_message": None,
            }
        ]

    def test_no_prior_manual_outdated_history_passes_explicit_empty_titles(self, manual_history_controller):
        controller = manual_history_controller
        content_item = self._build_content_item()
        recipient_key = controller._normalize_manual_recipient_key("api", "123")

        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
            title="recent cached title should be ignored without anchor",
        )

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        self._configure_manual_analysis_success(controller, content_item)

        result = controller.analyze_by_time_window(
            chat_id="123",
            time_window_hours=3,
            manual_source="api",
        )

        assert result["success"] is True
        assert controller.llm_analyzer.analyze_content_batch.call_args.kwargs["historical_titles"] == []

    def test_anchor_manual_outdated_history_passes_empty_titles_when_window_has_no_matches(self, manual_history_controller):
        controller = manual_history_controller
        content_item = self._build_content_item()
        recipient_key = controller._normalize_manual_recipient_key("api", "123")
        prior_success = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)

        self._seed_analysis_success(controller, recipient_key, prior_success)
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success - timedelta(hours=48, seconds=1),
            title="too old for anchored window",
        )
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success + timedelta(minutes=5),
            title="too new for anchored window",
        )

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        self._configure_manual_analysis_success(controller, content_item)

        result = controller.analyze_by_time_window(
            chat_id="123",
            time_window_hours=3,
            manual_source="api",
        )

        assert result["success"] is True
        assert controller.llm_analyzer.analyze_content_batch.call_args.kwargs["historical_titles"] == []

    def test_anchor_manual_outdated_history_includes_titles_at_both_window_boundaries(self, manual_history_controller):
        controller = manual_history_controller
        content_item = self._build_content_item()
        recipient_key = controller._normalize_manual_recipient_key("api", "123")
        other_recipient_key = controller._normalize_manual_recipient_key("telegram", "123")
        prior_success = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)

        self._seed_analysis_success(controller, recipient_key, prior_success)
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success - timedelta(hours=48),
            title="window start title",
        )
        self._seed_cached_title(
            controller,
            recipient_key=other_recipient_key,
            sent_at=prior_success - timedelta(hours=24),
            title="other recipient title",
        )
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success,
            title="anchor boundary title",
        )

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        self._configure_manual_analysis_success(controller, content_item)

        result = controller.analyze_by_time_window(
            chat_id="123",
            time_window_hours=3,
            manual_source="api",
        )

        assert result["success"] is True
        assert controller.llm_analyzer.analyze_content_batch.call_args.kwargs["historical_titles"] == [
            "window start title",
            "anchor boundary title",
        ]

    def test_anchor_manual_outdated_history_excludes_titles_after_anchor_even_if_recent_now(self, manual_history_controller):
        controller = manual_history_controller
        content_item = self._build_content_item()
        recipient_key = controller._normalize_manual_recipient_key("api", "123")
        prior_success = datetime.now(timezone.utc) - timedelta(hours=2)

        self._seed_analysis_success(controller, recipient_key, prior_success)
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success - timedelta(hours=1),
            title="before anchor title",
        )
        self._seed_cached_title(
            controller,
            recipient_key=recipient_key,
            sent_at=prior_success + timedelta(minutes=30),
            title="after anchor title",
        )

        controller.content_repository.get_content_items_since = Mock(return_value=[content_item])
        self._configure_manual_analysis_success(controller, content_item)

        result = controller.analyze_by_time_window(
            chat_id="123",
            time_window_hours=3,
            manual_source="api",
        )

        assert result["success"] is True
        assert controller.llm_analyzer.analyze_content_batch.call_args.kwargs["historical_titles"] == [
            "before anchor title",
        ]

    def test_required_llm_provider_env_vars_include_opencode_go(self, temp_config_file):
        controller = MainController(temp_config_file)
        llm_config = LLMConfig(
            model=ModelConfig(provider="opencode-go", name="kimi-k2.5", options={}),
            fallback_models=[ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={})],
            market_model=ModelConfig(provider="kimi", name="kimi-k2.5", options={}),
        )

        assert controller._required_llm_provider_env_vars(llm_config) == [
            "GROK_API_KEY",
            "KIMI_API_KEY",
            "OPENCODE_API_KEY",
        ]

    def test_resolve_provider_credentials_maps_opencode_go_correctly(self, temp_config_file):
        controller = MainController(temp_config_file)
        llm_config = LLMConfig(
            model=ModelConfig(provider="opencode-go", name="kimi-k2.5", options={}),
            fallback_models=[ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={})],
            market_model=ModelConfig(provider="kimi", name="kimi-k2.5", options={}),
        )
        auth_config = AuthConfig(
            X_CT0="",
            X_AUTH_TOKEN="",
            GROK_API_KEY="  grok-key  ",
            KIMI_API_KEY=" kimi-key ",
            OPENAI_API_KEY="",
            OPENCODE_API_KEY=" opencode-key ",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHANNEL_ID="",
        )

        assert controller._resolve_provider_credentials(auth_config, llm_config) == {
            "grok": "grok-key",
            "kimi": "kimi-key",
            "opencode-go": "opencode-key",
        }

    def test_runtime_auth_requires_opencode_api_key_when_opencode_go_configured(self, temp_config_file):
        controller = MainController(temp_config_file)
        llm_config = LLMConfig(
            model=ModelConfig(provider="opencode-go", name="kimi-k2.5", options={}),
            fallback_models=[],
            market_model=ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={}),
        )
        auth_config = AuthConfig(
            X_CT0="",
            X_AUTH_TOKEN="",
            GROK_API_KEY="grok-key",
            KIMI_API_KEY="",
            OPENAI_API_KEY="",
            OPENCODE_API_KEY="",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHANNEL_ID="",
        )

        with pytest.raises(ValueError, match="OPENCODE_API_KEY"):
            controller._validate_runtime_auth(auth_config, llm_config, mode="analysis-service")

    def test_runtime_auth_does_not_require_opencode_api_key_when_unused(self, temp_config_file):
        controller = MainController(temp_config_file)
        llm_config = LLMConfig(
            model=ModelConfig(provider="kimi", name="kimi-k2.5", options={}),
            fallback_models=[],
            market_model=ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={}),
        )
        auth_config = AuthConfig(
            X_CT0="",
            X_AUTH_TOKEN="",
            GROK_API_KEY="grok-key",
            KIMI_API_KEY="kimi-key",
            OPENAI_API_KEY="",
            OPENCODE_API_KEY="",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHANNEL_ID="",
        )

        controller._validate_runtime_auth(auth_config, llm_config, mode="analysis-service")


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
                "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [{"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}],
                "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
                "temperature": 0.1,
                "max_tokens": 1000,
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
                "llm_config": {
                    "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                    "fallback_models": [{"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}],
                    "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "batch_size": 10
                }
            }
            controller.config_manager.load_config.return_value = controller.config_manager.config_data
            controller.config_manager.get_rss_sources.return_value = []
            controller.config_manager.get_x_sources.return_value = []
            controller.config_manager.get_rest_api_sources.return_value = []
            controller.config_manager.get_auth_config.return_value = Mock(
                X_CT0="", X_AUTH_TOKEN="", KIMI_API_KEY="test_key", GROK_API_KEY="",
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
            controller.content_repository = Mock()
            controller.content_repository.save_many.return_value = 0
            controller.content_repository.deduplicate.return_value = 0
            controller.content_repository.save_crawl_status = Mock()
            controller.content_repository.get_recent_content_items.return_value = []
            controller.analysis_repository = Mock()
            controller.cache_repository = Mock()
            
            controller.llm_analyzer = Mock()
            controller.llm_analyzer.batch_analyze.return_value = []
            controller.llm_analyzer.analyze_content_batch.return_value = []
            
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
