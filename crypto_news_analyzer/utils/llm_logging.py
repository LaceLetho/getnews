"""
LLM debug logging helpers.

Provides gated logging for LLM request/response/error payloads. When debug
logging is disabled only a safe summary is emitted; when enabled the full
payloads are logged. Also includes a context manager to temporarily raise
openai and httpx logger levels to DEBUG.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Optional

__all__ = [
    "is_llm_debug_logging_enabled",
    "log_llm_request",
    "log_llm_response",
    "log_llm_error",
    "llm_sdk_debug_logging",
]


def is_llm_debug_logging_enabled(config: Optional[dict[str, Any]], default: bool = False) -> bool:
    """
    Read ``llm_config.enable_debug_logging`` from a dict-like config.

    Supports two layouts:
      - nested: ``{"llm_config": {"enable_debug_logging": True}}``
      - flat:  ``{"enable_debug_logging": True}``

    Args:
        config: Configuration dict, may be None.
        default: Value to return when config is None or the key is absent.

    Returns:
        True when debug logging is explicitly enabled, False otherwise.
    """
    if config is None:
        return default

    # Try nested form first, then fall back to flat.
    llm_cfg: Optional[dict[str, Any]] = config.get("llm_config")
    if llm_cfg is not None:
        val = llm_cfg.get("enable_debug_logging")
        if isinstance(val, bool):
            return val

    # Direct key.
    val = config.get("enable_debug_logging")
    if isinstance(val, bool):
        return val

    return default


# ---------------------------------------------------------------------------
# Payload stringification helpers (safe summaries – no credentials)
# ---------------------------------------------------------------------------


def _is_binary_bytes(data: bytes) -> bool:
    """Return True when bytes likely contain non-text binary data."""
    # If decoded losslessly as UTF-8, it is text; otherwise binary.
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def _str_payload(payload: Any) -> str:
    """
    Render ``payload`` to a string, handling raw HTTP bodies, byte strings,
    and structured objects.
    """
    if isinstance(payload, bytes):
        if _is_binary_bytes(payload):
            return "<binary payload>"
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, bytearray):
        if _is_binary_bytes(bytes(payload)):
            return "<binary payload>"
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload
    # Dumped as JSON for readability rather than repr().
    try:
        import json

        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        return repr(payload)


def _safe_summary_for_auth() -> str:
    """Placeholder returned instead of any auth credential."""
    return "<auth suppressed>"


def _safe_summary_for_client() -> str:
    """Placeholder returned instead of a client object."""
    return "<client object suppressed>"


def _summarize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of ``data`` with known credential keys replaced.

    Replacements:
      - ``headers``           -> ``_safe_summary_for_headers()``
      - ``Authorization``     -> ``_safe_summary_for_auth()``
      - ``Proxy-Authorization``-> ``_safe_summary_for_auth()``
      - ``WWW-Authenticate``  -> ``_safe_summary_for_auth()``
      - ``api_key`` / ``apiKey`` / ``api_key `` -> ``_safe_summary_for_auth()``
      - ``password``, ``secret``, ``token`` (case-insensitive) -> ``_safe_summary_for_auth()``
      - ``client``            -> ``_safe_summary_for_client()``
      - ``_client``            -> ``_safe_summary_for_client()``
      - ``http_client``       -> ``_safe_summary_for_client()``
      - ``sync_client`` / ``async_client`` -> ``_safe_summary_for_client()``
    """
    SENSITIVE_KEYS = frozenset(
        [
            "headers",
            "authorization",
            "proxy-authorization",
            "www-authenticate",
            "x-api-key",
            "api_key",
            "apikey",
            "api_key ",
            "password",
            "secret",
            "token",
            "client",
            "_client",
            "http_client",
            "sync_client",
            "async_client",
        ]
    )
    AUTH_KEYS = frozenset(
        [
            "x-api-key",
            "authorization",
            "proxy-authorization",
            "www-authenticate",
            "api_key",
            "apikey",
            "api_key ",
            "password",
            "secret",
            "token",
        ]
    )
    result: dict[str, Any] = {}
    for key, val in data.items():
        key_lower = key.lower()
        if key_lower == "headers" and isinstance(val, dict):
            result[key] = _summarize_dict(val)
        elif key_lower in SENSITIVE_KEYS:
            if key_lower in AUTH_KEYS:
                result[key] = _safe_summary_for_auth()
            else:
                result[key] = _safe_summary_for_client()
        elif isinstance(val, dict):
            result[key] = _summarize_dict(val)
        elif isinstance(val, list):
            result[key] = [
                _summarize_dict(item) if isinstance(item, dict) else item for item in val
            ]
        else:
            result[key] = val
    return result


def stringify_request_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        cleaned = _summarize_dict(payload)
        return _str_payload(cleaned)
    if isinstance(payload, list):
        return _str_payload(
            [_summarize_dict(item) if isinstance(item, dict) else item for item in payload]
        )
    return _str_payload(payload)


def stringify_response_payload(payload: Any) -> str:
    """
    Safe stringification of an LLM response payload.

    Works the same as ``stringify_request_payload`` — applied to both request
    and response sides for consistency.

    Args:
        payload: Raw response data.

    Returns:
        Human-readable string representation of the payload.
    """
    return stringify_request_payload(payload)


def stringify_error_payload(error: Any) -> str:
    """
    Render a raw error so it is readable without inspecting internal attributes.

    Special handling:
      - ``requests.Response`` objects: extracts ``.text`` or ``.content``
        and returns it directly so the caller sees the actual server error body.
      - ``httpx.Response`` objects: extracts ``.text``.
      - ``openai.APIResponse`` objects: extracts ``.text`` or ``.content``.
      - Other exceptions / unknown types: falls back to ``str()`` or ``repr()``.

    Args:
        error: Any exception or error object.

    Returns:
        Readable error description or body.
    """
    # ── requests.Response ────────────────────────────────────────────────
    try:
        import requests

        if isinstance(error, requests.Response):
            text = error.text
            if text:
                return text
            content = error.content
            if content:
                return content.decode("utf-8", errors="replace")
            return f"<HTTP {error.status_code} empty response>"
    except ImportError:
        pass

    # ── httpx.Response ───────────────────────────────────────────────────
    try:
        import httpx

        if isinstance(error, httpx.Response):
            text = error.text
            if text:
                return text
            return f"<HTTP {error.status_code} empty response>"
    except ImportError:
        pass

    # ── openai API responses ─────────────────────────────────────────────
    try:
        import openai  # noqa: F401

        if hasattr(error, "text") and error.text:
            return error.text
        if hasattr(error, "content") and error.content:
            content = error.content
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)
    except ImportError:
        pass

    # ── fallback ───────────────────────────────────────────────────────────
    if isinstance(error, (str, bytes, bytearray)):
        return _str_payload(error)

    # Generic exception – use str() then repr().
    s = str(error)
    if s and s != f"<{type(error).__name__} object>":
        return s
    return repr(error)


# ---------------------------------------------------------------------------
# Logger helpers
# ---------------------------------------------------------------------------


def _get_llm_logger() -> logging.Logger:
    """Return (or create) the ``crypto_news_analyzer.llm`` logger."""
    return logging.getLogger("crypto_news_analyzer.llm")


def log_llm_request(
    logger: logging.Logger,
    message: str,
    payload: Any,
    enabled: Optional[bool] = None,
) -> None:
    """
    Log an LLM request, respecting the debug flag.

    When debug is enabled the full payload is emitted; otherwise a safe
    summary that strips credentials is logged.

    Args:
        logger: Logger instance to write to.
        message: Descriptive message (e.g. "LLM request payload").
        payload: Request payload of any type.
    """
    should_log_full = logger.isEnabledFor(logging.DEBUG) if enabled is None else enabled
    if should_log_full:
        logger.info("%s\n%s", message, stringify_request_payload(payload))
    else:
        logger.info("%s [%s]", message, "debug disabled – use DEBUG level for full payload")


def log_llm_response(
    logger: logging.Logger,
    message: str,
    payload: Any,
    enabled: Optional[bool] = None,
) -> None:
    """
    Log an LLM response, respecting the debug flag.

    Args:
        logger: Logger instance to write to.
        message: Descriptive message (e.g. "LLM response payload").
        payload: Response payload of any type.
    """
    should_log_full = logger.isEnabledFor(logging.DEBUG) if enabled is None else enabled
    if should_log_full:
        logger.info("%s\n%s", message, stringify_response_payload(payload))
    else:
        logger.info("%s [%s]", message, "debug disabled – use DEBUG level for full payload")


def log_llm_error(
    logger: logging.Logger,
    message: str,
    error: Any,
    enabled: Optional[bool] = None,
) -> None:
    """
    Log an LLM error, respecting the debug flag.

    When debug is enabled the raw error content is extracted and logged;
    otherwise a brief summary is emitted.

    Args:
        logger: Logger instance to write to.
        message: Descriptive message (e.g. "LLM error").
        error: Exception or error object.
    """
    should_log_full = logger.isEnabledFor(logging.DEBUG) if enabled is None else enabled
    if should_log_full:
        logger.error("%s\n%s", message, stringify_error_payload(error))
    else:
        logger.info(
            "%s: %s [%s]",
            message,
            type(error).__name__,
            "debug disabled – use DEBUG level for full error",
        )


# ---------------------------------------------------------------------------
# Context manager for SDK-level debug logging
# ---------------------------------------------------------------------------


@contextmanager
def llm_sdk_debug_logging(config: Optional[dict[str, Any]], default: bool = False):
    """
    Context manager that temporarily raises ``openai`` and ``httpx`` logger
    levels to DEBUG when ``llm_config.enable_debug_logging`` is true.

    Original levels are restored on exit, even if an exception is raised
    inside the ``with`` block.

    Args:
        config: Configuration dict (same format as ``is_llm_debug_logging_enabled``).
        default: Default value when config is None or key is absent.

    Yields:
        bool – the effective debug-enabled state.

    Example::

        with llm_sdk_debug_logging(config) as is_debug:
            if is_debug:
                # SDKs will now emit verbose debug output
                ...
    """
    if not is_llm_debug_logging_enabled(config, default):
        yield False
        return

    # Map of logger name -> original level
    _SDK_LOGGERS = ["openai", "httpx"]
    original_levels: dict[str, int] = {}

    for name in _SDK_LOGGERS:
        lgr = logging.getLogger(name)
        original_levels[name] = lgr.level
        lgr.setLevel(logging.DEBUG)
        # Propagate DEBUG messages up to our crypto_news_analyzer.llm logger
        lgr.propagate = False

    try:
        yield True
    finally:
        for name, original_level in original_levels.items():
            logging.getLogger(name).setLevel(original_level)
