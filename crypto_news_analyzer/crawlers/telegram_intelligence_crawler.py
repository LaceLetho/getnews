# pyright: reportIncompatibleMethodOverride=false, reportMissingImports=false
"""
Allowlisted Telegram intelligence collector.

This crawler uses Telethon only for explicitly configured chats. It never lists
dialogs, never joins chats, and keeps Telegram session material in environment
variables only.
"""

import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .data_source_interface import ConfigValidationError, CrawlError, DataSourceInterface
from ..domain.models import CheckpointStatus, IntelligenceCrawlCheckpoint, RawIntelligenceItem
from ..domain.repositories import IntelligenceRepository
from ..utils.logging import get_logger


SOURCE_TYPE = "telegram_group"
SESSION_ENV_VAR = "TELEGRAM_STRING_SESSION"


class TelegramFloodWait(Exception):
    """Internal wrapper carrying partial crawl results for FloodWait failures."""

    def __init__(self, seconds: Optional[int], partial_items: List[RawIntelligenceItem]):
        self.seconds = seconds
        self.partial_items = partial_items
        super().__init__(f"Telegram FloodWait encountered: {seconds} seconds")


class TelegramIntelligenceCrawler(DataSourceInterface):
    """Telethon-based collector for a single explicitly configured Telegram chat."""

    def __init__(self, time_window_hours: int, **kwargs: Any):
        self.time_window_hours = time_window_hours
        self.repository: Optional[IntelligenceRepository] = kwargs.get(
            "intelligence_repository", kwargs.get("repository")
        )
        self.logger = get_logger(__name__)

    def get_source_type(self) -> str:
        return SOURCE_TYPE

    def get_supported_config_fields(self) -> List[str]:
        return ["id", "name", "chat_id", "chat_username", "limit"]

    def get_required_config_fields(self) -> List[str]:
        return ["chat_id or chat_username"]

    def validate_config(self, config: Dict[str, Any]) -> bool:
        chat_id = config.get("chat_id")
        chat_username = config.get("chat_username")
        if chat_id in (None, "") and not str(chat_username or "").strip():
            raise ConfigValidationError(
                "telegram_group source requires chat_id or chat_username",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown Telegram Source"),
            )
        return True

    def crawl(self, config: Dict[str, Any]) -> List[RawIntelligenceItem]:
        self.validate_config(config)
        source_id = self._source_id(config)
        checkpoint = self._get_checkpoint(source_id)
        since = self._crawl_since(checkpoint)

        try:
            items = self._run_async(self._fetch_messages(config, source_id, checkpoint, since))
            self._save_checkpoint(
                source_id=source_id,
                status=CheckpointStatus.OK.value,
                items=items,
                since=since,
            )
            return items
        except TelegramFloodWait as exc:
            self.logger.warning(
                "Telegram source %s rate limited by FloodWait for %s seconds",
                source_id,
                exc.seconds,
            )
            self._save_checkpoint(
                source_id=source_id,
                status=CheckpointStatus.RATE_LIMITED.value,
                items=exc.partial_items,
                since=since,
                error_message=f"FloodWait: {exc.seconds} seconds",
            )
            return exc.partial_items
        except Exception as exc:
            error_msg = f"Telegram crawl failed for {source_id}: {exc}"
            self.logger.error(error_msg)
            self._save_error_checkpoint(source_id, error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type(), source_name=source_id) from exc

    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_items: List[RawIntelligenceItem] = []
        results: List[Dict[str, Any]] = []

        for config in sources:
            source_id = "unknown"
            try:
                self.validate_config(config)
                source_id = self._source_id(config)
                items = self.crawl(config)
                all_items.extend(items)
                checkpoint = self._get_checkpoint(source_id)
                results.append(
                    {
                        "source_id": source_id,
                        "status": checkpoint.status if checkpoint else CheckpointStatus.OK.value,
                        "items_count": len(items),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "source_id": source_id,
                        "status": CheckpointStatus.ERROR.value,
                        "items_count": 0,
                        "error": str(exc),
                    }
                )

        return {"items": all_items, "results": results, "total_items": len(all_items)}

    async def _fetch_messages(
        self,
        config: Dict[str, Any],
        source_id: str,
        checkpoint: Optional[IntelligenceCrawlCheckpoint],
        since: datetime,
    ) -> List[RawIntelligenceItem]:
        TelegramClient, StringSession, flood_wait_error = self._load_telethon_modules()
        api_id, api_hash, string_session = self._load_credentials()
        entity = self._chat_entity(config)
        client = TelegramClient(StringSession(string_session), api_id, api_hash)
        items: List[RawIntelligenceItem] = []

        try:
            await client.start()
            iter_kwargs: Dict[str, Any] = {}
            if config.get("limit") is not None:
                iter_kwargs["limit"] = int(config["limit"])
            use_since_cutoff = True
            if checkpoint and checkpoint.last_external_id:
                try:
                    iter_kwargs["min_id"] = int(checkpoint.last_external_id)
                    use_since_cutoff = False
                except (TypeError, ValueError):
                    pass

            try:
                async for message in client.iter_messages(entity, **iter_kwargs):
                    if use_since_cutoff and self._message_is_before_cutoff(message, since):
                        break
                    item = self._message_to_raw_item(message, source_id)
                    if item is not None:
                        items.append(item)
            except Exception as exc:
                if self._is_flood_wait(exc, flood_wait_error):
                    raise TelegramFloodWait(getattr(exc, "seconds", None), items) from exc
                raise
        finally:
            disconnect = getattr(client, "disconnect", None)
            if disconnect is not None:
                result = disconnect()
                if asyncio.iscoroutine(result):
                    await result

        return items

    def _message_to_raw_item(self, message: Any, source_id: str) -> Optional[RawIntelligenceItem]:
        raw_text = getattr(message, "message", None)
        if raw_text is None:
            raw_text = getattr(message, "text", None)
        if raw_text is None or raw_text == "":
            return None

        now = datetime.utcnow()
        external_id = str(getattr(message, "id", "")) or None
        published_at = getattr(message, "date", None)
        content_hash = hashlib.sha256(str(raw_text).encode()).hexdigest()[:16]
        return RawIntelligenceItem.create(
            source_type=self.get_source_type(),
            source_id=source_id,
            external_id=external_id,
            chat_id=source_id,
            raw_text=str(raw_text),
            content_hash=content_hash,
            published_at=published_at,
            expires_at=now + timedelta(days=30),
        )

    def _message_is_before_cutoff(self, message: Any, cutoff: datetime) -> bool:
        published_at = getattr(message, "date", None)
        if not isinstance(published_at, datetime):
            return False
        if published_at.tzinfo is not None:
            published_at = published_at.replace(tzinfo=None)
        if cutoff.tzinfo is not None:
            cutoff = cutoff.replace(tzinfo=None)
        return published_at < cutoff

    def _source_id(self, config: Dict[str, Any]) -> str:
        return str(config.get("chat_id") or config.get("chat_username")).strip()

    def _chat_entity(self, config: Dict[str, Any]) -> Any:
        return config.get("chat_id") if config.get("chat_id") not in (None, "") else config["chat_username"]

    def _crawl_since(self, checkpoint: Optional[IntelligenceCrawlCheckpoint]) -> datetime:
        if checkpoint and checkpoint.last_crawled_at:
            return checkpoint.last_crawled_at
        return datetime.utcnow() - timedelta(hours=self.time_window_hours)

    def _get_checkpoint(self, source_id: str) -> Optional[IntelligenceCrawlCheckpoint]:
        if self.repository is None:
            return None
        return self.repository.get_checkpoint(self.get_source_type(), source_id)

    def _save_checkpoint(
        self,
        source_id: str,
        status: str,
        items: List[RawIntelligenceItem],
        since: datetime,
        error_message: Optional[str] = None,
    ) -> None:
        if self.repository is None:
            self.logger.warning("No intelligence repository configured; checkpoint not saved")
            return

        now = datetime.utcnow()
        latest_item = self._latest_item(items)
        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type=self.get_source_type(),
            source_id=source_id,
            last_crawled_at=now,
            last_external_id=latest_item.external_id if latest_item else None,
            checkpoint_data={"since": since.isoformat(), "items_count": len(items)},
            status=status,
            error_message=error_message,
        )
        self.repository.save_checkpoint(checkpoint)

    def _save_error_checkpoint(self, source_id: str, error_message: str) -> None:
        if self.repository is None:
            return
        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type=self.get_source_type(),
            source_id=source_id,
            last_crawled_at=datetime.utcnow(),
            checkpoint_data={},
            status=CheckpointStatus.ERROR.value,
            error_message=error_message,
        )
        self.repository.save_checkpoint(checkpoint)

    def _latest_item(self, items: List[RawIntelligenceItem]) -> Optional[RawIntelligenceItem]:
        if not items:
            return None
        return max(items, key=lambda item: int(item.external_id or 0))

    def _load_credentials(self) -> Tuple[int, str, str]:
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        string_session = os.getenv(SESSION_ENV_VAR)
        missing = [
            name
            for name, value in (
                ("TELEGRAM_API_ID", api_id),
                ("TELEGRAM_API_HASH", api_hash),
                (SESSION_ENV_VAR, string_session),
            )
            if not value
        ]
        if missing:
            raise ConfigValidationError(
                f"Missing Telegram credential environment variables: {missing}",
                source_type=self.get_source_type(),
            )
        return int(str(api_id)), str(api_hash), str(string_session)

    def _load_telethon_modules(self) -> Tuple[Any, Any, Any]:
        try:
            from telethon import TelegramClient  # type: ignore
            from telethon.errors import FloodWaitError  # type: ignore
            from telethon.sessions import StringSession  # type: ignore

            return TelegramClient, StringSession, FloodWaitError
        except ImportError as exc:
            raise ConfigValidationError(
                "Telethon is required at runtime for telegram_group crawling",
                source_type=self.get_source_type(),
            ) from exc

    def _is_flood_wait(self, exc: Exception, flood_wait_error: Any) -> bool:
        if flood_wait_error is not None and isinstance(exc, flood_wait_error):
            return True
        return exc.__class__.__name__ == "FloodWaitError" and hasattr(exc, "seconds")

    def _run_async(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        raise CrawlError(
            "TelegramIntelligenceCrawler cannot run inside an existing event loop",
            source_type=self.get_source_type(),
        )
