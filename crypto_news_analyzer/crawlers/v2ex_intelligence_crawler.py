"""
V2EX 官方 API 智能采集器。

仅使用 V2EX 官方 API v1/v2 拉取 allowlist 节点的主题与回复，
不进行 HTML 抓取或页面解析。
"""

from __future__ import annotations

import hashlib
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..domain.models import IntelligenceCrawlCheckpoint, RawIntelligenceItem, CheckpointStatus
from ..utils.logging import get_logger
from .data_source_interface import ConfigValidationError, CrawlError, DataSourceInterface


class V2EXIntelligenceCrawler(DataSourceInterface):
    """V2EX 官方 API 采集器。"""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN,zh;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    V1_BASE_URL = "https://www.v2ex.com/api/"
    V2_BASE_URL = "https://www.v2ex.com/api/v2/"

    def __init__(
        self,
        time_window_hours: int,
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs: Any,
    ):
        self.time_window_hours = time_window_hours
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_kwargs = dict(kwargs)
        self.intelligence_repository = kwargs.get("intelligence_repository") or kwargs.get("repository")
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.last_rate_limit_remaining: Optional[int] = None
        self.last_rate_limit_reset: Optional[datetime] = None

    def get_source_type(self) -> str:
        return "v2ex"

    def get_supported_config_fields(self) -> List[str]:
        return [
            "name",
            "api_version",
            "node_allowlist",
            "pat_env_var_name",
            "page_size",
            "timeout",
            "max_retries",
            "description",
        ]

    def get_required_config_fields(self) -> List[str]:
        return ["name", "api_version", "node_allowlist"]

    def validate_config(self, config: Dict[str, Any]) -> bool:
        missing = [field for field in self.get_required_config_fields() if field not in config]
        if missing:
            raise ConfigValidationError(
                f"缺少必需的配置字段: {missing}",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )

        api_version = str(config.get("api_version", "")).strip().lower()
        if api_version not in {"v1", "v2"}:
            raise ConfigValidationError(
                "api_version must be 'v1' or 'v2'",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )

        node_allowlist = config.get("node_allowlist")
        if not isinstance(node_allowlist, list):
            raise ConfigValidationError(
                "node_allowlist must be a list",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )

        if not node_allowlist:
            raise ConfigValidationError(
                "node_allowlist must contain at least one node",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )

        normalized_nodes = [str(node).strip() for node in node_allowlist if str(node).strip()]
        if len(normalized_nodes) != len(node_allowlist):
            raise ConfigValidationError(
                "node_allowlist entries must be non-empty strings",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )

        pat_env_var_name = config.get("pat_env_var_name")
        if pat_env_var_name is not None:
            pat_env_var_name = str(pat_env_var_name).strip()
            if not pat_env_var_name.isidentifier() or not pat_env_var_name.upper() == pat_env_var_name:
                raise ConfigValidationError(
                    "pat_env_var_name must be an environment variable name, not a PAT value",
                    source_type=self.get_source_type(),
                    source_name=str(config.get("name", "Unknown")),
                )

        if api_version == "v2" and pat_env_var_name is not None:
            if not pat_env_var_name:
                raise ConfigValidationError(
                    "pat_env_var_name must be a non-empty environment variable name",
                    source_type=self.get_source_type(),
                    source_name=str(config.get("name", "Unknown")),
                )

        return True

    def crawl(self, config: Dict[str, Any]) -> List[Any]:
        self.validate_config(config)

        api_version = str(config["api_version"]).strip().lower()
        page_size = int(config.get("page_size", 20))
        cutoff_floor = datetime.utcnow() - timedelta(hours=max(self.time_window_hours, 24))
        repository = self._resolve_repository(config)
        node_allowlist = [str(node).strip() for node in config["node_allowlist"] if str(node).strip()]
        pat_env_var_name = str(config.get("pat_env_var_name") or "V2EX_PAT").strip()
        pat_token = os.environ.get(pat_env_var_name, "") if api_version == "v2" else ""

        all_items: List[RawIntelligenceItem] = []
        seen_external_ids: set[str] = set()

        for node_name in node_allowlist:
            checkpoint = repository.get_checkpoint(self.get_source_type(), node_name) if repository else None
            node_cutoff = checkpoint.last_crawled_at if checkpoint and checkpoint.last_crawled_at else cutoff_floor

            node_items, node_state = self._crawl_node(
                api_version=api_version,
                node_name=node_name,
                node_cutoff=node_cutoff,
                page_size=page_size,
                pat_token=pat_token,
                seen_external_ids=seen_external_ids,
            )
            all_items.extend(node_items)

            if repository is not None:
                self._save_checkpoint(
                    repository=repository,
                    node_name=node_name,
                    node_state=node_state,
                    api_version=api_version,
                )

        return all_items

    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        items: List[RawIntelligenceItem] = []
        results: List[Dict[str, Any]] = []
        for source in sources:
            try:
                crawled = self.crawl(source)
                items.extend(crawled)
                results.append({"source_name": source.get("name", "Unknown"), "status": "success", "item_count": len(crawled), "error_message": None})
            except Exception as exc:
                results.append({"source_name": source.get("name", "Unknown"), "status": "error", "item_count": 0, "error_message": str(exc)})
        return {"items": items, "results": results, "total_items": len(items)}

    def cleanup(self) -> None:
        if hasattr(self, "session"):
            self.session.close()

    def _resolve_repository(self, config: Dict[str, Any]) -> Optional[Any]:
        repository = config.get("intelligence_repository") or getattr(self, "intelligence_repository", None)
        if repository is not None and not all(
            hasattr(repository, method) for method in ("save_checkpoint", "get_checkpoint")
        ):
            raise ConfigValidationError(
                "intelligence_repository must implement IntelligenceRepository",
                source_type=self.get_source_type(),
                source_name=str(config.get("name", "Unknown")),
            )
        return repository

    def _crawl_node(
        self,
        api_version: str,
        node_name: str,
        node_cutoff: datetime,
        page_size: int,
        pat_token: str,
        seen_external_ids: set[str],
    ) -> Tuple[List[RawIntelligenceItem], Dict[str, Any]]:
        items: List[RawIntelligenceItem] = []
        latest_crawled_at = node_cutoff
        latest_external_id: Optional[str] = None
        rate_limited = False

        page = 1
        while True:
            topics, headers = self._fetch_topics(api_version, node_name, page, page_size, pat_token)
            self._update_rate_limit_state(headers)
            if not topics:
                break
            rate_limited_after_topics = self._rate_limit_exhausted()

            stop_pagination = False
            for topic in topics:
                topic_item, topic_created_at = self._build_topic_item(node_name, topic)
                if topic_item is None:
                    continue

                topic_key = f"topic:{topic_item.external_id}"
                if topic_key in seen_external_ids:
                    continue

                if topic_created_at and topic_created_at < node_cutoff:
                    stop_pagination = True
                    continue

                seen_external_ids.add(topic_key)
                items.append(topic_item)
                latest_crawled_at = max(latest_crawled_at, topic_created_at or latest_crawled_at)
                latest_external_id = topic_item.external_id

                if rate_limited_after_topics:
                    rate_limited = True
                    stop_pagination = True
                    break

                replies = self._fetch_all_replies(api_version, topic, page_size, pat_token)
                for reply in replies:
                    reply_item, reply_created_at = self._build_reply_item(node_name, topic, reply)
                    if reply_item is None:
                        continue
                    reply_key = f"reply:{reply_item.external_id}"
                    if reply_key in seen_external_ids:
                        continue
                    if reply_created_at and reply_created_at < node_cutoff:
                        continue
                    seen_external_ids.add(reply_key)
                    items.append(reply_item)
                    latest_crawled_at = max(latest_crawled_at, reply_created_at or latest_crawled_at)
                    latest_external_id = reply_item.external_id
                if self._rate_limit_exhausted():
                    rate_limited = True
                    stop_pagination = True
                    break

            if stop_pagination:
                break
            if api_version == "v1" and len(topics) < page_size:
                break
            page += 1

        if self.last_rate_limit_remaining == 0:
            rate_limited = True

        return items, {
            "last_crawled_at": latest_crawled_at,
            "last_external_id": latest_external_id,
            "rate_limited": rate_limited,
        }

    def _fetch_topics(
        self,
        api_version: str,
        node_name: str,
        page: int,
        page_size: int,
        pat_token: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        if api_version == "v1":
            url = f"{self.V1_BASE_URL}topics/show.json"
            params = {"node_name": node_name, "page": page, "page_size": page_size}
            payload, response = self._request_json(url, params=params)
        else:
            url = f"{self.V2_BASE_URL}nodes/{node_name}/topics"
            headers = self._auth_headers(pat_token)
            payload, response = self._request_json(url, headers=headers, params={"p": page})
        return self._extract_items(payload), dict(response.headers)

    def _fetch_all_replies(
        self,
        api_version: str,
        topic: Dict[str, Any],
        page_size: int,
        pat_token: str,
    ) -> List[Dict[str, Any]]:
        topic_id = self._extract_id(topic)
        if not topic_id:
            return []

        replies: List[Dict[str, Any]] = []
        page = 1
        while True:
            if api_version == "v1":
                url = f"{self.V1_BASE_URL}replies/show.json"
                params = {"topic_id": topic_id, "page": page, "page_size": page_size}
                payload, response = self._request_json(url, params=params)
            else:
                url = f"{self.V2_BASE_URL}topics/{topic_id}/replies"
                headers = self._auth_headers(pat_token)
                payload, response = self._request_json(url, headers=headers, params={"p": page})
            self._update_rate_limit_state(dict(response.headers))
            if self._rate_limit_exhausted():
                break
            page_items = self._extract_items(payload)
            if not page_items:
                break
            replies.extend(page_items)
            if api_version == "v1" and len(page_items) < page_size:
                break
            if api_version != "v1":
                break
            page += 1
        return replies

    def _request_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[Any, requests.Response]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                self._update_rate_limit_state(dict(response.headers))
                if getattr(response, "status_code", None) == 429:
                    return [], response
                response.raise_for_status()
                return response.json(), response
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    raise CrawlError(f"V2EX API request failed: {exc}") from exc
                time.sleep((2 ** attempt) + random.uniform(0, 1))
        raise CrawlError(f"V2EX API request failed: {last_error}")

    def _auth_headers(self, pat_token: str) -> Dict[str, str]:
        if not pat_token:
            raise ConfigValidationError(
                "v2 api_version requires a PAT in the configured environment variable",
                source_type=self.get_source_type(),
            )
        return {"Authorization": f"Bearer {pat_token}"}

    def _update_rate_limit_state(self, headers: Dict[str, str]) -> None:
        remaining = headers.get("X-Rate-Limit-Remaining")
        reset = headers.get("X-Rate-Limit-Reset")
        if remaining is not None:
            try:
                self.last_rate_limit_remaining = int(remaining)
            except ValueError:
                self.last_rate_limit_remaining = None
        if reset is not None:
            try:
                reset_ts = int(reset)
                self.last_rate_limit_reset = datetime.utcfromtimestamp(reset_ts)
            except ValueError:
                self.last_rate_limit_reset = None

    def _rate_limit_exhausted(self) -> bool:
        return self.last_rate_limit_remaining == 0

    def _build_topic_item(self, node_name: str, topic: Dict[str, Any]) -> Tuple[Optional[RawIntelligenceItem], Optional[datetime]]:
        topic_id = self._extract_id(topic)
        raw_text = self._extract_raw_text(topic)
        published_at = self._extract_datetime(topic)
        if not topic_id or not raw_text:
            return None, published_at

        now = datetime.utcnow()
        return (
            RawIntelligenceItem.create(
                source_type=self.get_source_type(),
                source_id=node_name,
                external_id=str(topic_id),
                source_url=f"https://www.v2ex.com/t/{topic_id}",
                topic_id=str(topic_id),
                raw_text=raw_text,
                content_hash=hashlib.sha256(raw_text.encode()).hexdigest()[:16],
                published_at=published_at,
                expires_at=now + timedelta(days=30),
            ),
            published_at,
        )

    def _build_reply_item(
        self,
        node_name: str,
        topic: Dict[str, Any],
        reply: Dict[str, Any],
    ) -> Tuple[Optional[RawIntelligenceItem], Optional[datetime]]:
        reply_id = self._extract_id(reply)
        topic_id = self._extract_id(topic)
        raw_text = self._extract_raw_text(reply)
        published_at = self._extract_datetime(reply)
        if not reply_id or not topic_id or not raw_text:
            return None, published_at

        now = datetime.utcnow()
        return (
            RawIntelligenceItem.create(
                source_type=self.get_source_type(),
                source_id=node_name,
                external_id=str(reply_id),
                source_url=f"https://www.v2ex.com/t/{topic_id}",
                topic_id=str(topic_id),
                raw_text=raw_text,
                content_hash=hashlib.sha256(raw_text.encode()).hexdigest()[:16],
                published_at=published_at,
                expires_at=now + timedelta(days=30),
            ),
            published_at,
        )

    def _save_checkpoint(
        self,
        repository: Any,
        node_name: str,
        node_state: Dict[str, Any],
        api_version: str,
    ) -> None:
        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type=self.get_source_type(),
            source_id=node_name,
            last_crawled_at=node_state.get("last_crawled_at"),
            last_external_id=node_state.get("last_external_id"),
            checkpoint_data={
                "api_version": api_version,
                "node_name": node_name,
                "rate_limit_remaining": self.last_rate_limit_remaining,
                "rate_limit_reset": self.last_rate_limit_reset.isoformat() if self.last_rate_limit_reset else None,
            },
            status=CheckpointStatus.RATE_LIMITED.value if node_state.get("rate_limited") else CheckpointStatus.OK.value,
        )
        repository.save_checkpoint(checkpoint)

    def _extract_items(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("topics", "replies", "items", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [payload]
        return []

    def _extract_id(self, item: Dict[str, Any]) -> Optional[str]:
        for key in ("id", "topic_id", "reply_id"):
            value = item.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    def _extract_raw_text(self, item: Dict[str, Any]) -> str:
        for key in ("content_raw", "content", "text", "content_rendered", "body"):
            value = item.get(key)
            if value is not None:
                return str(value)
        title = item.get("title")
        return str(title) if title is not None else ""

    def _extract_datetime(self, item: Dict[str, Any]) -> Optional[datetime]:
        for key in ("created", "created_at", "updated", "updated_at", "last_modified"):
            value = item.get(key)
            parsed = self._parse_datetime(value)
            if parsed:
                return parsed
        return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(float(value))
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            return None
