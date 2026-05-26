"""
Focused tests for the LLM debug logging helpers.
"""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest

from crypto_news_analyzer.utils.llm_logging import (
    is_llm_debug_logging_enabled,
    log_llm_error,
    log_llm_request,
    log_llm_response,
    llm_sdk_debug_logging,
    stringify_error_payload,
    stringify_request_payload,
    stringify_response_payload,
)

# ---------------------------------------------------------------------------
# is_llm_debug_logging_enabled
# ---------------------------------------------------------------------------


class TestIsLlmDebugLoggingEnabled:
    def test_nested_true(self) -> None:
        config = {"llm_config": {"enable_debug_logging": True}}
        assert is_llm_debug_logging_enabled(config) is True

    def test_nested_false(self) -> None:
        config = {"llm_config": {"enable_debug_logging": False}}
        assert is_llm_debug_logging_enabled(config) is False

    def test_nested_absent_returns_default(self) -> None:
        config = {"llm_config": {"model": "kimi"}}
        assert is_llm_debug_logging_enabled(config) is False
        assert is_llm_debug_logging_enabled(config, default=True) is True

    def test_flat_true(self) -> None:
        config = {"enable_debug_logging": True}
        assert is_llm_debug_logging_enabled(config) is True

    def test_flat_false(self) -> None:
        config = {"enable_debug_logging": False}
        assert is_llm_debug_logging_enabled(config) is False

    def test_flat_absent_returns_default(self) -> None:
        config = {"model": "kimi"}
        assert is_llm_debug_logging_enabled(config) is False
        assert is_llm_debug_logging_enabled(config, default=True) is True

    def test_none_config_returns_default(self) -> None:
        assert is_llm_debug_logging_enabled(None) is False
        assert is_llm_debug_logging_enabled(None, default=True) is True

    def test_non_bool_values_return_default(self) -> None:
        assert (
            is_llm_debug_logging_enabled({"llm_config": {"enable_debug_logging": "yes"}}) is False
        )
        assert is_llm_debug_logging_enabled({"enable_debug_logging": 1}) is False
        assert is_llm_debug_logging_enabled({"enable_debug_logging": None}) is False

    def test_empty_config_returns_default(self) -> None:
        assert is_llm_debug_logging_enabled({}) is False
        assert is_llm_debug_logging_enabled({}, default=True) is True


# ---------------------------------------------------------------------------
# stringify_request_payload / stringify_response_payload
# ---------------------------------------------------------------------------


class TestStringifyRequestPayload:
    def test_plain_dict(self) -> None:
        payload = {"model": "kimi-k2.5", "messages": [{"role": "user", "content": "hello"}]}
        result = stringify_request_payload(payload)
        assert "kimi-k2.5" in result
        assert "hello" in result

    def test_headers_sanitized(self) -> None:
        payload = {"headers": {"Authorization": "Bearer secret"}}
        result = stringify_request_payload(payload)
        assert "secret" not in result
        assert "<auth suppressed>" in result
        assert "headers" in result

    def test_nested_sanitization(self) -> None:
        payload = {
            "config": {
                "headers": {"X-API-Key": "my-secret-key"},
                "auth": {"password": "hunter2"},
            }
        }
        result = stringify_request_payload(payload)
        assert "my-secret-key" not in result
        assert "hunter2" not in result
        assert "<auth suppressed>" in result
        assert "<auth suppressed>" in result

    def test_api_key_sanitized(self) -> None:
        for key in ("api_key", "apiKey", "api_key "):
            payload = {"model": "kimi", key: "sk-12345"}
            result = stringify_request_payload(payload)
            assert "sk-12345" not in result

    def test_password_secret_token_sanitized(self) -> None:
        for key in ("password", "secret", "token"):
            payload = {"user": {"name": "alice", key: "hunter2"}}
            result = stringify_request_payload(payload)
            assert "hunter2" not in result

    def test_client_objects_sanitized(self) -> None:
        for key in ("client", "_client", "http_client", "sync_client", "async_client"):
            payload = {"model": "kimi", key: Mock()}
            result = stringify_request_payload(payload)
            assert "<client object suppressed>" in result

    def test_bytes_payload_decoded(self) -> None:
        payload = b'{"model": "kimi", "content": "hello"}'
        result = stringify_request_payload(payload)
        assert "kimi" in result
        assert "hello" in result

    def test_binary_bytes_payload(self) -> None:
        payload = b"\x00\xff\xfe"
        result = stringify_request_payload(payload)
        assert "<binary payload>" in result

    def test_string_payload_passed_through(self) -> None:
        payload = '{"model": "kimi"}'
        result = stringify_request_payload(payload)
        assert "kimi" in result

    def test_bytearray_decoded(self) -> None:
        payload = bytearray(b"hello world")
        result = stringify_request_payload(payload)
        assert "hello world" in result

    def test_list_of_dicts_sanitized(self) -> None:
        payload = [
            {"headers": {"Authorization": "Bearer tok"}},
            {"model": "kimi"},
        ]
        result = stringify_request_payload(payload)
        assert "tok" not in result
        assert "<auth suppressed>" in result
        assert "kimi" in result

    def test_non_serializable_fallback_to_repr(self) -> None:
        class UnSerializable:
            pass

        payload = {"item": UnSerializable()}
        result = stringify_request_payload(payload)
        # Should not raise, repr is acceptable
        assert "<" in result


class TestStringifyResponsePayload:
    """Identical logic to request, just verify it works."""

    def test_passthrough_same_as_request(self) -> None:
        payload = {"choices": [{"message": {"content": "answer"}}]}
        assert stringify_response_payload(payload) == stringify_request_payload(payload)


# ---------------------------------------------------------------------------
# stringify_error_payload
# ---------------------------------------------------------------------------


class TestStringifyErrorPayload:
    def test_plain_exception(self) -> None:
        err = ValueError("something went wrong")
        result = stringify_error_payload(err)
        assert "something went wrong" in result

    def test_empty_error_str(self) -> None:
        class EmptyStrError(Exception):
            def __str__(self):
                return ""

        result = stringify_error_payload(EmptyStrError())
        assert "EmptyStrError" in result

    def test_requests_response_text(self) -> None:
        response = Mock()
        response.text = "server error: rate limit exceeded"
        response.content = b""
        response.status_code = 429

        result = stringify_error_payload(response)

        assert "rate limit" in result

    def test_requests_response_binary_content(self) -> None:
        response = Mock()
        response.text = ""
        response.content = b'{"error": "internal error"}'
        response.status_code = 500

        result = stringify_error_payload(response)

        assert "internal error" in result

    def test_httpx_response_text(self) -> None:
        import httpx

        response = Mock(spec=httpx.Response)
        response.text = "httpx error body"
        response.status_code = 503

        result = stringify_error_payload(response)
        assert "httpx error body" in result

    def test_openai_response_text(self) -> None:
        response = Mock()
        response.text = "openai error: model not found"
        response.content = None

        result = stringify_error_payload(response)
        assert "model not found" in result

    def test_openai_response_content_bytes(self) -> None:
        response = Mock()
        response.text = ""
        response.content = b"raw content from openai"

        result = stringify_error_payload(response)
        assert "raw content from openai" in result

    def test_string_error(self) -> None:
        result = stringify_error_payload("just a string error")
        assert "just a string error" in result

    def test_bytes_error(self) -> None:
        result = stringify_error_payload(b"byte error message")
        assert "byte error message" in result

    def test_bytearray_error(self) -> None:
        result = stringify_error_payload(bytearray(b"bytearray error"))
        assert "bytearray error" in result


# ---------------------------------------------------------------------------
# log_llm_request / log_llm_response / log_llm_error
# ---------------------------------------------------------------------------


class TestLogLlmRequest:
    def test_debug_enabled_logs_full_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_debug_request")
        logger.setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_llm_request(logger, "test msg", {"model": "kimi", "secret": "hide-me"})
            assert "kimi" in caplog.text
            assert "hide-me" not in caplog.text
            assert "<auth suppressed>" in caplog.text

    def test_debug_disabled_logs_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_no_debug_request")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO, logger=logger.name):
            log_llm_request(logger, "test msg", {"model": "kimi"})
            assert "test msg" in caplog.text
            assert "debug disabled" in caplog.text
            assert "kimi" not in caplog.text


class TestLogLlmResponse:
    def test_debug_enabled_logs_full_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_debug_response")
        logger.setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_llm_response(logger, "response msg", {"choices": [{"content": "answer"}]})
            assert "answer" in caplog.text

    def test_debug_disabled_logs_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_no_debug_response")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO, logger=logger.name):
            log_llm_response(logger, "response msg", {"choices": [{}]})
            assert "debug disabled" in caplog.text


class TestLogLlmError:
    def test_debug_enabled_logs_raw_error(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_debug_error")
        logger.setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_llm_error(logger, "error msg", ValueError("raw error body"))
            assert "raw error body" in caplog.text

    def test_debug_disabled_logs_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_no_debug_error")
        logger.setLevel(logging.INFO)

        with caplog.at_level(logging.INFO, logger=logger.name):
            log_llm_error(logger, "error msg", ValueError("raw error body"))
            assert "debug disabled" in caplog.text
            assert "ValueError" in caplog.text
            assert "raw error body" not in caplog.text


# ---------------------------------------------------------------------------
# llm_sdk_debug_logging
# ---------------------------------------------------------------------------


class TestLlmSdkDebugLogging:
    def test_disabled_yields_false_and_does_not_change_levels(self) -> None:
        config = {"llm_config": {"enable_debug_logging": False}}
        openai_logger = logging.getLogger("openai")
        httpx_logger = logging.getLogger("httpx")

        original_openai = openai_logger.level
        original_httpx = httpx_logger.level

        with llm_sdk_debug_logging(config) as is_debug:
            assert is_debug is False

        # Levels must be restored (unchanged)
        assert openai_logger.level == original_openai
        assert httpx_logger.level == original_httpx

    def test_enabled_yields_true_and_sets_debug(self) -> None:
        config = {"llm_config": {"enable_debug_logging": True}}
        openai_logger = logging.getLogger("openai")
        httpx_logger = logging.getLogger("httpx")

        original_openai = openai_logger.level
        original_httpx = httpx_logger.level

        with llm_sdk_debug_logging(config) as is_debug:
            assert is_debug is True
            assert openai_logger.level == logging.DEBUG
            assert httpx_logger.level == logging.DEBUG

        # Restored after exit
        assert openai_logger.level == original_openai
        assert httpx_logger.level == original_httpx

    def test_restores_levels_even_after_exception(self) -> None:
        config = {"llm_config": {"enable_debug_logging": True}}
        openai_logger = logging.getLogger("openai")
        httpx_logger = logging.getLogger("httpx")

        original_level = openai_logger.level

        with pytest.raises(RuntimeError):
            with llm_sdk_debug_logging(config):
                openai_logger.setLevel(logging.DEBUG)
                raise RuntimeError("boom")

        # Level restored despite exception
        assert openai_logger.level == original_level

    def test_none_config_yields_false_by_default(self) -> None:
        with llm_sdk_debug_logging(None) as is_debug:
            assert is_debug is False

    def test_missing_key_yields_false_by_default(self) -> None:
        config = {"llm_config": {}}
        with llm_sdk_debug_logging(config) as is_debug:
            assert is_debug is False

    def test_flat_enable_debug_logging_true(self) -> None:
        config = {"enable_debug_logging": True}
        with llm_sdk_debug_logging(config) as is_debug:
            assert is_debug is True

    def test_default_parameter_respected(self) -> None:
        with llm_sdk_debug_logging(None, default=True) as is_debug:
            assert is_debug is True
