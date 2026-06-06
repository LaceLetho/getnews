"""Shared service factory for TopicPromptWorkflowService and TopicFindingMergeService.

Both the HTTP API and Telegram surfaces need these services constructed from
the same controller dependencies. This module eliminates the duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..execution_coordinator import MainController
    from ..domain.repositories import IntelligenceRepository
    from .topic_prompts import TopicPromptWorkflowService
    from .topic_findings import TopicFindingMergeService


def get_topic_prompt_workflow_service(
    controller: "MainController",
    repository: "IntelligenceRepository",
) -> "TopicPromptWorkflowService":
    from .topic_prompts import TopicPromptWorkflowService

    llm_analyzer = getattr(controller, "llm_analyzer", None)
    llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
    model_name = ""
    if llm_analyzer and hasattr(llm_analyzer, "analysis_model_runtime"):
        runtime = llm_analyzer.analysis_model_runtime
        model_name = getattr(runtime, "model_name", "") if runtime else ""
    if not model_name and llm_analyzer:
        model_name = getattr(llm_analyzer, "model", "")

    llm_config_payload = (
        dict(getattr(llm_analyzer, "config", {}) or {})
        if llm_analyzer
        else {}
    )

    return TopicPromptWorkflowService(
        repository=repository,
        llm_client=llm_client,
        model_name=model_name,
        config=llm_config_payload,
    )


def get_topic_finding_merge_service(
    controller: "MainController",
    repository: "IntelligenceRepository",
) -> "TopicFindingMergeService":
    from .topic_findings import TopicFindingMergeService

    llm_analyzer = getattr(controller, "llm_analyzer", None)
    llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
    model_name = ""
    if llm_analyzer and hasattr(llm_analyzer, "analysis_model_runtime"):
        runtime = llm_analyzer.analysis_model_runtime
        model_name = getattr(runtime, "model_name", "") if runtime else ""
    if not model_name and llm_analyzer:
        model_name = getattr(llm_analyzer, "model", "")

    llm_config_payload = (
        dict(getattr(llm_analyzer, "config", {}) or {})
        if llm_analyzer
        else {}
    )

    return TopicFindingMergeService(
        intelligence_repository=repository,
        llm_client=llm_client,
        model_name=model_name,
        config=llm_config_payload,
    )
