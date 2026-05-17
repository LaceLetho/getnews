from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from crypto_news_analyzer.crawlers import get_data_source_factory
from crypto_news_analyzer.crawlers.v2ex_intelligence_crawler import V2EXIntelligenceCrawler  # pyright: ignore[reportMissingImports]
from crypto_news_analyzer.domain.models import IntelligenceCrawlCheckpoint


def _response(payload, headers=None):
    response = Mock()
    response.json.return_value = payload
    response.headers = headers or {}
    response.raise_for_status.return_value = None
    return response


class TestV2EXIntelligenceCrawler:
    @pytest.fixture
    def crawler(self):
        return V2EXIntelligenceCrawler(time_window_hours=12)

    @pytest.fixture
    def recent_topic_time(self):
        return datetime.utcnow() - timedelta(hours=1)

    @pytest.fixture
    def old_topic_time(self):
        return datetime.utcnow() - timedelta(days=2)

    @patch("crypto_news_analyzer.crawlers.v2ex_intelligence_crawler.requests.Session.get")
    def test_v1_crawl_uses_api_urls_reads_rate_limits_and_saves_checkpoint(
        self,
        mock_get,
        crawler,
        recent_topic_time,
        old_topic_time,
    ):
        repo = Mock()
        repo.get_checkpoint.return_value = None

        topic_payload = [
            {
                "id": 101,
                "title": "Recent topic",
                "content": "<p>topic raw body</p>",
                "created": recent_topic_time.isoformat(),
            },
            {
                "id": 102,
                "title": "Old topic",
                "content": "<p>old raw body</p>",
                "created": old_topic_time.isoformat(),
            },
        ]
        reply_payload = [
            {
                "id": 201,
                "content": "<p>reply raw body</p>",
                "created": recent_topic_time.isoformat(),
            }
        ]

        def fake_get(url, params=None, headers=None, timeout=None):
            if url.endswith("/topics/show.json"):
                return _response(
                    topic_payload,
                    {
                        "X-Rate-Limit-Remaining": "0",
                        "X-Rate-Limit-Reset": str(int(datetime.utcnow().timestamp()) + 60),
                    },
                )
            if url.endswith("/replies/show.json"):
                return _response(reply_payload, {"X-Rate-Limit-Remaining": "1"})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = fake_get

        items = crawler.crawl(
            {
                "name": "V2EX Crypto",
                "api_version": "v1",
                "node_allowlist": ["crypto"],
                "intelligence_repository": repo,
            }
        )

        assert all("/api/" in call.args[0] for call in mock_get.call_args_list)
        assert all("/t/" not in call.args[0] for call in mock_get.call_args_list)
        assert len(items) == 1
        assert items[0].raw_text == "<p>topic raw body</p>"
        assert crawler.last_rate_limit_remaining == 0
        assert repo.save_checkpoint.called

        checkpoint = repo.save_checkpoint.call_args.args[0]
        assert checkpoint.source_type == "v2ex"
        assert checkpoint.source_id == "crypto"
        assert checkpoint.checkpoint_data["api_version"] == "v1"
        assert checkpoint.status == "rate_limited"
        assert checkpoint.checkpoint_data["rate_limit_remaining"] == 0

    @patch("crypto_news_analyzer.crawlers.v2ex_intelligence_crawler.requests.Session.get")
    def test_v2_crawl_reads_pat_from_env_and_uses_checkpoint_cutoff(
        self,
        mock_get,
        crawler,
        recent_topic_time,
        old_topic_time,
        monkeypatch,
    ):
        monkeypatch.setenv("V2EX_PAT", "pat-123")

        repo = Mock()
        repo.get_checkpoint.return_value = IntelligenceCrawlCheckpoint.create(
            source_type="v2ex",
            source_id="crypto",
            last_crawled_at=datetime.utcnow() - timedelta(hours=2),
            last_external_id="999",
        )

        topic_payload = [
            {
                "id": 302,
                "title": "Fresh topic",
                "content": "fresh topic body",
                "created": recent_topic_time.isoformat(),
            },
            {
                "id": 301,
                "title": "Too old",
                "content": "old topic body",
                "created": old_topic_time.isoformat(),
            },
        ]
        reply_payload = [
            {
                "id": 401,
                "content": "reply body exact",
                "created": recent_topic_time.isoformat(),
            }
        ]

        def fake_get(url, params=None, headers=None, timeout=None):
            if url.endswith("/nodes/crypto/topics"):
                assert headers == {"Authorization": "Bearer pat-123"}
                assert params == {"p": 1}
                return _response(
                    topic_payload,
                    {"X-Rate-Limit-Remaining": "2", "X-Rate-Limit-Reset": "0"},
                )
            if url.endswith("/topics/302/replies"):
                assert headers == {"Authorization": "Bearer pat-123"}
                assert params == {"p": 1}
                return _response(reply_payload, {"X-Rate-Limit-Remaining": "2"})
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = fake_get

        items = crawler.crawl(
            {
                "name": "V2EX Crypto",
                "api_version": "v2",
                "node_allowlist": ["crypto"],
                "pat_env_var_name": "V2EX_PAT",
                "intelligence_repository": repo,
            }
        )

        assert all("/api/v2/" in call.args[0] for call in mock_get.call_args_list)
        assert len(items) == 2
        assert items[0].external_id == "302"
        assert items[0].raw_text == "fresh topic body"
        assert items[1].raw_text == "reply body exact"
        checkpoint = repo.save_checkpoint.call_args.args[0]
        assert checkpoint.checkpoint_data["api_version"] == "v2"
        assert checkpoint.checkpoint_data["node_name"] == "crypto"
        assert checkpoint.checkpoint_data["rate_limit_remaining"] == 2
        assert "pat-123" not in str(checkpoint.checkpoint_data)


def test_v2ex_factory_registers_source_type():
    factory = get_data_source_factory()
    assert "v2ex" in factory.get_available_source_types()
