"""Runtime orchestration for hidden-channel intelligence ingestion."""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from ..domain.models import (
    CheckpointStatus,
    DataSource,
    EntryType,
    IntelligenceCrawlCheckpoint,
    RawIntelligenceItem,
)
from .merge import IntelligenceMergeEngine

INTELLIGENCE_SOURCE_TYPES = ("telegram_group", "v2ex")


class IntelligencePipeline:
    """Collect raw intelligence, extract observations, merge entries, and enforce raw TTL."""

    def __init__(
        self,
        data_source_factory: Any,
        intelligence_repository: Any,
        extractor: Any,
        merge_engine: Any,
        search_service: Any,
    ):
        self.data_source_factory = data_source_factory
        self.intelligence_repository = intelligence_repository
        self.extractor = extractor
        self.merge_engine = merge_engine
        self.search_service = search_service
        set_search_service = getattr(self.merge_engine, "set_search_service", None)
        if callable(set_search_service) and self.search_service is not None:
            set_search_service(self.search_service)
        self.logger = logging.getLogger(__name__)
        self.backfill_hours = self._resolve_backfill_hours(extractor)

    def run_intelligence_collection_once(self) -> Dict[str, Any]:
        """Run one intelligence collection cycle across configured intelligence sources."""

        result: Dict[str, Any] = {
            "success": True,
            "sources_processed": 0,
            "items_crawled": 0,
            "items_new": 0,
            "observations": 0,
            "canonical_entries": 0,
            "embeddings_updated": 0,
            "skipped_untracked_slang_items": 0,
            "raw_text_purged": 0,
            "errors": [],
        }

        for datasource in self._list_intelligence_datasources():
            try:
                source_result = self._run_source(datasource)
                result["sources_processed"] += 1
                for key in (
                    "items_crawled",
                    "items_new",
                    "observations",
                    "canonical_entries",
                    "embeddings_updated",
                    "skipped_untracked_slang_items",
                ):
                    result[key] += int(source_result.get(key, 0))
            except Exception as exc:
                result["success"] = False
                error_msg = (
                    f"Intelligence source {datasource.source_type}:{datasource.name} failed: {exc}"
                )
                result["errors"].append(error_msg)
                self.logger.exception(error_msg)
                self._save_error_checkpoint(datasource, str(exc))

        result["raw_text_purged"] = self._run_ttl_cleanup()
        return result

    def _run_source(self, datasource: DataSource) -> Dict[str, int]:
        source_id = self._source_identifier(datasource)
        checkpoint = self.intelligence_repository.get_checkpoint(datasource.source_type, source_id)
        time_window_hours = self._time_window_hours(checkpoint)
        config_payload = self._crawler_config(datasource)

        crawler = self.data_source_factory.create_source(
            datasource.source_type,
            time_window_hours,
            intelligence_repository=self.intelligence_repository,
            repository=self.intelligence_repository,
        )
        items = list(crawler.crawl(config_payload) or [])
        new_items = self._save_new_items(items)
        extract_items, skipped_untracked_slang_items = self._filter_untracked_slang_items(new_items)
        observations = list(self.extractor.extract(extract_items) or []) if extract_items else []
        canonical_entries = (
            list(self.merge_engine.canonicalize_observations(observations) or [])
            if observations
            else []
        )
        embeddings_updated = self._generate_embeddings(canonical_entries)
        self._create_related_candidates(canonical_entries)
        self._save_success_checkpoint(datasource, source_id, items)

        return {
            "items_crawled": len(items),
            "items_new": len(new_items),
            "observations": len(observations),
            "canonical_entries": len(canonical_entries),
            "embeddings_updated": embeddings_updated,
            "skipped_untracked_slang_items": skipped_untracked_slang_items,
        }

    def _filter_untracked_slang_items(
        self, items: Sequence[RawIntelligenceItem]
    ) -> Tuple[List[RawIntelligenceItem], int]:
        if not items:
            return [], 0

        untracked_terms, followed_terms = self._slang_filter_terms()
        if not untracked_terms:
            return list(items), 0

        kept_items: List[RawIntelligenceItem] = []
        skipped_matches: Dict[str, List[str]] = {}
        for item in items:
            raw_text = item.raw_text or ""
            untracked_matches = self._matching_terms(raw_text, untracked_terms)
            if not untracked_matches:
                kept_items.append(item)
                continue

            followed_matches = self._matching_terms(raw_text, followed_terms)
            if followed_matches:
                kept_items.append(item)
                continue

            skipped_matches[item.id] = untracked_matches

        if skipped_matches:
            self.logger.info(
                "Skipped %d intelligence raw items matching untracked/ignored slang terms: %s",
                len(skipped_matches),
                skipped_matches,
            )

        return kept_items, len(skipped_matches)

    def _slang_filter_terms(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        entries = self._list_slang_entries_for_filter()
        untracked_terms: Dict[str, str] = {}
        followed_terms: Dict[str, str] = {}

        for entry in entries:
            if getattr(entry, "entry_type", "") != EntryType.SLANG.value:
                continue
            target = (
                untracked_terms
                if getattr(entry, "is_ignored", False)
                or not getattr(entry, "tracking_enabled", False)
                else followed_terms
            )
            for raw_term in self._slang_entry_terms(entry):
                normalized_term = self._normalize_slang_text(raw_term)
                if normalized_term:
                    target.setdefault(normalized_term, str(raw_term))

        return untracked_terms, followed_terms

    def _list_slang_entries_for_filter(self) -> List[Any]:
        entries_by_id: Dict[str, Any] = {}
        list_entries = getattr(self.intelligence_repository, "list_canonical_entries", None)
        if callable(list_entries):
            canonical_entries = cast(
                Iterable[Any],
                list_entries(
                    entry_type=EntryType.SLANG.value,
                    page=1,
                    page_size=10000,
                    tracking_scope="all",
                )
                or [],
            )
            for entry in canonical_entries:
                entries_by_id[getattr(entry, "id", str(id(entry)))] = entry

        list_ignored = getattr(self.intelligence_repository, "list_ignored_canonical_entries", None)
        if callable(list_ignored):
            ignored_entries = cast(
                Iterable[Any],
                list_ignored(
                    entry_type=EntryType.SLANG.value,
                    page=1,
                    page_size=10000,
                )
                or [],
            )
            for entry in ignored_entries:
                entries_by_id[getattr(entry, "id", str(id(entry)))] = entry

        return list(entries_by_id.values())

    def _slang_entry_terms(self, entry: Any) -> List[str]:
        return [
            str(term)
            for term in [
                getattr(entry, "display_name", ""),
                getattr(entry, "normalized_key", ""),
                *list(getattr(entry, "aliases", []) or []),
            ]
            if str(term or "").strip()
        ]

    def _normalize_slang_text(self, value: str) -> str:
        return IntelligenceMergeEngine.normalize_slang_key(self.merge_engine, value)

    def _matching_terms(self, raw_text: str, terms: Dict[str, str]) -> List[str]:
        normalized_text = self._normalize_slang_text(raw_text)
        lowered_text = str(raw_text or "").lower()
        matches: List[str] = []
        for term in sorted(terms):
            if not term:
                continue
            if self._is_short_ascii_term(term):
                if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", lowered_text):
                    matches.append(terms[term])
                continue
            if term in normalized_text:
                matches.append(terms[term])
        return matches

    def _is_short_ascii_term(self, term: str) -> bool:
        return len(term) <= 3 and re.fullmatch(r"[a-z0-9_]+", term) is not None

    def _list_intelligence_datasources(self) -> List[DataSource]:
        datasource_repository = self._datasource_repository()
        sources: List[DataSource] = []
        for source_type in INTELLIGENCE_SOURCE_TYPES:
            sources.extend(
                list(
                    datasource_repository.list(
                        purpose="intelligence",
                        source_type=source_type,
                    )
                    or []
                )
            )
        return sources

    def _datasource_repository(self) -> Any:
        for owner in (self.intelligence_repository, self.data_source_factory):
            repository = getattr(owner, "datasource_repository", None)
            if repository is not None and hasattr(repository, "list"):
                return repository
            if hasattr(owner, "list"):
                return owner
            if hasattr(owner, "list_datasources"):
                return _ListDatasourcesAdapter(owner)
        raise ValueError("DataSourceRepository is required for intelligence collection")

    def _time_window_hours(self, checkpoint: Optional[IntelligenceCrawlCheckpoint]) -> int:
        if checkpoint is None or checkpoint.last_crawled_at is None:
            return self.backfill_hours
        last = checkpoint.last_crawled_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0.0, (datetime.now(timezone.utc) - last).total_seconds())
        return max(1, int(math.ceil(elapsed_seconds / 3600.0)))

    def _crawler_config(self, datasource: DataSource) -> Dict[str, Any]:
        payload = dict(datasource.config_payload or {})
        payload.setdefault("id", datasource.id)
        payload.setdefault("name", datasource.name)
        return payload

    def _save_new_items(self, items: Sequence[RawIntelligenceItem]) -> List[RawIntelligenceItem]:
        existing_keys = self._existing_dedupe_keys(items)
        seen_keys: Set[Tuple[str, str, str]] = set()
        new_items: List[RawIntelligenceItem] = []

        for item in items:
            key = self._dedupe_key(item)
            if key in seen_keys or key in existing_keys:
                continue
            seen_keys.add(key)
            self.intelligence_repository.save_raw_item(item)
            new_items.append(item)

        return new_items

    def _existing_dedupe_keys(
        self, items: Sequence[RawIntelligenceItem]
    ) -> Set[Tuple[str, str, str]]:
        keys: Set[Tuple[str, str, str]] = set()
        source_pairs = {(item.source_type, item.source_id or "") for item in items}
        for source_type, source_id in source_pairs:
            try:
                existing_items = self.intelligence_repository.get_raw_items_by_source(
                    source_type,
                    source_id,
                    limit=10000,
                    offset=0,
                )
            except TypeError:
                existing_items = self.intelligence_repository.get_raw_items_by_source(
                    source_type,
                    source_id,
                    10000,
                    0,
                )
            except Exception:
                self.logger.debug(
                    "Unable to preload intelligence dedupe keys for %s:%s",
                    source_type,
                    source_id,
                    exc_info=True,
                )
                continue
            keys.update(self._dedupe_key(existing_item) for existing_item in existing_items)
        return keys

    def _generate_embeddings(self, canonical_entries: Sequence[Any]) -> int:
        if not canonical_entries or self.search_service is None:
            return 0
        active_entries = [
            entry for entry in canonical_entries if not getattr(entry, "is_ignored", False)
        ]
        if not active_entries:
            return 0
        return int(self.search_service.batch_generate_embeddings(active_entries) or 0)

    def _create_related_candidates(self, canonical_entries: Sequence[Any]) -> None:
        if not canonical_entries or self.search_service is None:
            return
        for entry in canonical_entries:
            build_embedding_text = getattr(self.search_service, "build_embedding_text", None)
            if not callable(build_embedding_text):
                continue
            query_text = build_embedding_text(entry)
            if not query_text:
                continue
            try:
                results, _ = self.search_service.semantic_search(
                    query_text=query_text,
                    entry_type=entry.entry_type,
                    page_size=6,
                )
            except Exception:
                self.logger.debug(
                    "Unable to create related candidates for intelligence entry %s",
                    getattr(entry, "id", "unknown"),
                    exc_info=True,
                )
                continue
            try:
                result_pairs = list(results or [])
            except TypeError:
                continue
            for candidate, score in result_pairs:
                if getattr(candidate, "id", None) == getattr(entry, "id", None):
                    continue
                if float(score) < 0.75:
                    continue
                self.merge_engine.create_related_candidates(entry, candidate, float(score))

    def _run_ttl_cleanup(self) -> int:
        cutoff_time = datetime.utcnow()
        expiring_items = self.intelligence_repository.get_raw_items_expiring_before(cutoff_time)
        expiring_with_text = [item for item in expiring_items if getattr(item, "raw_text", None)]
        purged_count = int(self.intelligence_repository.purge_raw_text_older_than(cutoff_time) or 0)
        self.logger.info(
            "Purged raw_text for %s expired intelligence raw items",
            purged_count,
        )
        if purged_count != len(expiring_with_text):
            self.logger.debug(
                "Expired intelligence raw items with text=%s, repository purged=%s",
                len(expiring_with_text),
                purged_count,
            )
        return purged_count

    def _save_success_checkpoint(
        self,
        datasource: DataSource,
        source_id: str,
        items: Sequence[RawIntelligenceItem],
    ) -> None:
        latest_item = self._latest_item(items)
        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type=datasource.source_type,
            source_id=source_id,
            last_crawled_at=datetime.now(timezone.utc),
            last_external_id=getattr(latest_item, "external_id", None) if latest_item else None,
            checkpoint_data={"datasource_id": datasource.id, "datasource_name": datasource.name},
            status=CheckpointStatus.OK.value,
        )
        self.intelligence_repository.save_checkpoint(checkpoint)

    def _save_error_checkpoint(self, datasource: DataSource, error_message: str) -> None:
        source_id = self._source_identifier(datasource)
        existing = self.intelligence_repository.get_checkpoint(datasource.source_type, source_id)
        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type=datasource.source_type,
            source_id=source_id,
            last_crawled_at=existing.last_crawled_at if existing else None,
            last_external_id=existing.last_external_id if existing else None,
            checkpoint_data=existing.checkpoint_data if existing else {},
            status=CheckpointStatus.ERROR.value,
            error_message=error_message,
        )
        self.intelligence_repository.save_checkpoint(checkpoint)

    def _latest_item(self, items: Sequence[RawIntelligenceItem]) -> Optional[RawIntelligenceItem]:
        if not items:
            return None
        return max(
            items, key=lambda item: self._safe_dt_key(item.published_at or item.collected_at)
        )

    @staticmethod
    def _safe_dt_key(dt: Optional[datetime]) -> datetime:
        """Return a naive datetime suitable for comparison keys."""

        if dt is None:
            return datetime(1970, 1, 1)
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

    def _source_identifier(self, datasource: DataSource) -> str:
        payload = dict(datasource.config_payload or {})
        for key in ("source_id", "chat_id", "chat_username", "node_name", "name"):
            value = payload.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return datasource.name

    def _dedupe_key(self, item: RawIntelligenceItem) -> Tuple[str, str, str]:
        stable_id = item.external_id or item.content_hash
        return (item.source_type, item.source_id or "", stable_id)

    def _resolve_backfill_hours(self, extractor: Any) -> int:
        config = getattr(extractor, "config", None)
        collection = getattr(config, "collection", None)
        return max(1, int(getattr(collection, "backfill_hours", 24) or 24))


class _ListDatasourcesAdapter:
    def __init__(self, owner: Any):
        self.owner = owner

    def list(
        self,
        purpose: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> Iterable[DataSource]:
        return self.owner.list_datasources(purpose=purpose, source_type=source_type)
