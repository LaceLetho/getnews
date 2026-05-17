"""
GROUP/FORUM INTELLIGENCE DOMAIN — Telegram/V2EX message collection, AI topic
research, and findings pipeline (separate from crypto news analysis).

Sources: telegram_group, v2ex (DataSourcePurpose.INTELLIGENCE).
Primary models: RawIntelligenceItem, IntelligenceTopic, TopicPrompt, TopicFinding.
Commands: /topic_create, /topic_revise, /topic_set_prompt, /topic_confirm,
  /topic_list, /topic_detail, /topic_logs, /topic_merge, /topic_pause,
  /topic_archive.
API routes: /intelligence/* (create_topic_draft, revise, confirm, etc.).
"""

from .pipeline import IntelligencePipeline
from .search import IntelligenceSearchService

__all__ = ["IntelligencePipeline", "IntelligenceSearchService"]
