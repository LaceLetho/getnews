import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, cast

from crypto_news_analyzer.analyzers.intelligence_extractor import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    IntelligenceExtractor,
)
from crypto_news_analyzer.domain.models import EntryType, PrimaryLabel, RawIntelligenceItem
from crypto_news_analyzer.domain.repositories import IntelligenceRepository
from crypto_news_analyzer.models import IntelligenceConfig, IntelligenceExtractionConfig


class FakeChatCompletions:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.payloads: List[Dict[str, Any]] = list(payloads)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.completions: FakeChatCompletions = FakeChatCompletions(payloads)
        self.chat: SimpleNamespace = SimpleNamespace(completions=self.completions)


class FakeIntelligenceRepository:
    def __init__(self, existing_ids: Optional[List[str]] = None):
        self.saved_observations: List[Any] = []
        self.existing_ids = set(existing_ids or [])

    def save_observation(self, observation: Any) -> str:
        self.saved_observations.append(observation)
        return str(observation.id)

    def get_raw_item_ids_with_existing_observations(
        self, raw_item_ids: List[str], prompt_version: str
    ) -> set[str]:
        return set(raw_item_ids) & self.existing_ids


def _config(batch_size: int = 200):
    config = IntelligenceConfig(
        extraction=IntelligenceExtractionConfig(
            provider="opencode-go",
            model_name="deepseek-v4-pro",
            thinking_level="high",
            max_tokens=2000,
            batch_size=batch_size,
        )
    )
    return config


def _raw_item(raw_text: str, item_id: str = "raw-1") -> RawIntelligenceItem:
    return RawIntelligenceItem(
        id=item_id,
        source_type="telegram_group",
        source_id="chat-1",
        raw_text=raw_text,
        content_hash=f"hash-{item_id}",
        expires_at=datetime.utcnow() + timedelta(days=30),
        collected_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


def _extract_with_payload(
    raw_text: str, payload: Dict[str, Any]
) -> Tuple[IntelligenceExtractor, FakeIntelligenceRepository, List[Any]]:
    repository = FakeIntelligenceRepository()
    extractor = IntelligenceExtractor(
        _config(), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient([payload])

    observations = extractor.extract([_raw_item(raw_text)])

    return extractor, repository, observations


def test_extracts_biquan_danbao_as_slang_observation():
    _, repository, observations = _extract_with_payload(
        "找币圈担保，U 到账后再放号。",
        {
            "channels": [],
            "slangs": [
                {
                    "term": "币圈担保",
                    "normalized_term": "币圈担保",
                    "literal_meaning": "加密货币圈内的第三方担保",
                    "contextual_meaning": "交易双方通过币圈中介托管资金或账号以降低欺诈风险",
                    "usage_quote": "找币圈担保",
                    "aliases_or_variants": ["币圈中介"],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.CRYPTO.value,
                    "secondary_tags": ["担保"],
                    "confidence": 0.91,
                }
            ],
        },
    )

    assert len(observations) == 1
    slang = observations[0]
    assert slang.entry_type == EntryType.SLANG.value
    assert slang.term == "币圈担保"
    assert slang.contextual_meaning is not None
    assert "托管资金" in slang.contextual_meaning
    assert repository.saved_observations == observations


def test_extracts_tuqu_gift_card_with_payment_or_account_label():
    _, _, observations = _extract_with_payload(
        "土区礼品卡便宜出，支持支付宝。",
        {
            "channels": [],
            "slangs": [
                {
                    "term": "土区礼品卡",
                    "normalized_term": "土区礼品卡",
                    "literal_meaning": "土耳其区礼品卡",
                    "contextual_meaning": "用于跨区购买数字订阅或账号服务的支付载体",
                    "usage_quote": "土区礼品卡便宜出",
                    "aliases_or_variants": ["土区卡"],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.PAYMENT.value,
                    "secondary_tags": ["礼品卡", "跨区"],
                    "confidence": 0.88,
                }
            ],
        },
    )

    assert observations[0].term == "土区礼品卡"
    assert observations[0].primary_label in {
        PrimaryLabel.ACCOUNT_TRADING.value,
        PrimaryLabel.PAYMENT.value,
    }


def test_extracts_channel_and_slang_from_same_raw_item():
    extractor, _, observations = _extract_with_payload(
        "GPT Plus 土区礼品卡渠道 @seller",
        {
            "channels": [
                {
                    "channel_name": "@seller",
                    "channel_description": "GPT Plus 土区礼品卡卖家渠道",
                    "channel_urls": [],
                    "channel_handles": ["@seller"],
                    "channel_domains": [],
                    "primary_label": PrimaryLabel.ACCOUNT_TRADING.value,
                    "secondary_tags": ["telegram", "gpt-plus"],
                    "confidence": 0.84,
                }
            ],
            "slangs": [
                {
                    "term": "土区礼品卡",
                    "normalized_term": "土区礼品卡",
                    "literal_meaning": "土耳其区礼品卡",
                    "contextual_meaning": "跨区订阅 GPT Plus 的礼品卡交易术语",
                    "usage_quote": "GPT Plus 土区礼品卡渠道",
                    "aliases_or_variants": [],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.PAYMENT.value,
                    "secondary_tags": ["跨区订阅"],
                    "confidence": 0.9,
                }
            ],
        },
    )

    assert {observation.entry_type for observation in observations} == {
        EntryType.CHANNEL.value,
        EntryType.SLANG.value,
    }
    channel = next(
        observation for observation in observations if observation.entry_type == "channel"
    )
    slang = next(observation for observation in observations if observation.entry_type == "slang")
    assert channel.channel_handles == ["@seller"]
    assert slang.term == "土区礼品卡"
    call = cast(FakeOpenAIClient, extractor.client).completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["model"] == "deepseek-v4-pro"


def test_records_prompt_model_schema_versions():
    _, _, observations = _extract_with_payload(
        "土区礼品卡",
        {
            "channels": [],
            "slangs": [
                {
                    "term": "土区礼品卡",
                    "normalized_term": "土区礼品卡",
                    "literal_meaning": "土耳其区礼品卡",
                    "contextual_meaning": "跨区支付术语",
                    "usage_quote": "土区礼品卡",
                    "aliases_or_variants": [],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.PAYMENT.value,
                    "secondary_tags": [],
                    "confidence": 0.7,
                }
            ],
        },
    )

    assert observations[0].model_name == "deepseek-v4-pro"
    assert observations[0].prompt_version == PROMPT_VERSION
    assert observations[0].schema_version == SCHEMA_VERSION


def test_low_confidence_observations_are_stored_but_not_auto_canonicalized():
    _, repository, observations = _extract_with_payload(
        "疑似新黑话：猫池号",
        {
            "channels": [],
            "slangs": [
                {
                    "term": "猫池号",
                    "normalized_term": "猫池号",
                    "literal_meaning": "疑似设备池相关账号",
                    "contextual_meaning": "低置信度账号交易术语",
                    "usage_quote": "疑似新黑话：猫池号",
                    "aliases_or_variants": [],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.ACCOUNT_TRADING.value,
                    "secondary_tags": [],
                    "confidence": 0.22,
                }
            ],
        },
    )

    assert observations[0].confidence == 0.22
    assert observations[0].is_canonicalized is False
    assert repository.saved_observations[0].is_canonicalized is False


def test_secrets_and_tokens_are_not_promoted_to_observation_fields():
    _, _, observations = _extract_with_payload(
        "联系 @seller，不要发 api_key=sk-test password=hunter2",
        {
            "channels": [
                {
                    "channel_name": "api_key=sk-test",
                    "channel_description": "password=hunter2",
                    "channel_urls": ["https://t.me/seller?auth_token=secret"],
                    "channel_handles": ["@seller", "authorization=Bearer abc"],
                    "channel_domains": ["api_key.example"],
                    "primary_label": PrimaryLabel.ACCOUNT_TRADING.value,
                    "secondary_tags": ["password=hunter2", "telegram"],
                    "confidence": 0.76,
                }
            ],
            "slangs": [
                {
                    "term": "private_key=abc",
                    "normalized_term": "private_key=abc",
                    "literal_meaning": "secret",
                    "contextual_meaning": "secret",
                    "usage_quote": "private_key=abc",
                    "aliases_or_variants": ["api_key=sk-test"],
                    "detected_language": "en",
                    "primary_label": PrimaryLabel.OTHER.value,
                    "secondary_tags": [],
                    "confidence": 0.8,
                }
            ],
        },
    )

    assert len(observations) == 1
    channel = observations[0]
    assert channel.entry_type == EntryType.CHANNEL.value
    assert channel.channel_name is None
    assert channel.channel_description is None
    assert channel.channel_urls == []
    assert channel.channel_handles == ["@seller"]
    assert channel.channel_domains == []
    assert channel.secondary_tags == ["telegram"]


def test_entry_type_dispatch_is_channel_vs_slang():
    _, _, observations = _extract_with_payload(
        "频道 @seller 说币圈担保安全",
        {
            "channels": [
                {
                    "channel_name": "@seller",
                    "channel_description": "公开卖家入口",
                    "channel_urls": [],
                    "channel_handles": ["@seller"],
                    "channel_domains": [],
                    "primary_label": PrimaryLabel.ACCOUNT_TRADING.value,
                    "secondary_tags": [],
                    "confidence": 0.7,
                }
            ],
            "slangs": [
                {
                    "term": "币圈担保",
                    "normalized_term": "币圈担保",
                    "literal_meaning": "加密货币圈担保",
                    "contextual_meaning": "交易担保术语",
                    "usage_quote": "币圈担保安全",
                    "aliases_or_variants": [],
                    "detected_language": "zh-CN",
                    "primary_label": PrimaryLabel.CRYPTO.value,
                    "secondary_tags": [],
                    "confidence": 0.8,
                }
            ],
        },
    )

    channel = next(item for item in observations if item.entry_type == EntryType.CHANNEL.value)
    slang = next(item for item in observations if item.entry_type == EntryType.SLANG.value)
    assert channel.channel_handles == ["@seller"]
    assert channel.term is None
    assert slang.term == "币圈担保"
    assert slang.channel_handles == []


def test_multi_item_batch_maps_observations_by_raw_item_id():
    repository = FakeIntelligenceRepository()
    extractor = IntelligenceExtractor(
        _config(batch_size=20), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient(
        [
            {
                "channels": [],
                "slangs": [
                    {
                        "raw_item_id": "raw-2",
                        "term": "土区礼品卡",
                        "normalized_term": "土区礼品卡",
                        "literal_meaning": "土耳其区礼品卡",
                        "contextual_meaning": "跨区订阅支付术语",
                        "usage_quote": "土区礼品卡",
                        "aliases_or_variants": [],
                        "detected_language": "zh-CN",
                        "primary_label": PrimaryLabel.PAYMENT.value,
                        "secondary_tags": [],
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    observations = extractor.extract(
        [_raw_item("第一条无关", "raw-1"), _raw_item("土区礼品卡", "raw-2")]
    )

    assert len(observations) == 1
    assert observations[0].raw_item_id == "raw-2"
    assert repository.saved_observations == observations


def test_multi_item_batch_skips_unknown_raw_item_id_without_fallback():
    repository = FakeIntelligenceRepository()
    extractor = IntelligenceExtractor(
        _config(batch_size=20), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient(
        [
            {
                "channels": [],
                "slangs": [
                    {
                        "raw_item_id": "missing-raw",
                        "term": "土区礼品卡",
                        "normalized_term": "土区礼品卡",
                        "literal_meaning": "土耳其区礼品卡",
                        "contextual_meaning": "跨区订阅支付术语",
                        "usage_quote": "土区礼品卡",
                        "aliases_or_variants": [],
                        "detected_language": "zh-CN",
                        "primary_label": PrimaryLabel.PAYMENT.value,
                        "secondary_tags": [],
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    observations = extractor.extract([_raw_item("第一条", "raw-1"), _raw_item("第二条", "raw-2")])

    assert observations == []
    assert repository.saved_observations == []


def test_extract_sends_already_extracted_raw_item_ids_again():
    repository = FakeIntelligenceRepository(existing_ids=["raw-1"])
    extractor = IntelligenceExtractor(
        _config(batch_size=20), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient(
        [
            {
                "channels": [],
                "slangs": [
                    {
                        "raw_item_id": "raw-2",
                        "term": "土区礼品卡",
                        "normalized_term": "土区礼品卡",
                        "literal_meaning": "土耳其区礼品卡",
                        "contextual_meaning": "跨区订阅支付术语",
                        "usage_quote": "土区礼品卡",
                        "aliases_or_variants": [],
                        "detected_language": "zh-CN",
                        "primary_label": PrimaryLabel.PAYMENT.value,
                        "secondary_tags": [],
                        "confidence": 0.9,
                    }
                ],
            }
        ]
    )

    observations = extractor.extract(
        [_raw_item("已处理", "raw-1"), _raw_item("土区礼品卡", "raw-2")]
    )

    call = cast(FakeOpenAIClient, extractor.client).completions.calls[0]
    sent_items = json.loads(call["messages"][1]["content"])["items"]
    assert [item["id"] for item in sent_items] == ["raw-1", "raw-2"]
    assert len(observations) == 1
    assert observations[0].raw_item_id == "raw-2"


def test_extract_prompt_payload_only_contains_provided_raw_items():
    repository = FakeIntelligenceRepository()
    extractor = IntelligenceExtractor(
        _config(batch_size=20), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient([{"channels": [], "slangs": []}])

    observations = extractor.extract([_raw_item("保留：币圈担保", "kept-raw")])

    call = cast(FakeOpenAIClient, extractor.client).completions.calls[0]
    sent_items = json.loads(call["messages"][1]["content"])["items"]
    assert observations == []
    assert [item["id"] for item in sent_items] == ["kept-raw"]
    assert "未跟踪黑话" not in sent_items[0]["raw_text"]


def test_extract_calls_client_even_when_all_raw_items_were_already_extracted():
    repository = FakeIntelligenceRepository(existing_ids=["raw-1"])
    extractor = IntelligenceExtractor(
        _config(batch_size=20), repository=cast(IntelligenceRepository, cast(object, repository))
    )
    extractor.client = FakeOpenAIClient([{"channels": [], "slangs": []}])

    observations = extractor.extract([_raw_item("已处理", "raw-1")])

    assert observations == []
    call = cast(FakeOpenAIClient, extractor.client).completions.calls[0]
    sent_items = json.loads(call["messages"][1]["content"])["items"]
    assert [item["id"] for item in sent_items] == ["raw-1"]
