from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


class _ConfigManagerStub:
    def get_analysis_config(self):
        return {"max_analysis_window_hours": 24}


class _DataManagerStub:
    def __init__(self, last_analysis_time):
        self._last_analysis_time = last_analysis_time
        self.requested_chat_ids = []

    def get_last_successful_analysis_time(self, chat_id):
        self.requested_chat_ids.append(chat_id)
        return self._last_analysis_time


class _CoordinatorStub:
    def __init__(self, last_analysis_time):
        self.config_manager = _ConfigManagerStub()
        self.data_manager = _DataManagerStub(last_analysis_time)
        self.telegram_sender = Mock()
        self._record_manual_analysis_success = Mock()
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

    def _resolve_manual_recipient_key(self, chat_id, manual_source="telegram"):
        return f"{manual_source}:{chat_id}"

    def _persist_manual_analysis_success(
        self,
        recipient_key,
        time_window_hours,
        items_count,
        final_report_messages=None,
    ):
        self._record_manual_analysis_success(
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
        )


class _HistoricalDataManagerStub:
    def __init__(self):
        self.logged_rows = []

    def log_analysis_execution(
        self,
        chat_id,
        time_window_hours,
        items_count,
        success,
        error_message=None,
    ):
        self.logged_rows.append(
            {
                "chat_id": chat_id,
                "time_window_hours": time_window_hours,
                "items_count": items_count,
                "success": success,
                "error_message": error_message,
                "execution_time": datetime.now(timezone.utc),
            }
        )

    def get_last_successful_analysis_time(self, chat_id):
        for row in reversed(self.logged_rows):
            if row["chat_id"] == chat_id and row["success"]:
                return row["execution_time"]
        return None


class _HistoricalCacheManagerStub:
    def __init__(self):
        self.cached_messages = []

    def cache_sent_messages(self, messages, recipient_key=None):
        sent_at = datetime.now(timezone.utc)
        for message in messages:
            self.cached_messages.append(
                {
                    "title": message["title"],
                    "body": message["body"],
                    "category": message["category"],
                    "time": message["time"],
                    "recipient_key": recipient_key,
                    "sent_at": sent_at,
                }
            )
        return len(messages)

    def get_recipient_cached_titles(self, recipient_key, anchor_time):
        window_start = anchor_time - timedelta(hours=48)
        return [
            message["title"]
            for message in self.cached_messages
            if message["recipient_key"] == recipient_key
            and window_start <= message["sent_at"] <= anchor_time
        ]


class _HistoricalCoordinatorStub:
    def __init__(self):
        self.config_manager = _ConfigManagerStub()
        self.data_manager = _HistoricalDataManagerStub()
        self.cache_manager = _HistoricalCacheManagerStub()
        self.telegram_sender = Mock()
        self.telegram_sender.send_report_to_chat.return_value = Mock(success=True, error_message=None)
        self.analyze_calls = []
        self.report_titles_by_chat = {}

    def is_execution_running(self):
        return False

    def get_execution_status(self):
        return Mock(execution_id="x", current_stage="analyzing", progress=0.5)

    def set_report_titles(self, chat_id, titles):
        self.report_titles_by_chat[chat_id] = list(titles)

    def _resolve_manual_recipient_key(self, chat_id, manual_source="telegram"):
        normalized_chat_id = str(chat_id).strip()
        if normalized_chat_id.startswith("telegram:") or normalized_chat_id.startswith("api:"):
            return normalized_chat_id
        return f"{manual_source}:{normalized_chat_id}"

    def _record_manual_analysis_success(self, recipient_key, time_window_hours, items_count):
        self.data_manager.log_analysis_execution(
            chat_id=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
            success=True,
        )

    def _persist_manual_analysis_success(
        self,
        recipient_key,
        time_window_hours,
        items_count,
        final_report_messages=None,
    ):
        if final_report_messages:
            self.cache_manager.cache_sent_messages(
                final_report_messages,
                recipient_key=recipient_key,
            )
        self._record_manual_analysis_success(
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
        )

    def analyze_by_time_window(self, chat_id, hours):
        recipient_key = self._resolve_manual_recipient_key(chat_id, manual_source="telegram")
        anchor_time = self.data_manager.get_last_successful_analysis_time(recipient_key)
        historical_titles = (
            self.cache_manager.get_recipient_cached_titles(recipient_key, anchor_time)
            if anchor_time is not None
            else []
        )
        self.analyze_calls.append(
            {
                "chat_id": chat_id,
                "recipient_key": recipient_key,
                "hours": hours,
                "historical_titles": historical_titles,
            }
        )

        titles = self.report_titles_by_chat.get(chat_id, [f"title-{chat_id}"])
        return {
            "success": True,
            "report_content": f"# Report for {chat_id}",
            "items_processed": len(titles),
            "execution_id": f"exec-{len(self.analyze_calls)}",
            "errors": [],
            "final_report_messages": [
                {
                    "title": title,
                    "body": f"body-{title}",
                    "category": "Test Category",
                    "time": "Fri, 27 Mar 2026 00:00:00 +0000",
                }
                for title in titles
            ],
        }


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


def test_analyze_looks_up_last_success_with_normalized_telegram_recipient_key():
    last_run = datetime.now(timezone.utc) - timedelta(hours=2)
    coordinator = _CoordinatorStub(last_run)

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    with patch("threading.Thread.start", return_value=None):
        handler.handle_analyze_command("1", "tester", "chat_1")

    assert coordinator.data_manager.requested_chat_ids == ["telegram:chat_1"]


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


def test_analyze_records_telegram_success_only_after_send_report_succeeds():
    coordinator = _CoordinatorStub(None)
    coordinator._analyze_result = {
        "success": True,
        "report_content": "# report",
        "items_processed": 3,
        "execution_id": "exec_1",
        "errors": [],
    }
    coordinator.telegram_sender.send_report_to_chat.return_value = Mock(
        success=True,
        error_message=None,
    )

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    handler._send_message_sync = lambda *args, **kwargs: None
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )

    coordinator._record_manual_analysis_success.assert_called_once_with(
        recipient_key="telegram:chat_1",
        time_window_hours=2,
        items_count=3,
    )


def test_analyze_does_not_record_telegram_success_when_report_send_fails():
    coordinator = _CoordinatorStub(None)
    coordinator._analyze_result = {
        "success": True,
        "report_content": "# report",
        "items_processed": 2,
        "execution_id": "exec_1",
        "errors": [],
    }
    coordinator.telegram_sender.send_report_to_chat.return_value = Mock(
        success=False,
        error_message="send failed",
    )

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    handler._send_message_sync = lambda *args, **kwargs: None
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )

    coordinator._record_manual_analysis_success.assert_not_called()


def test_analyze_second_success_in_same_chat_reuses_prior_chat_titles():
    coordinator = _HistoricalCoordinatorStub()
    coordinator.set_report_titles("chat_1", ["same-chat-title"])

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    handler._send_message_sync = lambda *args, **kwargs: None
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )
    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )

    assert coordinator.analyze_calls[0]["recipient_key"] == "telegram:chat_1"
    assert coordinator.analyze_calls[0]["historical_titles"] == []
    assert coordinator.analyze_calls[1]["historical_titles"] == ["same-chat-title"]


def test_analyze_different_chats_keep_historical_titles_isolated():
    coordinator = _HistoricalCoordinatorStub()
    coordinator.set_report_titles("chat_1", ["shared-title"])
    coordinator.set_report_titles("chat_2", ["shared-title"])

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    handler._send_message_sync = lambda *args, **kwargs: None
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )
    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_2",
        hours=2,
        window_description="最近 2 小时",
    )

    assert coordinator.analyze_calls[0]["historical_titles"] == []
    assert coordinator.analyze_calls[1]["recipient_key"] == "telegram:chat_2"
    assert coordinator.analyze_calls[1]["historical_titles"] == []


def test_analyze_failed_telegram_send_does_not_cache_titles_or_advance_history():
    coordinator = _HistoricalCoordinatorStub()
    coordinator.set_report_titles("chat_1", ["failed-send-title"])
    coordinator.telegram_sender.send_report_to_chat.return_value = Mock(
        success=False,
        error_message="send failed",
    )

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    handler._send_message_sync = lambda *args, **kwargs: None
    handler._log_command_execution = lambda *args, **kwargs: None

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )

    assert coordinator.cache_manager.cached_messages == []
    assert coordinator.data_manager.get_last_successful_analysis_time("telegram:chat_1") is None
    assert coordinator.analyze_calls[0]["historical_titles"] == []

    coordinator.telegram_sender.send_report_to_chat.return_value = Mock(success=True, error_message=None)

    handler._execute_analyze_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=2,
        window_description="最近 2 小时",
    )

    assert coordinator.analyze_calls[1]["historical_titles"] == []


def test_analyze_command_still_available_in_public_analysis_runtime(monkeypatch):
    monkeypatch.setenv("CRYPTO_NEWS_RUNTIME_MODE", "analysis-service")
    coordinator = _CoordinatorStub(None)

    handler = TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
    )

    with patch("threading.Thread.start", return_value=None):
        response = handler.handle_analyze_command("1", "tester", "chat_1", hours=2)

    assert "🔍 开始分析" in response
    assert "最近 2 小时" in response
