"""Static provider/model registry for LLM config validation."""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class LLMRegistryError(ValueError):
    """Raised when LLM config payload is invalid."""


class ThinkingLevel(str, Enum):
    """LLM thinking level options."""

    DISABLED = "disabled"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass
class ModelConfig:
    """Structured model selection config."""

    provider: str
    name: str
    options: Dict[str, Any]

    def __post_init__(self):
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("模型provider不能为空")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("模型name不能为空")

        if self.options is None:
            self.options = {}

        if not isinstance(self.options, dict):
            raise ValueError("模型options必须是对象")

        self.provider = self.provider.strip()
        self.name = self.name.strip()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMConfig:
    """Structured LLM runtime config."""

    model: ModelConfig
    fallback_models: List[ModelConfig]
    market_model: ModelConfig
    temperature: float = 0.5
    max_tokens: int = 4000
    batch_size: int = 10
    market_prompt_path: str = "./prompts/market_summary_prompt.md"
    analysis_prompt_path: str = "./prompts/analysis_prompt.md"
    min_weight_score: int = 50
    cache_ttl_minutes: int = 240
    cached_messages_hours: int = 24
    enable_debug_logging: bool = False

    def __post_init__(self):
        if not isinstance(self.model, ModelConfig):
            raise ValueError("llm_config.model必须是ModelConfig")

        if not isinstance(self.market_model, ModelConfig):
            raise ValueError("llm_config.market_model必须是ModelConfig")

        if self.fallback_models is None:
            self.fallback_models = []

        if not isinstance(self.fallback_models, list):
            raise ValueError("llm_config.fallback_models必须是列表")

        if not all(isinstance(model, ModelConfig) for model in self.fallback_models):
            raise ValueError("llm_config.fallback_models必须只包含ModelConfig")

        if not isinstance(self.temperature, (int, float)):
            raise ValueError("temperature必须是数字")
        self.temperature = float(self.temperature)

        if self.max_tokens <= 0:
            raise ValueError("max_tokens必须大于0")

        if self.batch_size <= 0:
            raise ValueError("batch_size必须大于0")

        if self.min_weight_score < 0 or self.min_weight_score > 100:
            raise ValueError("min_weight_score必须在0到100之间")

        if self.cache_ttl_minutes <= 0:
            raise ValueError("cache_ttl_minutes必须大于0")

        if self.cached_messages_hours <= 0:
            raise ValueError("cached_messages_hours必须大于0")

        if not isinstance(self.market_prompt_path, str) or not self.market_prompt_path.strip():
            raise ValueError("market_prompt_path不能为空")

        if not isinstance(self.analysis_prompt_path, str) or not self.analysis_prompt_path.strip():
            raise ValueError("analysis_prompt_path不能为空")


@dataclass(frozen=True)
class ProviderRecord:
    """Provider metadata used for auth and client construction."""

    name: str
    env_var: str
    base_url: str
    default_headers: Mapping[str, str]
    client_class: str
    conversation_header_name: Optional[str] = None


@dataclass(frozen=True)
class ModelRecord:
    """Static model metadata."""

    provider: str
    name: str
    supports_web_search: bool
    supports_x_search: bool
    supports_thinking_level: bool
    supports_responses_api: bool


@dataclass(frozen=True)
class ResolvedModelRuntime:
    """Resolved runtime metadata for a configured model."""

    config: ModelConfig
    provider: ProviderRecord
    model: ModelRecord

    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def name(self) -> str:
        return self.model.name

    @property
    def options(self) -> Dict[str, Any]:
        return dict(self.config.options)

    def to_dict(self) -> Dict[str, Any]:
        return self.config.to_dict()


THINKING_LEVEL_VALUES = tuple(level.value for level in ThinkingLevel)
SUPPORTED_MODEL_OPTIONS = {"thinking_level"}

LEGACY_MODEL_MIGRATIONS = {
    "kimi-for-coding": (
        "kimi-for-coding has been removed. Migrate to an explicit Kimi model: "
        "kimi-k2.5, kimi-k2-turbo-preview, or kimi-k2-thinking-turbo."
    )
}

PROVIDERS: Dict[str, ProviderRecord] = {
    "kimi": ProviderRecord(
        name="kimi",
        env_var="KIMI_API_KEY",
        base_url="https://api.kimi.com/coding/v1",
        default_headers={"User-Agent": "claude-code/1.0"},
        client_class="openai.OpenAI",
    ),
    "grok": ProviderRecord(
        name="grok",
        env_var="GROK_API_KEY",
        base_url="https://api.x.ai/v1",
        default_headers={"x-grok-conv-id": "<conversation-id>"},
        client_class="openai.OpenAI",
        conversation_header_name="x-grok-conv-id",
    ),
}

MODELS: Dict[str, Dict[str, ModelRecord]] = {
    "kimi": {
        "kimi-k2.5": ModelRecord(
            provider="kimi",
            name="kimi-k2.5",
            supports_web_search=True,
            supports_x_search=False,
            supports_thinking_level=True,
            supports_responses_api=False,
        ),
        "kimi-k2-turbo-preview": ModelRecord(
            provider="kimi",
            name="kimi-k2-turbo-preview",
            supports_web_search=True,
            supports_x_search=False,
            supports_thinking_level=False,
            supports_responses_api=False,
        ),
        "kimi-k2-thinking-turbo": ModelRecord(
            provider="kimi",
            name="kimi-k2-thinking-turbo",
            supports_web_search=True,
            supports_x_search=False,
            supports_thinking_level=False,
            supports_responses_api=False,
        ),
    },
    "grok": {
        "grok-4-1-fast-reasoning": ModelRecord(
            provider="grok",
            name="grok-4-1-fast-reasoning",
            supports_web_search=True,
            supports_x_search=True,
            supports_thinking_level=False,
            supports_responses_api=True,
        ),
        "grok-4-1-fast-non-reasoning": ModelRecord(
            provider="grok",
            name="grok-4-1-fast-non-reasoning",
            supports_web_search=True,
            supports_x_search=True,
            supports_thinking_level=False,
            supports_responses_api=True,
        ),
        "grok-4.20-reasoning": ModelRecord(
            provider="grok",
            name="grok-4.20-reasoning",
            supports_web_search=True,
            supports_x_search=True,
            supports_thinking_level=False,
            supports_responses_api=True,
        ),
        "grok-4.20-non-reasoning": ModelRecord(
            provider="grok",
            name="grok-4.20-non-reasoning",
            supports_web_search=True,
            supports_x_search=True,
            supports_thinking_level=False,
            supports_responses_api=True,
        ),
    },
}


def get_provider_record(provider: str) -> ProviderRecord:
    normalized_provider = (provider or "").strip()
    record = PROVIDERS.get(normalized_provider)
    if record is None:
        supported = ", ".join(sorted(PROVIDERS))
        raise LLMRegistryError(f"Unsupported LLM provider '{provider}'. Supported providers: {supported}.")
    return record


def get_model_record(provider: str, model_name: str) -> ModelRecord:
    normalized_name = (model_name or "").strip()
    if normalized_name in LEGACY_MODEL_MIGRATIONS:
        raise LLMRegistryError(LEGACY_MODEL_MIGRATIONS[normalized_name])

    provider_record = get_provider_record(provider)
    model_record = MODELS[provider_record.name].get(normalized_name)
    if model_record is None:
        supported = ", ".join(sorted(MODELS[provider_record.name]))
        raise LLMRegistryError(
            f"Unsupported model '{normalized_name}' for provider '{provider_record.name}'. "
            f"Supported models: {supported}."
        )
    return model_record


def validate_model_config(payload: Any, field_name: str) -> ModelConfig:
    if not isinstance(payload, dict):
        raise LLMRegistryError(
            f"llm_config.{field_name} must be an object with provider, name, and optional options."
        )

    unknown_keys = sorted(set(payload) - {"provider", "name", "options"})
    if unknown_keys:
        raise LLMRegistryError(
            f"llm_config.{field_name} contains unsupported keys: {', '.join(unknown_keys)}."
        )

    provider = payload.get("provider", "")
    name = payload.get("name", "")
    options = payload.get("options", {})

    if not isinstance(options, dict):
        raise LLMRegistryError(f"llm_config.{field_name}.options must be an object.")

    try:
        model_record = get_model_record(provider, name)
    except LLMRegistryError as exc:
        raise LLMRegistryError(f"llm_config.{field_name}: {exc}") from exc

    unknown_options = sorted(set(options) - SUPPORTED_MODEL_OPTIONS)
    if unknown_options:
        raise LLMRegistryError(
            f"llm_config.{field_name}.options contains unsupported keys: {', '.join(unknown_options)}."
        )

    normalized_options = dict(options)
    thinking_level = normalized_options.get("thinking_level")
    if thinking_level is not None:
        try:
            normalized_options["thinking_level"] = ThinkingLevel(thinking_level).value
        except ValueError as exc:
            supported_levels = ", ".join(THINKING_LEVEL_VALUES)
            raise LLMRegistryError(
                f"llm_config.{field_name}.options.thinking_level must be one of: {supported_levels}."
            ) from exc

        if not model_record.supports_thinking_level:
            raise LLMRegistryError(
                f"Model '{model_record.name}' does not support thinking_level. "
                f"Remove llm_config.{field_name}.options.thinking_level or choose a supported model."
            )

    return ModelConfig(provider=model_record.provider, name=model_record.name, options=normalized_options)


def validate_llm_config_payload(payload: Any) -> LLMConfig:
    if not isinstance(payload, dict):
        raise LLMRegistryError("llm_config must be an object.")

    if "summary_model" in payload:
        raise LLMRegistryError(
            "llm_config.summary_model has been removed. Use llm_config.market_model for market snapshots "
            "and llm_config.fallback_models for fallback analysis models."
        )

    required_fields = {"model", "fallback_models", "market_model"}
    missing_fields = sorted(field for field in required_fields if field not in payload)
    if missing_fields:
        raise LLMRegistryError(
            f"llm_config is missing required fields: {', '.join(missing_fields)}."
        )

    fallback_payloads = payload.get("fallback_models", [])
    if not isinstance(fallback_payloads, list):
        raise LLMRegistryError("llm_config.fallback_models must be a list.")

    return LLMConfig(
        model=validate_model_config(payload.get("model"), "model"),
        fallback_models=[
            validate_model_config(item, f"fallback_models[{index}]")
            for index, item in enumerate(fallback_payloads)
        ],
        market_model=validate_model_config(payload.get("market_model"), "market_model"),
        temperature=payload.get("temperature", 0.5),
        max_tokens=payload.get("max_tokens", 4000),
        batch_size=payload.get("batch_size", 10),
        market_prompt_path=payload.get("market_prompt_path", "./prompts/market_summary_prompt.md"),
        analysis_prompt_path=payload.get("analysis_prompt_path", "./prompts/analysis_prompt.md"),
        min_weight_score=payload.get("min_weight_score", 50),
        cache_ttl_minutes=payload.get("cache_ttl_minutes", 240),
        cached_messages_hours=payload.get("cached_messages_hours", 24),
        enable_debug_logging=payload.get("enable_debug_logging", False),
    )


def resolve_model_runtime(model_config: ModelConfig) -> ResolvedModelRuntime:
    """Resolve provider/model metadata for a validated model config."""

    provider_record = get_provider_record(model_config.provider)
    model_record = get_model_record(model_config.provider, model_config.name)
    return ResolvedModelRuntime(
        config=model_config,
        provider=provider_record,
        model=model_record,
    )


def registry_metadata() -> Dict[str, Any]:
    """Expose registry metadata for future consumers and tests."""

    return {
        "providers": PROVIDERS,
        "models": MODELS,
        "thinking_levels": THINKING_LEVEL_VALUES,
    }
