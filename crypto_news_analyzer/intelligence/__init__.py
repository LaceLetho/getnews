"""Hidden-channel intelligence canonicalization utilities."""

from .merge import IntelligenceMergeEngine
from .pipeline import IntelligencePipeline
from .search import IntelligenceSearchService

__all__ = ["IntelligenceMergeEngine", "IntelligencePipeline", "IntelligenceSearchService"]
