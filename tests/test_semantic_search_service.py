from datetime import datetime, timedelta, timezone
from typing import Any, cast

from crypto_news_analyzer.config.llm_registry import LLMConfig, ModelConfig
from crypto_news_analyzer.models import ContentItem, SemanticSearchConfig
from crypto_news_analyzer.semantic_search.service import SemanticSearchService


class _StubEmbeddingService:
    def __init__(self):
        self.enabled = True
        self.calls: list[str] = []

    def generate_embedding(self, text: str):
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class _StubContentRepository:
    def __init__(self, results_by_call):
        self.results_by_call = list(results_by_call)
        self.calls = []

    def semantic_search_by_similarity(self, query_embedding, since_time, max_hours, limit):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "since_time": since_time,
                "max_hours": max_hours,
                "limit": limit,
            }
        )
        return self.results_by_call.pop(0) if self.results_by_call else []


def test_query_planner_caps_unique_subqueries_and_keeps_original_query(monkeypatch):
    service = _build_service(repository=_StubContentRepository([[]]))
    responses = iter(
        [
            '{"normalized_intent":"比特币ETF资金流与机构需求","subqueries":["ETF inflows","BTC ETF demand","ETF inflows","macro spillover"]}'
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    normalized_intent, subqueries = service._plan_subqueries("btc etf flows")

    assert normalized_intent == "比特币ETF资金流与机构需求"
    assert subqueries == [
        "btc etf flows",
        "ETF inflows",
        "BTC ETF demand",
        "macro spillover",
    ]


def test_global_retained_set_is_capped_to_200_unique_items(monkeypatch):
    first_batch = [(_build_item(f"item-{index}", minutes=index), 0.9) for index in range(180)]
    second_batch = [
        (_build_item(f"item-{index}", minutes=500 - index), 0.8) for index in range(120, 260)
    ]
    repository = _StubContentRepository([first_batch, second_batch])
    service = _build_service(
        repository=repository,
        semantic_search_config=SemanticSearchConfig(synthesis_batch_size=200),
    )
    responses = iter(
        [
            '{"normalized_intent":"ETF资金流","subqueries":["btc etf flows","institutional demand"]}',
            "## 关键信号\n\n### 信号 1\n批次里出现了一个具体入口。\n来源：[CoinDesk](https://example.com/item-1)",
            "## 关键信号\n\n### 信号 1\n最终保留了一个具体 alpha 信号。\n来源：[CoinDesk](https://example.com/item-2)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="btc etf flows", time_window_hours=24)

    assert result["success"] is True
    assert result["matched_count"] == 260
    assert result["retained_count"] == 200
    assert len(repository.calls) == 2
    assert all(call["limit"] == 50 for call in repository.calls)
    assert result["report_content"].startswith("# 主题检索报告")
    assert "- 匹配条数: 260" in result["report_content"]
    assert "- 保留条数: 200" in result["report_content"]
    assert "## 关键信号" in result["report_content"]
    assert "## 核心结论" not in result["report_content"]
    assert "来源：[CoinDesk](https://example.com/item-2)" in result["report_content"]


def test_no_match_returns_compact_non_error_report_shape(monkeypatch):
    service = _build_service(repository=_StubContentRepository([[]]))
    responses = iter(['{"normalized_intent":"SOL生态空投","subqueries":["sol airdrop"]}'])
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="sol airdrop", time_window_hours=12)

    assert result == {
        "success": True,
        "report_content": "# 主题检索报告\n\n- 归一化意图: SOL生态空投\n- 原始查询: sol airdrop\n- 时间窗口: 12 小时\n- 匹配条数: 0\n- 保留条数: 0\n\n## 关键信号\n现有材料未显示出足够具体的渠道/入口/活动/产品级信号。",
        "normalized_intent": "SOL生态空投",
        "matched_count": 0,
        "retained_count": 0,
        "subqueries": ["sol airdrop"],
    }


def test_report_builder_uses_signal_only_sections():
    builder = _build_service(repository=_StubContentRepository([[]])).report_builder
    report = builder.build_no_match(
        normalized_intent="ETF资金流",
        original_query="btc etf flows",
        time_window_hours=24,
    )

    assert report.startswith("# 主题检索报告")
    assert "## 关键信号" in report
    assert "## 核心结论" not in report
    assert "## 来源" not in report


def _build_service(
    repository: _StubContentRepository,
    semantic_search_config: SemanticSearchConfig | None = None,
) -> SemanticSearchService:
    return SemanticSearchService(
        content_repository=cast(Any, repository),
        embedding_service=cast(Any, _StubEmbeddingService()),
        semantic_search_config=semantic_search_config or SemanticSearchConfig(),
        llm_config=_build_llm_config(),
        client=object(),
    )


def _build_llm_config() -> LLMConfig:
    model = ModelConfig(provider="kimi", name="kimi-k2.5", options={})
    return LLMConfig(
        model=model,
        fallback_models=[ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={})],
        market_model=ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={}),
        temperature=0.1,
        max_tokens=2000,
        batch_size=100,
    )


def _build_item(item_id: str, minutes: int) -> ContentItem:
    return ContentItem(
        id=item_id,
        title=f"Title {item_id}",
        content=f"Body {item_id}",
        url=f"https://example.com/{item_id}",
        publish_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
        source_name="CoinDesk",
        source_type="rss",
    )
