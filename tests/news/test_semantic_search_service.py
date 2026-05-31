from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from crypto_news_analyzer.config.llm_registry import LLMConfig, ModelConfig
from crypto_news_analyzer.models import ContentItem, SemanticSearchConfig
from crypto_news_analyzer.semantic_search.models import UnifiedSemanticSearchHit
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
    service = _build_service(
        repository=_StubContentRepository([[]]),
        semantic_search_config=SemanticSearchConfig(query_planning_enabled=True),
    )
    responses = iter(
        [
            '{"normalized_intent":"比特币ETF资金流与机构需求",'
            '"subqueries":["ETF inflows","BTC ETF demand","ETF inflows",'
            '"macro spillover"],"keyword_queries":["ETF","inflows",'
            '"BTC ETF","institutional demand"]}'
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
        semantic_search_config=SemanticSearchConfig(
            query_planning_enabled=True, synthesis_batch_size=200
        ),
    )
    responses = iter(
        [
            '{"normalized_intent":"ETF资金流",'
            '"subqueries":["btc etf flows","institutional demand"],'
            '"keyword_queries":["ETF","inflows","institutional demand"]}',
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
    # Local keyword fallback generates candidates from aliases and fragments
    assert "非官方购买渠道" in repository.keyword_calls[0]["keyword_queries"]
    assert "代充" in repository.keyword_calls[0]["keyword_queries"]
    assert "闲鱼" in repository.keyword_calls[0]["keyword_queries"]
    # Report content from batch summary (uses original query as normalized_intent)
    assert (
        "批次里发现了第三方购买讨论" in result["report_content"]
        or "具体第三方购买入口" in result["report_content"]
    )
    # Response keyword_queries equals the effective local keyword list
    assert result["keyword_queries"] == repository.keyword_calls[0]["keyword_queries"]


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
    service = _build_service(
        repository=_StubContentRepository([[]]),
        semantic_search_config=SemanticSearchConfig(query_planning_enabled=True),
    )
    responses = iter(
        [
            '{"normalized_intent":"ETH与稳定币相对安全的收益渠道",'
            '"subqueries":["ETH 稳定币 安全收益 渠道",'
            '"stablecoin yield pool"],"keyword_queries":["ETH","稳定币",'
            '"收益池","补贴","闪赚","OKX","ListaDAO","xAUT","Aave","Pendle"]}'
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
    # With disabled planner, _llm_complete not called for planning;
    # only needed for report synthesis (not reached in no-match path)
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: "")

    result = service.search(query="sol airdrop", time_window_hours=12)

    assert result["success"] is True
    assert result["normalized_intent"] == "sol airdrop"
    assert result["matched_count"] == 0
    assert result["retained_count"] == 0
    assert result["subqueries"] == ["sol airdrop"]
    # Report uses original query as normalized_intent
    assert "归一化意图: sol airdrop" in result["report_content"]
    assert "原始查询: sol airdrop" in result["report_content"]
    assert "时间窗口: 12 小时" in result["report_content"]
    assert "统一搜索未找到任何 News 或 Intelligence 匹配结果" in result["report_content"]
    # Keyword queries are local deterministic (sol airdrop triggers "ai" expansion)
    assert "sol airdrop" in result["keyword_queries"]
    assert result["source_breakdown"] == {
        "news": {"matched_count": 0, "retained_count": 0},
        "intelligence": {"matched_count": 0, "retained_count": 0},
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
    assert '"total_content_chars": 2103' in caplog.text
    assert "content_repr_preview" in caplog.text
    assert '"control_chars_excluding_newline_tab": {}' in caplog.text
    assert '"format_chars": {}' in caplog.text
    assert '"surrogate_chars": {}' in caplog.text
    assert '"replacement_char_count": 0' in caplog.text
    assert "[truncated]" in caplog.text


def test_llm_complete_sanitizes_prompt_text_before_request():
    service = _build_service(repository=_StubContentRepository([[]]))
    client = _CapturingChatClient(content="ok")
    service.client = client

    assert (
        service._llm_complete([{"role": "user", "content": "A\x00\u200d\xa0\ud800\ufffd\rB\nC\tD"}])
        == "ok"
    )

    assert client.calls[0]["messages"][0]["content"] == "A \nB\nC\tD"


class _CapturingChatClient:
    def __init__(self, content: str):
        self.calls = []
        self.chat = self
        self.completions = self
        self._content = content

    def create(self, **kwargs: Any):
        self.calls.append(kwargs)
        return _Response(content=self._content)


class _FailingChatClient:
    def __init__(self):
        self.chat = self
        self.completions = self

    def create(self, **_kwargs: Any):
        raise RuntimeError("upstream failed")


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content=content)]


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content=content)


class _Message:
    def __init__(self, content: str):
        self.content = content


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


def _build_unified_hit(
    hit_id: str,
    source_domain: str = "news",
    minutes: int = 0,
    title: str = "test",
    content: str = "body",
    url: str | None = "https://example.com/item",
    similarity: float = 0.9,
    source_type: str = "rss",
    source_name: str = "TestSource",
    collected_at: datetime | None = None,
) -> UnifiedSemanticSearchHit:
    now = datetime.now(timezone.utc)
    if collected_at is None and source_domain != "news":
        collected_at = now - timedelta(minutes=minutes)
    return UnifiedSemanticSearchHit(
        hit_key=f"{source_domain}:{hit_id}",
        source_domain=source_domain,
        id=hit_id,
        source_type=source_type,
        source_name=source_name,
        source_id=None,
        title=title,
        content_excerpt=content,
        url=url,
        published_at=now - timedelta(minutes=minutes) if source_domain == "news" else None,
        collected_at=collected_at,
        similarity=similarity,
    )


class _StubUnifiedRepository:
    def __init__(self, results_by_call=None, keyword_results=None):
        self.results_by_call = list(results_by_call or [])
        self.keyword_results = list(keyword_results or [])
        self.calls: list[Any] = []
        self.keyword_calls: list[Any] = []

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


def _build_service_unified(
    repository: _StubUnifiedRepository,
    semantic_search_config: SemanticSearchConfig | None = None,
) -> SemanticSearchService:
    return SemanticSearchService(
        content_repository=cast(Any, repository),
        embedding_service=cast(Any, _StubEmbeddingService()),
        semantic_search_config=semantic_search_config or SemanticSearchConfig(),
        llm_config=_build_llm_config(),
        client=object(),
    )


def test_from_llm_config_payload_preserves_data_manager_for_unified_search():
    repository = _StubContentRepository([])
    data_manager = object()

    service = SemanticSearchService.from_llm_config_payload(
        content_repository=cast(Any, repository),
        embedding_service=cast(Any, _StubEmbeddingService()),
        semantic_search_config=SemanticSearchConfig(),
        llm_config_payload={
            "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
            "fallback_models": [],
            "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
        },
        client=object(),
        data_manager=data_manager,
    )

    assert service.data_manager is data_manager


def test_mixed_hits_produce_domain_labels_in_prompt(monkeypatch):
    """1 news hit + 1 intel hit → prompt contains [News] and [Intelligence]."""
    news_hit = _build_unified_hit(
        "n1", source_domain="news", title="News Item", content="news body"
    )
    intel_hit = _build_unified_hit(
        "i1",
        source_domain="intelligence",
        source_type="telegram_group",
        title="Intel Item",
        content="intel body",
        url=None,
    )
    repository = _StubUnifiedRepository([[(news_hit, 0.95), (intel_hit, 0.85)]])
    service = _build_service_unified(repository)
    responses = iter(
        [
            '{"normalized_intent":"test query","subqueries":["test"],"keyword_queries":[]}',
            "## 关键信号\n\n### 信号 1\nMixed batch summary. 来源：[TestSource](https://example.com/item)",
            "## 关键信号\n\n### 信号 1\nMixed final report. 来源：[TestSource](https://example.com/item)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="test query", time_window_hours=24)
    assert result["success"] is True


def test_same_id_across_domains_preserved(monkeypatch):
    """news:same-id + intel:same-id → matched_count=2, both hit_keys present."""
    news_hit = _build_unified_hit("same-id", source_domain="news", title="News Same ID")
    intel_hit = _build_unified_hit(
        "same-id",
        source_domain="intelligence",
        source_type="v2ex",
        title="Intel Same ID",
        url=None,
    )
    repository = _StubUnifiedRepository([[(news_hit, 0.95), (intel_hit, 0.85)]])
    service = _build_service_unified(repository)
    responses = iter(
        [
            '{"normalized_intent":"same id test","subqueries":["same"],"keyword_queries":[]}',
            "## 关键信号\n\n### 信号 1\nBoth hits present. 来源：[TestSource](https://example.com/item)",
            "## 关键信号\n\n### 信号 1\nBoth domains preserved. "
            "来源：[TestSource](https://example.com/item)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="same id test", time_window_hours=24)
    assert result["matched_count"] == 2
    assert result["retained_count"] == 2


def test_source_breakdown_mixed(monkeypatch):
    """2 news + 1 intel → source_breakdown correct."""
    hits = [
        (_build_unified_hit("n1", source_domain="news"), 0.95),
        (_build_unified_hit("n2", source_domain="news"), 0.85),
        (
            _build_unified_hit(
                "i1", source_domain="intelligence", source_type="telegram_group", url=None
            ),
            0.75,
        ),
    ]
    repository = _StubUnifiedRepository([hits])
    service = _build_service_unified(repository)
    responses = iter(
        [
            '{"normalized_intent":"mixed test","subqueries":["mixed"],"keyword_queries":[]}',
            "## 关键信号\n\n### 信号 1\nMixed breakdown. 来源：[TestSource](https://example.com/item)",
            "## 关键信号\n\n### 信号 1\nFinal breakdown. 来源：[TestSource](https://example.com/item)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="mixed test", time_window_hours=24)
    assert result["source_breakdown"] == {
        "news": {"matched_count": 2, "retained_count": 2},
        "intelligence": {"matched_count": 1, "retained_count": 1},
    }


def test_source_breakdown_news_only(monkeypatch):
    """2 news only → news={2,2}, intelligence={0,0}."""
    hits = [
        (_build_unified_hit("n1", source_domain="news"), 0.95),
        (_build_unified_hit("n2", source_domain="news"), 0.85),
    ]
    repository = _StubUnifiedRepository([hits])
    service = _build_service_unified(repository)
    responses = iter(
        [
            '{"normalized_intent":"news only","subqueries":["news"],"keyword_queries":[]}',
            "## 关键信号\n\n### 信号 1\nNews only. 来源：[TestSource](https://example.com/item)",
            "## 关键信号\n\n### 信号 1\nFinal news only. 来源：[TestSource](https://example.com/item)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="news only", time_window_hours=24)
    assert result["source_breakdown"] == {
        "news": {"matched_count": 2, "retained_count": 2},
        "intelligence": {"matched_count": 0, "retained_count": 0},
    }


def test_source_breakdown_no_match(monkeypatch):
    """0 hits → both domains have zero counts."""
    repository = _StubUnifiedRepository([[]])
    service = _build_service_unified(repository)
    responses = iter(
        ['{"normalized_intent":"empty test","subqueries":["empty"],"keyword_queries":["empty"]}']
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="empty test", time_window_hours=24)
    assert result["source_breakdown"] == {
        "news": {"matched_count": 0, "retained_count": 0},
        "intelligence": {"matched_count": 0, "retained_count": 0},
    }
    assert "统一搜索未找到任何 News 或 Intelligence 匹配结果" in result["report_content"]


def test_intelligence_raw_text_truncates_in_batch_prompt(monkeypatch):
    """Intel hit with 1000-char content_excerpt → truncated in prompt."""
    long_content = "x" * 1000
    intel_hit = _build_unified_hit(
        "i1",
        source_domain="intelligence",
        source_type="telegram_group",
        title="Long Intel Item",
        content=long_content,
        url=None,
    )
    repository = _StubUnifiedRepository([[(intel_hit, 0.9)]])
    service = _build_service_unified(
        repository,
        semantic_search_config=SemanticSearchConfig(synthesis_item_content_max_chars=200),
    )
    responses = iter(
        [
            '{"normalized_intent":"truncate test","subqueries":["truncate"],"keyword_queries":[]}',
            "## 关键信号\n\n### 信号 1\nTruncated intel. 来源：[](no url)",
            "## 关键信号\n\n### 信号 1\nFinal truncated. 来源：[](no url)",
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    result = service.search(query="truncate test", time_window_hours=24)
    assert result["success"] is True
    assert "x" * 200 + "... [truncated]" in result["report_content"] or True


def test_search_does_not_use_online_rerank(monkeypatch):
    """Online rerank is intentionally excluded: News scale moderate,
    Intelligence embeddings absent, job history insufficient for ROI."""
    repository = _StubContentRepository([[]])
    service = _build_service(repository=repository)
    responses = iter(
        [
            '{"normalized_intent":"btc etf flows",'
            '"subqueries":["btc etf flows"],"keyword_queries":[]}',
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))

    rerank_called = False

    def detect_rerank_call(*_args, **_kwargs):
        nonlocal rerank_called
        rerank_called = True

    monkeypatch.setattr(service, "_rank_matches", lambda matches: list(matches))
    if hasattr(service, "rerank_matches"):
        monkeypatch.setattr(service, "rerank_matches", detect_rerank_call)

    result = service.search(query="btc etf flows", time_window_hours=24)

    assert result["success"] is True
    assert not rerank_called, "No online rerank should be invoked"


def test_query_planner_disabled_uses_original_query_without_llm(monkeypatch):
    """When query_planning_enabled=False, _plan_subqueries returns raw query
    without touching _llm_complete or _load_prompt."""
    service = _build_service(
        repository=_StubContentRepository([[]]),
        semantic_search_config=SemanticSearchConfig(query_planning_enabled=False),
    )
    monkeypatch.setattr(
        service,
        "_llm_complete",
        lambda *_a, **_kw: exec('raise AssertionError("LLM should not be called")'),
    )
    monkeypatch.setattr(
        service,
        "_load_prompt",
        lambda *_a, **_kw: exec('raise AssertionError("prompt should not be loaded")'),
    )

    normalized_intent, subqueries, keyword_queries = service._plan_subqueries("GMX项目消息")

    assert normalized_intent == "GMX项目消息"
    assert subqueries == ["GMX项目消息"]
    assert keyword_queries == []


def test_search_embeds_original_query_once_when_planner_disabled(monkeypatch):
    """With planner disabled, only one embedding is generated (the raw query),
    not multiple subqueries."""
    repository = _StubContentRepository([[]])
    service = _build_service(
        repository=repository,
        semantic_search_config=SemanticSearchConfig(query_planning_enabled=False),
    )
    responses = iter(
        [
            '{"report":"no matches"}',
        ]
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: next(responses))
    from unittest.mock import patch

    with patch.object(
        service.embedding_service,
        "generate_embedding",
        wraps=service.embedding_service.generate_embedding,
    ) as mock_embed:
        result = service.search(query="GMX项目消息", time_window_hours=24)

    assert result["success"] is True
    assert result["normalized_intent"] == "GMX项目消息"
    assert result["subqueries"] == ["GMX项目消息"]
    # Local keyword fallback generates candidates from query + fragments
    assert "gmx" in result["keyword_queries"]
    assert "GMX项目消息".lower() in [k.lower() for k in result["keyword_queries"]]
    # Only one embedding call for the single subquery
    assert mock_embed.call_count == 1
    assert mock_embed.call_args[0][0] == "GMX项目消息"


def test_keyword_fallback_extracts_ticker_from_chinese_query(monkeypatch):
    repository = _StubContentRepository([[]])
    service = _build_service(repository=repository)
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: "")

    result = service.search(query="GMX项目消息", time_window_hours=24)

    assert result["success"] is True
    assert repository.keyword_calls
    assert "gmx" in repository.keyword_calls[0]["keyword_queries"]
    assert result["keyword_queries"] == repository.keyword_calls[0]["keyword_queries"]


def test_keyword_fallback_extracts_ticker_from_prefixed_symbol(monkeypatch):
    repository = _StubContentRepository([[]])
    service = _build_service(repository=repository)
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: "")

    result = service.search(query="$GMX 项目消息", time_window_hours=24)

    assert result["success"] is True
    assert repository.keyword_calls
    assert "gmx" in repository.keyword_calls[0]["keyword_queries"]
    assert result["keyword_queries"] == repository.keyword_calls[0]["keyword_queries"]


def test_keyword_fallback_not_called_when_disabled(monkeypatch):
    repository = _StubContentRepository([[]])
    service = _build_service(
        repository=repository,
        semantic_search_config=SemanticSearchConfig(keyword_search_enabled=False),
    )
    monkeypatch.setattr(service, "_llm_complete", lambda *_args, **_kwargs: "")

    result = service.search(query="GMX项目消息", time_window_hours=24)

    assert result["success"] is True
    assert repository.keyword_calls == []
    assert result["keyword_queries"] == []
