import io
import logging

from crypto_news_analyzer.utils.logging import setup_logging


def test_setup_logging_redacts_telegram_bot_urls_and_tokens(tmp_path):
    setup_logging(log_level="INFO", log_dir=str(tmp_path))

    root_logger = logging.getLogger()
    capture_stream = io.StringIO()
    capture_handler = logging.StreamHandler(capture_stream)
    capture_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(capture_handler)

    try:
        logger = logging.getLogger("telegram.http")
        logger.info(
            'HTTP Request: POST https://api.telegram.org/bot123:ABC/sendMessage "HTTP/1.1 200 OK"'
        )
        logger.info("Standalone bot token 123:ABC")

        output = capture_stream.getvalue()
        assert "https://api.telegram.org/bot123:ABC" not in output
        assert "123:ABC" not in output
        assert "https://api.telegram.org/bot[REDACTED]/sendMessage" in output
        assert "Standalone bot token [REDACTED]" in output
    finally:
        root_logger.removeHandler(capture_handler)
