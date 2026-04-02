from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer.models import ContentItem


def test_analyze_by_time_window_respects_requested_window(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        """
{
  "execution_interval": 10,
  "time_window_hours": 1,
  "storage": {"database_path": ":memory:", "retention_days": 30, "max_storage_mb": 1000, "cleanup_frequency": "daily"},
  "llm_config": {"min_weight_score": 50},
  "rss_sources": [],
  "x_sources": [],
  "rest_api_sources": []
}
""".strip(),
        encoding="utf-8",
    )

    controller = MainController(str(config_file))
    controller._initialized = True

    now = datetime.now(timezone.utc)
    content_items = [
        ContentItem(
            id="item_1",
            title="title_1",
            content="content_1",
            url="https://example.com/1",
            publish_time=now - timedelta(hours=17),
            source_name="test",
            source_type="rss",
        ),
        ContentItem(
            id="item_2",
            title="title_2",
            content="content_2",
            url="https://example.com/2",
            publish_time=now - timedelta(hours=2),
            source_name="test",
            source_type="rss",
        ),
    ]

    controller.config_manager = Mock()
    controller.config_manager.get_time_window_hours.return_value = 1
    controller.config_manager.config_data = {"llm_config": {"min_weight_score": 50}}

    controller.content_repository = Mock()
    controller.content_repository.get_content_items_since.return_value = content_items
    controller.analysis_repository = Mock()
    controller.analysis_repository.get_last_successful_analysis.return_value = None

    controller.llm_analyzer = Mock()
    controller.llm_analyzer.analyze_content_batch.return_value = [
        StructuredAnalysisResult(
            time="Thu, 26 Mar 2026 04:00:00 +0000",
            category="Whale",
            weight_score=80,
            title="标题1",
            body="正文1",
            source="https://example.com/1",
            related_sources=[],
        ),
        StructuredAnalysisResult(
            time="Thu, 26 Mar 2026 04:00:00 +0000",
            category="Whale",
            weight_score=81,
            title="标题2",
            body="正文2",
            source="https://example.com/2",
            related_sources=[],
        ),
    ]

    controller.report_generator = Mock()
    controller.report_generator.generate_telegram_report.return_value = "report"

    result = controller.analyze_by_time_window(chat_id="chat_1", time_window_hours=18)

    assert result["success"] is True
    assert result["items_processed"] == 2

    assert controller.content_repository.get_content_items_since.call_args.kwargs["max_hours"] == 18

    analyzed_input = controller.llm_analyzer.analyze_content_batch.call_args.args[0]
    assert analyzed_input == content_items
