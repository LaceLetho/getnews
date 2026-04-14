from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from crypto_news_analyzer.config.llm_registry import LLMConfig, ModelConfig
from crypto_news_analyzer.models import ContentItem, SemanticSearchConfig
from crypto_news_analyzer.semantic_search.service import SemanticSearchMatch, SemanticSearchService


class _StubEmbeddingService:
    def __init__(self):
        self.enabled = True
        self.calls: list[str] = []

    def generate_embedding(self, text: str):
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class _StubContentRepository:
    def __init__(self, results_by_call, keyword_results=None):
        self.results_by_call = list(results_by_call)
        self.keyword_results = list(keyword_results or [])
        self.calls = []
        self.keyword_calls = []

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

    def semantic_search_by_keywords(self, keyword_queries, since_time, max_hours, limit):
        self.keyword_calls.append(
            {
                "keyword_queries": keyword_queries,
                "since_time": since_time,
                "max_hours": max_hours,
                "limit": limit,
            }
        )
        return self.keyword_results.pop(0) if self.keyword_results else []


def test_query_planner_caps_unique_subqueries_and_keeps_original_query(monkeypatch):
    service = _build_service(repository=_StubContentRepository([[]]))
    responses = iter(
        [
            '{"normalized_intent":"比特币ETF资金流与机构需求","subqueries":["ETF inflows","BTC ETF demand","ETF inflows","macro spillover"],"keyword_queries":["ETF","inflows","BTC ETF","institutional demand"]}'
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    normalized_intent, subqueries, keyword_queries = service._plan_subqueries("btc etf flows")

    assert normalized_intent == "比特币ETF资金流与机构需求"
    assert subqueries == [
        "btc etf flows",
        "ETF inflows",
        "BTC ETF demand",
        "macro spillover",
    ]
    assert keyword_queries == ["etf", "inflows", "btc etf", "institutional demand"]


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
            '{"normalized_intent":"ETF资金流","subqueries":["btc etf flows","institutional demand"],"keyword_queries":["ETF","inflows","institutional demand"]}',
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


def test_keyword_recall_fills_gap_when_vector_search_is_empty(monkeypatch):
    keyword_item = _build_item("keyword-hit", minutes=1)
    repository = _StubContentRepository([[]], keyword_results=[[(keyword_item, 12.0)]])
    service = _build_service(repository=repository)
    responses = iter(
        [
            '{"normalized_intent":"AI套餐非官方购买渠道","subqueries":["AI套餐 购买渠道"],"keyword_queries":["AI套餐","AI token","非官方购买渠道","第三方购买","代充","闲鱼","共享账号"]}',
            "## 关键信号\n\n### 信号 1\n批次里发现了第三方购买讨论。\n来源：[CoinDesk](https://example.com/keyword-hit)",
            "## 关键信号\n\n### 信号 1\n发现了具体第三方购买入口。\n来源：[CoinDesk](https://example.com/keyword-hit)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(
        query="帮我找一下AI套餐或者token的非官方购买渠道",
        time_window_hours=24,
    )

    assert result["success"] is True
    assert result["matched_count"] == 1
    assert repository.keyword_calls
    assert repository.keyword_calls[0]["limit"] == 30
    assert "非官方购买渠道" in repository.keyword_calls[0]["keyword_queries"]
    assert "代充" in repository.keyword_calls[0]["keyword_queries"]
    assert "闲鱼" in repository.keyword_calls[0]["keyword_queries"]
    assert "具体第三方购买入口" in result["report_content"]
    assert result["keyword_queries"] == [
        "ai套餐",
        "ai token",
        "非官方购买渠道",
        "第三方购买",
        "代充",
        "闲鱼",
        "共享账号",
    ]


def test_build_keyword_queries_prefers_llm_dynamic_keywords():
    service = _build_service(repository=_StubContentRepository([[]]))

    keyword_queries = service._build_keyword_queries(
        query="帮我找一下AI套餐或者token的非官方购买渠道",
        normalized_intent="AI套餐与token的非官方购买渠道",
        subqueries=["AI套餐 购买渠道", "token 第三方购买"],
        planned_keyword_queries=[
            "AI套餐",
            "AI token",
            "非官方购买渠道",
            "第三方购买",
            "代充",
            "闲鱼",
        ],
    )

    assert "ai套餐或者token的非官方购买渠道" in keyword_queries
    assert "ai套餐" in keyword_queries
    assert "非官方购买渠道" in keyword_queries
    assert "代充" in keyword_queries
    assert "闲鱼" in keyword_queries
    assert "ai token" in keyword_queries
    assert "第三方充值" not in keyword_queries


def test_build_keyword_queries_uses_local_fallback_when_llm_keywords_are_sparse():
    service = _build_service(repository=_StubContentRepository([[]]))

    keyword_queries = service._build_keyword_queries(
        query="帮我找一下AI套餐或者token的非官方购买渠道",
        normalized_intent="AI套餐与token的非官方购买渠道",
        subqueries=["AI套餐 购买渠道", "token 第三方购买"],
        planned_keyword_queries=["AI套餐"],
    )

    assert "ai套餐" in keyword_queries
    assert "非官方购买渠道" in keyword_queries
    assert "第三方充值" in keyword_queries
    assert "代充" in keyword_queries
    assert "闲鱼" in keyword_queries


def test_query_planner_can_return_yield_channel_keywords(monkeypatch):
    service = _build_service(repository=_StubContentRepository([[]]))
    responses = iter(
        [
            '{"normalized_intent":"ETH与稳定币相对安全的收益渠道","subqueries":["ETH 稳定币 安全收益 渠道","stablecoin yield pool"],"keyword_queries":["ETH","稳定币","收益池","补贴","闪赚","OKX","ListaDAO","xAUT","Aave","Pendle"]}'
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    normalized_intent, subqueries, keyword_queries = service._plan_subqueries(
        "帮我汇总ETH与稳定币安全的理财或收益渠道与方法"
    )

    assert normalized_intent == "ETH与稳定币相对安全的收益渠道"
    assert subqueries[0] == "帮我汇总ETH与稳定币安全的理财或收益渠道与方法"
    assert "收益池" in keyword_queries
    assert "补贴" in keyword_queries
    assert "okx" in keyword_queries
    assert "listadao" in keyword_queries
    assert "xaut" in keyword_queries


def test_no_match_returns_compact_non_error_report_shape(monkeypatch):
    service = _build_service(repository=_StubContentRepository([[]]))
    responses = iter(
        [
            '{"normalized_intent":"SOL生态空投","subqueries":["sol airdrop"],"keyword_queries":["SOL","airdrop"]}'
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="sol airdrop", time_window_hours=12)

    assert result == {
        "success": True,
        "report_content": "# 主题检索报告\n\n- 归一化意图: SOL生态空投\n- 原始查询: sol airdrop\n- 时间窗口: 12 小时\n- 匹配条数: 0\n- 保留条数: 0\n\n## 关键信号\n现有材料未显示出足够具体的渠道/入口/活动/产品级信号。",
        "normalized_intent": "SOL生态空投",
        "matched_count": 0,
        "retained_count": 0,
        "subqueries": ["sol airdrop"],
        "keyword_queries": ["sol", "airdrop"],
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


def test_batch_prompt_truncates_item_content():
    service = _build_service(
        repository=_StubContentRepository([[]]),
        semantic_search_config=SemanticSearchConfig(synthesis_item_content_max_chars=12),
    )
    match = SemanticSearchMatch(
        item=_build_item("long", minutes=1, content="a" * 20),
        best_similarity=0.9,
        matched_subqueries=["ai token"],
    )

    prompt = service._build_batch_prompt(
        query="ai token",
        normalized_intent="AI token",
        time_window_hours=24,
        batch=[match],
    )

    assert "aaaaaaaaaaaa... [truncated]" in prompt
    assert "aaaaaaaaaaaaaaaaaaaa" not in prompt


def test_llm_complete_logs_request_details_on_failure(caplog):
    service = _build_service(repository=_StubContentRepository([[]]))
    service.client = _FailingChatClient()

    with pytest.raises(RuntimeError, match="upstream failed"):
        service._llm_complete(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "\x00\u200b\ud800\ufffd" + ("x" * 2100)},
            ],
            response_format={"type": "json_object"},
        )

    assert "语义搜索LLM请求失败，请求详情=" in caplog.text
    assert '"model": "kimi-k2.5"' in caplog.text
    assert '"message_count": 2' in caplog.text
    assert '"total_content_chars": 2107' in caplog.text
    assert "content_repr_preview" in caplog.text
    assert '"control_chars_excluding_newline_tab": {"U+0000": 1}' in caplog.text
    assert '"format_chars": {"U+200B": 1}' in caplog.text
    assert '"surrogate_chars": {"U+D800": 1}' in caplog.text
    assert '"replacement_char_count": 1' in caplog.text
    assert "[truncated]" in caplog.text


class _FailingChatClient:
    def __init__(self):
        self.chat = self
        self.completions = self

    def create(self, **_kwargs: Any):
        raise RuntimeError("upstream failed")


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


def _build_item(item_id: str, minutes: int, content: str | None = None) -> ContentItem:
    return ContentItem(
        id=item_id,
        title=f"Title {item_id}",
        content=content if content is not None else f"Body {item_id}",
        url=f"https://example.com/{item_id}",
        publish_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
        source_name="CoinDesk",
        source_type="rss",
    )
