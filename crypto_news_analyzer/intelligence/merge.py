"""Conservative merge engine for extracted intelligence observations.

Only exact normalized identifiers are allowed to merge into canonical entries.
Semantic similarity is represented as a related-candidate edge and never as an
identity merge decision.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Sequence
from urllib.parse import urlparse

from ..domain.models import CanonicalIntelligenceEntry, EntryType, ExtractionObservation


class IntelligenceMergeEngine:
    """Canonicalize extraction observations using exact normalized keys only."""

    def __init__(self, intelligence_repository: Any, confidence_threshold: float = 0.6):
        self.intelligence_repository = intelligence_repository
        self.confidence_threshold = float(confidence_threshold)

    def canonicalize_observations(
        self, observations: List[ExtractionObservation]
    ) -> List[CanonicalIntelligenceEntry]:
        """Create or update canonical entries for high-confidence observations.

        Observations below ``confidence_threshold`` are intentionally left
        uncanonicalized. Entries are merged only when ``(entry_type,
        normalized_key)`` matches exactly after deterministic normalization.
        """

        canonical_entries: List[CanonicalIntelligenceEntry] = []

        for observation in observations:
            if observation.confidence < self.confidence_threshold:
                continue

            normalized_key = self._normalized_key_for_observation(observation)
            if not normalized_key:
                continue

            existing = self.intelligence_repository.get_canonical_entry_by_normalized_key(
                observation.entry_type,
                normalized_key,
            )
            if existing is None:
                entry = self._new_entry_from_observation(observation, normalized_key)
            else:
                entry = self._merge_observation_into_entry(existing, observation)

            self.intelligence_repository.upsert_canonical_entry(entry)
            self.intelligence_repository.mark_observation_canonicalized(observation.id)
            observation.is_canonicalized = True
            canonical_entries.append(entry)

        return canonical_entries

    def create_related_candidates(
        self,
        entry_a: CanonicalIntelligenceEntry,
        entry_b: CanonicalIntelligenceEntry,
        similarity_score: float,
    ) -> None:
        """Persist a semantic-similarity edge without merging identities."""

        if entry_a.id == entry_b.id:
            return
        self.intelligence_repository.save_related_candidate(
            entry_a.id,
            entry_b.id,
            float(similarity_score),
            "semantic_similarity",
        )

    def normalize_channel_key(self, config: Any) -> str:
        """Normalize a channel URL, Telegram handle, or domain to an exact key."""

        values = self._channel_candidate_values(config)
        for kind in ("url", "handle", "domain"):
            for value_kind, raw_value in values:
                if value_kind != kind:
                    continue
                normalized = self._normalize_channel_value(kind, raw_value)
                if normalized:
                    return normalized
        return ""

    def normalize_slang_key(self, term: str) -> str:
        """Normalize slang terms for exact matching."""

        compact = re.sub(r"\s+", "", str(term or "").lower())
        return re.sub(r"[^\w]", "", compact, flags=re.UNICODE)

    def merge_aliases(self, existing: List[str], new: List[str]) -> List[str]:
        """Combine aliases case-insensitively while preserving deterministic order."""

        aliases: List[str] = []
        seen = set()
        for alias in [*existing, *new]:
            normalized = str(alias or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            aliases.append(normalized)
        return aliases

    def merge_confidence(self, existing_conf: float, existing_count: int, new_conf: float) -> float:
        """Weighted average with current evidence count as the existing weight."""

        count = max(0, int(existing_count))
        return (float(existing_conf) * count + float(new_conf)) / (count + 1)

    def _normalized_key_for_observation(self, observation: ExtractionObservation) -> str:
        if observation.entry_type == EntryType.SLANG.value:
            return self.normalize_slang_key(observation.normalized_term or observation.term or "")
        return self.normalize_channel_key(observation)

    def _new_entry_from_observation(
        self, observation: ExtractionObservation, normalized_key: str
    ) -> CanonicalIntelligenceEntry:
        now = datetime.utcnow()
        return CanonicalIntelligenceEntry.create(
            entry_type=observation.entry_type,
            normalized_key=normalized_key,
            display_name=self._display_name(observation),
            explanation=observation.channel_description or observation.contextual_meaning,
            usage_summary=observation.usage_quote,
            primary_label=observation.primary_label,
            secondary_tags=list(observation.secondary_tags),
            confidence=observation.confidence,
            first_seen_at=observation.created_at or now,
            last_seen_at=observation.created_at or now,
            evidence_count=1,
            latest_raw_item_id=observation.raw_item_id,
            prompt_version=observation.prompt_version,
            model_name=observation.model_name,
            schema_version=observation.schema_version,
            aliases=self._aliases_from_observation(observation),
        )

    def _merge_observation_into_entry(
        self,
        entry: CanonicalIntelligenceEntry,
        observation: ExtractionObservation,
    ) -> CanonicalIntelligenceEntry:
        previous_count = entry.evidence_count
        entry.evidence_count = previous_count + 1
        entry.confidence = self.merge_confidence(
            entry.confidence,
            previous_count,
            observation.confidence,
        )
        entry.last_seen_at = max(
            [
                dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
                for dt in [entry.last_seen_at, observation.created_at, datetime.utcnow()]
                if dt
            ]
        )
        entry.latest_raw_item_id = observation.raw_item_id
        entry.aliases = self.merge_aliases(entry.aliases, self._aliases_from_observation(observation))
        entry.secondary_tags = self.merge_aliases(entry.secondary_tags, observation.secondary_tags)
        entry.prompt_version = observation.prompt_version or entry.prompt_version
        entry.model_name = observation.model_name or entry.model_name
        entry.schema_version = observation.schema_version or entry.schema_version
        entry.updated_at = datetime.utcnow()
        return entry

    def _aliases_from_observation(self, observation: ExtractionObservation) -> List[str]:
        aliases = list(observation.aliases_or_variants)
        if observation.channel_name:
            aliases.append(observation.channel_name)
        if observation.term:
            aliases.append(observation.term)
        if observation.normalized_term:
            aliases.append(observation.normalized_term)
        aliases.extend(observation.channel_handles)
        aliases.extend(observation.channel_domains)
        return self.merge_aliases([], aliases)

    def _display_name(self, observation: ExtractionObservation) -> str:
        if observation.entry_type == EntryType.SLANG.value:
            return str(observation.term or observation.normalized_term or "").strip()
        return str(
            observation.channel_name
            or (observation.channel_handles[0] if observation.channel_handles else "")
            or (observation.channel_domains[0] if observation.channel_domains else "")
            or (observation.channel_urls[0] if observation.channel_urls else "")
        ).strip()

    def _channel_candidate_values(self, config: Any) -> List[tuple[str, str]]:
        if isinstance(config, ExtractionObservation):
            return [
                *(("url", value) for value in config.channel_urls),
                *(("handle", value) for value in config.channel_handles),
                *(("domain", value) for value in config.channel_domains),
            ]

        payload: Dict[str, Any] = dict(config or {})
        values: List[tuple[str, str]] = []
        for key in ("url", "channel_url", "source_url"):
            self._append_values(values, "url", payload.get(key))
        for key in ("urls", "channel_urls"):
            self._append_values(values, "url", payload.get(key))
        for key in ("handle", "username", "telegram_username", "channel_handle"):
            self._append_values(values, "handle", payload.get(key))
        for key in ("handles", "channel_handles"):
            self._append_values(values, "handle", payload.get(key))
        for key in ("domain", "channel_domain"):
            self._append_values(values, "domain", payload.get(key))
        for key in ("domains", "channel_domains"):
            self._append_values(values, "domain", payload.get(key))
        return values

    def _append_values(self, values: List[tuple[str, str]], kind: str, raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, str):
            values.append((kind, raw))
            return
        if isinstance(raw, Sequence):
            for item in raw:
                values.append((kind, str(item)))

    def _normalize_channel_value(self, kind: str, value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        if kind == "handle":
            handle = raw.lstrip("@").strip("/")
            if handle.startswith("t.me/"):
                return self._normalize_url(handle)
            return handle
        if kind == "domain":
            return self._strip_www(raw).strip("/")
        return self._normalize_url(raw)

    def _normalize_url(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        parse_target = raw if re.match(r"^[a-z][a-z0-9+.-]*://", raw) else f"https://{raw}"
        parsed = urlparse(parse_target)
        host = self._strip_www(parsed.netloc or parsed.path.split("/", 1)[0])
        path = parsed.path if parsed.netloc else ("/" + parsed.path.split("/", 1)[1] if "/" in parsed.path else "")
        path = path.rstrip("/")
        return f"{host}{path}"

    def _strip_www(self, value: str) -> str:
        return re.sub(r"^www\.", "", str(value or "").strip().lower())
