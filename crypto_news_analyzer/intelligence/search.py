"""Semantic retrieval for canonical intelligence entries."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional, Sequence, Tuple

from ..domain.models import CanonicalIntelligenceEntry
from ..models import StorageConfig

logger = logging.getLogger(__name__)


class IntelligenceSearchService:
    """Generate embeddings and run semantic search for intelligence entries."""

    def __init__(
        self,
        embedding_service: Any,
        intelligence_repository: Any,
        storage_config: StorageConfig,
    ):
        self.embedding_service = embedding_service
        self.intelligence_repository = intelligence_repository
        self.storage_config = storage_config

    def build_embedding_text(self, entry: CanonicalIntelligenceEntry) -> str:
        """Build the canonical text used for intelligence entry embeddings."""

        parts = [
            entry.display_name,
            entry.explanation or "",
            entry.usage_summary or "",
            " ".join(entry.aliases or []),
            entry.primary_label or "",
            " ".join(entry.secondary_tags or []),
        ]
        return " ".join(part.strip() for part in parts if str(part or "").strip())

    def generate_and_store_embedding(self, entry: CanonicalIntelligenceEntry) -> bool:
        """Generate and persist an embedding for one canonical intelligence entry."""

        embedding_text = self.build_embedding_text(entry)
        if not embedding_text:
            logger.warning("Skipping empty intelligence embedding text: entry_id=%s", entry.id)
            return False

        embedding = self.embedding_service.generate_embedding(embedding_text)
        if embedding is None:
            logger.warning("Intelligence embedding generation failed: entry_id=%s", entry.id)
            return False

        model = str(getattr(self.embedding_service, "model", "") or "").strip()
        if not model:
            logger.warning("Embedding model metadata missing: entry_id=%s", entry.id)
            return False

        return bool(self.intelligence_repository.update_embedding(entry.id, embedding, model))

    def semantic_search(
        self,
        query_text: str,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window_days: Optional[int] = None,
        window: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[Tuple[CanonicalIntelligenceEntry, float]]:
        """Search canonical intelligence entries by query embedding."""

        normalized_query = str(query_text or "").strip()
        if not normalized_query:
            return []

        query_embedding = self.embedding_service.generate_embedding(normalized_query)
        if query_embedding is None:
            logger.warning("Intelligence query embedding generation failed")
            return []

        if window is None and window_days is not None:
            bounded_days = max(1, int(window_days))
            window = datetime.utcnow() - timedelta(days=bounded_days)

        return self.intelligence_repository.semantic_search(
            query_embedding=query_embedding,
            entry_type=entry_type,
            primary_label=primary_label,
            window=window,
            limit=max(1, int(limit)),
        )

    def batch_generate_embeddings(
        self,
        entries: Sequence[CanonicalIntelligenceEntry],
        batch_size: int = 20,
    ) -> int:
        """Generate embeddings for entries in bounded synchronous batches."""

        if not entries:
            return 0

        bounded_batch_size = max(1, int(batch_size))
        updated_count = 0

        for start in range(0, len(entries), bounded_batch_size):
            batch = entries[start : start + bounded_batch_size]
            for entry in batch:
                if self.generate_and_store_embedding(entry):
                    updated_count += 1

        return updated_count
