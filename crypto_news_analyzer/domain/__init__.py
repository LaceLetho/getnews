"""
Domain package initialization

Shared domain contracts for Railway service split architecture.

Version: 1.0.0
"""

from .models import (
    AnalysisRequest,
    IngestionJob,
    AnalysisResult,
    JobStatus,
    IngestionJobStatus,
    Priority,
)

from .repositories import (
    AnalysisRepository,
    IngestionRepository,
    ContentRepository,
    CacheRepository,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "AnalysisRequest",
    "IngestionJob",
    "AnalysisResult",
    # Enums
    "JobStatus",
    "IngestionJobStatus",
    "Priority",
    # Repositories
    "AnalysisRepository",
    "IngestionRepository",
    "ContentRepository",
    "CacheRepository",
    # Version
    "__version__",
]
