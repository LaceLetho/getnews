"""Automatic topic creation and entry-to-topic linking."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from ..domain.models import (
    CanonicalIntelligenceEntry,
    EntryType,
    IntelligenceTopic,
    IntelligenceTopicRunLog,
)

logger = logging.getLogger(__name__)

ENTRY_TOPIC_AUTO_LINK_THRESHOLD = 0.78


def build_topic_embedding_text(topic: IntelligenceTopic) -> str:
    parts = [
        topic.name,
        topic.description or "",
        topic.enriched_summary or "",
        " ".join(channel.get("name", "") for channel in topic.source_channels),
        " ".join(channel.get("url", "") for channel in topic.source_channels),
        topic.methods or "",
        topic.vulnerabilities or "",
        " ".join(topic.latest_findings or []),
    ]
    return " ".join(part.strip() for part in parts if str(part or "").strip())


class IntelligenceTopicService:
    def __init__(self, intelligence_repository: Any, search_service: Any = None):
        self._repo = intelligence_repository
        self._search = search_service

    def ensure_entry_topic(self, entry: CanonicalIntelligenceEntry) -> Optional[IntelligenceTopic]:
        if entry.follow_status != "follow":
            return None

        if entry.topic_id:
            existing = self._repo.get_topic_by_id(entry.topic_id)
            if existing and existing.is_active:
                return existing

        if self._search is None:
            return self._create_topic_from_entry(entry, "auto_link")

        entry_embedding = None
        build_text = getattr(self._search, "build_embedding_text", None)
        if callable(build_text):
            embedding_text = build_text(entry)
            if embedding_text:
                embed_service = getattr(self._search, "embedding_service", None)
                if embed_service:
                    entry_embedding = embed_service.generate_embedding(embedding_text)

        if entry_embedding:
            try:
                topic_results = self._repo.semantic_search_topics(
                    entry_embedding, is_active=True, limit=5
                )
                for topic, score in topic_results:
                    if score >= ENTRY_TOPIC_AUTO_LINK_THRESHOLD:
                        self._repo.assign_entry_to_topic(entry.id, topic.id)
                        entry.topic_id = topic.id
                        self._write_run_log("auto_link", "success", topic.id, entry.id)
                        return topic
            except Exception:
                logger.debug(
                    "Topic semantic search failed for entry %s", entry.id, exc_info=True
                )

        topic = self._create_topic_from_entry(entry, "auto_link")
        if topic:
            self._repo.assign_entry_to_topic(entry.id, topic.id)
            entry.topic_id = topic.id
        return topic

    def _create_topic_from_entry(
        self, entry: CanonicalIntelligenceEntry, run_type: str
    ) -> Optional[IntelligenceTopic]:
        try:
            source_channels: list = []
            if entry.entry_type == EntryType.CHANNEL.value:
                channel_name = entry.display_name or ""
                source_channels.append(
                    {"name": channel_name, "url": "", "type": "unknown", "confidence": 0.5}
                )
            topic = IntelligenceTopic.create(
                name=entry.display_name,
                description=entry.explanation or entry.usage_summary,
                enriched_summary=entry.explanation,
                source_channels=source_channels,
            )
            self._repo.save_topic(topic)
            self._write_run_log(run_type, "success", topic.id, entry.id)
            self._generate_topic_embedding(topic)
            return topic
        except Exception:
            logger.exception("Failed to create topic from entry %s", entry.id)
            self._write_run_log(run_type, "failed", None, entry.id, "Failed to create topic")
            return None

    def _generate_topic_embedding(self, topic: IntelligenceTopic) -> None:
        if self._search is None:
            return
        try:
            embedding_text = build_topic_embedding_text(topic)
            if not embedding_text:
                return
            embed_service = getattr(self._search, "embedding_service", None)
            if embed_service is None:
                return
            embedding = embed_service.generate_embedding(embedding_text)
            if embedding is None:
                return
            model = str(getattr(embed_service, "model", "") or "").strip()
            if not model:
                return
            self._repo.update_topic_embedding(topic.id, embedding, model)
        except Exception:
            logger.debug("Topic embedding generation failed: %s", topic.id, exc_info=True)

    def _write_run_log(
        self,
        run_type: str,
        status: str,
        topic_id: Optional[str],
        entry_id: Optional[str],
        message: Optional[str] = None,
    ) -> None:
        try:
            now = datetime.utcnow()
            log_entry = IntelligenceTopicRunLog.create(
                run_type=run_type,
                status=status,
                topic_id=topic_id,
                entry_id=entry_id,
                message=message,
                started_at=now,
                finished_at=now,
            )
            self._repo.save_topic_run_log(log_entry)
        except Exception:
            logger.debug("Failed to write topic run log", exc_info=True)
