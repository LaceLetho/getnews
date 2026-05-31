"""
Shared PostgreSQL connection and readiness retry helper.

Provides bounded exponential-backoff retry around ``psycopg.connect()``
and a lightweight readiness probe that executes ``SELECT 1``.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _calculate_delay(attempt: int, initial_delay: float, max_delay: float) -> float:
    """Calculate exponential backoff delay for a given attempt (1-based)."""
    delay = initial_delay * (2 ** (attempt - 1))
    return float(min(delay, max_delay))


@contextmanager
def connect_postgres_with_retry(
    database_url: str,
    *,
    row_factory: Optional[Any] = None,
    config: Any,
    logger: Optional[logging.Logger] = None,
) -> Generator[Any, None, None]:
    """Connect to PostgreSQL with bounded exponential backoff retry.

    Retries ``psycopg.connect()`` up to ``config.postgres_connect_max_attempts``
    times. Between attempts, sleeps for an exponentially increasing delay
    capped at ``config.postgres_connect_max_delay_seconds``.

    Args:
        database_url: PostgreSQL connection string.
        row_factory: psycopg row factory (defaults to ``dict_row``).
        config: StorageConfig (or compatible) with ``postgres_connect_*`` fields.
        logger: Optional logger for retry messages.

    Yields:
        The established psycopg connection.

    Raises:
        ImportError: If psycopg is not installed.
        psycopg.OperationalError: If all retry attempts are exhausted.
    """
    if psycopg is None:
        raise ImportError(
            "psycopg is required for PostgreSQL connections. "
            "Install it with: pip install psycopg[binary]"
        )

    log = logger or logging.getLogger(__name__)
    max_attempts = config.postgres_connect_max_attempts
    initial_delay = config.postgres_connect_initial_delay_seconds
    max_delay = config.postgres_connect_max_delay_seconds
    connect_timeout = config.postgres_connect_timeout_seconds

    if row_factory is None:
        row_factory = dict_row

    last_exception: Optional[BaseException] = None
    conn = None

    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg.connect(
                database_url,
                row_factory=row_factory,
                connect_timeout=connect_timeout,
            )
            log.info(
                "PostgreSQL connection established on attempt %d/%d",
                attempt,
                max_attempts,
            )
            break  # Connected successfully
        except Exception as exc:
            last_exception = exc
            if attempt < max_attempts:
                delay = _calculate_delay(attempt, initial_delay, max_delay)
                log.warning(
                    "PostgreSQL connection attempt %d/%d failed (%s), "
                    "retrying in %.1fs",
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
            else:
                log.error(
                    "PostgreSQL connection failed after %d attempts",
                    max_attempts,
                )

    if conn is None:
        assert last_exception is not None
        raise last_exception

    # Connected successfully — yield the connection (NO retry on yielded block exceptions)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_postgres_ready(database_url: str, config: Any) -> bool:
    """Check if PostgreSQL is reachable and ready to accept connections.

    Calls ``connect_postgres_with_retry`` internally, then executes
    ``SELECT 1`` to verify the connection is functional.

    Args:
        database_url: PostgreSQL connection string.
        config: StorageConfig (or compatible) with ``postgres_connect_*`` fields.

    Returns:
        ``True`` if the connection succeeds and ``SELECT 1`` executes,
        ``False`` on any failure. Never raises exceptions.
    """
    try:
        with connect_postgres_with_retry(
            database_url, config=config, logger=logger
        ) as conn:
            conn.execute("SELECT 1")
            return True
    except Exception:
        return False
