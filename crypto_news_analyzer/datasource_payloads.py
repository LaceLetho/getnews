from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Union
from urllib.parse import urlparse

from .domain.models import DataSource, DataSourceType
from .models import RESTAPISource, RSSSource, XSource


RuntimeSource = Union[RSSSource, XSource, RESTAPISource]

SUPPORTED_DATASOURCE_TYPES = {item.value for item in DataSourceType}
REQUIRED_REST_API_MAPPING_FIELDS = ("title_field", "content_field", "url_field", "time_field")
MAX_DATASOURCE_TAGS = 16
MAX_DATASOURCE_TAG_LENGTH = 32
TELEGRAM_INLINE_SECRET_KEY_TOKENS = (
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "apikey",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "bearer",
    "secret",
    "password",
    "passwd",
    "session",
    "auth",
)
TELEGRAM_INLINE_SECRET_VALUE_TOKENS = ("bearer ", "token", "api_key", "apikey", "cookie")


class DataSourcePayloadValidationError(ValueError):
    pass


class TelegramDataSourceInputError(ValueError):
    pass


def normalize_datasource_tags(tags: List[str] | None) -> List[str]:
    normalized_tags = {
        str(tag).strip().lower()
        for tag in (tags or [])
        if str(tag).strip()
    }
    return sorted(normalized_tags)


def validate_datasource_tags(tags: List[str] | None) -> List[str]:
    normalized_tags = normalize_datasource_tags(tags)
    if len(normalized_tags) > MAX_DATASOURCE_TAGS:
        raise DataSourcePayloadValidationError(
            f"tags cannot contain more than {MAX_DATASOURCE_TAGS} unique values"
        )

    for tag in normalized_tags:
        if len(tag) > MAX_DATASOURCE_TAG_LENGTH:
            raise DataSourcePayloadValidationError(
                f"each tag must be at most {MAX_DATASOURCE_TAG_LENGTH} characters"
            )

    return normalized_tags


@dataclass(frozen=True)
class ValidatedDataSourcePayload:
    source_type: str
    name: str
    tags: List[str]
    config_payload: Dict[str, Any]

    def to_domain_datasource(self) -> DataSource:
        return DataSource.create(
            name=self.name,
            source_type=self.source_type,
            tags=self.tags,
            config_payload=self.config_payload,
        )

    def to_runtime_source(self) -> RuntimeSource:
        return runtime_source_from_record(self)


def validate_datasource_create_payload(payload: Mapping[str, Any]) -> ValidatedDataSourcePayload:
    if not isinstance(payload, Mapping):
        raise DataSourcePayloadValidationError("Datasource payload must be an object")

    raw_source_type = payload.get("source_type")
    source_type = str(raw_source_type or "").strip().lower()
    if source_type not in SUPPORTED_DATASOURCE_TYPES:
        raise DataSourcePayloadValidationError(
            "source_type must be one of: rss, x, rest_api"
        )

    raw_tags = payload.get("tags", [])
    if raw_tags is None:
        raw_tags = []
    if not isinstance(raw_tags, list):
        raise DataSourcePayloadValidationError("tags must be a list of strings")

    raw_config_payload = payload.get("config_payload")
    if not isinstance(raw_config_payload, Mapping):
        raise DataSourcePayloadValidationError("config_payload must be an object")

    config_payload = validate_datasource_config_payload(source_type, raw_config_payload)
    top_level_name = str(payload.get("name") or "").strip()
    if top_level_name and top_level_name != config_payload["name"]:
        raise DataSourcePayloadValidationError(
            "name must match config_payload.name when both are provided"
        )

    return ValidatedDataSourcePayload(
        source_type=source_type,
        name=config_payload["name"],
        tags=validate_datasource_tags(raw_tags),
        config_payload=config_payload,
    )


def validate_datasource_config_payload(source_type: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    normalized_source_type = str(source_type or "").strip().lower()
    if normalized_source_type == DataSourceType.RSS.value:
        return _validate_rss_payload(payload)
    if normalized_source_type == DataSourceType.X.value:
        return _validate_x_payload(payload)
    if normalized_source_type == DataSourceType.REST_API.value:
        return _validate_rest_api_payload(payload)

    raise DataSourcePayloadValidationError(
        f"Unsupported datasource type: {source_type}"
    )


def runtime_source_from_record(record: Union[DataSource, ValidatedDataSourcePayload, Mapping[str, Any]]) -> RuntimeSource:
    if isinstance(record, ValidatedDataSourcePayload):
        source_type = record.source_type
        config_payload = record.config_payload
    elif isinstance(record, DataSource):
        source_type = record.source_type
        config_payload = record.config_payload
    elif isinstance(record, Mapping):
        source_type = str(record.get("source_type") or "").strip().lower()
        raw_config_payload = record.get("config_payload")
        if not isinstance(raw_config_payload, Mapping):
            raise DataSourcePayloadValidationError("config_payload must be an object")
        config_payload = dict(raw_config_payload)
    else:
        raise DataSourcePayloadValidationError("Unsupported datasource record type")

    validated_payload = validate_datasource_config_payload(source_type, config_payload)

    if source_type == DataSourceType.RSS.value:
        return RSSSource(
            name=validated_payload["name"],
            url=validated_payload["url"],
            description=validated_payload.get("description", ""),
        )
    if source_type == DataSourceType.X.value:
        return XSource(
            name=validated_payload["name"],
            url=validated_payload["url"],
            type=validated_payload["type"],
        )
    if source_type == DataSourceType.REST_API.value:
        return RESTAPISource(
            name=validated_payload["name"],
            endpoint=validated_payload["endpoint"],
            method=validated_payload["method"],
            headers=validated_payload.get("headers", {}),
            params=validated_payload.get("params", {}),
            response_mapping=validated_payload["response_mapping"],
        )

    raise DataSourcePayloadValidationError(
        f"Unsupported datasource type: {source_type}"
    )


def parse_telegram_datasource_command_json(command_text: str, command_name: str) -> Dict[str, Any]:
    raw_command_text = str(command_text or "").strip()
    prefix = str(command_name or "").strip()
    if not raw_command_text.startswith(prefix):
        raise TelegramDataSourceInputError(
            f"❌ 参数错误\n\n请输入 {prefix} 后紧跟单个 JSON 对象。"
        )

    _, separator, json_payload = raw_command_text.partition(" ")
    if not separator or not json_payload.strip():
        raise TelegramDataSourceInputError(
            f"❌ 参数错误\n\n请输入 {prefix} 后紧跟单个 JSON 对象。"
        )

    try:
        parsed_payload = json.loads(json_payload)
    except json.JSONDecodeError as exc:
        raise TelegramDataSourceInputError(
            f"❌ 参数错误\n\n请输入有效的 JSON 对象，例如：{prefix} {{\"source_type\":\"rss\",\"config_payload\":{{...}}}}"
        ) from exc

    if not isinstance(parsed_payload, dict):
        raise TelegramDataSourceInputError(
            "❌ 参数错误\n\nTelegram 数据源命令仅支持单个 JSON 对象作为参数。"
        )

    return parsed_payload


def validate_telegram_datasource_create_payload(payload: Mapping[str, Any]) -> ValidatedDataSourcePayload:
    raw_source_type = str(payload.get("source_type") or "").strip().lower()
    raw_config_payload = payload.get("config_payload")
    if raw_source_type == DataSourceType.REST_API.value and isinstance(raw_config_payload, Mapping):
        _reject_telegram_rest_api_inline_auth(raw_config_payload)
        raw_headers = raw_config_payload.get("headers", {})
        raw_params = raw_config_payload.get("params", {})
        if isinstance(raw_headers, Mapping):
            _reject_telegram_inline_secrets(raw_headers, container_name="headers")
        if isinstance(raw_params, Mapping):
            _reject_telegram_inline_secrets(raw_params, container_name="params")

    validated_payload = validate_datasource_create_payload(payload)
    if validated_payload.source_type != DataSourceType.REST_API.value:
        return validated_payload

    config_payload = validated_payload.config_payload
    _reject_telegram_inline_secrets(config_payload.get("headers", {}), container_name="headers")
    _reject_telegram_inline_secrets(config_payload.get("params", {}), container_name="params")
    return validated_payload


def _validate_rss_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = _require_non_empty_string(payload, field_name="name", source_type="rss")
    url = _require_http_url(payload, field_name="url", source_type="rss")
    description = payload.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise DataSourcePayloadValidationError("rss.description must be a string")

    return {"name": name, "url": url, "description": description}


def _validate_x_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = _require_non_empty_string(payload, field_name="name", source_type="x")
    url = _require_non_empty_string(payload, field_name="url", source_type="x")
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in {"x.com", "www.x.com"}:
        raise DataSourcePayloadValidationError("x.url must be a valid https://x.com URL")

    source_subtype = _require_non_empty_string(payload, field_name="type", source_type="x")
    if source_subtype not in {"list", "timeline"}:
        raise DataSourcePayloadValidationError("x.type must be one of: list, timeline")

    return {"name": name, "url": url, "type": source_subtype}


def _validate_rest_api_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = _require_non_empty_string(payload, field_name="name", source_type="rest_api")
    endpoint = _require_http_url(payload, field_name="endpoint", source_type="rest_api")
    method = _require_non_empty_string(payload, field_name="method", source_type="rest_api").upper()
    if method not in {"GET", "POST", "PUT", "DELETE"}:
        raise DataSourcePayloadValidationError(
            "rest_api.method must be one of: GET, POST, PUT, DELETE"
        )

    response_mapping = payload.get("response_mapping")
    if not isinstance(response_mapping, Mapping):
        raise DataSourcePayloadValidationError("rest_api.response_mapping must be an object")

    normalized_response_mapping: Dict[str, str] = {}
    for field_name in REQUIRED_REST_API_MAPPING_FIELDS:
        value = response_mapping.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise DataSourcePayloadValidationError(
                f"rest_api.response_mapping.{field_name} is required"
            )
        normalized_response_mapping[field_name] = value.strip()

    headers = _normalize_object_field(payload, field_name="headers", source_type="rest_api")
    params = _normalize_object_field(payload, field_name="params", source_type="rest_api")

    return {
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "headers": headers,
        "params": params,
        "response_mapping": normalized_response_mapping,
    }


def _normalize_object_field(
    payload: Mapping[str, Any], *, field_name: str, source_type: str
) -> Dict[str, Any]:
    value = payload.get(field_name, {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DataSourcePayloadValidationError(f"{source_type}.{field_name} must be an object")
    return dict(value)


def _require_non_empty_string(payload: Mapping[str, Any], *, field_name: str, source_type: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise DataSourcePayloadValidationError(f"{source_type}.{field_name} is required")
    return value.strip()


def _require_http_url(payload: Mapping[str, Any], *, field_name: str, source_type: str) -> str:
    url = _require_non_empty_string(payload, field_name=field_name, source_type=source_type)
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise DataSourcePayloadValidationError(f"{source_type}.{field_name} must be a valid http(s) URL")
    return url


def _reject_telegram_inline_secrets(container: Mapping[str, Any], *, container_name: str) -> None:
    if not isinstance(container, Mapping):
        return

    for raw_key, raw_value in container.items():
        normalized_key = str(raw_key).strip().lower().replace("_", "-")
        normalized_value = str(raw_value).strip().lower()
        if any(token in normalized_key for token in TELEGRAM_INLINE_SECRET_KEY_TOKENS):
            raise TelegramDataSourceInputError(
                f"❌ 无效输入\n\nTelegram 不支持在 rest_api.{container_name} 中内联提交敏感认证字段: {raw_key}"
            )
        if any(token in normalized_value for token in TELEGRAM_INLINE_SECRET_VALUE_TOKENS):
            raise TelegramDataSourceInputError(
                f"❌ 无效输入\n\nTelegram 不支持在 rest_api.{container_name} 中内联提交敏感认证值: {raw_key}"
            )


def _reject_telegram_rest_api_inline_auth(payload: Mapping[str, Any]) -> None:
    if "auth" in payload:
        raise TelegramDataSourceInputError(
            "❌ 无效输入\n\nTelegram 不支持在 rest_api 数据源中内联提交认证信息，请改用服务端密钥配置。"
        )
