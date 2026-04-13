"""One-off embedding backfill runner for historical content."""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, cast

from ..config.manager import ConfigManager
from ..models import ContentItem
from ..storage.data_manager import DataManager
from ..utils.errors import UnsupportedBackendError
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingBackfillReport:
    """Summary of a historical embedding backfill run."""

    batches_processed: int = 0
    rows_examined: int = 0
    rows_embedded: int = 0
    rows_skipped: int = 0
    rows_failed: int = 0


class EmbeddingBackfillRunner:
    """Backfills missing embeddings in bounded batches."""

    def __init__(
        self,
        data_manager: DataManager,
        embedding_service: EmbeddingService,
        batch_size: int = 100,
        limit: Optional[int] = None,
        logger_: Optional[logging.Logger] = None,
    ):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive when provided")

        self.data_manager: DataManager = data_manager
        self.embedding_service: EmbeddingService = embedding_service
        self.batch_size: int = batch_size
        self.limit: Optional[int] = limit
        self.logger: logging.Logger = logger_ or logger

        if self.data_manager.backend != "postgres":
            raise UnsupportedBackendError(
                self.data_manager.backend, "embedding backfill runtime"
            )
        if not self.embedding_service.enabled:
            raise RuntimeError(
                "EmbeddingService不可用，请检查OPENAI_API_KEY和openai依赖"
            )

    def run(self) -> EmbeddingBackfillReport:
        report = EmbeddingBackfillReport()
        failed_ids: set[str] = set()

        while True:
            remaining = (
                None if self.limit is None else self.limit - report.rows_examined
            )
            if remaining is not None and remaining <= 0:
                break

            fetch_limit = (
                self.batch_size
                if remaining is None
                else min(self.batch_size, remaining)
            )
            batch = self.data_manager.get_content_items_missing_embeddings(
                limit=fetch_limit,
                exclude_ids=list(failed_ids),
            )
            if not batch:
                break

            report.batches_processed += 1
            report.rows_examined += len(batch)
            embedded_count, skipped_count, failed_count, failed_batch_ids = (
                self._process_batch(batch)
            )
            report.rows_embedded += embedded_count
            report.rows_skipped += skipped_count
            report.rows_failed += failed_count
            failed_ids.update(failed_batch_ids)

            self.logger.info(
                "Embedding backfill batch complete: batch=%s selected=%s embedded=%s skipped=%s failed=%s",
                report.batches_processed,
                len(batch),
                embedded_count,
                skipped_count,
                failed_count,
            )

        self.logger.info(
            "Embedding backfill finished: batches=%s examined=%s embedded=%s skipped=%s failed=%s",
            report.batches_processed,
            report.rows_examined,
            report.rows_embedded,
            report.rows_skipped,
            report.rows_failed,
        )
        return report

    def _process_batch(
        self, batch: Sequence[ContentItem]
    ) -> tuple[int, int, int, list[str]]:
        updates: list[tuple[str, list[float]]] = []
        failed_count = 0
        failed_ids: list[str] = []

        embeddings = self._generate_batch_embeddings(batch)
        for item, embedding in zip(batch, embeddings):
            if embedding is None:
                self.logger.warning("内容 %s 的Embedding生成失败，跳过该行", item.id)
                failed_count += 1
                failed_ids.append(item.id)
                continue

            updates.append((item.id, embedding))

        updated_count = self._persist_batch(updates)
        skipped_count = max(0, len(updates) - updated_count)
        return updated_count, skipped_count, failed_count, failed_ids

    def _generate_batch_embeddings(
        self,
        batch: Sequence[ContentItem],
    ) -> list[Optional[list[float]]]:
        if not batch:
            return []

        batch_generator = getattr(
            self.embedding_service, "generate_for_content_items", None
        )
        if callable(batch_generator):
            try:
                generated = cast(
                    Sequence[Optional[list[float]]], batch_generator(batch)
                )
                results = list(generated)
            except Exception as exc:
                self.logger.warning("批量Embedding生成异常，整批跳过: %s", exc)
                return [None for _ in batch]

            if len(results) != len(batch):
                self.logger.warning(
                    "批量Embedding返回数量不匹配，整批跳过: expected=%s actual=%s",
                    len(batch),
                    len(results),
                )
                return [None for _ in batch]

            return [cast(Optional[list[float]], result) for result in results]

        results: list[Optional[list[float]]] = []
        for item in batch:
            try:
                results.append(self.embedding_service.generate_for_content_item(item))
            except Exception as exc:
                self.logger.warning(
                    "内容 %s 的Embedding生成异常，跳过: %s", item.id, exc
                )
                results.append(None)
        return results

    def _persist_batch(self, updates: Sequence[tuple[str, list[float]]]) -> int:
        if not updates:
            return 0

        batch_timestamp = datetime.now(timezone.utc).isoformat()
        updated_count = 0
        lock = getattr(self.data_manager, "_lock", threading.RLock())

        with lock:
            with self.data_manager._get_connection() as conn:
                connection = cast(Any, conn)
                cursor = cast(Any, connection.cursor())

                for content_id, embedding in updates:
                    cursor.execute(
                        cast(
                            Any,
                            self.data_manager._sql("""
                            UPDATE content_items
                            SET embedding = CAST(? AS vector),
                                embedding_model = ?,
                                embedding_updated_at = ?
                            WHERE id = ?
                              AND embedding IS NULL
                            """),
                        ),
                        (
                            self.data_manager._pgvector_literal(embedding),
                            self.embedding_service.model,
                            batch_timestamp,
                            content_id,
                        ),
                    )
                    if cursor.rowcount > 0:
                        updated_count += 1

                connection.commit()

        return updated_count


def run_embedding_backfill_once(
    config_path: str = "./config.json",
    batch_size: int = 100,
    limit: Optional[int] = None,
) -> EmbeddingBackfillReport:
    """Build dependencies from config and execute one bounded backfill run."""

    config_manager = ConfigManager(config_path)
    _ = config_manager.load_config()

    storage_config = config_manager.get_storage_config()
    auth_config = config_manager.get_auth_config()
    semantic_search_config = config_manager.get_semantic_search_config()
    data_manager = DataManager(storage_config)

    try:
        embedding_service = EmbeddingService(
            api_key=auth_config.OPENAI_API_KEY,
            model=semantic_search_config.embedding_model,
            dimensions=semantic_search_config.embedding_dimensions,
        )
        runner = EmbeddingBackfillRunner(
            data_manager=data_manager,
            embedding_service=embedding_service,
            batch_size=batch_size,
            limit=limit,
        )
        return runner.run()
    finally:
        data_manager.close()
