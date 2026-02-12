"""
测试执行协调器与缓存管理器的集成

验证需求:
- 需求17.9: 报告发送成功后调用cache_sent_messages
- 需求17.12: 系统启动时调用cleanup_expired_cache
- 需求17.13: 手动触发的/run命令也使用缓存机制
- 需求17.14: 实现缓存统计和监控
"""

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from crypto_news_analyzer.execution_coordinator import MainController, ExecutionStatus
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult


@pytest.fixture
def temp_config_file():
    """创建临时配置文件"""
    config_data = {
        "execution_interval": 3600,
        "time_window_hours": 24,
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "database_path": ":memory:"
        },
        "llm_config": {
            "model": "gpt-4",
            "temperature": 0.1,
            "max_tokens": 1000,
            "batch_size": 10
        },
        "rss_sources": [],
        "x_sources": []
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_cache_manager_initialized_on_system_startup(temp_config_file):
    """测试系统启动时初始化缓存管理器"""
    controller = MainController(temp_config_file)
    
    # 初始化系统
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        success = controller.initialize_system()
    
    assert success
    assert controller.cache_manager is not None


def test_cleanup_expired_cache_called_on_startup(temp_config_file):
    """测试系统启动时调用cleanup_expired_cache（需求17.12）"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        with patch('crypto_news_analyzer.storage.cache_manager.SentMessageCacheManager.cleanup_expired_cache') as mock_cleanup:
            mock_cleanup.return_value = 5
            controller.initialize_system()
            
            # 验证cleanup_expired_cache被调用
            mock_cleanup.assert_called_once_with(hours=24)


def test_cache_sent_messages_after_successful_send(temp_config_file):
    """测试报告发送成功后缓存消息（需求17.9）"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        controller.initialize_system()
    
    # 创建模拟的分类内容
    categorized_items = {
        "大户动向": [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="大户动向",
                weight_score=85,
                summary="某巨鲸地址转移10000 ETH",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 13:00",
                category="大户动向",
                weight_score=90,
                summary="大户买入BTC",
                source="https://example.com/2"
            )
        ],
        "市场新现象": [
            StructuredAnalysisResult(
                time="2024-01-01 14:00",
                category="市场新现象",
                weight_score=75,
                summary="新的DeFi协议上线",
                source="https://example.com/3"
            )
        ]
    }
    
    # 模拟Telegram发送成功
    mock_send_result = Mock()
    mock_send_result.success = True
    mock_send_result.message_id = "123"
    
    controller.telegram_sender = Mock()
    controller.telegram_sender.send_report.return_value = mock_send_result
    controller.telegram_sender.config.channel_id = "test_channel"
    
    # 执行发送阶段
    result = controller._execute_sending_stage(
        "Test report content",
        target_chat_id=None,
        categorized_items=categorized_items
    )
    
    assert result["success"]
    
    # 验证缓存中有3条消息
    cached_messages = controller.cache_manager.get_cached_messages(hours=24)
    assert len(cached_messages) == 3
    
    # 验证缓存内容
    summaries = [msg["summary"] for msg in cached_messages]
    assert "某巨鲸地址转移10000 ETH" in summaries
    assert "大户买入BTC" in summaries
    assert "新的DeFi协议上线" in summaries


def test_cache_statistics_logged_after_caching(temp_config_file):
    """测试缓存后记录统计信息（需求17.14）"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        controller.initialize_system()
    
    categorized_items = {
        "大户动向": [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="大户动向",
                weight_score=85,
                summary="测试消息",
                source="https://example.com/1"
            )
        ]
    }
    
    mock_send_result = Mock()
    mock_send_result.success = True
    mock_send_result.message_id = "123"
    
    controller.telegram_sender = Mock()
    controller.telegram_sender.send_report.return_value = mock_send_result
    controller.telegram_sender.config.channel_id = "test_channel"
    
    # 执行发送阶段
    with patch.object(controller.cache_manager, 'get_cache_statistics') as mock_stats:
        mock_stats.return_value = {
            "total_cached": 1,
            "cache_by_category": {"大户动向": 1}
        }
        
        result = controller._execute_sending_stage(
            "Test report",
            target_chat_id=None,
            categorized_items=categorized_items
        )
        
        assert result["success"]
        # 验证统计方法被调用
        mock_stats.assert_called_once()


def test_cache_failure_does_not_affect_main_flow(temp_config_file):
    """测试缓存失败不影响主流程（需求17.15）"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        controller.initialize_system()
    
    categorized_items = {
        "大户动向": [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="大户动向",
                weight_score=85,
                summary="测试消息",
                source="https://example.com/1"
            )
        ]
    }
    
    mock_send_result = Mock()
    mock_send_result.success = True
    mock_send_result.message_id = "123"
    
    controller.telegram_sender = Mock()
    controller.telegram_sender.send_report.return_value = mock_send_result
    controller.telegram_sender.config.channel_id = "test_channel"
    
    # 模拟缓存失败
    with patch.object(controller.cache_manager, 'cache_sent_messages', side_effect=Exception("Cache error")):
        result = controller._execute_sending_stage(
            "Test report",
            target_chat_id=None,
            categorized_items=categorized_items
        )
        
        # 主流程应该成功
        assert result["success"]


def test_manual_execution_uses_cache(temp_config_file):
    """测试手动触发的执行也使用缓存机制（需求17.13）"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        controller.initialize_system()
    
    # 模拟工作流各阶段
    with patch.object(controller, '_execute_crawling_stage') as mock_crawl, \
         patch.object(controller, '_execute_analysis_stage') as mock_analyze, \
         patch.object(controller, '_execute_reporting_stage') as mock_report, \
         patch.object(controller, '_execute_sending_stage') as mock_send:
        
        mock_crawl.return_value = {
            "success": True,
            "content_items": [],
            "crawl_status": Mock(),
            "errors": []
        }
        
        mock_analyze.return_value = {
            "success": True,
            "categorized_items": {
                "大户动向": [
                    StructuredAnalysisResult(
                        time="2024-01-01 12:00",
                        category="大户动向",
                        weight_score=85,
                        summary="手动触发测试",
                        source="https://example.com/1"
                    )
                ]
            },
            "analysis_results": {},
            "errors": []
        }
        
        mock_report.return_value = {
            "success": True,
            "report_content": "Test report",
            "errors": []
        }
        
        mock_send.return_value = {
            "success": True,
            "errors": []
        }
        
        # 触发手动执行
        result = controller.trigger_manual_execution(user_id="test_user", chat_id="test_chat")
        
        assert result.success
        # 验证发送阶段被调用时传递了categorized_items
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "categorized_items" in call_args[1]


def test_cache_manager_closed_on_cleanup(temp_config_file):
    """测试资源清理时关闭缓存管理器"""
    controller = MainController(temp_config_file)
    
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHANNEL_ID': 'test_channel'
    }):
        controller.initialize_system()
    
    # 模拟缓存管理器的close方法
    with patch.object(controller.cache_manager, 'close') as mock_close:
        controller.cleanup_resources()
        mock_close.assert_called_once()
