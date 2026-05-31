"""
Tests for crypto_news_analyzer.storage.postgres_connection.

Uses unittest.mock.patch to fake psycopg.connect behavior.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeConfig:
    """Minimal config with postgres_connect_* fields."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.01,
        max_delay: float = 0.1,
        timeout: int = 10,
    ):
        self.postgres_connect_max_attempts = max_attempts
        self.postgres_connect_initial_delay_seconds = initial_delay
        self.postgres_connect_max_delay_seconds = max_delay
        self.postgres_connect_timeout_seconds = timeout


class _FakePsycopgOperationalError(Exception):
    """Stand-in for psycopg.OperationalError in tests."""
    pass


def _make_fake_psycopg(
    side_effect=None,
    return_value=None,
):
    """Create a fake psycopg module with a configurable connect() behaviour."""

    class _FakePsycopgModule:
        OperationalError = _FakePsycopgOperationalError

    fake = _FakePsycopgModule()

    if side_effect is not None:
        connect_mock = MagicMock(side_effect=side_effect)
    elif return_value is not None:
        connect_mock = MagicMock(return_value=return_value)
    else:
        connect_mock = MagicMock()

    fake.connect = connect_mock  # type: ignore[attr-defined]
    return fake, connect_mock


def _make_fake_connection():
    """Create a fake psycopg connection object."""
    conn = MagicMock()
    conn.execute = MagicMock()
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    conn.close = MagicMock()
    return conn


MODULE_PATH = "crypto_news_analyzer.storage.postgres_connection"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConnectPostgresWithRetry:
    """Tests for connect_postgres_with_retry."""

    def test_connect_postgres_with_retry_succeeds_after_transient_failures(self):
        """Connect fails twice with OperationalError, then succeeds on 3rd attempt."""
        fake_conn = _make_fake_connection()
        fake_psycopg, connect_mock = _make_fake_psycopg(
            side_effect=[
                _FakePsycopgOperationalError("connection refused"),
                _FakePsycopgOperationalError("connection refused"),
                fake_conn,
            ]
        )

        config = _FakeConfig(max_attempts=3, initial_delay=0.001, max_delay=0.01)

        with patch(f"{MODULE_PATH}.psycopg", fake_psycopg):
            with patch(f"{MODULE_PATH}.dict_row", MagicMock()):
                from crypto_news_analyzer.storage.postgres_connection import (
                    connect_postgres_with_retry,
                )

                with connect_postgres_with_retry(
                    "postgresql://test", config=config, logger=logging.getLogger(__name__)
                ) as conn:
                    assert conn is fake_conn

        assert connect_mock.call_count == 3

    def test_connect_postgres_with_retry_stops_on_permanent_failure(self):
        max_attempts = 3
        fake_psycopg, connect_mock = _make_fake_psycopg(
            side_effect=_FakePsycopgOperationalError("permanent failure")
        )

        config = _FakeConfig(max_attempts=max_attempts, initial_delay=0.001, max_delay=0.01)

        with patch(f"{MODULE_PATH}.psycopg", fake_psycopg):
            with patch(f"{MODULE_PATH}.dict_row", MagicMock()):
                from crypto_news_analyzer.storage.postgres_connection import (
                    connect_postgres_with_retry,
                )

                with pytest.raises(_FakePsycopgOperationalError, match="permanent failure"):
                    with connect_postgres_with_retry(
                        "postgresql://test", config=config, logger=logging.getLogger(__name__)
                    ):
                        pass  # pragma: no cover

        assert connect_mock.call_count == max_attempts

    def test_connect_timeout_passed_to_psycopg(self):
        """Verify connect_timeout kwarg is passed to psycopg.connect()."""
        fake_conn = _make_fake_connection()
        fake_psycopg, connect_mock = _make_fake_psycopg(return_value=fake_conn)

        config = _FakeConfig(timeout=42, max_attempts=1)

        with patch(f"{MODULE_PATH}.psycopg", fake_psycopg):
            with patch(f"{MODULE_PATH}.dict_row", MagicMock()):
                from crypto_news_analyzer.storage.postgres_connection import (
                    connect_postgres_with_retry,
                )

                with connect_postgres_with_retry(
                    "postgresql://test", config=config, logger=logging.getLogger(__name__)
                ):
                    pass

        connect_mock.assert_called_once()
        call_kwargs = connect_mock.call_args.kwargs
        assert call_kwargs["connect_timeout"] == 42


class TestCheckPostgresReady:
    """Tests for check_postgres_ready."""

    def test_check_postgres_ready_executes_select_one(self):
        """Connect succeeds, SELECT 1 is executed via cursor. Assert returns True."""
        fake_conn = _make_fake_connection()
        fake_psycopg, connect_mock = _make_fake_psycopg(return_value=fake_conn)

        config = _FakeConfig(max_attempts=1)

        with patch(f"{MODULE_PATH}.psycopg", fake_psycopg):
            with patch(f"{MODULE_PATH}.dict_row", MagicMock()):
                from crypto_news_analyzer.storage.postgres_connection import (
                    check_postgres_ready,
                )

                result = check_postgres_ready("postgresql://test", config)

        assert result is True
        fake_conn.execute.assert_called_once_with("SELECT 1")

    def test_check_postgres_ready_returns_false_on_failure(self):
        """Connect always fails. Assert returns False (no exception raised)."""
        fake_psycopg, _connect_mock = _make_fake_psycopg(
            side_effect=_FakePsycopgOperationalError("connection refused")
        )

        config = _FakeConfig(max_attempts=2, initial_delay=0.001, max_delay=0.01)

        with patch(f"{MODULE_PATH}.psycopg", fake_psycopg):
            with patch(f"{MODULE_PATH}.dict_row", MagicMock()):
                from crypto_news_analyzer.storage.postgres_connection import (
                    check_postgres_ready,
                )

                # Must NOT raise
                result = check_postgres_ready("postgresql://test", config)

        assert result is False

    def test_check_postgres_ready_returns_false_when_psycopg_unavailable(self):
        """psycopg is None. Assert returns False (no exception raised)."""
        config = _FakeConfig(max_attempts=1)

        with patch(f"{MODULE_PATH}.psycopg", None):
            with patch(f"{MODULE_PATH}.dict_row", None):
                from crypto_news_analyzer.storage.postgres_connection import (
                    check_postgres_ready,
                )

                result = check_postgres_ready("postgresql://test", config)

        assert result is False
