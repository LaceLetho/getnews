from datetime import datetime, timedelta

import pytest

from crypto_news_analyzer.domain.models import (
    DataSource,
    FindingArchive,
    IntelligenceTopic,
    MergePreview,
    RawIntelligenceItem,
    TopicFinding,
    TopicPrompt,
    TopicResearchRun,
)


def test_raw_intelligence_item_round_trip_and_validation():
    item = RawIntelligenceItem.create(
        source_type="Telegram",
        source_id="chat-1",
        raw_text="alpha signal",
        content_hash="hash-1",
        expires_at=datetime.utcnow() + timedelta(days=30),
        external_id="msg-1",
    )

    loaded = RawIntelligenceItem.from_dict(item.to_dict())

    assert loaded.id == item.id
    assert loaded.source_type == "telegram"
    assert loaded.external_id == "msg-1"

    with pytest.raises(ValueError, match="raw_text is required"):
        RawIntelligenceItem.create(
            source_type="telegram",
            raw_text=" ",
            content_hash="hash",
            expires_at=datetime.utcnow(),
        )


def test_datasource_secret_rejection():
    """DataSource.create rejects secrets in config_payload (still relevant in topic-only world)."""
    with pytest.raises(ValueError, match="private credential"):
        DataSource.create(
            name="Hidden API",
            source_type="rest_api",
            purpose="intelligence",
            config_payload={"api_key": "secret"},
        )
    with pytest.raises(ValueError, match="private credential"):
        DataSource.create(
            name="V2EX",
            source_type="rest_api",
            purpose="intelligence",
            config_payload={"V2EX_PAT": "secret"},
        )


def test_no_audit_domain_model_introduced():
    import crypto_news_analyzer.domain.models as models

    names = dir(models)
    assert "IntelligenceAudit" not in names
    assert "QueryAudit" not in names


def test_topic_lifecycle_prompt_version_and_research_run_models():
    topic = IntelligenceTopic.create(name="Exploit watch", lifecycle_status="draft")
    active = IntelligenceTopic.from_dict({**topic.to_dict(), "lifecycle_status": "active"})
    paused = IntelligenceTopic.from_dict({**topic.to_dict(), "lifecycle_status": "paused"})
    prompt = TopicPrompt.create(
        intelligence_topic_id=topic.id,
        prompt_version="topic-prompt-v1",
        prompt_text="Extract exploit campaign findings only",
        schema_version="finding-v1",
        status="active",
        audit_history=[{"event": "activated", "actor": "analyst"}],
    )
    run = TopicResearchRun.create(
        intelligence_topic_id=topic.id,
        prompt_version_id=prompt.id,
        status="running",
        checkpoint_cursor="raw-42",
        checkpoint_payload={"collected_after": "2026-01-01T00:00:00"},
    )

    assert topic.lifecycle_status == "draft"
    assert active.is_active is True
    assert paused.is_active is False
    assert TopicPrompt.from_dict(prompt.to_dict()).audit_history[0]["event"] == "activated"
    assert TopicResearchRun.from_dict(run.to_dict()).checkpoint_cursor == "raw-42"
    with pytest.raises(ValueError, match="lifecycle_status"):
        IntelligenceTopic.create(name="Bad", lifecycle_status="deleted")


def test_topic_finding_citations_merge_preview_and_archive_metadata():
    finding = TopicFinding.create(
        intelligence_topic_id="topic-1",
        prompt_version_id="prompt-version-1",
        finding_payload={"summary": "wallet drainer campaign", "severity": "high"},
        content_hash="finding-hash-1",
        citations=[{"raw_item_id": "raw-1", "quote": "drainer kit shipped"}],
        source_raw_item_ids=["raw-1"],
        confidence=0.91,
    )
    superseded = TopicFinding.create(
        intelligence_topic_id="topic-1",
        prompt_version_id="prompt-version-1",
        finding_payload={"summary": "old finding"},
        content_hash="finding-hash-old",
        status="superseded",
        superseded_by_finding_id=finding.id,
    )
    preview = MergePreview.create(
        intelligence_topic_id="topic-1",
        source_finding_ids=[finding.id, superseded.id],
        preview_payload={"merged_summary": "wallet drainer campaign"},
        content_hash="preview-hash-1",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    archive = FindingArchive.create(
        finding_id=superseded.id,
        intelligence_topic_id="topic-1",
        archive_reason="superseded",
        superseded_by_finding_id=finding.id,
        archive_metadata={"merge_preview_id": preview.id},
    )

    assert TopicFinding.from_dict(finding.to_dict()).citations[0]["raw_item_id"] == "raw-1"
    assert superseded.superseded_by_finding_id == finding.id
    assert MergePreview.from_dict(preview.to_dict()).state == "pending"
    assert FindingArchive.from_dict(archive.to_dict()).superseded_by_finding_id == finding.id
    with pytest.raises(ValueError, match="superseded_by_finding_id"):
        TopicFinding.create(
            intelligence_topic_id="topic-1",
            prompt_version_id="prompt-version-1",
            finding_payload={"summary": "bad"},
            content_hash="finding-hash-bad",
            status="superseded",
        )


def test_topic_only_models_do_not_reuse_legacy_entry_channel_or_slang_vocabulary():
    import crypto_news_analyzer.domain.models as models

    for model_name in (
        "TopicPrompt",
        "TopicFinding",
        "TopicResearchRun",
        "MergePreview",
        "FindingArchive",
    ):
        field_names = set(models.__dict__[model_name].__dataclass_fields__)
        assert "entry_type" not in field_names
        assert "channel" not in field_names
        assert "slang" not in field_names
