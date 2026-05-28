"""Unified data models for semantic search hits across domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UnifiedSemanticSearchHit:
    """A search hit from either the News or Intelligence domain."""

    hit_key: str
    source_domain: str
    id: str
    source_type: str
    source_name: str
    source_id: Optional[str] = None
    title: str = ""
    content_excerpt: str = ""
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    similarity: float = 0.0
    matched_subqueries: list[str] = field(default_factory=list)
