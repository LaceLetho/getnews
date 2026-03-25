from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


class _ConfigManagerStub:
    def get_analysis_config(self):
        return {"max_analysis_window_hours": 24}


class _DataManagerStub:
    def __init__(self, last_analysis_time):
        self._last_analysis_time = last_analysis_time

    def get_last_successful_analysis_time(self, chat_id):
        return self._last_analysis_time


class _CoordinatorStub:
    def __init__(self, last_analysis_time):
        self.config_manager = _ConfigManagerStub()
        self.data_manager = _DataManagerStub(last_analysis_time)
        self.telegram_sender = Mock()
        self._analyze_result = {
            "success": True,
            "report_content": "",
            "items_processed": 0,
            "execution_id": "exec_1",
            "errors": [],
        }

    def is_execution_running(self):
        return False

    def get_execution_status(self):
        return Mock(execution_id="x", current_stage="analyzing", progress=0.5)

    def analyze_by_time_window(self, chat_id, hours):
        return self._analyze_result


def test_analyze_uses_since_last_success_description_for_quick_retrigger():
    last_run = datetime.now(timezone.utc) - timedelta(minutes=5)
    coordinator = _CoordinatorStub(last_run)

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    with patch("threading.Thread.start", return_value=None):
        response = handler.handle_analyze_command("1", "tester", "chat_1")

    assert "自上次成功运行以来（约 1 小时）" in response
    assert "24 小时" not in response


def test_analyze_falls_back_to_recent_window_description_when_capped_by_max_hours():
    last_run = datetime.now(timezone.utc) - timedelta(days=3)
    coordinator = _CoordinatorStub(last_run)

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    with patch("threading.Thread.start", return_value=None):
        response = handler.handle_analyze_command("1", "tester", "chat_1")

    assert "最近 24 小时" in response
    assert "自上次成功运行以来" not in response


def test_analyze_no_content_sends_success_notification_instead_of_failure():
    coordinator = _CoordinatorStub(None)

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    sent_messages = []
    def _capture_message(user_id, message):
        sent_messages.append(message)

    handler._send_message_sync = _capture_message
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=1,
        window_description="从上次成功运行到现在",
    )

    assert sent_messages
    assert "✅ *分析完成*" in sent_messages[0]
    assert "暂无符合条件的新内容" in sent_messages[0]
    assert "分析失败" not in sent_messages[0]
