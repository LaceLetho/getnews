"""
Test to verify that next_execution_time is calculated correctly based on
the last scheduled execution start time, not the end time.
"""
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from crypto_news_analyzer.execution_coordinator import MainController


class TestNextExecutionTimeFix:
    """Test that next execution time is calculated from last scheduled start time"""
    
    @pytest.fixture
    def mock_controller(self):
        """创建模拟的MainController实例"""
        with patch('crypto_news_analyzer.execution_coordinator.ConfigManager'):
            controller = MainController("test_config.json")
            controller._initialized = True
            
            # Mock config_manager
            controller.config_manager = Mock()
            controller.config_manager.get_execution_interval.return_value = 10  # 10 seconds
            
            yield controller
            
            # Cleanup
            if controller._scheduler_thread and controller._scheduler_thread.is_alive():
                controller.stop_scheduler()
    
    def test_next_execution_time_uses_scheduled_start_time(self, mock_controller):
        """
        Test that next_execution_time is calculated from the scheduled start time,
        not from the execution end time.
        
        This ensures that if an execution takes 5 seconds, and the interval is 10 seconds,
        the next execution will be 10 seconds from when the last one started, not from
        when it ended.
        """
        # Start the scheduler
        mock_controller.start_scheduler(interval_seconds=10)
        
        # Wait a moment for scheduler to initialize
        time.sleep(0.1)
        
        # Verify scheduler is running
        assert mock_controller._scheduler_thread is not None
        assert mock_controller._scheduler_thread.is_alive()
        
        # Get the initial next execution time
        next_time_1 = mock_controller.get_next_execution_time()
        assert next_time_1 is not None
        
        # The next execution time should be approximately 10 seconds from now
        # (allowing for small timing variations)
        expected_time = datetime.now() + timedelta(seconds=10)
        time_diff = abs((next_time_1 - expected_time).total_seconds())
        assert time_diff < 1.0, f"Next execution time should be ~10s from now, but diff is {time_diff}s"
        
        # Stop the scheduler
        mock_controller.stop_scheduler()
        
        # After stopping, next_execution_time should be None
        assert mock_controller.get_next_execution_time() is None
    
    def test_next_execution_time_with_last_scheduled_time(self, mock_controller):
        """
        Test that when _last_scheduled_time is set, next execution time
        is calculated from that time plus the interval.
        """
        # Set a specific last scheduled time
        last_scheduled = datetime(2026, 2, 11, 10, 0, 0)
        mock_controller._last_scheduled_time = last_scheduled
        
        # Start scheduler
        mock_controller.start_scheduler(interval_seconds=10)
        
        # Get next execution time
        next_time = mock_controller.get_next_execution_time()
        
        # Should be last_scheduled + 10 seconds
        expected_time = last_scheduled + timedelta(seconds=10)
        assert next_time == expected_time
        
        # Stop scheduler
        mock_controller.stop_scheduler()
    
    def test_next_execution_time_without_last_scheduled_time(self, mock_controller):
        """
        Test that when _last_scheduled_time is None, next execution time
        is estimated from current time.
        """
        # Ensure _last_scheduled_time is None
        mock_controller._last_scheduled_time = None
        
        # Start scheduler
        mock_controller.start_scheduler(interval_seconds=10)
        
        # Get next execution time
        next_time = mock_controller.get_next_execution_time()
        
        # Should be approximately current time + 10 seconds
        expected_time = datetime.now() + timedelta(seconds=10)
        time_diff = abs((next_time - expected_time).total_seconds())
        assert time_diff < 1.0, f"Next execution time should be ~10s from now, but diff is {time_diff}s"
        
        # Stop scheduler
        mock_controller.stop_scheduler()
