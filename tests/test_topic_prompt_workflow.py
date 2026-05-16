"""Contract tests for the topic prompt draft, revision, manual edit, and confirm workflow.

These tests verify that the new prompt files exist, contain required schema/version
markers, include citation requirements, and exclude old channel/slang category language.

Old concepts being replaced: EntryType, SlangObservation, ChannelObservation,
/intel_*, /intelligence/entries*.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from crypto_news_analyzer.domain.models import (
    IntelligenceTopic,
    TopicFinding,
)
from crypto_news_analyzer.intelligence.topic_prompts import (
    PROMPT_GENERATION_SCHEMA_VERSION,
    PROMPT_REVISION_SCHEMA_VERSION,
    TopicPromptWorkflowService,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

NEW_PROMPT_FILES = [
    "topic_prompt_generation_prompt.md",
    "topic_prompt_revision_prompt.md",
    "topic_research_prompt.md",
    "topic_findings_merge_prompt.md",
]

SCHEMA_VERSION_MARKERS = {
    "topic_prompt_generation_prompt.md": "topic-prompt-generation-v1",
    "topic_prompt_revision_prompt.md": "topic-prompt-revision-v1",
    "topic_research_prompt.md": "topic-research-v1",
    "topic_findings_merge_prompt.md": "topic-findings-merge-v1",
}

OLD_CATEGORY_PATTERNS = [
    "channel_name",
    "channel_urls",
    "channel_handles",
    "channel_domains",
    "normalized_term",
    "literal_meaning",
    "contextual_meaning",
    "usage_quote",
    "aliases_or_variants",
    "detected_language",
    '"channels"',
    '"slangs"',
    "黑话",
    "行业黑话",
    "隐蔽渠道",
    "渠道情报",
]


def _read_prompt(filename: str) -> str:
    filepath = PROMPTS_DIR / filename
    assert filepath.exists(), f"Prompt file not found: {filepath}"
    return filepath.read_text(encoding="utf-8")


class TestPromptFilesExist:
    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_prompt_file_exists(self, filename: str) -> None:
        filepath = PROMPTS_DIR / filename
        assert filepath.exists(), f"Prompt file missing: {filepath}"
        assert filepath.stat().st_size > 0, f"Prompt file is empty: {filepath}"

    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_prompt_file_is_readable(self, filename: str) -> None:
        content = _read_prompt(filename)
        assert len(content) > 50, f"Prompt file too short to be useful: {filename}"


class TestSchemaVersionMarkers:
    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_prompt_contains_schema_version(self, filename: str) -> None:
        content = _read_prompt(filename)
        expected_marker = SCHEMA_VERSION_MARKERS[filename]
        assert expected_marker in content, (
            f"Prompt {filename} missing schema version marker: {expected_marker}"
        )

    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_schema_version_in_header(self, filename: str) -> None:
        content = _read_prompt(filename)
        first_lines = "\n".join(content.split("\n")[:5])
        expected_marker = SCHEMA_VERSION_MARKERS[filename]
        assert expected_marker in first_lines, (
            f"Schema version marker should be in header of {filename}"
        )


class TestResearchPromptCitations:
    def test_research_prompt_requires_citations(self) -> None:
        content = _read_prompt("topic_research_prompt.md")
        assert "citation" in content.lower(), (
            "Research prompt must mention citation requirements"
        )
        assert "message_id" in content, (
            "Research prompt must require message_id in citations"
        )
        assert "message_snippet" in content, (
            "Research prompt must require message_snippet in citations"
        )

    def test_research_prompt_requires_findings_array(self) -> None:
        content = _read_prompt("topic_research_prompt.md")
        assert "findings" in content, (
            "Research prompt must output a findings array"
        )

    def test_research_prompt_schema_version(self) -> None:
        content = _read_prompt("topic_research_prompt.md")
        assert "topic-research-v1" in content


class TestMergePromptStructure:
    def test_merge_prompt_requires_source_finding_ids(self) -> None:
        content = _read_prompt("topic_findings_merge_prompt.md")
        assert "source_finding_ids" in content, (
            "Merge prompt must require source_finding_ids in output"
        )

    def test_merge_prompt_requires_merged_findings(self) -> None:
        content = _read_prompt("topic_findings_merge_prompt.md")
        assert "merged_findings" in content, (
            "Merge prompt must output merged_findings array"
        )

    def test_merge_prompt_schema_version(self) -> None:
        content = _read_prompt("topic_findings_merge_prompt.md")
        assert "topic-findings-merge-v1" in content


class TestPromptGenerationStructure:
    def test_generation_prompt_outputs_draft(self) -> None:
        content = _read_prompt("topic_prompt_generation_prompt.md")
        assert "research_prompt_draft" in content, (
            "Generation prompt must output research_prompt_draft"
        )

    def test_generation_prompt_schema_version(self) -> None:
        content = _read_prompt("topic_prompt_generation_prompt.md")
        assert "topic-prompt-generation-v1" in content


class TestPromptRevisionStructure:
    def test_revision_prompt_outputs_version(self) -> None:
        content = _read_prompt("topic_prompt_revision_prompt.md")
        assert '"version"' in content, (
            "Revision prompt must output version number"
        )
        assert "revision_note" in content, (
            "Revision prompt must output revision_note"
        )

    def test_revision_prompt_schema_version(self) -> None:
        content = _read_prompt("topic_prompt_revision_prompt.md")
        assert "topic-prompt-revision-v1" in content


class TestNewPromptsExcludeOldCategoryLanguage:
    """Verify NO new prompt contains instructions to extract channel/slang
    as intelligence categories.

    The old intelligence_extraction_prompt.md used these patterns. The new
    prompts must NOT include them. Source/channel metadata may only appear
    as raw source context for citations.
    """

    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_no_channel_extraction_fields(self, filename: str) -> None:
        content = _read_prompt(filename)
        content_lower = content.lower()

        forbidden_fields = [
            "channel_name",
            "channel_urls",
            "channel_handles",
            "channel_domains",
        ]
        for field in forbidden_fields:
            assert field not in content_lower, (
                f"Prompt {filename} must not contain old channel extraction field: {field}"
            )

    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_no_slang_extraction_fields(self, filename: str) -> None:
        content = _read_prompt(filename)
        content_lower = content.lower()

        forbidden_fields = [
            "normalized_term",
            "literal_meaning",
            "contextual_meaning",
            "usage_quote",
            "aliases_or_variants",
            "detected_language",
        ]
        for field in forbidden_fields:
            assert field not in content_lower, (
                f"Prompt {filename} must not contain old slang extraction field: {field}"
            )

    @pytest.mark.parametrize("filename", NEW_PROMPT_FILES)
    def test_no_channels_or_slangs_top_level_keys(self, filename: str) -> None:
        content = _read_prompt(filename)
        assert '"channels"' not in content, (
            f"Prompt {filename} must not use 'channels' as output key"
        )
        assert '"slangs"' not in content, (
            f"Prompt {filename} must not use 'slangs' as output key"
        )

    def test_old_prompt_still_exists_untouched(self) -> None:
        old_prompt = PROMPTS_DIR / "intelligence_extraction_prompt.md"
        assert old_prompt.exists(), (
            "Old intelligence_extraction_prompt.md should still exist (not deleted)"
        )


class FakeChatCompletions:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.payloads = list(payloads)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(self.payloads.pop(0), ensure_ascii=False)
                    )
                )
            ]
        )


class FakeLLMClient:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.completions = FakeChatCompletions(payloads)
        self.chat = SimpleNamespace(completions=self.completions)


def _build_repository(db_path: Path):
    manager = DataManager(StorageConfig(database_path=str(db_path)))
    return manager, SQLiteIntelligenceRepository(manager)


def _generation_payload(topic_name: str = "BTC ETF flow") -> Dict[str, Any]:
    return {
        "schema_version": PROMPT_GENERATION_SCHEMA_VERSION,
        "topic_name": topic_name,
        "topic_description": f"Tracking {topic_name}",
        "research_prompt_draft": f"Research {topic_name} and output findings JSON with citations.",
        "suggested_time_window_hours": 24,
        "confidence": 0.91,
    }


def _revision_payload(version: int = 2) -> Dict[str, Any]:
    return {
        "schema_version": PROMPT_REVISION_SCHEMA_VERSION,
        "topic_name": "BTC ETF flow",
        "revised_prompt": "Revised: research BTC ETF flow and output findings JSON with citations.",
        "version": version,
        "revision_note": "Made it clearer",
        "changes_summary": ["Clarified wording"],
        "confidence": 0.92,
    }


class TestGenerateConfirm:
    def test_generate_confirm(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "generate-confirm.db")
        try:
            client = FakeLLMClient([_generation_payload()])
            service = TopicPromptWorkflowService(
                repository=repository,
                llm_client=client,
            )

            prompt = service.create_draft_topic("BTC ETF flow")

            assert prompt.status == "draft"
            assert prompt.prompt_version == "1"
            assert "findings JSON" in prompt.prompt_text

            confirmed = service.confirm_prompt(
                prompt.intelligence_topic_id,
                prompt.id,
                activated_by="tester",
            )

            assert confirmed.status == "active"
            assert confirmed.activated_by == "tester"

            active = repository.get_active_topic_prompt(prompt.intelligence_topic_id)
            assert active is not None
            assert active.id == confirmed.id
        finally:
            manager.close()


class TestManualReplace:
    def test_manual_replace(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "manual-replace.db")
        try:
            service = TopicPromptWorkflowService(repository=repository)

            topic = IntelligenceTopic.create(name="Test Topic")
            repository.save_topic(topic)

            prompt = service.replace_prompt_manual(
                topic.id,
                "Manually crafted prompt text.",
                created_by="operator",
            )

            assert prompt.status == "draft"
            assert prompt.prompt_version == "1"
            assert prompt.prompt_text == "Manually crafted prompt text."
            assert prompt.created_by == "operator"
        finally:
            manager.close()

    def test_manual_replace_rejects_empty(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "manual-empty.db")
        try:
            service = TopicPromptWorkflowService(repository=repository)
            topic = IntelligenceTopic.create(name="Test Topic")
            repository.save_topic(topic)

            with pytest.raises(ValueError, match="empty"):
                service.replace_prompt_manual(topic.id, "")

            with pytest.raises(ValueError, match="empty"):
                service.replace_prompt_manual(topic.id, "   ")
        finally:
            manager.close()

    def test_manual_replace_rejects_oversized(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "manual-oversized.db")
        try:
            service = TopicPromptWorkflowService(
                repository=repository,
                max_prompt_length=100,
            )
            topic = IntelligenceTopic.create(name="Test Topic")
            repository.save_topic(topic)

            with pytest.raises(ValueError, match="exceeds"):
                service.replace_prompt_manual(topic.id, "x" * 101)
        finally:
            manager.close()


class TestReviseFeedback:
    def test_revise_feedback(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "revise.db")
        try:
            client = FakeLLMClient([
                _generation_payload(),
                _revision_payload(version=2),
            ])
            service = TopicPromptWorkflowService(
                repository=repository,
                llm_client=client,
            )

            draft = service.create_draft_topic("BTC ETF flow")
            assert draft.prompt_version == "1"

            revised = service.revise_prompt(
                draft.intelligence_topic_id,
                "Make it clearer",
            )

            assert revised.prompt_version == "2"
            assert revised.status == "draft"
            assert revised.intelligence_topic_id == draft.intelligence_topic_id
            assert revised.audit_history[-1]["action"] == "revised"

            all_prompts = repository.list_topic_prompts(draft.intelligence_topic_id)
            assert len(all_prompts) == 2
        finally:
            manager.close()


class TestEditActivePromptVersion:
    def test_edit_active_prompt_version(self, tmp_path: Path) -> None:
        manager, repository = _build_repository(tmp_path / "edit-active.db")
        try:
            client = FakeLLMClient([_generation_payload()])
            service = TopicPromptWorkflowService(
                repository=repository,
                llm_client=client,
            )

            draft = service.create_draft_topic("BTC ETF flow")
            confirmed = service.confirm_prompt(
                draft.intelligence_topic_id,
                draft.id,
            )

            finding = TopicFinding.create(
                intelligence_topic_id=confirmed.intelligence_topic_id,
                prompt_version_id=confirmed.id,
                finding_payload={"summary": "finding"},
                content_hash="hash-1",
                confidence=0.8,
            )
            repository.create_topic_finding(finding)

            edited = service.edit_active_prompt(
                confirmed.intelligence_topic_id,
                "Updated prompt text",
                created_by="editor",
            )

            assert edited.status == "draft"
            assert edited.prompt_version == "2"
            assert edited.prompt_text == "Updated prompt text"
            assert edited.created_by == "editor"

            loaded_finding = repository.get_topic_finding_by_id(finding.id)
            assert loaded_finding is not None
            assert loaded_finding.prompt_version_id == confirmed.id
        finally:
            manager.close()
