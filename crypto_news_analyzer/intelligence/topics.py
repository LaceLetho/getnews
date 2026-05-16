"""Topic embedding utilities (topic-only refactor)."""
from __future__ import annotations

import logging

from ..domain.models import IntelligenceTopic

logger = logging.getLogger(__name__)


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
