"""Tests for topic-datasource association domain contracts (Wave 1 Task 2)."""

import json

import pytest

from crypto_news_analyzer.domain.models import (
    DataSource,
    DataSourcePurpose,
    DataSourceType,
    SafeDataSourceSummary,
)
from crypto_news_analyzer.domain.repositories import IntelligenceRepository


# ---------------------------------------------------------------------------
# Import / acyclic verification
# ---------------------------------------------------------------------------


def test_safe_datasource_summary_imports_cleanly():
    """SafeDataSourceSummary and parent types import without error."""
    assert SafeDataSourceSummary is not None
    assert DataSourcePurpose is not None
    assert DataSourceType is not None


def test_intelligence_repository_imports_cleanly():
    """IntelligenceRepository ABC imports and can be inspected."""
    assert IntelligenceRepository is not None
    methods = {
        name for name in dir(IntelligenceRepository)
        if not name.startswith("_") and callable(getattr(IntelligenceRepository, name, None))
    }
    assert "get_topic_datasource_ids" in methods
    assert "set_topic_datasources" in methods
    assert "add_topic_datasources" in methods
    assert "remove_topic_datasources" in methods
    assert "get_topic_datasources" in methods


def test_no_cyclic_imports():
    """Domain models and repositories can be imported together without cycle."""
    from crypto_news_analyzer.domain.repositories import IntelligenceRepository as IR

    from crypto_news_analyzer.domain.models import DataSourcePurpose as DSP

    assert IR is not None
    assert DSP is not None
    assert DSP.INTELLIGENCE.value == "intelligence"
    assert DSP.NEWS.value == "news"


# ---------------------------------------------------------------------------
# SafeDataSourceSummary — structure & serialization
# ---------------------------------------------------------------------------


def test_safe_summary_excludes_config_payload():
    """SafeDataSourceSummary has no config_payload field."""
    ds = DataSource.create(
        name="Test Source",
        source_type="telegram_group",
        purpose="intelligence",
        tags=["crypto", "Alpha"],
        config_payload={"endpoint": "https://example.com", "method": "GET"},
    )
    summary = SafeDataSourceSummary.from_datasource(ds)
    assert not hasattr(summary, "config_payload")

    d = summary.to_dict()
    assert "config_payload" not in d
    assert d["id"] == ds.id
    assert d["source_type"] == "telegram_group"
    assert d["name"] == "Test Source"
    assert set(d["tags"]) == {"alpha", "crypto"}


def test_safe_summary_to_dict_and_back():
    """Round-trip: to_dict → from_dict preserves all public fields."""
    original = SafeDataSourceSummary(
        id="ds-001",
        source_type="v2ex",
        name="V2EX Hot",
        tags=["tech", "blockchain"],
    )
    reloaded = SafeDataSourceSummary.from_dict(original.to_dict())
    assert reloaded.id == original.id
    assert reloaded.source_type == original.source_type
    assert reloaded.name == original.name
    assert reloaded.tags == original.tags


def test_safe_summary_json_round_trip():
    """JSON serialization round-trips correctly."""
    summary = SafeDataSourceSummary(
        id="ds-002",
        source_type="rss",
        name="Crypto RSS",
        tags=["btc"],
    )
    dumped = json.dumps(summary.to_dict())
    loaded = json.loads(dumped)
    assert loaded["id"] == "ds-002"
    assert "config_payload" not in loaded


def test_safe_summary_validation_rejects_empty_id():
    with pytest.raises(ValueError, match="id is required"):
        SafeDataSourceSummary(id="", source_type="rss", name="x")


def test_safe_summary_validation_rejects_empty_name():
    with pytest.raises(ValueError, match="name is required"):
        SafeDataSourceSummary(id="ds-001", source_type="rss", name="")


def test_safe_summary_validation_rejects_empty_source_type():
    with pytest.raises(ValueError, match="source_type is required"):
        SafeDataSourceSummary(id="ds-001", source_type="", name="x")


def test_safe_summary_tags_normalized():
    """Tags are normalized: lowercased, deduped, sorted."""
    summary = SafeDataSourceSummary(
        id="ds-001",
        source_type="rss",
        name="x",
        tags=["Bitcoin", "  BITCOIN  ", "ethereum"],
    )
    assert summary.tags == ["bitcoin", "ethereum"]


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


def test_datasource_purpose_enum_values():
    assert DataSourcePurpose.NEWS.value == "news"
    assert DataSourcePurpose.INTELLIGENCE.value == "intelligence"


def test_datasource_type_enum_values():
    assert DataSourceType.RSS.value == "rss"
    assert DataSourceType.X.value == "x"
    assert DataSourceType.REST_API.value == "rest_api"
    assert DataSourceType.TELEGRAM_GROUP.value == "telegram_group"
    assert DataSourceType.V2EX.value == "v2ex"


# ---------------------------------------------------------------------------
# Repository contract — default behavior for unimplemented methods
# ---------------------------------------------------------------------------


class _MinimalIntelligenceRepo(IntelligenceRepository):
    """Minimal concrete subclass implementing only abstractmethods."""

    def save_raw_item(self, raw_item):
        return raw_item.id

    def get_raw_items_by_source(self, source_type, source_id, limit, offset):
        return []

    def get_raw_items_expiring_before(self, cutoff_time):
        return []

    def get_raw_item_by_id(self, raw_item_id):
        return None

    def delete_expired_raw_items(self, cutoff_time):
        return 0

    def purge_raw_text_older_than(self, cutoff_time):
        return 0

    def save_checkpoint(self, checkpoint):
        pass

    def get_checkpoint(self, source_type, source_id):
        return None


def test_new_methods_raise_not_implemented_by_default():
    """Before a backend implements topic-datasource associations, new methods raise NotImplementedError."""
    repo = _MinimalIntelligenceRepo()

    with pytest.raises(NotImplementedError, match="topic-datasource associations"):
        repo.get_topic_datasource_ids("topic-1")

    with pytest.raises(NotImplementedError, match="topic-datasource associations"):
        repo.set_topic_datasources("topic-1", ["ds-1"])

    with pytest.raises(NotImplementedError, match="topic-datasource associations"):
        repo.add_topic_datasources("topic-1", ["ds-1"])

    with pytest.raises(NotImplementedError, match="topic-datasource associations"):
        repo.remove_topic_datasources("topic-1", ["ds-1"])

    with pytest.raises(NotImplementedError, match="topic-datasource associations"):
        repo.get_topic_datasources("topic-1")


def test_get_raw_items_since_default_is_empty_with_optional_datasource_filter():
    """get_raw_items_since returns empty list by default, accepts optional datasource_ids."""
    repo = _MinimalIntelligenceRepo()

    from datetime import datetime

    result = repo.get_raw_items_since("topic-1", None, 10)
    assert result == []

    result = repo.get_raw_items_since("topic-1", None, 10, datasource_ids=["ds-1", "ds-2"])
    assert result == []

    result = repo.get_raw_items_since(
        "topic-1", datetime.utcnow(), 10, datasource_ids=None
    )
    assert result == []


def test_minimal_repo_can_be_instantiated():
    """A minimal repository instantiates without errors (no abstractmethod violations)."""
    repo = _MinimalIntelligenceRepo()
    assert isinstance(repo, IntelligenceRepository)
