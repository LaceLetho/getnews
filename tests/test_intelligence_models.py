from datetime import datetime, timedelta

import pytest

from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    CheckpointStatus,
    DataSource,
    EntryType,
    ExtractionObservation,
    IntelligenceCrawlCheckpoint,
    PrimaryLabel,
    RawIntelligenceItem,
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


def test_extraction_observation_validates_channel_and_slang_dispatch():
    channel = ExtractionObservation.create(
        raw_item_id="raw-1",
        entry_type=EntryType.CHANNEL.value,
        confidence=0.8,
        model_name="grok-test",
        prompt_version="v1",
        schema_version="v1",
        channel_name="Alpha Channel",
        channel_urls=["https://t.me/alpha"],
        primary_label=PrimaryLabel.CRYPTO.value,
    )
    slang = ExtractionObservation.create(
        raw_item_id="raw-1",
        entry_type=EntryType.SLANG.value,
        confidence=0.7,
        model_name="grok-test",
        prompt_version="v1",
        schema_version="v1",
        term="冲土狗",
        normalized_term="冲土狗",
    )

    assert ExtractionObservation.from_dict(channel.to_dict()).channel_name == "Alpha Channel"
    assert ExtractionObservation.from_dict(slang.to_dict()).normalized_term == "冲土狗"

    with pytest.raises(ValueError, match="slang observation requires term"):
        ExtractionObservation.create(
            raw_item_id="raw-1",
            entry_type="slang",
            confidence=0.5,
            model_name="m",
            prompt_version="p",
            schema_version="s",
            normalized_term="n",
        )
    with pytest.raises(ValueError, match="confidence"):
        ExtractionObservation.create(
            raw_item_id="raw-1",
            entry_type="channel",
            confidence=1.5,
            model_name="m",
            prompt_version="p",
            schema_version="s",
            channel_name="c",
        )


def test_canonical_entry_and_checkpoint_round_trip_and_secret_rejection():
    entry = CanonicalIntelligenceEntry.create(
        entry_type=EntryType.CHANNEL.value,
        normalized_key="HTTPS://T.ME/Alpha",
        display_name="Alpha",
        primary_label=PrimaryLabel.AI.value,
        confidence=0.9,
        aliases=["alpha"],
        embedding=[0.1, 0.2, 0.3],
    )
    checkpoint = IntelligenceCrawlCheckpoint.create(
        source_type="telegram",
        source_id="alpha",
        checkpoint_data={"cursor": "42"},
        status=CheckpointStatus.OK.value,
    )

    assert (
        CanonicalIntelligenceEntry.from_dict(entry.to_dict()).normalized_key == "https://t.me/alpha"
    )
    assert IntelligenceCrawlCheckpoint.from_dict(checkpoint.to_dict()).checkpoint_data == {
        "cursor": "42"
    }

    with pytest.raises(ValueError, match="private credential"):
        IntelligenceCrawlCheckpoint.create(
            source_type="telegram",
            source_id="alpha",
            checkpoint_data={"StringSession": "secret"},
        )
    with pytest.raises(ValueError, match="private credential"):
        DataSource.create(
            name="Hidden API",
            source_type="rest_api",
            config_payload={"api_key": "secret"},
        )
    with pytest.raises(ValueError, match="private credential"):
        DataSource.create(
            name="V2EX",
            source_type="rest_api",
            config_payload={"V2EX_PAT": "secret"},
        )


def test_no_audit_domain_model_introduced():
    import crypto_news_analyzer.domain.models as models

    names = dir(models)
    assert "IntelligenceAudit" not in names
    assert "QueryAudit" not in names
