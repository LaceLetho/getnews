from datetime import datetime, timezone
from types import SimpleNamespace

from crypto_news_analyzer.models import ContentItem
from crypto_news_analyzer.semantic_search.embedding_service import EmbeddingService


class _EmbeddingsAPI:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, *, model, input):
        self.calls.append({"model": model, "input": input})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _embedding_response(values):
    return SimpleNamespace(data=[SimpleNamespace(embedding=values)])


def _build_service(api):
    service = EmbeddingService(api_key="test-key", dimensions=3)
    service.client = SimpleNamespace(embeddings=api)
    return service


def _build_item(item_id: str, content: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        title=f"Title {item_id}",
        content=content,
        url=f"https://example.com/{item_id}",
        publish_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_name="CoinDesk",
        source_type="rss",
    )


def test_generate_embedding_retries_with_truncated_text_on_length_limit():
    api = _EmbeddingsAPI(
        [
            Exception(
                "Error code: 400 - Invalid input: maximum input length is 8192 tokens"
            ),
            _embedding_response([0.1, 0.2, 0.3]),
        ]
    )
    service = _build_service(api)

    text = "x" * 20000
    result = service.generate_embedding(text)

    assert result == [0.1, 0.2, 0.3]
    assert len(api.calls) == 2
    assert len(api.calls[0]["input"]) == 20000
    assert len(api.calls[1]["input"]) == 12000


def test_generate_for_content_items_falls_back_to_per_item_when_batch_hits_length_limit():
    api = _EmbeddingsAPI(
        [
            Exception(
                "Error code: 400 - {'error': {'message': \"Invalid 'input[1]': maximum input length is 8192 tokens.\"}}"
            ),
            _embedding_response([0.1, 0.2, 0.3]),
            Exception(
                "Error code: 400 - Invalid input: maximum input length is 8192 tokens"
            ),
            _embedding_response([0.4, 0.5, 0.6]),
        ]
    )
    service = _build_service(api)

    items = [
        _build_item("short", "short body"),
        _build_item("long", "x" * 20000),
    ]

    result = service.generate_for_content_items(items)

    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert isinstance(api.calls[0]["input"], list)
    assert len(api.calls[0]["input"]) == 2
    assert isinstance(api.calls[1]["input"], str)
    assert isinstance(api.calls[2]["input"], str)
    assert len(api.calls[3]["input"]) == 12000
