"""Semantic search services and orchestration helpers."""

from crypto_news_analyzer.semantic_search.embedding_service import EmbeddingService

__all__ = [
    "EmbeddingBackfillReport",
    "EmbeddingBackfillRunner",
    "EmbeddingService",
    "run_embedding_backfill_once",
]


def __getattr__(name: str):
    """Lazy-import backfill runner to avoid circular import with storage.data_manager."""
    if name in {"EmbeddingBackfillReport", "EmbeddingBackfillRunner", "run_embedding_backfill_once"}:
        from crypto_news_analyzer.semantic_search.backfill_runner import (
            EmbeddingBackfillReport,
            EmbeddingBackfillRunner,
            run_embedding_backfill_once,
        )

        # Cache in module globals so subsequent accesses are fast
        globals().update({
            "EmbeddingBackfillReport": EmbeddingBackfillReport,
            "EmbeddingBackfillRunner": EmbeddingBackfillRunner,
            "run_embedding_backfill_once": run_embedding_backfill_once,
        })
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
