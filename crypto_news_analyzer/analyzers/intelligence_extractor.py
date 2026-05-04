"""Structured intelligence extraction from raw forum/chat text."""

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, cast

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..config.llm_registry import ModelConfig, ResolvedModelRuntime, resolve_model_runtime
from ..domain.models import EntryType, ExtractionObservation, PrimaryLabel, RawIntelligenceItem
from ..domain.repositories import IntelligenceRepository
from ..models import IntelligenceConfig

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency presence is environment-specific
    OpenAI = None


PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_PROMPT_PATH = Path("prompts/intelligence_extraction_prompt.md")

_PRIMARY_LABEL_VALUES = {label.value for label in PrimaryLabel}
_SECRET_MARKERS = (
    "private key",
    "private_key",
    "privkey",
    "mnemonic",
    "seed phrase",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "auth_token",
    "access_token",
    "authorization",
    "bearer ",
    "stringsession",
    "string_session",
    "api_hash",
)


class ChannelObservation(BaseModel):
    """LLM channel-intelligence observation payload."""

    channel_name: str = Field(default="")
    channel_description: str = Field(default="")
    channel_urls: List[str] = Field(default_factory=list)
    channel_handles: List[str] = Field(default_factory=list)
    channel_domains: List[str] = Field(default_factory=list)
    primary_label: str = Field(default=PrimaryLabel.OTHER.value)
    secondary_tags: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator(
        "channel_urls",
        "channel_handles",
        "channel_domains",
        "secondary_tags",
        mode="before",
    )
    @classmethod
    def normalize_string_list(cls, value: Any) -> List[str]:
        return _normalize_string_list(value)


class SlangObservation(BaseModel):
    """LLM slang-intelligence observation payload."""

    term: str = Field(default="")
    normalized_term: str = Field(default="")
    literal_meaning: str = Field(default="")
    contextual_meaning: str = Field(default="")
    usage_quote: str = Field(default="")
    aliases_or_variants: List[str] = Field(default_factory=list)
    detected_language: str = Field(default="")
    primary_label: str = Field(default=PrimaryLabel.OTHER.value)
    secondary_tags: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("aliases_or_variants", "secondary_tags", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> List[str]:
        return _normalize_string_list(value)


class IntelligenceExtractionResult(BaseModel):
    """Structured response expected from the extraction LLM."""

    channels: List[ChannelObservation] = Field(default_factory=list)
    slangs: List[SlangObservation] = Field(default_factory=list)


class IntelligenceExtractor:
    """Extract channel and slang observations from raw intelligence items."""

    def __init__(
        self,
        config: IntelligenceConfig,
        mock_mode: bool = False,
        repository: Optional[IntelligenceRepository] = None,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
    ):
        self.config = config
        self.mock_mode = mock_mode
        self.repository = repository
        self.prompt_path = Path(prompt_path)
        self.logger = logging.getLogger(__name__)
        self.prompt_version = PROMPT_VERSION
        self.schema_version = SCHEMA_VERSION
        self.batch_size = max(1, int(getattr(config.extraction, "batch_size", 1) or 1))
        self.runtime = resolve_model_runtime(
            ModelConfig(
                provider=config.extraction.provider,
                name=config.extraction.model_name,
                options={},
            )
        )
        self.model_name = self.runtime.name
        self.conversation_id = str(uuid.uuid4())
        self.client: Any = None

        api_key = os.getenv(self.runtime.provider.env_var, "").strip()
        if not mock_mode and api_key and OpenAI:
            self.client = self._build_client(self.runtime, api_key)
        elif not mock_mode and not api_key:
            self.logger.warning("未提供 intelligence extraction 所需的 OPENCODE_API_KEY")

    def _build_client(self, runtime: ResolvedModelRuntime, api_key: str):
        """Build an OpenAI-compatible client using provider registry metadata."""
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")

        default_headers = dict(runtime.provider.default_headers)
        conversation_header_name = runtime.provider.conversation_header_name
        if conversation_header_name:
            default_headers[conversation_header_name] = self.conversation_id

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": runtime.provider.base_url,
        }
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        client = OpenAI(**client_kwargs)
        setattr(client, "_provider", runtime.provider_name)
        return client

    def extract(self, raw_items: List[RawIntelligenceItem]) -> List[ExtractionObservation]:
        """Extract and persist observations for raw intelligence items."""
        if not raw_items:
            return []

        observations: List[ExtractionObservation] = []
        for batch in _chunks(raw_items, self.batch_size):
            result = self._mock_extract_batch(batch) if self.mock_mode else self._extract_batch(batch)
            batch_observations = self._result_to_observations(result, batch)
            for observation in batch_observations:
                if self.repository is not None:
                    self.repository.save_observation(observation)
                observations.append(observation)

        return observations

    def _extract_batch(self, batch: Sequence[RawIntelligenceItem]) -> IntelligenceExtractionResult:
        if self.client is None:
            raise RuntimeError("intelligence extraction client is not initialized")

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=cast(Any, self._build_messages(batch)),
            temperature=self.config.extraction.temperature,
            max_tokens=self.config.extraction.max_tokens,
            response_format={"type": "json_object"},
        )
        content = _extract_response_content(response)
        return self._parse_result(content)

    def _build_messages(self, batch: Sequence[RawIntelligenceItem]) -> List[Dict[str, str]]:
        items_payload = [
            {
                "id": item.id,
                "source_type": item.source_type,
                "source_url": item.source_url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "raw_text": item.raw_text,
            }
            for item in batch
        ]
        return [
            {"role": "system", "content": self._load_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "schema_version": self.schema_version,
                        "items": items_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _load_prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def _parse_result(self, content: str) -> IntelligenceExtractionResult:
        try:
            payload = json.loads(content)
            return IntelligenceExtractionResult(**payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self.logger.error("intelligence extraction response parsing failed: %s", exc)
            raise

    def _result_to_observations(
        self,
        result: IntelligenceExtractionResult,
        batch: Sequence[RawIntelligenceItem],
    ) -> List[ExtractionObservation]:
        observations: List[ExtractionObservation] = []
        for channel in result.channels:
            sanitized = _sanitize_channel_observation(channel)
            if sanitized is None:
                continue
            raw_item = _select_raw_item_for_channel(sanitized, batch)
            observations.append(
                ExtractionObservation.create(
                    raw_item_id=raw_item.id,
                    entry_type=EntryType.CHANNEL.value,
                    confidence=sanitized.confidence,
                    model_name=self.model_name,
                    prompt_version=self.prompt_version,
                    schema_version=self.schema_version,
                    channel_name=sanitized.channel_name.strip() or None,
                    channel_description=sanitized.channel_description.strip() or None,
                    channel_urls=sanitized.channel_urls,
                    channel_handles=sanitized.channel_handles,
                    channel_domains=sanitized.channel_domains,
                    primary_label=_normalize_primary_label(sanitized.primary_label),
                    secondary_tags=sanitized.secondary_tags,
                    is_canonicalized=False,
                )
            )

        for slang in result.slangs:
            sanitized = _sanitize_slang_observation(slang)
            if sanitized is None:
                continue
            raw_item = _select_raw_item_for_slang(sanitized, batch)
            observations.append(
                ExtractionObservation.create(
                    raw_item_id=raw_item.id,
                    entry_type=EntryType.SLANG.value,
                    confidence=sanitized.confidence,
                    model_name=self.model_name,
                    prompt_version=self.prompt_version,
                    schema_version=self.schema_version,
                    term=sanitized.term.strip(),
                    normalized_term=sanitized.normalized_term.strip(),
                    literal_meaning=sanitized.literal_meaning.strip() or None,
                    contextual_meaning=sanitized.contextual_meaning.strip() or None,
                    usage_example_raw_item_id=raw_item.id,
                    usage_quote=sanitized.usage_quote.strip() or None,
                    aliases_or_variants=sanitized.aliases_or_variants,
                    detected_language=sanitized.detected_language.strip() or None,
                    primary_label=_normalize_primary_label(sanitized.primary_label),
                    secondary_tags=sanitized.secondary_tags,
                    is_canonicalized=False,
                )
            )
        return observations

    def _mock_extract_batch(
        self, batch: Sequence[RawIntelligenceItem]
    ) -> IntelligenceExtractionResult:
        channels: List[ChannelObservation] = []
        slangs: List[SlangObservation] = []
        for item in batch:
            raw_text = item.raw_text
            if "币圈担保" in raw_text:
                slangs.append(
                    SlangObservation(
                        term="币圈担保",
                        normalized_term="币圈担保",
                        literal_meaning="加密货币圈内的第三方担保",
                        contextual_meaning="交易双方用中间人或群组托管来降低欺诈风险的灰色交易安排",
                        usage_quote="币圈担保",
                        detected_language="zh-CN",
                        primary_label=PrimaryLabel.CRYPTO.value,
                        secondary_tags=["担保", "场外交易"],
                        confidence=0.8,
                    )
                )
            if "土区礼品卡" in raw_text:
                slangs.append(
                    SlangObservation(
                        term="土区礼品卡",
                        normalized_term="土区礼品卡",
                        literal_meaning="土耳其区礼品卡",
                        contextual_meaning="利用土耳其区价格或支付渠道购买数字服务订阅的账号/支付交易术语",
                        usage_quote="土区礼品卡",
                        detected_language="zh-CN",
                        primary_label=PrimaryLabel.PAYMENT.value,
                        secondary_tags=["礼品卡", "跨区"],
                        confidence=0.8,
                    )
                )
            handles = sorted(set(re.findall(r"@[A-Za-z0-9_]{3,32}", raw_text)))
            if handles:
                channels.append(
                    ChannelObservation(
                        channel_name=handles[0],
                        channel_description="原文中出现的卖家或频道联系入口",
                        channel_handles=handles,
                        primary_label=PrimaryLabel.ACCOUNT_TRADING.value,
                        secondary_tags=["telegram"],
                        confidence=0.75,
                    )
                )
        return IntelligenceExtractionResult(channels=channels, slangs=slangs)


def _chunks(items: Sequence[RawIntelligenceItem], size: int) -> List[Sequence[RawIntelligenceItem]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _extract_response_content(response: Any) -> str:
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("intelligence extraction response content is empty")
    return content


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_primary_label(label: str) -> str:
    normalized = str(label or "").strip()
    return normalized if normalized in _PRIMARY_LABEL_VALUES else PrimaryLabel.OTHER.value


def _contains_secret(text: Optional[str]) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _filter_public_values(values: List[str]) -> List[str]:
    return [value for value in values if not _contains_secret(value)]


def _sanitize_channel_observation(
    observation: ChannelObservation,
) -> Optional[ChannelObservation]:
    channel_name = "" if _contains_secret(observation.channel_name) else observation.channel_name
    channel_description = (
        "" if _contains_secret(observation.channel_description) else observation.channel_description
    )
    sanitized = observation.model_copy(
        update={
            "channel_name": channel_name,
            "channel_description": channel_description,
            "channel_urls": _filter_public_values(observation.channel_urls),
            "channel_handles": _filter_public_values(observation.channel_handles),
            "channel_domains": _filter_public_values(observation.channel_domains),
            "secondary_tags": _filter_public_values(observation.secondary_tags),
            "primary_label": _normalize_primary_label(observation.primary_label),
        }
    )
    if not (
        sanitized.channel_name
        or sanitized.channel_urls
        or sanitized.channel_handles
        or sanitized.channel_domains
    ):
        return None
    return sanitized


def _sanitize_slang_observation(observation: SlangObservation) -> Optional[SlangObservation]:
    if _contains_secret(observation.term) or _contains_secret(observation.normalized_term):
        return None
    sanitized = observation.model_copy(
        update={
            "literal_meaning": ""
            if _contains_secret(observation.literal_meaning)
            else observation.literal_meaning,
            "contextual_meaning": ""
            if _contains_secret(observation.contextual_meaning)
            else observation.contextual_meaning,
            "usage_quote": "" if _contains_secret(observation.usage_quote) else observation.usage_quote,
            "aliases_or_variants": _filter_public_values(observation.aliases_or_variants),
            "secondary_tags": _filter_public_values(observation.secondary_tags),
            "primary_label": _normalize_primary_label(observation.primary_label),
        }
    )
    if not sanitized.normalized_term:
        sanitized = sanitized.model_copy(update={"normalized_term": sanitized.term})
    return sanitized


def _select_raw_item_for_channel(
    observation: ChannelObservation,
    batch: Sequence[RawIntelligenceItem],
) -> RawIntelligenceItem:
    needles = [
        observation.channel_name,
        *observation.channel_handles,
        *observation.channel_urls,
        *observation.channel_domains,
    ]
    return _select_raw_item_by_needles(needles, batch)


def _select_raw_item_for_slang(
    observation: SlangObservation,
    batch: Sequence[RawIntelligenceItem],
) -> RawIntelligenceItem:
    needles = [observation.term, observation.normalized_term, observation.usage_quote]
    return _select_raw_item_by_needles(needles, batch)


def _select_raw_item_by_needles(
    needles: Sequence[str],
    batch: Sequence[RawIntelligenceItem],
) -> RawIntelligenceItem:
    normalized_needles = [str(needle).strip().lower() for needle in needles if str(needle).strip()]
    for item in batch:
        text = item.raw_text.lower()
        if any(needle in text for needle in normalized_needles):
            return item
    return batch[0]
